# ruff: noqa: T201

"""Dongchedi brand data crawler - Fetch car series from brand IDs"""

import csv
import json
import sys
from pathlib import Path

import certifi
import pandas as pd
import requests

# ==================== Configuration Constants ====================
API_CONFIG = {
    'url': 'https://www.dongchedi.com/motor/pc/car/brand/select_series_v2?aid=1839&app_name=auto_web_pc',
    'timeout': 15,
}

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Encoding': 'gzip, deflate, zstd',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://www.dongchedi.com',
    'Referer': 'https://www.dongchedi.com/auto/library-energy/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x',
}

DEFAULT_PARAMS = {
    'sort_new': 'hot_desc',
    'city_name': '北京',
    'fuel_form': '4,5,6',
}

TARGET_KEYS = ['brand_id', 'brand_name', 'concern_id', 'outter_name']


# ==================== Utility Functions ====================
def generate_key_variants(key: str) -> list[str]:
    """Generate multiple naming variants for a key (snake_case, camelCase, PascalCase)"""
    parts = key.split('_')
    camel = parts[0] + ''.join(p.capitalize() for p in parts[1:])
    pascal = ''.join(p.capitalize() for p in parts)
    return [key, camel, pascal, key.replace('_', '')]


def find_all_dicts(obj: object) -> iter:
    """Recursively find all dictionaries in an object"""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from find_all_dicts(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from find_all_dicts(item)


def extract_value_from_dict(d: dict, key: str) -> str:
    """Extract value from dictionary, supporting multiple naming formats"""
    for variant in generate_key_variants(key):
        if variant in d:
            val = d.get(variant) or ''
            # Normalize complex types to JSON string
            return json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val)
    return ''


def extract_rows_from_response(response_obj: object, target_keys: list[str] | None = None) -> list[list[str]]:
    """Extract target row data from API response"""
    if target_keys is None:
        target_keys = TARGET_KEYS

    seen = set()
    rows = []

    for d in find_all_dicts(response_obj):
        # Only process dictionaries containing target keys
        if not any(any(var in d for var in generate_key_variants(k)) for k in target_keys):
            continue

        row = [extract_value_from_dict(d, k) for k in target_keys]
        row_tuple = tuple(row)

        if row_tuple not in seen:
            seen.add(row_tuple)
            rows.append(row)

    return rows


def write_to_csv(rows: list[list[str]], csv_path: str | Path, header: list[str] | None = None):
    """Write data rows to CSV file"""
    if not rows:
        return

    out_path = Path(csv_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(header)
        writer.writerows(rows)

    print(f'Written {len(rows)} rows to {out_path}')


def fetch_single_page(
    session: requests.Session,
    brand_id: int | str,
    page: int,
    extra_params: dict | None = None,
) -> dict:
    """Fetch single page data for a brand"""
    params = {**DEFAULT_PARAMS, 'brand': str(brand_id), 'page': str(page)}
    if extra_params:
        params.update(extra_params)

    try:
        resp = session.post(
            API_CONFIG['url'],
            headers=DEFAULT_HEADERS,
            data=params,
            timeout=API_CONFIG['timeout'],
            verify=certifi.where(),
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.JSONDecodeError:
        return {'text': resp.text}
    except Exception as e:  # noqa: BLE001
        print(f'Request failed (page {page}): {e}')
        return {}


def fetch_single_brand(
    brand_id: int | str,
    start_page: int = 1,
    max_pages: int | None = None,
    extra_params: dict | None = None,
) -> list[list[str]]:
    """Crawl all page data for a single brand"""
    session = requests.Session()
    collected = []
    page = start_page
    pages_fetched = 0

    while True:
        result = fetch_single_page(session, brand_id, page, extra_params)
        rows = extract_rows_from_response(result)

        if not rows:
            break

        collected.extend(rows)
        pages_fetched += 1
        page += 1

        if max_pages and pages_fetched >= max_pages:
            break

    return collected


def fetch_brand_series(
    brand_id: int | str | list,
    start_page: int = 1,
    max_pages: int | None = None,
    extra_params: dict | None = None,
    write_csv: bool = True,
    csv_path: str | Path = 'output/car_ids.csv',
    target_keys: list[str] | None = None,
) -> list[list[str]]:
    """Crawl brand car series data

    Args:
        brand_id: Brand ID(s) - single value or list
        start_page: Starting page number
        max_pages: Maximum pages to fetch per brand
        extra_params: Additional request parameters
        write_csv: Whether to write results to CSV
        csv_path: CSV output path
        target_keys: Target field list

    Returns:
        List of extracted data rows

    """
    if target_keys is None:
        target_keys = TARGET_KEYS

    # Handle multiple brand IDs
    if isinstance(brand_id, (list, tuple)):
        all_rows = []
        for bid in brand_id:
            print(f'Crawling brand ID: {bid}')
            rows = fetch_single_brand(bid, start_page, max_pages, extra_params)
            all_rows.extend(rows)
            print(f'  -> Fetched {len(rows)} rows')

        if write_csv and all_rows:
            write_to_csv(all_rows, csv_path, target_keys)

        return all_rows

    # Single brand ID
    rows = fetch_single_brand(brand_id, start_page, max_pages, extra_params)

    if write_csv and rows:
        write_to_csv(rows, csv_path, target_keys)

    return rows


# ==================== Main Entry Point ====================
if __name__ == '__main__':
    if 1:
        all_brand_csv_path = Path(
            'C:/Users/linxu/OneDrive - The University of Nottingham/PEMC/251006-Ferrari_Future_Traction_PhD_Program/review/Companies/Dongchedi/tables/top_ev_brands-brands.csv'
        )
        if all_brand_csv_path.exists():
            try:
                df = pd.read_csv(all_brand_csv_path)
                if 'brand_id' in df.columns:
                    brand_list = df['brand_id'].dropna().astype(int).tolist()
                    # preserve order, remove duplicates
                    brand_list = list(dict.fromkeys(brand_list))
                else:
                    sys.exit(0)
            except Exception as e:  # noqa: BLE001
                print(f'[warn] failed to read {all_brand_csv_path}: {e}; using default ids', file=sys.stderr)
                sys.exit(0)
        else:
            sys.exit(0)
    else:
        brand_list = [16, 4, 63]
    rows = fetch_brand_series(brand_id=brand_list)
    print(f'\nTotal fetched: {len(rows)} rows')
