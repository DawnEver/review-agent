"""Main entry for SciVal crawl and plotting pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from scival_crawler import COOKIE, crawl_and_export
from scival_plot import export_area_comparison_plots

log = print


def main() -> None:
    """Run crawl and plotting pipeline.

    Environment Variables:
        SCIVAL_RUN_CRAWL: Set to "1" to enable network crawl. Default is "0".
        SCIVAL_COOKIE: Optional cookie override used by crawl session.

    """
    # Load environment variables from .env file
    load_dotenv()

    output_dir = Path('./output/scival')
    html_dir = output_dir / 'scival_html'
    csv_path = output_dir / 'scival_authors.csv'
    chart_dir = output_dir / 'charts'

    run_crawl = os.environ.get('SCIVAL_RUN_CRAWL', '0') == '1'

    if run_crawl:
        cookie = os.environ.get('SCIVAL_COOKIE', COOKIE)
        crawl_and_export(html_dir=html_dir, csv_path=csv_path, cookie=cookie)
    else:
        log(f'crawl_skip=1 reason=SCIVAL_RUN_CRAWL!=1 csv={csv_path}')

    chart_paths = export_area_comparison_plots(csv_path=csv_path, chart_dir=chart_dir, top_n=10)
    if chart_paths:
        for chart_path in chart_paths:
            log(f'chart_export={chart_path}')
    else:
        log(f'chart_export=none csv={csv_path}')


if __name__ == '__main__':
    main()
