import sys
from pathlib import Path

from .review import review2csv


def main():  # Entry point for console_script
    input_folder_path = input('Enter the path to folder containing files (default: input/): ').strip()
    if not input_folder_path:
        input_folder_path = './input'
    input_folder_path = Path(input_folder_path.strip('"').strip("'"))
    if not input_folder_path.exists() or not input_folder_path.is_dir():
        sys.exit(1)

    output_folder_path = input('Enter the path to output folder(default: output/): ').strip() or None
    recursive_answer = input('Process subfolders recursively? (y/N): ').strip().lower()
    recursive = recursive_answer in {'y', 'yes', 'true', '1'}
    review_type_answer = input('Select review type (0=literature_review, 1=automotive_article) [default: 0]: ').strip()
    review_type_id = int(review_type_answer) if review_type_answer.isdigit() else None

    review2csv(input_folder_path, output_folder_path, recursive=recursive, review_type_id=review_type_id)


if __name__ == '__main__':  # pragma: no cover
    main()
