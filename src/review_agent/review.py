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
from .config import (
    AI_MODELS_IN_USE as DEFAULT_AI_MODELS_IN_USE,
)
from .config import (
    PROMPTS_IN_USE as DEFAULT_PROMPTS_IN_USE,
)
from .config import (
    get_review_config,
)
from .extract_text import extract_text_from_html, extract_text_from_pdf, extract_text_from_txt
from .logger import log

# Output Configuration
OUTPUT_CONFIG = {
    'csv_filename_prefix': 'review',
    'raw_responses_filename_prefix': 'raw_responses',
    'timestamp_format': '%Y%m%d_%H%M',
}
timestamp = datetime.now().strftime(OUTPUT_CONFIG['timestamp_format'])

# Supported input file suffixes
SUPPORTED_SUFFIXES = ('.txt', '.md', '.pdf', '.html', '.htm')


def literature_review(
    input_folder_path: Path,
    output_folder: Path | None = None,
    *,
    ai_models_in_use: dict | None = None,
    prompts_in_use: dict | None = None,
):
    """Summarize all files in a single folder and return aggregated raw responses.

    Args:
        input_folder_path: Folder containing source documents.
        output_folder: Destination folder to write outputs. Defaults to 'output/'.

    """
    input_folder_path = Path(input_folder_path)
    output_folder = Path(output_folder) if output_folder else Path('output')
    output_folder.mkdir(parents=True, exist_ok=True)
    file_path_list = []
    for suffix in SUPPORTED_SUFFIXES:
        file_path_list += list(input_folder_path.glob(f'*{suffix}'))

    if not file_path_list:
        log('No files found', level='warning', folder=str(input_folder_path))
        return ''

    raw_responses_folder = output_folder / f'{OUTPUT_CONFIG["raw_responses_filename_prefix"]}-{timestamp}'
    ai_models_in_use = ai_models_in_use or DEFAULT_AI_MODELS_IN_USE
    prompts_in_use = prompts_in_use or DEFAULT_PROMPTS_IN_USE
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
            extracted_folder = output_folder / f'extracted_texts-{timestamp}'
            extracted_folder.mkdir(parents=True, exist_ok=True)
            with Path.open(extracted_folder / file_path.with_suffix('.txt').name, 'w', encoding='utf-8') as f:
                f.write(text)

        log(f'Task: {i_file} Start summarizing file', file=file_path.name)
        char_count = len(text)
        summary_model_dict = ai_models_in_use['summary']
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
            {'role': 'system', 'content': prompts_in_use['system']},
            {'role': 'user', 'content': f'{prompts_in_use["summary"]}\n{base_info}\n\nPaper Content:\n{text}'},
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

        raw_responses_folder.mkdir(parents=True, exist_ok=True)
        md_path = raw_responses_folder / (file_path.stem + '.md')
        with Path.open(md_path, 'w', encoding='utf-8') as f:
            f.write(f'# Raw Response for {file_path.name}\n\n{final}\n\n{"=" * 80}\n')
        return final

    aggregated = [unit_process(i_file=i, file_path=p) for i, p in enumerate(file_path_list)]
    log('Completed summarization of batch', total=len(aggregated))
    return '\n\n---\n\n'.join(aggregated)


def organize_responses_to_csv(
    combined_responses: list | str,
    output_folder: Path | None = None,
    *,
    ai_models_in_use: dict | None = None,
    prompts_in_use: dict | None = None,
):
    """Convert aggregated raw responses into a structured CSV via AI.

    Args:
        combined_responses: Aggregated markdown or string content from summarization.
        output_folder: Destination folder to write CSV. Defaults to 'output/'.

    """
    if not combined_responses:
        log('Empty combined responses - skip CSV generation', level='warning')
        return None
    output_folder = Path(output_folder) if output_folder else Path('output')
    output_folder.mkdir(parents=True, exist_ok=True)

    csv_file = output_folder / f'{OUTPUT_CONFIG["csv_filename_prefix"]}-{timestamp}.csv'

    ai_models_in_use = ai_models_in_use or DEFAULT_AI_MODELS_IN_USE
    prompts_in_use = prompts_in_use or DEFAULT_PROMPTS_IN_USE
    sort_model_dict = ai_models_in_use['sort_csv']
    # Accept both list of strings or a single string
    combined_as_text = ''.join(combined_responses) if isinstance(combined_responses, list) else str(combined_responses)
    if len(combined_as_text) > sort_model_dict['context_length'] * 3 // 4:
        msg = 'Combined responses exceed model context length'
        log(msg, level='error', size=len(combined_as_text))
        raise RuntimeError(msg)

    log('Requesting CSV organization from model')
    messages = [
        {'role': 'system', 'content': prompts_in_use['system']},
        {'role': 'user', 'content': f'{prompts_in_use["sort_csv"]}\n\nRaw Data:\n{combined_as_text}'},
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


def review2csv(
    input_folder_path: Path,
    output_folder: Path | None = None,
    recursive: bool = False,
    review_type_id: int | str | None = None,
):
    """End-to-end pipeline: summarize files then produce CSV.

    Args:
        input_folder_path: Root folder to process.
        output_folder: Root output folder; when recursive=True, the structure under this root mirrors input.
        recursive: If True, process all subfolders and mirror output structure.

    Returns:
        - If recursive is False: Path to the generated CSV or None.
        - If recursive is True: Dict mapping each processed relative folder to its CSV Path (or None if failed).

    """
    input_root = Path(input_folder_path)
    output_root = Path(output_folder) if output_folder else Path('output')

    # Resolve runtime configuration
    cfg = get_review_config(review_type_id)
    ai_models_in_use = cfg['AI_MODELS_IN_USE']
    prompts_in_use = cfg['PROMPTS_IN_USE']

    raw_prefix = f'{OUTPUT_CONFIG["raw_responses_filename_prefix"]}-'

    def process_single_folder(folder: Path, out_folder: Path):
        # If folder itself is a raw-responses folder, reuse MDs
        if folder.is_dir() and folder.name.startswith(raw_prefix):
            log('Reusing existing raw responses folder', folder=str(folder))
            md_files = sorted(folder.glob('*.md'))
            if not md_files:
                log('No markdown files found in raw responses folder', level='warning', folder=str(folder))
                return None
            combined_local = '\n\n---\n\n'.join(Path(md_file).read_text(encoding='utf-8') for md_file in md_files)
        else:
            combined_local = literature_review(
                folder,
                out_folder,
                ai_models_in_use=ai_models_in_use,
                prompts_in_use=prompts_in_use,
            )
            if not combined_local:
                log('No summaries produced; skipping CSV', level='warning', folder=str(folder))
                return None
        csv_path_local = organize_responses_to_csv(
            combined_local,
            out_folder,
            ai_models_in_use=ai_models_in_use,
            prompts_in_use=prompts_in_use,
        )
        if csv_path_local:
            log('Pipeline success', csv=str(csv_path_local), folder=str(folder))
        else:
            log('Pipeline finished without CSV output', level='warning', folder=str(folder))
        return csv_path_local

    if not recursive:
        return process_single_folder(input_root, output_root)

    # Recursive mode: traverse directories and process those with supported files or raw-responses
    results: dict[str, Path | None] = {}
    # Always include the root itself
    candidate_dirs = {input_root}
    candidate_dirs.update(p for p in input_root.rglob('*') if p.is_dir())

    for folder in sorted(candidate_dirs):
        # Determine if folder should be processed: contains supported files or is a raw-responses folder
        has_supported = any(folder.glob(f'*{suf}') for suf in SUPPORTED_SUFFIXES)
        is_raw = folder.name.startswith(raw_prefix)
        if not has_supported and not is_raw:
            continue
        rel = folder.relative_to(input_root) if folder != input_root else Path()
        out_folder = output_root / rel if rel != Path() else output_root
        out_folder.mkdir(parents=True, exist_ok=True)
        csvp = process_single_folder(folder, out_folder)
        results[str(rel)] = csvp

    return results
