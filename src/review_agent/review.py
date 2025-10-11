"""Batch literature review utilities.

This module provides functions to:
    * Extract text from files.
    * Generate per-paper AI summaries (raw markdown outputs stored per file).
    * Aggregate all raw responses into a single string.
    * Ask an AI model to normalize the aggregated content into a CSV table.

Entry point (CLI) asks for a folder path and produces both raw markdown responses
and a timestamped CSV summarizing the papers.
"""

from datetime import datetime
from pathlib import Path

from .ai_chat_response import chat_response
from .config import AI_MODELS_IN_USE, PROMPTS_IN_USE
from .extract_text import extract_text_from_html, extract_text_from_pdf, extract_text_from_txt
from .logger import log

# Output Configuration
OUTPUT_CONFIG = {
    'extracted_texts_subfolder': 'extracted_texts',
    'csv_filename_prefix': 'review',
    'raw_responses_filename_prefix': 'raw_responses',
    'timestamp_format': '%Y%m%d_%H%M',
}
timestamp = datetime.now().strftime(OUTPUT_CONFIG['timestamp_format'])


def literature_review(input_folder_path, output_folder=None):
    """Summarize all Files in a folder and return aggregated raw responses."""
    input_folder_path = Path(input_folder_path)
    output_folder = Path(output_folder)
    output_folder.mkdir(exist_ok=True)
    file_path_list = []
    for suffix in ('.txt', '.md', '.pdf', '.html', '.htm'):
        file_path_list += list(input_folder_path.glob(f'*{suffix}'))

    if not file_path_list:
        log('No files found', level='warning', folder=str(input_folder_path))
        return ''

    raw_responses_folder = output_folder / f'{OUTPUT_CONFIG["raw_responses_filename_prefix"]}-{timestamp}'
    log('Discovered files', count=len(file_path_list), output=str(raw_responses_folder))

    def unit_process(i_file: int, file_path: Path):
        start_time = datetime.now()
        base_info = f'Filename: {file_path.name}, File Path: {file_path}, '
        file_suffix = file_path.suffix.lower()
        match file_suffix:
            case '.txt' | '.md':
                text = extract_text_from_txt(file_path)
            case '.pdf':
                text = extract_text_from_pdf(file_path)
            case '.html' | '.htm':
                text = extract_text_from_html(file_path)
            case _:
                dt = (datetime.now() - start_time).total_seconds()
                log(
                    f'Task: {i_file} File text extraction failed', level='error', file=file_path.name, time=f'{dt:.2f}s'
                )
                return base_info + f'Character Count: N/A, Processing Time: {dt:.2f}s, Status: Extraction Failed'

        if file_suffix in ['.pdf', '.html', '.htm']:
            # Save extracted text alongside original PDF for reference
            extracted_folder = output_folder / OUTPUT_CONFIG['extracted_texts_subfolder'] + '-' + timestamp
            extracted_folder.mkdir(exist_ok=True)
            with Path.open(extracted_folder / file_path.with_suffix('.txt').name, 'w', encoding='utf-8') as f:
                f.write(text)

        log(f'Task: {i_file} Start summarizing file', file=file_path.name)
        char_count = len(text)

        summary_model_dict = AI_MODELS_IN_USE['summary']
        max_chars = summary_model_dict['context_length'] * 3 // 4
        if char_count > max_chars:
            text = text[:max_chars] + '\n\n[Text truncated due to length]'
            msg = f'Task: {i_file}  Input text truncated to fit model context length'
            log(
                msg,
                level='warning',
                file=file_path.name,
                original_chars=char_count,
                truncated_chars=len(text),
                max_chars=max_chars,
            )
        messages = [
            {'role': 'system', 'content': PROMPTS_IN_USE['system']},
            {'role': 'user', 'content': f'{PROMPTS_IN_USE["summary"]}\n{base_info}\n\nPaper Content:\n{text}'},
        ]
        content = chat_response(model_dict=summary_model_dict, messages=messages)

        dt = (datetime.now() - start_time).total_seconds()
        if content:
            log(f'Task: {i_file} Summary success', file=file_path.name, chars=char_count, time=f'{dt:.2f}s')
            final = (
                base_info
                + f'Character Count: {char_count}, Processing Time: {dt:.2f}s, Status: Success, Response: {content}'
            )
        else:
            log(
                f'Task: {i_file} Summary failed',
                level='warning',
                file=file_path.name,
                chars=char_count,
                time=f'{dt:.2f}s',
            )
            final = (
                base_info
                + f'Character Count: {char_count}, Processing Time: {dt:.2f}s, Status: Summary Failed, Response: Unable to generate summary'
            )

        raw_responses_folder.mkdir(exist_ok=True)
        md_path = raw_responses_folder / (file_path.stem + '.md')
        with Path.open(md_path, 'w', encoding='utf-8') as f:
            f.write(f'# Raw Response for {file_path.name}\n\n{final}\n\n{"=" * 80}\n')
        return final

    aggregated = [unit_process(i_file=i, file_path=p) for i, p in enumerate(file_path_list)]
    log('Completed summarization of batch', total=len(aggregated))
    return '\n\n---\n\n'.join(aggregated)


def organize_responses_to_csv(combined_responses, output_folder=None):
    """Convert aggregated raw responses into a structured CSV via AI."""
    if not combined_responses:
        log('Empty combined responses - skip CSV generation', level='warning')
        return None
    output_folder = Path(output_folder or OUTPUT_CONFIG['output_folder'])
    output_folder.mkdir(exist_ok=True)

    csv_file = output_folder / f'{OUTPUT_CONFIG["csv_filename_prefix"]}-{timestamp}.csv'

    sort_model_dict = AI_MODELS_IN_USE['sort_csv']
    if len(combined_responses) > sort_model_dict['context_length'] * 3 // 4:
        msg = 'Combined responses exceed model context length'
        log(msg, level='error', size=len(combined_responses))
        raise RuntimeError(msg)

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


def review2csv(input_folder_path, output_folder=None):
    """End-to-end pipeline: summarize all files then produce a CSV."""
    raw_responses_folder_name = f'{OUTPUT_CONFIG["raw_responses_filename_prefix"]}-'
    input_folder_path_obj = Path(input_folder_path)
    if input_folder_path_obj.is_dir() and input_folder_path_obj.name.startswith(raw_responses_folder_name):
        # Reuse existing raw responses if input folder is a raw responses folder
        log('Reusing existing raw responses folder', folder=str(input_folder_path_obj))
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
