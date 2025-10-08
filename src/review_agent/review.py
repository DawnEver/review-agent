"""Batch literature review utilities.

This module provides functions to:
    * Extract text from PDF files.
    * Generate per-paper AI summaries (raw markdown outputs stored per file).
    * Aggregate all raw responses into a single string.
    * Ask an AI model to normalize the aggregated content into a CSV table.

Entry point (CLI) asks for a folder path and produces both raw markdown responses
and a timestamped CSV summarizing the papers.
"""

from datetime import datetime
from pathlib import Path

from ollama import ResponseError
from ollama import chat as ollama_chat
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError, WrongPasswordError

from .config import AI_MODELS_IN_USE, OUTPUT_CONFIG, PROMPTS_IN_USE
from .logger import log


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


def chat_response(model_dict, messages):
    match model_dict['type']:
        case 'ollama':
            response = ollama_chat(
                model=model_dict['model_name'],
                messages=messages,
                think=model_dict.get('think', None),
                options=model_dict.get('options', {}),
            )
        case _:
            msg = f'Unsupported model type: {model_dict["type"]}'
            raise ValueError(msg)
    return response['message']['content'].strip()


def literature_review(input_folder_path, output_folder=None):
    """Summarize all PDFs in a folder and return aggregated raw responses."""
    input_folder_path = Path(input_folder_path)
    output_folder = Path(output_folder or OUTPUT_CONFIG['output_folder'])
    output_folder.mkdir(exist_ok=True)

    file_path_list = list(input_folder_path.glob('*.pdf'))  # TODO: 支持更多类型
    if not file_path_list:
        log('No PDF files found', level='warning', folder=str(input_folder_path))
        return ''

    timestamp = datetime.now().strftime(OUTPUT_CONFIG['timestamp_format'])
    raw_responses_folder = output_folder / f'{OUTPUT_CONFIG["raw_responses_filename_prefix"]}-{timestamp}'
    log('Discovered PDF files', count=len(file_path_list), output=str(raw_responses_folder))

    def unit_process(pdf_path: Path):
        start_time = datetime.now()
        text = extract_text_from_pdf(pdf_path)
        log('Start summarizing file', file=pdf_path.name)
        base_info = f'Filename: {pdf_path.name}, File Path: {pdf_path}, '
        if text is None:
            dt = (datetime.now() - start_time).total_seconds()
            log('PDF text extraction failed', level='error', file=pdf_path.name, time=f'{dt:.2f}s')
            return base_info + f'Character Count: N/A, Processing Time: {dt:.2f}s, Status: Extraction Failed'

        char_count = len(text)
        try:
            summary_model_dict = AI_MODELS_IN_USE['summary']
            max_chars = summary_model_dict['context_length'] * 3 // 4
            if char_count > max_chars:
                text = text[:max_chars] + '\n\n[Text truncated due to length]'
            messages = [
                {'role': 'system', 'content': PROMPTS_IN_USE['system']},
                {'role': 'user', 'content': f'{PROMPTS_IN_USE["summary"]}\n{base_info}\n\nPaper Content:\n{text}'},
            ]
            content = chat_response(model_dict=summary_model_dict, messages=messages)
        except ResponseError:
            content = None
            log('Model summary request failed', level='error', file=pdf_path.name)
        dt = (datetime.now() - start_time).total_seconds()
        if content:
            log('Summary success', file=pdf_path.name, chars=char_count, time=f'{dt:.2f}s')
            final = (
                base_info
                + f'Character Count: {char_count}, Processing Time: {dt:.2f}s, Status: Success, Response: {content}'
            )
        else:
            log('Summary failed', level='warning', file=pdf_path.name, chars=char_count, time=f'{dt:.2f}s')
            final = (
                base_info
                + f'Character Count: {char_count}, Processing Time: {dt:.2f}s, Status: Summary Failed, Response: Unable to generate summary'
            )

        raw_responses_folder.mkdir(exist_ok=True)
        md_path = raw_responses_folder / (pdf_path.stem + '.md')
        with Path.open(md_path, 'w', encoding='utf-8') as f:
            f.write(f'# Raw Response for {pdf_path.name}\n\n{final}\n\n{"=" * 80}\n')
        return final

    aggregated = [unit_process(p) for p in file_path_list]
    log('Completed summarization of batch', total=len(aggregated))
    return '\n\n---\n\n'.join(aggregated)


def organize_responses_to_csv(combined_responses, output_folder=None):
    """Convert aggregated raw responses into a structured CSV via AI."""
    if not combined_responses:
        log('Empty combined responses - skip CSV generation', level='warning')
        return None
    output_folder = Path(output_folder or OUTPUT_CONFIG['output_folder'])
    output_folder.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime(OUTPUT_CONFIG['timestamp_format'])
    csv_file = output_folder / f'{OUTPUT_CONFIG["csv_filename_prefix"]}-{timestamp}.csv'

    sort_model_dict = AI_MODELS_IN_USE['sort_csv']
    if len(combined_responses) > sort_model_dict['context_length'] * 3 // 4:
        msg = 'Combined responses exceed model context length'
        log(msg, level='error', size=len(combined_responses))
        raise RuntimeError(msg)

    try:
        log('Requesting CSV organization from model')
        messages = [
            {'role': 'system', 'content': PROMPTS_IN_USE['system']},
            {'role': 'user', 'content': f'{PROMPTS_IN_USE["sort_csv"]}\n\nRaw Data:\n{combined_responses}'},
        ]
        csv_content = chat_response(model_dict=sort_model_dict, messages=messages)

        if csv_content.startswith('```'):
            first_newline = csv_content.find('\n')
            if first_newline != -1:
                csv_content = csv_content[first_newline + 1 :]
        csv_content = csv_content.removesuffix('```').strip()
        with Path.open(csv_file, 'w', encoding='utf-8-sig') as f:
            f.write(csv_content)
        log('CSV file written', path=str(csv_file), bytes=csv_file.stat().st_size)
        return csv_file
    except ResponseError:
        log('CSV generation model call failed', level='error')
        return None


def review2csv(input_folder_path, output_folder=None):
    """End-to-end pipeline: summarize all files then produce a CSV."""
    raw_responses_folder_name = f'{OUTPUT_CONFIG["raw_responses_filename_prefix"]}-'
    input_folder_path_obj = Path(input_folder_path)
    if input_folder_path_obj.is_dir() and input_folder_path_obj.name.startswith(raw_responses_folder_name):
        md_files = sorted(input_folder_path_obj.glob('*.md'))
        if not md_files:
            log('No markdown files found in raw responses folder', level='warning', folder=str(input_folder_path_obj))
            return None
        combined = '\n\n---\n\n'.join(Path(md_file).read_text(encoding='utf-8') for md_file in md_files)
    else:
        combined = literature_review(input_folder_path, output_folder)
        if not combined:
            log('No summaries produced; aborting pipeline', level='warning')
            return None
    csv_path = organize_responses_to_csv(combined, output_folder)
    if csv_path:
        log('Pipeline success', csv=str(csv_path))
    else:
        log('Pipeline finished without CSV output', level='warning')
    return csv_path
