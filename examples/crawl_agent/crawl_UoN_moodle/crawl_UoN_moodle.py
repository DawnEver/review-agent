import csv
import random
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# --- Configuration Area ---
MOODLE_SESSION = (
    'gluj22ertask6ugouvib2jb2v3; MOODLEID1_=sodium%3AmahscMAyEloXccb%2BbS6zrf2RNk3H0JHY5Em5rcl%2Fi8zTDUMN%2Bym4tZ8iHVwd'
)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Cookie': f'MoodleSession={MOODLE_SESSION}',
}

DOWNLOAD_DIR = Path('output/crawl_UoN_moodle')
script_folder = Path(__file__).resolve().parent
CSV_PATH = script_folder / 'index.csv'
REQUEST_DELAY = (0, 1)  # Delay range in seconds (min, max)


def sanitize_name(name):
    """Removes or replaces characters that are invalid in Windows filenames."""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()


def get_course_data():
    """Reads course list from index.csv and returns as a list of dicts."""
    data = []
    if CSV_PATH.exists():
        with Path.open(CSV_PATH, encoding='utf-8') as f:
            data.extend({'name': row[0].strip(), 'url': row[1].strip()} for row in csv.reader(f) if len(row) >= 2)
    return data


def save_resource(session, url, save_dir, default_name):
    """Downloads resource. Handles HTML cleaning (removing <script>) and binary file saving.
    Implements a caching mechanism based on file existence.
    Returns (BeautifulSoup object if HTML, Path to saved file).
    """
    # 1. Prepare potential target path (defaulting to .html)
    target_name = default_name if '.' in default_name else f'{default_name}.html'
    save_path = save_dir / target_name

    # 2. Cache check
    if save_path.exists() and save_path.stat().st_size > 1024:
        if save_path.suffix == '.html':
            with Path.open(save_path, encoding='utf-8', errors='ignore') as f:
                return BeautifulSoup(f.read(), 'html.parser'), save_path
        return None, save_path

    try:
        # Simulate human behavior with a random delay
        wait_time = random.uniform(*REQUEST_DELAY)
        time.sleep(wait_time)

        # 3. Fetch resource
        with session.get(url, stream=True, allow_redirects=True) as r:
            r.raise_for_status()
            content_type = r.headers.get('Content-Type', '').lower()

            if 'text/html' in content_type:
                # Clean HTML: Remove all script tags
                soup = BeautifulSoup(r.text, 'html.parser')
                for script in soup('script'):
                    script.decompose()

                save_path.write_text(str(soup), encoding='utf-8')
                return soup, save_path
            # Handle Binary: Extract filename from Content-Disposition if possible
            cd = r.headers.get('Content-Disposition')
            if cd:
                match = re.search('filename="(.+?)"', cd)
                if match:
                    save_path = save_dir / match.group(1)

            with Path.open(save_path, 'wb') as f:
                f.writelines(r.iter_content(chunk_size=8192))
            return None, save_path
    except Exception:  # noqa: BLE001
        return None, None


def download_files():
    """Main execution logic: scans courses, downloads resources, and localizes links."""
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    for course in get_course_data():
        name, url = sanitize_name(course['name']), course['url']
        root = DOWNLOAD_DIR / name
        src = root / 'src'
        for d in [root, src]:
            d.mkdir(exist_ok=True)

        url_map = {}

        # Step 1: Process course index
        soup, idx_path = save_resource(session, url, root, 'index')
        if not soup:
            continue
        url_map[url] = idx_path

        # Step 2: Download course resources
        patterns = ['mod/folder/view.php', 'mod/resource/view.php', 'pluginfile.php/']
        links = [a for a in soup.find_all('a', href=True) if any(p in a['href'] for p in patterns)]

        for a in links:
            href = a['href']
            title = sanitize_name(a.get_text(strip=True)) or 'resource'
            sub_soup, sub_path = save_resource(session, href, src, title)
            if sub_path:
                url_map[href] = sub_path

            # Sub-step: If intermediate HTML, scan for embedded pluginfiles
            if sub_soup:
                embedded = [ea for ea in sub_soup.find_all('a', href=True) if 'pluginfile.php/' in ea['href']]
                for ebda in embedded:
                    ehref = ebda['href']
                    etitle = sanitize_name(ebda.get_text(strip=True)) or 'embedded'
                    _, epath = save_resource(session, ehref, src, etitle)
                    if epath:
                        url_map[ehref] = epath

        # Step 3: Localization (Convert absolute Moodle links to local relative paths)
        for html_file in root.rglob('*.html'):
            with Path.open(html_file, encoding='utf-8', errors='ignore') as f:
                h_soup = BeautifulSoup(f.read(), 'html.parser')

            modified = False
            for atag in h_soup.find_all('a', href=True):
                orig_href = atag['href']
                if orig_href in url_map:
                    # Using Python 3.12+ walk_up feature for clean PathLib-based localization
                    rel_path = url_map[orig_href].relative_to(html_file.parent, walk_up=True).as_posix()
                    atag['href'] = rel_path
                    modified = True

                # Remove onclick attributes to prevent JS interference offline
                if atag.has_attr('onclick'):
                    del atag['onclick']
                    modified = True

            if modified:
                html_file.write_text(str(h_soup), encoding='utf-8')


if __name__ == '__main__':
    download_files()
