import csv
import random
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from lxml import html

from review_agent.logger import log

folder_path = Path('./output')
transformer_folder_path = folder_path / 'transformer'


base_url = 'https://www.ferroxcube.com/'


material_folder_path = transformer_folder_path / 'materials'
html_folder_path = material_folder_path / 'htmls'
html_folder_path.mkdir(parents=True, exist_ok=True)
pdf_folder_path = material_folder_path / 'pdfs'
pdf_folder_path.mkdir(parents=True, exist_ok=True)

rows = []
product_base_url = base_url + 'zh-CN/products_ferroxcube/detail/shape_cores_accessories/'
transformer_keys = [
    'planar_er_cores',
    'eq_cores',
    'u_and_ur_cores',
    'pq_cores',
    'pm_cores',
    'er_and_etd_cores',
    'efd_cores',
    'planar_e_cores',
    'ep_and_epx_cores',
    'e_cores',
    'ec_cores',
    'rm_cores',
    'p_cores',
]

for transformer_key in transformer_keys:
    url = product_base_url + transformer_key
    file_path = html_folder_path / f'{transformer_key}.html'
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    text = response.text
    with Path.open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)
    log(f'Downloaded {transformer_key} in {url} to {file_path}', LEVEL='INFO')
    length = len(text)
    if length < 10000:
        log('Error page, remove it', LEVEL='ERROR')
        file_path.unlink(missing_ok=True)
        sys.exit()
    else:
        time.sleep(random.randint(1, 10))

    # for each html extract the pdf links and download the pdfs
    tree = html.fromstring(text)
    anchors = tree.xpath('/html/body/div[2]/div[3]/div/div[1]/div[2]/ul/li/a')
    if not anchors:
        log(f'No MDS links found for {transformer_key}', LEVEL='WARNING')

    transformer_pdf_folder = pdf_folder_path / transformer_key
    transformer_pdf_folder.mkdir(parents=True, exist_ok=True)
    for anchor in anchors:
        href = anchor.get('href', '').strip()
        if not href:
            continue

        pdf_url = urljoin(base_url, href)
        pdf_name = Path(href).name or Path(pdf_url).name
        mds_key = (anchor.text or '').strip() or Path(pdf_name).stem.upper()

        pdf_output_path = transformer_pdf_folder / pdf_name
        if not pdf_output_path.exists():
            pdf_response = requests.get(pdf_url, timeout=30)
            pdf_response.raise_for_status()
            pdf_output_path.write_bytes(pdf_response.content)
            log(f'Downloaded PDF {pdf_name} from {pdf_url} to {pdf_output_path}', LEVEL='INFO')
            time.sleep(random.randint(1, 3))

        rows.append({
            'transformer_key': transformer_key,
            'MDS_key': mds_key,
            'pdf_name': pdf_name,
            'pdf_url': pdf_url,
        })

    # sort to tabel, transformer_key, MDS_key, pdf_name, pdf_url
rows = sorted(rows, key=lambda x: (x['transformer_key'], x['MDS_key'], x['pdf_name']))
csv_path = material_folder_path / 'ferroxcube_material_table.csv'
with Path.open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['transformer_key', 'MDS_key', 'pdf_name', 'pdf_url'])
    writer.writeheader()
    writer.writerows(rows)

log(f'Saved {len(rows)} rows to {csv_path}', LEVEL='INFO')
