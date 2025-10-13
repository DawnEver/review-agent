import time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from lxml import etree, html

from crawl_agent import download_pdf, download_webpage, headers, load_from_csv, save_to_csv
from review_agent.logger import log

# Setup paths
folder_path = Path('./output')
page_folder_path = folder_path / 'reports'
csv_folder_path = folder_path / 'reports_csv'
page_folder_path.mkdir(parents=True, exist_ok=True)
csv_folder_path.mkdir(parents=True, exist_ok=True)


base_url = 'https://www.apcuk.co.uk/knowledge-base'

routes = [
    '/media-type/quarterly-demand-reports',
    '/media-type/insight-reports',
    '/media-type/impacts',
    '/media-type/value-chains',
    '/roadmaps',
    '/2020-roadmaps-archived',
    '/partner-insights',
]

resource_arrow_svg_list = [
    """
<svg class="w-6 h-6 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path>
</svg>
""",
    """
<svg class="transition group-hover:scale-110" width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" role="img">
    <g fill="none" fill-rule="evenodd">
        <path d="M0 0h24v24H0z"></path>
        <path fill="#97D700" d="m15 5-1.41 1.41L18.17 11H2v2h16.17l-4.59 4.59L15 19l7-7z"></path>
    </g>
</svg>
""",
]


# Helpers: parse SVG variants and find matching anchors
def _get_arrow_path_ds() -> list[str]:
    ds: list[str] = []
    for svg_src in resource_arrow_svg_list:
        try:
            svg_tree = html.fromstring(svg_src)
            d_val = svg_tree.xpath('string(.//*[local-name()="path"]/@d)')
            if d_val:
                ds.append(d_val)
        except (etree.ParserError, ValueError, TypeError):
            continue
    return ds or ['M14 5l7 7m0 0l-7 7m7-7H3']


def _find_svg_anchors(tree: html.HtmlElement) -> list:
    path_ds = _get_arrow_path_ds()
    if len(path_ds) == 1:
        anchors = tree.xpath(f"//a[.//*[local-name()='svg']//*[local-name()='path' and @d='{path_ds[0]}']]")
    else:
        ors = ' or '.join([f"@d='{d}'" for d in path_ds])
        anchors = tree.xpath(f"//a[.//*[local-name()='svg']//*[local-name()='path' and ({ors})]]")
    if not anchors:
        anchors = tree.xpath(
            "//a[.//*[local-name()='svg' and (contains(@class,'text-secondary') or @viewBox='0 0 24 24')]"
            " or .//*[local-name()='path' and contains(@d,'l7 7')]]"
        )
    return anchors


def extract_report_info(page_content, page_url):
    """Extract report information from the webpage"""
    tree = html.fromstring(page_content)
    reports = []
    links = _find_svg_anchors(tree)

    for link in links:
        try:
            # Find the nearest container for this card/post
            parent = link.getparent()
            article = link
            for _ in range(5):  # Search up to 5 levels
                if parent is None:
                    break
                if parent.tag in ['article', 'div'] and any(
                    cls in parent.get('class', '') for cls in ['post', 'article', 'item', 'card', 'entry']
                ):
                    article = parent
                    break
                parent = parent.getparent()

            # Extract href from the <a> itself, else fallback to any anchor in the same container
            href = link.get('href')
            if not href and article is not None:
                anchors = article.xpath('.//a/@href')
                if anchors:
                    href = anchors[0]
            if not href:
                # Fallback: data-href on container
                href = article.get('data-href') if hasattr(article, 'get') else None
            if not href:
                continue  # Skip if no URL could be resolved

            url = urljoin(page_url, href)

            # Extract title
            title = ''
            title_elem = article.xpath('.//h1 | .//h2 | .//h3 | .//h4 | .//h5')
            if title_elem:
                title = title_elem[0].text_content().strip()

            # Extract summary
            summary = ''
            summary_elem = article.xpath('.//p[not(descendant::a)]')
            if summary_elem:
                summary = ' '.join([p.text_content().strip() for p in summary_elem[:2]])

            reports.append({'page_url': page_url, 'url': url, 'title': title, 'summary': summary})
        except (AttributeError, IndexError, ValueError, TypeError, etree.ParserError) as e:
            log(f'Error extracting info from svg-anchor CTA: {e}', level='error')
            continue

    return reports


def crawl_and_save():
    """Main function to crawl all routes and save to CSV"""
    all_reports = []

    for route in routes:
        i_page = 1
        route_seen_urls = set()
        for _ in range(10):  # Limit to 100 pages per route to avoid infinite loops
            try:
                full_url = base_url + route + f'/page/{i_page}'
                log(f'\nCrawling: {full_url}')

                # Download webpage (raises for non-200)
                page_content = download_webpage(full_url)

                # Extract report information
                reports = extract_report_info(page_content, full_url)
                log(f'Found {len(reports)} reports in {route} (page {i_page})')

                # If page has no items at all, consider it an end condition
                if not reports:
                    log(f'No reports found on {route} page {i_page}; stopping route iteration')
                    break

                # Only take items that are new for this route and exclude URLs with '#main' fragment
                new_reports = [
                    r
                    for r in reports
                    if r.get('url')
                    and r['url'] not in route_seen_urls
                    and urlparse(r['url']).fragment.lower() != 'main'
                ]
                if not new_reports:
                    log(f'No new reports on {route} page {i_page}; content likely repeated. Stopping.')
                    break

                all_reports.extend(new_reports)
                route_seen_urls.update(r['url'] for r in new_reports if r.get('url'))

                # Next page
                i_page += 1

                # Be polite
                time.sleep(0.5)

            except requests.exceptions.HTTPError as http_err:
                status_code = getattr(http_err.response, 'status_code', None)
                if status_code == 404:
                    log(f'End of pages for {route}: page {i_page} returned 404')
                else:
                    log(f'HTTP error on {full_url}: {http_err}', level='error')
                break
            except (requests.exceptions.RequestException, ValueError, TypeError) as e:
                log(f'Error processing {route} page {i_page}: {e}', level='error')
                break

    # Remove duplicates based on URL
    unique_reports = []
    seen_urls = set()
    for report in all_reports:
        if report['url'] not in seen_urls:
            unique_reports.append(report)
            seen_urls.add(report['url'])

    # Save to CSV
    csv_path = csv_folder_path / f'apc_uk_reports_{time.strftime("%Y%m%d_%H%M%S")}.csv'
    save_to_csv(unique_reports, csv_path, fieldnames=unique_reports[0].keys() if unique_reports else [])


def download_from_csv(csv_path):
    unique_reports = load_from_csv(csv_path)

    # Utilities
    def sanitize_name(text: str, max_len: int = 120) -> str:
        if not text:
            return 'untitled'
        # Replace invalid filename characters for Windows
        invalid = '<>:"/\\|?*\n\r\t'
        out = ''.join('_' if ch in invalid else ch for ch in text)
        # Collapse spaces
        out = ' '.join(out.split())
        # Trim
        return out[:max_len].strip(' .') or 'untitled'

    def url_to_dirname(u: str) -> str:
        p = urlparse(u)
        # Use host + path as name
        composed = (p.netloc + p.path).rstrip('/')
        if not composed:
            composed = p.netloc or 'page'
        return sanitize_name(composed.replace('/', '_'))

    def guess_filename_from_url(u: str, default: str = 'file') -> str:
        path = unquote(urlparse(u).path)
        name = Path(path).name
        return name if name else default

    def head_content_type(u: str) -> str | None:
        try:
            # Use shared headers; fallback to GET if HEAD unsupported
            resp = requests.head(u, headers=headers, allow_redirects=True, timeout=20)
            if resp.status_code >= 400:
                return None
            return resp.headers.get('Content-Type')
        except requests.exceptions.RequestException:
            return None

    def is_pdf_url_or_ct(u: str) -> bool:
        if u.lower().split('?', 1)[0].endswith('.pdf'):
            return True
        ct = head_content_type(u)
        return bool(ct and 'application/pdf' in ct.lower())

    def save_bytes(url: str, dest: Path) -> bool:
        try:
            log(f'  Downloading: {url}')
            resp = requests.get(url, headers=headers, timeout=40)
            resp.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with Path.open(dest, 'wb') as f:
                f.write(resp.content)
            log(f'    Saved to: {dest}')
            return True
        except (requests.exceptions.RequestException, OSError) as e:
            log(f'    Error downloading {url}: {e}', level='error')
            return False

    def save_html(content: bytes, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with Path.open(dest, 'wb') as f:
            f.write(content)
        log(f'    HTML saved: {dest}')

    def find_svg_resource_links(page_bytes: bytes, base: str) -> list[str]:
        try:
            t = html.fromstring(page_bytes)
        except (etree.ParserError, ValueError, TypeError):
            return []

        anchors = _find_svg_anchors(t)

        hrefs: list[str] = []
        for a in anchors:
            h = a.get('href')
            if not h:
                # try first descendant anchor href if nested structure
                desc_h = a.xpath('.//a/@href')
                if desc_h:
                    h = desc_h[0]
            if h:
                abs_u = urljoin(base, h)
                hrefs.append(abs_u)

        # Deduplicate preserving order
        seen = set()
        uniq = []
        for u in hrefs:
            if u not in seen:
                uniq.append(u)
                seen.add(u)
        return uniq

    # Track duplicates within this run
    processed_targets: set[str] = set()
    processed_resources: set[str] = set()

    # Process each report
    for i, rec in enumerate(unique_reports, start=1):
        page_url = rec.get('page_url') or ''
        target_url = rec.get('url') or ''
        title = rec.get('title') or ''

        if not target_url:
            continue

        if target_url in processed_targets:
            log(f'Skip duplicate target (already processed this run): {target_url}')
            continue
        processed_targets.add(target_url)

        group_dir = page_folder_path / url_to_dirname(page_url or 'page')
        group_dir.mkdir(parents=True, exist_ok=True)

        try:
            if is_pdf_url_or_ct(target_url):
                # Download PDF directly into the group folder
                pdf_name = guess_filename_from_url(target_url, default=sanitize_name(title or f'report_{i}') + '.pdf')
                if not pdf_name.lower().endswith('.pdf'):
                    pdf_name += '.pdf'
                dest = group_dir / sanitize_name(pdf_name)
                if dest.exists():
                    log(f'  Skip PDF (exists): {dest}')
                else:
                    download_pdf(target_url, dest)
                continue

            # Not a PDF: download the web page
            log(f'\nFetching page: {target_url}')
            html_path = group_dir / (sanitize_name(title) if title else url_to_dirname(target_url)) / 'index.html'
            item_dir = html_path.parent
            item_dir.mkdir(parents=True, exist_ok=True)

            if html_path.exists():
                log(f'  Skip page download (exists): {html_path}')
                # Read existing HTML for resource extraction
                try:
                    with Path.open(html_path, 'rb') as f:
                        page_bytes = f.read()
                except (OSError, ValueError):
                    # Fallback to re-download if read fails
                    page_bytes = download_webpage(target_url)
                    with Path.open(html_path, 'wb') as f:
                        f.write(page_bytes)
            else:
                page_bytes = download_webpage(target_url)
                with Path.open(html_path, 'wb') as f:
                    f.write(page_bytes)
                log(f'    HTML saved: {html_path}')

            # Find resource links indicated by the arrow SVG and download them
            res_links = find_svg_resource_links(page_bytes, target_url)
            if res_links:
                log(f'  Found {len(res_links)} resource link(s) on page')
            else:
                log('  No SVG-indicated resources found on page')

            for r_idx, res_url in enumerate(res_links, start=1):
                if res_url in processed_resources:
                    log(f'    Skip resource (already processed this run): {res_url}')
                    continue
                # Decide filename
                name = guess_filename_from_url(res_url, default=f'resource_{r_idx}')
                safe_name = sanitize_name(name)
                dest = item_dir / safe_name

                # If looks like HTML without extension and content-type is HTML, append .html
                if not Path(safe_name).suffix:
                    ct = head_content_type(res_url) or ''
                    if 'html' in ct.lower():
                        dest = dest.with_suffix('.html')

                if dest.exists():
                    log(f'    Skip resource (exists): {dest}')
                    processed_resources.add(res_url)
                    continue

                # Download bytes (works for PDFs and other binaries)
                if save_bytes(res_url, dest):
                    processed_resources.add(res_url)

            # be polite
            time.sleep(0.2)
        except (requests.exceptions.RequestException, OSError, ValueError, TypeError, etree.ParserError) as e:
            log(f'Error processing target {target_url}: {e}', level='error')
            continue


if __name__ == '__main__':
    # crawl_and_save()
    csv_path = r'C:\Users\linxu\OneDrive - The University of Nottingham\PEMC\251006-Ferrari_Future_Traction_PhD_Program\review\Government_Reports\APC UK\apc_uk_reports_20251013_205807.csv'
    download_from_csv(csv_path=csv_path)
