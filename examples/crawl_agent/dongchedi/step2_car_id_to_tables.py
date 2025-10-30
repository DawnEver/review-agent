"""Fetch dongchedi model parameter pages and extract all HTML tables to CSV.

Example URL:
    https://www.dongchedi.com/auto/params-carIds-x-100

This script will:
 - build URLs from `param_link_base` + model id from `model_id_list`
 - fetch each page (requests)
 - parse all HTML tables on the page (pandas.read_html)
 - add metadata columns: _model_id, _table_index, _source_url
 - either write a single combined CSV or one CSV per model

Dependencies: requests, pandas, lxml, beautifulsoup4
"""

# ruff: noqa: T201
from __future__ import annotations

import json
import random
import re
import sys
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

# Base URL (append model id)
PARAM_LINK_BASE = 'https://www.dongchedi.com/auto/params-carIds-x-'  # + model_id


def fetch_html(url: str, timeout: int = 15) -> str:
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    # Random sleep to avoid rate limiting
    time.sleep(random.uniform(1, 3))
    return resp.text


def extract_tables_from_html(html: str, model_id: int, source_url: str) -> list[pd.DataFrame]:
    """Return list of DataFrames extracted from html.

    Each DataFrame will gain three metadata columns:
      - _model_id
      - _table_index
      - _source_url
    """
    try:
        # pandas.read_html will warn when given a literal HTML string; wrap in StringIO
        dfs = pd.read_html(StringIO(html), flavor='bs4')
    except ValueError as e:
        # read_html may raise if no tables or parse error
        print(f'[warn] no tables or failed to parse for model {model_id}: {e}', file=sys.stderr)
        return []

    out = []
    for idx, df in enumerate(dfs):
        df = df.copy()
        df['_model_id'] = model_id
        df['_table_index'] = idx
        df['_source_url'] = source_url
        out.append(df)
    return out


def extract_tables_from_embedded_json(html: str, model_id: int, source_url: str) -> list[pd.DataFrame]:  # noqa: PLR0911
    """Some pages (dongchedi) embed the data as a JSON blob inside a large script.

    This function locates the JSON, parses `rawData`, and converts `car_info`
    (per-variant dictionaries) into a table where each row is a car variant and
    columns are property keys (mapped to human readable labels when available).
    """
    # find largest inline script and attempt to extract the JSON that contains "props" -> "pageProps"

    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, flags=re.DOTALL)
    if not scripts:
        return []
    candidate = max(scripts, key=len)
    start = candidate.find('{"props"')
    if start == -1:
        return []

    # find matching closing brace for the JSON object starting at start
    s = candidate
    i = start
    stack = []
    end = None
    while i < len(s):
        ch = s[i]
        if ch == '{':
            stack.append('{')
        elif ch == '}':
            stack.pop()
            if not stack:
                end = i
                break
        i += 1

    if end is None:
        return []

    json_text = s[start : end + 1]
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return []

    pp = parsed.get('props', {}).get('pageProps', {})
    raw = pp.get('rawData')
    if not raw:
        return []

    # Build key->label mapping from properties list (if present)
    properties = raw.get('properties', []) or []
    key2label = {p.get('key'): p.get('text') for p in properties if p.get('key')}

    car_info = raw.get('car_info', [])
    if not car_info:
        return []

    # Each car_info item contains 'info' dict with many property keys mapping to {value,...}
    rows = []
    for car in car_info:
        base = {k: car.get(k) for k in ('car_id', 'car_name', 'official_price', 'dealer_price', 'car_year')}
        info = car.get('info', {}) or {}
        for prop_key, prop_val in info.items():
            # many entries are dicts with a 'value' field
            if isinstance(prop_val, dict) and 'value' in prop_val:
                base[prop_key] = prop_val.get('value')
            else:
                base[prop_key] = prop_val
        rows.append(base)

    df = pd.DataFrame(rows)
    # rename columns using key2label when available
    rename_map = {k: key2label.get(k, k) for k in df.columns}
    df = df.rename(columns=rename_map)
    df['_model_id'] = model_id
    df['_source_url'] = source_url
    return [df]


def get_tables_for_model(model_id: int, try_mobile: bool = True) -> list[pd.DataFrame]:
    """Attempt multiple strategies to extract tables/data for a model.

    Returns a list of DataFrames (possibly empty).
    """
    url = f'{PARAM_LINK_BASE}{model_id}'
    print(f'Fetching: {url}')
    try:
        html = fetch_html(url)
    except ValueError as e:
        print(f'[error] failed to fetch {url}: {e}', file=sys.stderr)
        return []

    # 1) try direct HTML tables
    tables = extract_tables_from_html(html, model_id, url)
    if tables:
        return tables

    # 2) try embedded JSON in the page
    tables = extract_tables_from_embedded_json(html, model_id, url)
    if tables:
        return tables

    # 3) try mobile site (some pages embed JSON there)
    if try_mobile:
        mobile_url = url.replace('www.', 'm.')
        print(f'Trying mobile URL: {mobile_url}')
        try:
            mobile_html = fetch_html(mobile_url)
            return extract_tables_from_embedded_json(mobile_html, model_id, mobile_url)
        except ValueError as e:
            print(f'[warn] failed to fetch mobile url {mobile_url}: {e}')

    return []


def build_output_path(base_output: Path, model_id: int) -> Path:
    ext = base_output.suffix or '.csv'
    return base_output.with_name(f'{base_output.stem}_model_{model_id}{ext}')


def save_tables(tables: list[pd.DataFrame], out_path: Path, excel: bool = False) -> None:
    if not tables:
        print(f'No tables to save for {out_path}')
        return
    write_combined_output(tables, out_path, excel=excel)


def write_combined_output(dfs: list[pd.DataFrame], out_path: Path, excel: bool = False) -> None:
    if not dfs:
        print('No tables to write.')
        return

    # Ensure column labels are unique across dataframes to avoid pandas concat errors
    def make_unique(cols):
        seen = {}
        out = []
        for c in cols:
            if c not in seen:
                seen[c] = 0
                out.append(c)
            else:
                seen[c] += 1
                out.append(f'{c}__{seen[c]}')
        return out

    cleaned: list[pd.DataFrame] = []
    for df in dfs:
        df = df.copy()
        df.columns = make_unique(list(df.columns))
        cleaned.append(df)

    combined = pd.concat(cleaned, ignore_index=True, sort=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if excel:
        # Write Excel file
        try:
            combined.to_excel(out_path, index=False)
            print(f'Wrote combined Excel: {out_path}')
        except ValueError as e:
            print(f'[error] failed to write Excel {out_path}: {e}')
            # fallback to CSV
            csv_path = out_path.with_suffix('.csv')
            combined.to_csv(csv_path, index=False)
            print(f'Wrote fallback CSV: {csv_path}')
    else:
        combined.to_csv(out_path, index=False)
        print(f'Wrote combined CSV: {out_path}')


def model2table(output_path: Path, per_model: bool = False, excel: bool = True, model_ids=None) -> None:
    """Main entry: iterate model_id_list and save combined or per-model outputs.

    Parameters
    ----------
    - output_csv: base output path (CSV or XLSX depending on excel flag)
    - per_model: whether to write one file per model
    - excel: whether to write .xlsx files
    - model_ids: list of model IDs to process

    """
    if model_ids is None:
        model_ids = []
    all_tables: list[pd.DataFrame] = []

    batch_tables: list[pd.DataFrame] = []
    batch_idx = 0

    for idx, model_id in enumerate(model_ids, start=1):
        tables = get_tables_for_model(model_id)
        if per_model:
            if tables:
                path = build_output_path(output_path, model_id)
                save_tables(tables, path, excel=excel)
            else:
                print(f'No tables for model {model_id}; skipping per-model write.')
            continue

        # accumulate for final combined write
        if tables:
            all_tables.extend(tables)
            batch_tables.extend(tables)

        # every 10 models, flush batch to disk
        if idx % 10 == 0:
            batch_idx += 1
            ext = output_path.suffix or '.csv'
            batch_path = output_path.with_name(f'{output_path.stem}_batch_{batch_idx}{ext}')
            if batch_tables:
                save_tables(batch_tables, batch_path, excel=excel)
            batch_tables = []

    # save any remaining batch (<10 models)
    if not per_model and batch_tables:
        batch_idx += 1
        ext = output_path.suffix or '.csv'
        batch_path = output_path.with_name(f'{output_path.stem}_batch_{batch_idx}{ext}')
        save_tables(batch_tables, batch_path, excel=excel)

    # final unified save for all processed models
    if not per_model:
        save_tables(all_tables, output_path, excel=excel)


if __name__ == '__main__':
    if 1:
        brand_csv_path = Path('output/car_ids.csv')
        if brand_csv_path.exists():
            try:
                df = pd.read_csv(brand_csv_path)
                if 'concern_id' in df.columns:
                    model_id_list = df['concern_id'].dropna().astype(int).tolist()
                    # preserve order, remove duplicates
                    model_id_list = list(dict.fromkeys(model_id_list))
                else:
                    sys.exit(0)
            except Exception as e:  # noqa: BLE001
                print(f'[warn] failed to read {brand_csv_path}: {e}; using default ids', file=sys.stderr)
                sys.exit(0)
    else:
        model_id_list = [100, 25549, 25550, 25551, 20000]

    out_path = Path('output/dongchedi_tables.xlsx')
    model2table(out_path, per_model=False, excel=True, model_ids=model_id_list)
