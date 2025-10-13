import csv
from pathlib import Path

import requests

from review_agent.logger import log

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def download_webpage(url: str):
    """Download webpage content"""
    log(f'Downloading webpage: {url}')

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.content


def download_pdf(url: str, filepath: Path) -> bool:
    """Download a PDF file"""
    try:
        log(f'  Downloading: {url}')
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        with Path.open(filepath, 'wb') as f:
            f.write(response.content)

        log(f'    Saved to: {filepath}')
        return True
    except OSError as e:
        log(f'    Error downloading {url}: {e}', level='error')
        return False


def load_from_csv(csv_path: Path) -> list[dict]:
    """Read reports data from CSV file with robust encoding handling"""
    log(f'\nReading data from CSV: {csv_path}')
    reports_data: list[dict] = []

    encodings_to_try = (
        'utf-8',
        'utf-8-sig',
        'cp65001',  # Windows UTF-8
        'gb18030',  # Superset of GBK/GB2312
        'gbk',
        'latin-1',
    )

    last_err: Exception | None = None
    for enc in encodings_to_try:
        try:
            with Path.open(csv_path, 'r', encoding=enc, newline='') as f:
                reader = csv.DictReader(f)
                reports_data.extend(row for row in reader)
            log(f'Read {len(reports_data)} records from CSV (encoding={enc})')
            return reports_data
        except UnicodeDecodeError as e:
            last_err = e
            log(f'  Failed reading with encoding={enc}: {e}', level='warn')
            reports_data.clear()
            continue
        except (OSError, csv.Error, UnicodeError, ValueError) as e:
            last_err = e
            log(f'  Error reading CSV with encoding={enc}: {e}', level='error')
            reports_data.clear()
            continue

    # If all attempts failed, raise the last error
    if last_err:
        raise last_err
    return reports_data


def save_to_csv(reports_data: list[dict], csv_path: Path, fieldnames: list[str]):
    """Save reports data to CSV file"""
    log(f'\nSaving data to CSV: {csv_path}')

    with Path.open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(reports_data)

    log(f'CSV saved with {len(reports_data)} records')
