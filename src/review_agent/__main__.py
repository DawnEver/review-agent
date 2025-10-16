import argparse
import sys
from pathlib import Path

from .review import review2csv


def main():  # Entry point for console_script
    parser = argparse.ArgumentParser(description='Convert reviews to CSV.')
    parser.add_argument(
        '-i',
        '--input',
        dest='input_folder',
        default='./input',
        help='Path to folder containing files (default: ./input)',
    )
    parser.add_argument(
        '-o', '--output', dest='output_folder', default=None, help='Path to output folder (default: None)'
    )
    parser.add_argument('-r', '--recursive', action='store_true', help='Process subfolders recursively')
    parser.add_argument(
        '-t',
        '--review-type',
        dest='review_type_id',
        type=int,
        help='Review type (e.g., 0=literature_review, 1=automotive_article)',
    )

    args = parser.parse_args()

    input_folder_path = Path(args.input_folder.strip('"').strip("'"))
    if not input_folder_path.exists() or not input_folder_path.is_dir():
        sys.exit(1)

    output_folder_path = args.output_folder.strip('"').strip("'") if args.output_folder else None

    review2csv(
        input_folder_path,
        output_folder_path,
        recursive=args.recursive,
        review_type_id=args.review_type_id,
    )


if __name__ == '__main__':  # pragma: no cover
    main()
