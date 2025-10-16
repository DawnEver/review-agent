import random
import sys
import time
from pathlib import Path

import requests

from review_agent.logger import log

folder_path = Path('./output')
page_folder_path = folder_path / 'pages'
page_folder_path.mkdir(parents=True, exist_ok=True)
auto_key_list = [
    '849-testarossa',
    '849-testarossa-spider',
    '296-gtb',
    '296-gts',
    'ferrari-12cilindri',
    'ferrari-12cilindri-spider',
    'ferrari-purosangue',
    'ferrari-amalfi',
    'ferrari-roma-spider',
    '296-speciale',
    '296-speciale-a',
    'sf90-xx-stradale',
    'sf90-xx-spider',
    '812-competizione',
    '812-competizione-a',
    'ferrari-daytona-sp3',
    'monza-sp1',
    'monza-sp2',
    'f80',
    'laferrari-aperta',
    'laferrari',
    'enzo-ferrari',
    'f50',
    'f40',
    'gto',
]
ferrari_auto_base_url = 'https://www.ferrari.com/en-EN/auto/'

for auto_key in auto_key_list:
    url = ferrari_auto_base_url + auto_key
    file_path = page_folder_path / f'{auto_key}.html'
    response = requests.get(url, timeout=30)
    text = response.text
    with Path.open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)
    log(f'Downloaded {auto_key} in {url} to {file_path}', LEVEL='INFO')
    length = len(text)
    if length < 10000:
        log('Error page, remove it', LEVEL='ERROR')
        file_path.unlink(missing_ok=True)
        sys.exit()
    else:
        time.sleep(random.randint(1, 10))
