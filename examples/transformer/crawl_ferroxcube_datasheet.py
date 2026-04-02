import hashlib
import time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import pandas as pd
import requests
from lxml import html
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException, SSLError
from urllib3.util.retry import Retry

from review_agent.logger import log

folder_path = Path('./output')
transformer_folder_path = folder_path / 'transformer'


base_url = 'https://www.ferroxcube.com/'
REQUEST_SLEEP_SECONDS = 1.0


def build_http_session() -> requests.Session:
    """Create a requests session with retries for transient network failures."""
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(['GET']),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Connection': 'close',
    })
    return session


def http_get(session: requests.Session, url: str, timeout: int = 30) -> requests.Response:
    """GET with SSL EOF fallback and a short delay to reduce crawl pressure."""
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        time.sleep(REQUEST_SLEEP_SECONDS)
        return response
    except SSLError as exc:
        log(
            f'SSL handshake failed for {url}; retrying with certificate verification disabled. Error: {exc}',
            LEVEL='WARNING',
        )
        response = session.get(url, timeout=timeout, verify=False)
        response.raise_for_status()
        time.sleep(REQUEST_SLEEP_SECONDS)
        return response
    except RequestException as exc:
        log(f'HTTP request failed for {url}: {exc}', LEVEL='ERROR')
        raise


def extract_select_options(page_text: str, select_xpath: str) -> dict[str, str]:
    """Return non-empty option value/text pairs from a select element."""
    tree = html.fromstring(page_text)
    options = tree.xpath(f'{select_xpath}/option')
    result = {}
    for option in options:
        value = (option.get('value') or '').strip()
        label = (option.text or '').strip()
        if not value:
            continue
        result[value] = label or value
    return result


def sanitize_name(name: str, empty_fallback: str, strip_trailing_dot: bool) -> str:
    """Sanitize path segments for Windows file systems."""
    invalid_chars = '<>:"/\\|?*'
    sanitized = ''.join('_' if c in invalid_chars else c for c in name).strip()
    if strip_trailing_dot:
        sanitized = sanitized.strip('.')
    return sanitized or empty_fallback


def normalize_table_header(header: str) -> str:
    header_map = {
        'P/N': 'part_number',
        'Material': 'material',
        'Lef [mm]': 'lef_mm',
        'Aef [mm((2))]': 'aef_mm2',
        'Vef [mm((3))]': 'vef_mm3',
        'AL [nH/turns((2))]': 'al_nh_per_turn2',
        'Gap [µm]': 'gap_um',
        'µe': 'mu_e',
        'ROHS': 'rohs',
        'Datasheet': 'datasheet',
        'Accessory': 'accessory',
    }
    return header_map.get(header, header.lower().replace(' ', '_'))


def extract_cell_text(cell) -> str:
    text_parts = cell.xpath('.//span//text()')
    normalized = [' '.join(part.split()) for part in text_parts if part and part.strip()]
    return ' '.join(normalized).strip()


def save_checkpoint(rows: list[dict[str, str]], output_csv_path: Path) -> None:
    """Persist current crawl results as a checkpoint CSV."""
    if not rows:
        return
    df = pd.DataFrame(rows)
    df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')


def load_checkpoint(output_csv_path: Path) -> tuple[list[dict[str, str]], set[tuple[str, str, str]]]:
    """Load existing rows and processed parameter keys from checkpoint CSV."""
    all_rows: list[dict[str, str]] = []
    processed_keys: set[tuple[str, str, str]] = set()
    if not output_csv_path.exists():
        return all_rows, processed_keys

    existing_df = pd.read_csv(output_csv_path, dtype=str, keep_default_na=False)
    all_rows = existing_df.to_dict(orient='records')
    for row in all_rows:
        s_key = (row.get('s_sel') or '').strip()
        series_key = (row.get('series_sel') or '').strip()
        material_key = (row.get('material_sel') or '').strip()
        if s_key and series_key and material_key:
            processed_keys.add((s_key, series_key, material_key))
    log(
        f'Loaded checkpoint: {len(all_rows)} rows, {len(processed_keys)} parameter groups already processed',
        LEVEL='INFO',
    )
    return all_rows, processed_keys


def fetch_or_load_page(session: requests.Session, url: str, file_path: Path) -> str:
    """Return page text from local cache or network, and cache network responses."""
    if file_path.exists():
        log(f'Use cached HTML: {file_path}', LEVEL='INFO')
        return file_path.read_text(encoding='utf-8')

    log(f'Checking URL: {url}', LEVEL='INFO')
    response = http_get(session, url, timeout=30)
    log(f'URL is valid: {url}', LEVEL='INFO')

    page_text = response.text
    with Path.open(file_path, 'w', encoding='utf-8') as f:
        f.write(page_text)
    return page_text


def parse_table_rows(
    page_text: str,
    s_sel: str,
    transformer_name: str,
    series_sel: str,
    series_name: str,
    material_sel: str,
    material_name: str,
    url: str,
    file_path: Path,
) -> list[dict[str, str]]:
    """Parse datasheet table rows from one HTML page."""
    table_xpath = '/html/body/div[2]/div[3]/div/div[2]/div[1]/div/div/table/tbody'
    tree = html.fromstring(page_text)
    table_rows = tree.xpath(f'{table_xpath}/tr')
    if not table_rows:
        return []

    parsed_rows: list[dict[str, str]] = []
    for tr in table_rows:
        row_data: dict[str, str] = {
            's_sel': s_sel,
            'transformer_name': transformer_name,
            'series_sel': series_sel,
            'series_name': series_name,
            'material_sel': material_sel,
            'material_name': material_name,
            'source_url': url,
            'source_html_path': str(file_path),
        }

        cells = tr.xpath('./td')
        for cell in cells:
            raw_header = (cell.get('data-title') or '').strip()
            if not raw_header:
                continue

            column = normalize_table_header(raw_header)
            row_data[column] = extract_cell_text(cell)

            hrefs = cell.xpath('.//a/@href')
            if hrefs:
                pdf_url = urljoin(base_url, hrefs[0].strip())
                if column == 'material':
                    row_data['material_pdf_url'] = pdf_url
                elif column == 'datasheet':
                    row_data['datasheet_pdf_url'] = pdf_url

        parsed_rows.append(row_data)
    return parsed_rows


def process_one_combo(
    session: requests.Session,
    s_sel: str,
    transformer_name: str,
    series_sel: str,
    series_name: str,
    material_sel: str,
    material_name: str,
    step2_base_url: str,
    file_path: Path,
) -> list[dict[str, str]]:
    """Process one parameter combination and return extracted table rows."""
    url = step2_base_url + f'?s_sel={s_sel}&series_sel={series_sel}&material_sel={material_sel}'
    page_text = fetch_or_load_page(session, url, file_path)
    return parse_table_rows(
        page_text=page_text,
        s_sel=s_sel,
        transformer_name=transformer_name,
        series_sel=series_sel,
        series_name=series_name,
        material_sel=material_sel,
        material_name=material_name,
        url=url,
        file_path=file_path,
    )


def build_pdf_local_file_path(pdf_url: str, pdf_folder_path: Path) -> Path:
    """Build a deterministic local PDF path from URL with hash suffix to avoid collisions."""
    parsed = urlparse(pdf_url)
    raw_name = unquote(Path(parsed.path).name) or 'document.pdf'
    safe_name = sanitize_name(raw_name, empty_fallback='file', strip_trailing_dot=True)
    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix or '.pdf'
    url_hash = hashlib.sha256(pdf_url.encode('utf-8')).hexdigest()[:10]
    final_name = f'{stem}_{url_hash}{suffix}'
    return pdf_folder_path / final_name


def download_all_pdfs_from_csv(
    session: requests.Session,
    output_csv_path: Path,
    pdf_folder_path: Path,
) -> None:
    """Download unique PDF URLs from CSV and write local PDF paths back to the table."""
    if not output_csv_path.exists():
        log(f'CSV does not exist, skip PDF download: {output_csv_path}', LEVEL='WARNING')
        return

    df = pd.read_csv(output_csv_path, dtype=str, keep_default_na=False)
    if df.empty:
        log(f'CSV is empty, skip PDF download: {output_csv_path}', LEVEL='WARNING')
        return

    if 'local_pdf_paths' not in df.columns:
        df['local_pdf_paths'] = ''

    url_columns = [c for c in ('material_pdf_url', 'datasheet_pdf_url') if c in df.columns]
    if not url_columns:
        log('No PDF URL columns found in CSV, skip PDF download', LEVEL='WARNING')
        return

    pdf_folder_path.mkdir(parents=True, exist_ok=True)

    url_to_local: dict[str, str] = {}

    def unique_pdf_urls() -> list[str]:
        values: set[str] = set()
        for col in url_columns:
            values.update(df[col].astype(str).str.strip().tolist())
        values.discard('')
        return sorted(values)

    for pdf_url in unique_pdf_urls():
        local_file_path = build_pdf_local_file_path(pdf_url, pdf_folder_path)
        if local_file_path.exists():
            log(f'Use cached PDF: {local_file_path}', LEVEL='INFO')
            url_to_local[pdf_url] = str(local_file_path)
            continue

        try:
            response = http_get(session, pdf_url, timeout=60)
            with Path.open(local_file_path, 'wb') as f:
                f.write(response.content)
            url_to_local[pdf_url] = str(local_file_path)
            log(f'Downloaded PDF: {pdf_url} -> {local_file_path}', LEVEL='INFO')
        except RequestException:
            log(f'Failed to download PDF: {pdf_url}', LEVEL='ERROR')

    def compose_local_paths(row: pd.Series) -> str:
        paths: list[str] = []
        for col in url_columns:
            pdf_url = (row.get(col) or '').strip()
            local_path = url_to_local.get(pdf_url, '')
            if local_path and local_path not in paths:
                paths.append(local_path)
        return ';'.join(paths)

    df['local_pdf_paths'] = df.apply(compose_local_paths, axis=1)
    df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
    log(f'Updated local PDF paths in CSV: {output_csv_path}', LEVEL='INFO')


def main() -> None:
    # Datasheet crawl endpoints.
    step1_base_url = base_url + 'zh-CN/products_ferroxcube/stepOne/shape_cores_accessories'
    step2_base_url = base_url + 'zh-CN/products_ferroxcube/stepTwo/shape_cores_accessories'

    # Output folders for cached HTML and parsed table data.
    datasheet_folder_path = transformer_folder_path / 'datasheet'
    html_folder_path = datasheet_folder_path / 'htmls'
    html_folder_path.mkdir(parents=True, exist_ok=True)
    pdf_folder_path = datasheet_folder_path / 'pdfs'
    pdf_folder_path.mkdir(parents=True, exist_ok=True)

    start_url = step1_base_url + '?s_sel=163'
    xpath_s_sel = '/html/body/div[2]/div[3]/div/div/div/form/div[1]/select'
    xpath_series_sel = '/html/body/div[2]/div[3]/div/div/div/form/div[2]/select'
    xpath_material_sel = '/html/body/div[2]/div[3]/div/div/div/form/div[3]/select'

    session = build_http_session()

    start_response = http_get(session, start_url, timeout=30)
    transformer_map = extract_select_options(start_response.text, xpath_s_sel)
    log(f'Loaded {len(transformer_map)} transformer options', LEVEL='INFO')

    output_csv_path = datasheet_folder_path / 'ferroxcube_datasheet_table.csv'
    all_table_rows, processed_keys = load_checkpoint(output_csv_path)

    for s_sel, transformer_name in transformer_map.items():
        s_sel_url = step1_base_url + f'?s_sel={s_sel}'
        log(f'Checking URL: {s_sel_url}', LEVEL='INFO')
        s_sel_response = http_get(session, s_sel_url, timeout=30)

        series_map = extract_select_options(s_sel_response.text, xpath_series_sel)
        log(f'Loaded {len(series_map)} series options for s_sel={s_sel}', LEVEL='INFO')

        material_map = extract_select_options(s_sel_response.text, xpath_material_sel)
        log(f'Loaded {len(material_map)} material options for s_sel={s_sel}', LEVEL='INFO')

        if not series_map:
            log(f'No series options found for s_sel={s_sel}, skip', LEVEL='WARNING')
            continue
        if not material_map:
            log(f'No material options found for s_sel={s_sel}, skip', LEVEL='WARNING')
            continue

        transformer_output_path = html_folder_path / sanitize_name(
            transformer_name,
            empty_fallback='unknown',
            strip_trailing_dot=False,
        )
        for series_sel, series_name in series_map.items():
            series_folder_path = transformer_output_path / sanitize_name(
                series_name,
                empty_fallback='unknown',
                strip_trailing_dot=False,
            )
            for material_sel, material_name in material_map.items():
                material_folder_path = series_folder_path / sanitize_name(
                    material_name,
                    empty_fallback='unknown',
                    strip_trailing_dot=False,
                )
                material_folder_path.mkdir(parents=True, exist_ok=True)
                file_name = f'{s_sel}-{series_sel}-{material_sel}.html'
                file_path = material_folder_path / file_name
                crawl_key = (s_sel, series_sel, material_sel)

                if crawl_key in processed_keys:
                    log(
                        f'Skip processed params: s_sel={s_sel}, series_sel={series_sel}, material_sel={material_sel}',
                        LEVEL='INFO',
                    )
                    continue

                rows = process_one_combo(
                    session=session,
                    s_sel=s_sel,
                    transformer_name=transformer_name,
                    series_sel=series_sel,
                    series_name=series_name,
                    material_sel=material_sel,
                    material_name=material_name,
                    step2_base_url=step2_base_url,
                    file_path=file_path,
                )
                if not rows:
                    log(
                        f'No data table rows found for s_sel={s_sel}, series_sel={series_sel}, material_sel={material_sel}',
                        LEVEL='WARNING',
                    )
                    processed_keys.add(crawl_key)
                    continue

                all_table_rows.extend(rows)
                processed_keys.add(crawl_key)
                save_checkpoint(all_table_rows, output_csv_path)
                log(
                    f'Extracted {len(rows)} table rows for s_sel={s_sel}, series_sel={series_sel}, material_sel={material_sel}',
                    LEVEL='INFO',
                )

    if all_table_rows:
        save_checkpoint(all_table_rows, output_csv_path)
        log(f'Saved {len(all_table_rows)} rows to {output_csv_path}', LEVEL='INFO')
    else:
        log('No table rows extracted. CSV was not generated.', LEVEL='WARNING')

    download_all_pdfs_from_csv(
        session=session,
        output_csv_path=output_csv_path,
        pdf_folder_path=pdf_folder_path,
    )


if __name__ == '__main__':
    main()
