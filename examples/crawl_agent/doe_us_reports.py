import random
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from lxml import html

from crawl_agent import download_pdf, download_webpage, save_to_csv
from review_agent.logger import log

# Setup paths
folder_path = Path('./output')
page_folder_path = folder_path / 'reports'
csv_folder_path = folder_path / 'reports_csv'
page_folder_path.mkdir(parents=True, exist_ok=True)
csv_folder_path.mkdir(parents=True, exist_ok=True)

# URL to scrape
doe_us_reports_url = 'https://www.energy.gov/eere/vehicles/annual-progress-reports'

# Base XPath for report lists (adjust based on actual structure)
base_xpath = '//*[@id="block-main-page-content"]/article/div/section[1]/div/div/div/div/div/div/ul'


def parse_reports(html_content, base_url):
    """Parse HTML content and extract PDF information"""
    tree = html.fromstring(html_content)
    reports_data = []

    # Try to find all ul elements containing reports
    ul_elements = tree.xpath(f'{base_xpath}')

    log(f'Found {len(ul_elements)} report lists')

    for i_year, ul in enumerate(ul_elements, start=1):
        # Try to extract year from heading or nearby text
        year = extract_year_from_context(ul, i_year)

        # Find all li elements (reports) within this ul
        li_elements = ul.xpath('.//li')

        log(f'  List {i_year} (Year: {year}): Found {len(li_elements)} reports')

        for i_report, li in enumerate(li_elements, start=1):
            # Find PDF links within the li element
            pdf_links = li.xpath('.//a')

            for link in pdf_links:
                href = link.get('href')
                if href:
                    # Make absolute URL
                    pdf_url = urljoin(base_url, href)

                    # Get link text as title
                    title = link.text_content().strip()

                    # Generate filename from URL or title
                    filename = generate_filename(pdf_url, title, year, i_report)

                    reports_data.append({'year': year, 'title': title, 'url': pdf_url, 'filename': filename})

    return reports_data


def extract_year_from_context(ul_element, list_index):
    """Try to extract year from context around the ul element"""
    # Try to find preceding heading
    preceding_headings = ul_element.xpath('preceding::h2[1] | preceding::h3[1] | preceding::h4[1]')

    if preceding_headings:
        heading_text = preceding_headings[0].text_content()
        year_match = re.search(r'(19|20)\d{2}', heading_text)
        if year_match:
            return year_match.group(0)

    # If no year found, return a placeholder
    return f'{list_index}'


def generate_filename(url, title, year, report_num):
    """Generate a clean filename for the PDF"""
    # Extract filename from URL
    url_filename = url.split('/')[-1]

    # If URL has a good filename, use it
    if url_filename.endswith('.pdf') and len(url_filename) > 4:
        return url_filename

    # Otherwise, generate from title and year
    clean_title = re.sub(r'[^\w\s-]', '', title)
    return f'{year}_{report_num}_{clean_title}.pdf'


def main():
    """Main execution function"""
    log('=' * 80)
    log('DOE US Reports Downloader')
    log('=' * 80)

    # Step 1: Download webpage
    html_content = download_webpage(doe_us_reports_url)

    # Step 2: Parse and extract PDF information
    reports_data = parse_reports(html_content, doe_us_reports_url)

    log(f'\nTotal reports found: {len(reports_data)}')

    if not reports_data:
        log('No reports found! Check the XPath and webpage structure.', level='ERROR')
        return

    # Step 3: Save to CSV
    csv_filename = f'doe_reports_{time.strftime("%Y%m%d_%H%M%S")}.csv'
    csv_path = csv_folder_path / csv_filename
    save_to_csv(reports_data, csv_path, fieldnames=['year', 'title', 'url', 'filename'])

    # Step 4: Download PDFs
    log('\n' + '=' * 80)
    log(f'Downloading {len(reports_data)} PDF files...')
    log('=' * 80)

    success_count = 0
    for i, report in enumerate(reports_data, start=1):
        log(f'\n[{i}/{len(reports_data)}] {report["title"][:60]}...')

        pdf_path = page_folder_path / report['filename']

        # Skip if already exists
        if pdf_path.exists():
            log('  File already exists, skipping')
            success_count += 1
            continue

        # Download with delay to be polite
        if download_pdf(report['url'], pdf_path):
            success_count += 1

        # Random delay between downloads
        time.sleep(random.uniform(1, 3))

    log('\n' + '=' * 80)
    log(f'Download complete: {success_count}/{len(reports_data)} files')
    log(f'PDFs saved to: {page_folder_path}')
    log(f'CSV saved to: {csv_path}')
    log('=' * 80)


if __name__ == '__main__':
    main()
