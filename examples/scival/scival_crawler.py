"""Crawl and parse SciVal top-author HTML into normalized CSV rows."""

from __future__ import annotations

import csv
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from dotenv import load_dotenv

log = print  # Replace with custom logger if desired.

INSTITUTION_ID_MAP: dict[tuple[str, str], int] = {
    ('Asia', 'University of Nottingham'): 315090,
    ('EU', 'University of Nottingham'): 315090,
    ('USA', 'University of Nottingham'): 315090,
    # The University of Nottingham appears in multiple areas for visual comparison, but we will crawl it once and reuse the same data across areas.
    ('UK', 'University of Nottingham'): 315090,
    ('UK', 'University of Newcastle'): 315089,
    ('UK', 'University of Manchester'): 315088,
    ('UK', 'Imperial College London'): 315018,
    ('UK', 'University of Bristol'): 315067,
    ('UK', 'University of Sheffield'): 315096,
    ('Asia', 'Huazhong University of Science and Technology'): 203099,
    ('Asia', 'Harbin Institute of Technology'): 203076,
    ('Asia', 'Zhejiang University'): 203243,
    ('Asia', "Xi'an Jiaotong University"): 203223,
    ('Asia', 'The Hong Kong Polytechnic University'): 205004,
    ('Asia', 'Nanyang Technological University'): 215003,
    ('EU', 'Delft University of Technology'): 325001,
    ('EU', 'Ghent University'): 303004,
    ('EU', 'ETH Zurich'): 306003,
    ('EU', 'KTH Royal Institute of Technology'): 332012,
    ('EU', 'EPFL - Ecole polytechnique federale de Lausanne'): 306002,
    ('EU', 'Polytechnic University of Turin'): 321019,
    ('EU', 'Polytechnic University of Milan'): 321018,
    ('EU', 'Chalmers University of Technology'): 332001,
    ('EU', 'Aalborg University'): 310001,
    ('USA', 'University of Wisconsin-Madison'): 508359,
    ('USA', 'University of Illinois Urbana-Champaign'): 508285,
    ('USA', 'Georgia Institute of Technology'): 508072,
    ('USA', 'The Ohio State University'): 508179,
    ('USA', 'North Carolina State University'): 508169,
    ('USA', 'Virginia Polytechnic Institute and State University'): 508366,
}

BASE_URL: str = 'https://www.scival.com/overview/authors/topAuthorsByScholarlyOutput?uri=Institution/'
CONTEXT_URL_TEMPLATE: str = 'https://www.scival.com/overview/authors?uri=Institution/{institution_id}'
AUTHORS_LIST_URL: str = 'https://www.scival.com/overview/authors/topAuthorsByScholarlyOutput/authorsList'
USER_AGENT: str = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
)

# Load environment variables from .env file
load_dotenv()

COOKIE: str = os.environ.get('SCIVAL_COOKIE', '')
MAX_ROWS: int = int(os.environ.get('SCIVAL_MAX_ROWS', '30'))


@dataclass(slots=True)
class AuthorRow:
    """Normalized author row parsed from SciVal HTML."""

    area: str
    institution_id: int
    institute: str
    rank: str
    author_id: str
    author_name: str
    scholarly_output_count: str
    latest_publication_year: str
    num_cites: str
    cites_per_pub: str
    fwci: str
    h_index: str


CSV_FIELDNAMES: list[str] = [
    'area',
    'institution_id',
    'institute',
    'rank',
    'author_id',
    'author_name',
    'scholarly_output_count',
    'latest_publication_year',
    'num_cites',
    'cites_per_pub',
    'fwci',
    'h_index',
]


def _text(node: Tag | None) -> str:
    """Return normalized text for an optional HTML node.

    Args:
        node: Input BeautifulSoup tag.

    Returns:
        Whitespace-normalized text, or an empty string.

    """
    return node.get_text(' ', strip=True) if node is not None else ''


def _attr(node: Tag | None, key: str) -> str:
    """Return a normalized attribute value for an optional HTML node.

    Args:
        node: Input BeautifulSoup tag.
        key: Attribute key to read.

    Returns:
        Stripped attribute value, or an empty string.

    """
    return node.get(key, '').strip() if node is not None else ''


def build_session(cookie: str) -> requests.Session:
    """Create a requests session with browser-like headers.

    Args:
        cookie: Raw cookie header string copied from browser request.

    Returns:
        Configured requests session object.

    """
    session = requests.Session()
    session.headers.update({
        'accept': '*/*',
        'accept-language': 'en-GB,en;q=0.9,zh;q=0.8,en-US;q=0.7,zh-CN;q=0.6',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://www.scival.com',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': USER_AGENT,
        'x-requested-with': 'XMLHttpRequest',
        'cookie': cookie,
    })
    return session


def fetch_authors_html(session: requests.Session, institution_id: int, timeout: float = 30.0) -> str:
    """Fetch author list HTML for one institution.

    Args:
        session: Authenticated session.
        institution_id: SciVal institution numeric id.
        timeout: Request timeout in seconds.

    Returns:
        HTML string from the AJAX endpoint.

    """
    context_url = CONTEXT_URL_TEMPLATE.format(institution_id=institution_id)
    referer_url = f'{BASE_URL}{institution_id}'

    context_resp = session.get(context_url, headers={'referer': referer_url}, timeout=timeout)
    context_resp.raise_for_status()

    payload = {
        'ajax': 'true',
        'authorEntityLevel': 'total',
        'sortType': '',
        'sortDirection': '',
        'analysisId': '0',
    }
    ajax_resp = session.post(
        AUTHORS_LIST_URL,
        headers={'referer': referer_url},
        data=payload,
        timeout=timeout,
    )
    ajax_resp.raise_for_status()
    return ajax_resp.text


def parse_authors_html(html: str, institution_id: int, institute: str, area: str) -> list[AuthorRow]:
    """Parse author cards from SciVal response HTML.

    Args:
        html: Raw response text returned by authorsList endpoint.
        institution_id: Source institution id for data lineage.
        institute: Institution display name for output table.
        area: Area label for grouping institutions.

    Returns:
        List of normalized author rows.

    """
    soup = BeautifulSoup(html, 'html.parser')
    rows: list[AuthorRow] = []
    max_rows = MAX_ROWS
    for i_row, row in enumerate(soup.select('table.authorTable tbody tr.tableRow')):
        if i_row >= max_rows:
            break
        author_link = row.select_one('td.authorCol a.authLink[data-authorid]')
        if author_link is None:
            continue

        author_name = _text(author_link)
        if not author_name:
            continue

        rank_match = re.search(r'(\d+)', _text(row.select_one('td.countCol')))
        rank = rank_match.group(1) if rank_match else ''

        scholarly_output_link = row.select_one('a.showPublications[data-count]')
        scholarly_output_count = _attr(scholarly_output_link, 'data-count')

        author_id = _attr(author_link, 'data-authorid')

        number_cells = row.select('td.number')
        latest_publication_year = _text(number_cells[1].select_one('span')) if len(number_cells) > 1 else ''
        h_index = _text(number_cells[-1].select_one('span')) if number_cells else ''

        num_cites = _text(row.select_one('.authorTableMultiValueCol.NumCites'))
        cites_per_pub = _text(row.select_one('.authorTableMultiValueCol.CitesPerPub'))
        fwci = _text(row.select_one('.authorTableMultiValueCol.FWCI'))

        rows.append(
            AuthorRow(
                area=area,
                institution_id=institution_id,
                institute=institute,
                rank=rank,
                author_id=author_id,
                author_name=author_name,
                scholarly_output_count=scholarly_output_count,
                latest_publication_year=latest_publication_year,
                num_cites=num_cites,
                cites_per_pub=cites_per_pub,
                fwci=fwci,
                h_index=h_index,
            )
        )

    return rows


def write_rows_to_csv(rows: Iterable[AuthorRow], csv_path: Path) -> None:
    """Write parsed rows to a CSV file.

    Args:
        rows: Author rows to export.
        csv_path: Output CSV file path.

    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                'area': row.area,
                'institution_id': row.institution_id,
                'institute': row.institute,
                'rank': row.rank,
                'author_id': row.author_id,
                'author_name': row.author_name,
                'scholarly_output_count': row.scholarly_output_count,
                'latest_publication_year': row.latest_publication_year,
                'num_cites': row.num_cites,
                'cites_per_pub': row.cites_per_pub,
                'fwci': row.fwci,
                'h_index': row.h_index,
            })


def crawl_and_export(
    html_dir: Path,
    csv_path: Path,
    cookie: str = COOKIE,
    timeout: float = 30.0,
) -> list[AuthorRow]:
    """Run crawl, parse, and CSV export for configured institutions.

    Args:
        html_dir: Directory where institution HTML snapshots are cached.
        csv_path: Output CSV file path.
        cookie: SciVal session cookie.
        timeout: Request timeout in seconds.

    Returns:
        Parsed author rows from all configured institutions.

    """
    session = build_session(cookie)
    all_rows: list[AuthorRow] = []

    for (area, institute), institution_id in INSTITUTION_ID_MAP.items():
        html_path = html_dir / f'institution_{institution_id}_authors.html'
        html_path.parent.mkdir(parents=True, exist_ok=True)

        if html_path.exists():
            html = html_path.read_text(encoding='utf-8')
            html_source = 'cached'
        else:
            html = fetch_authors_html(session=session, institution_id=institution_id, timeout=timeout)
            html_path.write_text(html, encoding='utf-8')
            html_source = 'downloaded'

        rows = parse_authors_html(html=html, institution_id=institution_id, institute=institute, area=area)
        all_rows.extend(rows)
        log(
            f'institution={institution_id} institute={institute} '
            f'html={html_path.name} source={html_source} parsed_rows={len(rows)}'
        )

    write_rows_to_csv(all_rows, csv_path)
    log(f'csv_export={csv_path} total_rows={len(all_rows)}')
    return all_rows
