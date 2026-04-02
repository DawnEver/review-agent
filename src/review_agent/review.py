"""Batch review utilities.

This module provides functions to:
    * Extract text from files.
    * Generate per-paper AI summaries (raw markdown outputs stored per file).
    * Aggregate all raw responses into a single string.
    * Ask an AI model to normalize the aggregated content into a CSV table.

Entry point (CLI) asks for a folder path and produces both raw markdown responses
and a timestamped CSV summarizing the papers.
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .ai_chat_response import chat_response
from .extract_text import extract_text_from_html, extract_text_from_pdf, extract_text_from_txt
from .logger import log

# Output Configuration
OUTPUT_CONFIG = {
    'csv_filename_prefix': 'review',
    'raw_responses_filename_prefix': 'raw_responses',
    'timestamp_format': '%Y%m%d_%H%M',
}
raw_prefix = f'{OUTPUT_CONFIG["raw_responses_filename_prefix"]}-'
timestamp = datetime.now().strftime(OUTPUT_CONFIG['timestamp_format'])

# Supported input file suffixes
SUPPORTED_SUFFIXES = ('.txt', '.md', '.pdf', '.html', '.htm')

FILE_DELIMITER = '\n\n---\n\n---\n\n'  # delimiter between raw md files in combined text


def review_content(
    input_folder_path: Path,
    output_folder: Path | None = None,
    *,
    runtime_config: dict | None = None,
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
    active_config = runtime_config
    ai_models_in_use = active_config['AI_MODELS_IN_USE']
    prompts_in_use = active_config['PROMPTS_IN_USE']
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
    return FILE_DELIMITER.join(aggregated)


def organize_responses_to_csv(
    combined_responses: list | str,
    output_folder: Path | None = None,
    *,
    runtime_config: dict | None = None,
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

    active_config = runtime_config
    ai_models_in_use = active_config['AI_MODELS_IN_USE']
    prompts_in_use = active_config['PROMPTS_IN_USE']
    sort_model_dict = ai_models_in_use['sort_csv']
    # Accept both list of strings or a single string
    combined_as_text = ''.join(combined_responses) if isinstance(combined_responses, list) else str(combined_responses)

    # Helper: split text into chunks smaller than context, preserving full lines
    def _chunk_text_preserving_lines(text: str, limit: int) -> list[str]:
        chunks, current, cur_len = [], [], 0
        for ln in text.splitlines():
            ln_len = len(ln) + 1  # reinserting newline on join
            if ln_len > limit:
                msg = 'A single line exceeds the model context limit; cannot chunk without splitting lines.'
                raise RuntimeError(msg)
            if current and cur_len + ln_len > limit:
                chunks.append('\n'.join(current))
                current, cur_len = [ln], ln_len
            else:
                current.append(ln)
                cur_len += ln_len
        if current:
            chunks.append('\n'.join(current))
        return chunks

    # Helper: first try to chunk by md_file units (joined by the known delimiter),
    # so that we do not split inside a single md file. If a unit itself exceeds
    # the limit, we fall back to line-preserving chunking for that unit only.
    def _chunk_by_mdfile_units(text: str, limit: int, delimiter: str = FILE_DELIMITER) -> list[str]:
        if delimiter not in text:
            # No clear unit boundary; fall back to line-based chunking
            return _chunk_text_preserving_lines(text, limit)

        units = text.split(delimiter)
        chunks, parts, cur_len = [], [], 0
        for i, unit in enumerate(units):
            add_len = len(unit) + (len(delimiter) if parts else 0)
            if cur_len + add_len > limit:
                if parts:
                    chunks.append(delimiter.join(parts))
                    parts, cur_len = [], 0
                if len(unit) <= limit:
                    parts, cur_len = [unit], len(unit)
                else:
                    log(
                        'Single md_file exceeds context; splitting within file',
                        level='warning',
                        unit_index=i,
                        unit_chars=len(unit),
                        limit=limit,
                    )
                    chunks.extend(_chunk_text_preserving_lines(unit, limit))
            else:
                parts.append(unit)
                cur_len += add_len
        if parts:
            chunks.append(delimiter.join(parts))
        return chunks

    # Helper: normalize model CSV output to non-empty lines without fences
    def _normalize_csv_lines(text: str) -> list[str]:
        if text.startswith('```'):
            nl = text.find('\n')
            text = text[nl + 1 :] if nl != -1 else ''
        return [ln for ln in text.removesuffix('```').strip().splitlines() if ln.strip()]

    # Use a safety margin similar to summarization to avoid boundary issues
    max_chunk = sort_model_dict['context_length'] * 3 // 4
    if max_chunk <= 0:
        max_chunk = 2000  # fallback sane default

    # Create chunks if needed (prefer preserving md_file boundaries)
    if len(combined_as_text) > max_chunk:
        chunks = _chunk_by_mdfile_units(combined_as_text, max_chunk)
        log(
            'Combined responses exceed context; chunking (preserve md_file boundaries)',
            total_chars=len(combined_as_text),
            chunks=len(chunks),
            limit=max_chunk,
        )
    else:
        chunks = [combined_as_text]

    # Process each chunk and merge CSVs (keep only the first header)
    header_line: str | None = None
    merged_lines: list[str] = []

    for idx, chunk in enumerate(chunks, start=1):
        log(
            'Requesting CSV organization from model (chunk)',
            chunk_index=idx,
            chunks_total=len(chunks),
            chunk_chars=len(chunk),
        )
        messages = [
            {'role': 'system', 'content': prompts_in_use['system']},
            {'role': 'user', 'content': f'{prompts_in_use["sort_csv"]}\n\nRaw Data:\n{chunk}'},
        ]
        csv_content = chat_response(model_dict=sort_model_dict, messages=messages)
        lines = _normalize_csv_lines(csv_content)
        if not lines:
            log('Empty CSV content from chunk', level='warning', chunk_index=idx)
            continue
        if header_line is None:
            header_line = lines[0]
            merged_lines.extend(lines)
        else:
            # If the first line equals the previously captured header, skip it
            start_idx = 1 if lines[0] == header_line else 0
            merged_lines.extend(lines[start_idx:])

    # Write merged CSV
    final_csv = '\n'.join(merged_lines).strip()
    with Path.open(csv_file, 'w', encoding='utf-8-sig') as f:
        f.write(final_csv)
    log('CSV file written', path=str(csv_file), bytes=csv_file.stat().st_size)
    return csv_file


def process_single_folder(folder: Path, out_folder: Path, runtime_config: dict) -> Path | None:
    # If folder itself is a raw-responses folder, reuse MDs
    if folder.is_dir() and folder.name.startswith(raw_prefix):
        log('Reusing existing raw responses folder', folder=str(folder))
        md_files = sorted(folder.glob('*.md'))
        if not md_files:
            log('No markdown files found in raw responses folder', level='warning', folder=str(folder))
            return None
        combined_local = FILE_DELIMITER.join(Path(md_file).read_text(encoding='utf-8') for md_file in md_files)
    else:
        combined_local = review_content(
            folder,
            out_folder,
            runtime_config=runtime_config,
        )
        if not combined_local:
            log('No summaries produced; skipping CSV', level='warning', folder=str(folder))
            return None
    csv_path_local = organize_responses_to_csv(
        combined_local,
        out_folder,
        runtime_config=runtime_config,
    )
    if csv_path_local:
        log('Pipeline success', csv=str(csv_path_local), folder=str(folder))
    else:
        log('Pipeline finished without CSV output', level='warning', folder=str(folder))
    return csv_path_local


def review2csv(
    input_folder_path: Path,
    runtime_config: dict,
    output_folder: Path | None = None,
    recursive: bool = False,
    func_process_single_folder: Callable[[Path, Path, dict], Path | None] = process_single_folder,
):
    """End-to-end pipeline: summarize files then produce CSV.

    Args:
        input_folder_path: Root folder to process.
        runtime_config: Normalized runtime config built via build_runtime_config(...).
        output_folder: Root output folder; when recursive=True, the structure under this root mirrors input.
        recursive: If True, process all subfolders and mirror output structure.
        func_process_single_folder: Function to process a single folder; default is the internal process_single_folder. This is parameterized for easier DIY processing.

    Returns:
        - If recursive is False: Path to the generated CSV or None.
        - If recursive is True: Dict mapping each processed relative folder to its CSV Path (or None if failed).

    """
    input_root = Path(input_folder_path)
    output_root = Path(output_folder) if output_folder else Path('output')

    if runtime_config is None:
        msg = 'runtime_config cannot be None. Please build it via build_runtime_config(...) first.'
        raise ValueError(msg)

    if not recursive:
        return func_process_single_folder(input_root, output_root, runtime_config)

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
        csvp = func_process_single_folder(folder, out_folder, runtime_config)
        results[str(rel)] = csvp

    return results
