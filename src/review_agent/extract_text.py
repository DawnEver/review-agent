import re
from html.parser import HTMLParser
from pathlib import Path

from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError, WrongPasswordError


def extract_text_from_txt(file_path):
    """Extract all textual content from a plain text file."""
    with Path.open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


def extract_text_from_pdf(file_path):
    """Extract all textual content from a PDF file."""
    text = ''
    try:
        with Path.open(file_path, 'rb', encoding=None) as file:
            pdf_reader = PdfReader(file)
            num_pages = len(pdf_reader.pages)
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text += page.extract_text()
        return text
    except (PdfReadError, WrongPasswordError):
        return None


def extract_text_from_html(file_path):
    """Extract textual content from an HTML file, ignoring scripts, styles, and comments."""

    class _TextExtractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self._ignore = 0
            self._text = []

        def handle_starttag(self, tag, attrs):
            if tag in ('script', 'style', 'noscript'):
                self._ignore += 1
            elif tag == 'br':
                self._text.append('\n')

        def handle_endtag(self, tag):
            if tag in ('script', 'style', 'noscript'):
                self._ignore = max(0, self._ignore - 1)
            elif tag in ('p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                self._text.append('\n')

        def handle_data(self, data):
            if self._ignore == 0 and data.strip():
                self._text.append(data)

        def get_text(self):
            text = ''.join(self._text)
            return re.sub(r'\s+', ' ', text).strip()

    with Path.open(file_path, 'r', encoding='utf-8') as file:
        parser = _TextExtractor()
        parser.feed(file.read())
        return parser.get_text()
