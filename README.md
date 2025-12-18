# ReviewAgent — Batch Literature Review and Structured CSV Export

ReviewAgent is a lightweight batch-processing tool for documents. It reads PDF/HTML/TXT/Markdown sources, generates per-file structured summaries using local or cloud LLMs, archives raw Markdown responses, and consolidates everything into a clean CSV—ready for analysis or import into Excel/Notion/BI tools.

Use cases:
- Academic literature reviews
- Information extraction from industry reports or car model articles


## Core Features

- Batch text extraction and cleanup
	- Supports .pdf / .html / .htm / .txt / .md
	- For PDF/HTML, also emits a cleaned text copy for auditing
- Per-file AI summarization
	- Choose local Ollama models or online models like Gemini (via LiteLLM)
	- Stores one Markdown response per document for traceability
- Unified CSV consolidation
	- Aggregates all raw responses to a single CSV with consistent columns and escaping rules
- Recursive processing
	- Optionally process subfolders; output structure mirrors the input
- Logging and provenance
	- Logs and raw artifacts are saved under output/, making the pipeline auditable

## Installation and Requirements
- Python 3.13+
- Commands shown for Windows cmd
- Choose one option: pip or uv

### Option A — pip

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install .
```

Dev install (editable) and extras:

```cmd
pip install -e .[dev,crawl]
python -m pre-commit install
python -m pre-commit autoupdate
```

### Option B — uv

If uv is not installed:

```cmd
pipx install uv
```

Create venv and install:

```cmd
uv venv .venv
.venv\Scripts\activate
uv pip install .
```

Dev install (editable) and extras:

```cmd
uv pip install -e .[dev,crawl]
uv run pre-commit install
uv run pre-commit autoupdate
```


## Models and API Keys

The project uses LiteLLM to talk to multiple providers. Two are configured out of the box:

- Local Ollama (examples: gpt-oss:20b / gemma3:27b / qwen3:30b-a3b)
	- Install and run Ollama on Windows
	- Pull model(s) ahead of time, e.g.:

		```cmd
		ollama pull gpt-oss:20b
		```

	- Optional env: OLLAMA_HOST (for remote/custom ports)

- Google Gemini (gemini-2.5-flash / flash-lite / pro, etc.)
	- Provide GEMINI_API_KEY via .env or environment variables

The app loads settings from .env (dotenv). Example:

```env
GEMINI_API_KEY=your_api_key
```


## Quick Start (Interactive CLI)

After installation, run:

```cmd
review
```

or:

```cmd
python -m review_agent
```

Then answer the prompts:
1) Input folder containing documents (default: ./input)
2) Output folder (default: ./output)
3) Process subfolders recursively? (y/N)
4) Select review type (0=literature_review, 1=automotive_article) [default: 1]

Outputs include:
- Raw AI responses per file (Markdown): output/raw_responses-YYYYMMDD_HHMM/
- Cleaned text for PDF/HTML: output/extracted_texts-YYYYMMDD_HHMM/
- Consolidated CSV: output/review-YYYYMMDD_HHMM.csv
- Logs: output/logs/YYYYMMDD_HH.log


## Important: Task Type and Models

There are two built-in review types:

- 0 = `literature_review`
	- Default model preset: local Ollama (gpt-oss:20b)
	- CSV columns include:
		- Title / Author(s) / Year / Source Type / Source Name/Identifier / Affiliation
		- One-Sentence Summary / Abstract / Keywords
		- Innovations/Key Contributions / Main Methodology / Conclusions
		- Motor Type / Topology / Key Performance Metrics

- 1 = `automotive_article`
	- Default model preset: Gemini (gemini-2.5-flash)
	- CSV columns include (excerpt):
		- Model Name / Body Type / Powertrain / Engine Type / Architecture
		- Total Power / Specific Output / Electric Motor / Electric Only Max Speed
		- Fuel Consumption (WLTP) / CO2 Emissions (WLTP) / Electric Consumption
		- Weight-to-Power Ratio / Year / Innovations / Other Key Performance Metrics

How to select the review type:

- Interactive CLI: you’ll be prompted to choose it (default 1).
- Programmatic: pass `review_type_id` to `review2csv` (accepts int or name):

	```python
	from review_agent.review import review2csv

	# 0 or 'literature_review'; 1 or 'automotive_article'
	review2csv('./input', './output', review_type_id=0)
	# or
	review2csv('./input', './output', review_type_id='automotive_article')
	```

- Global default: you can still set the default in `src/review_agent/config.py`:

	```python
	REVIEW_TYPE_ID = 1  # default fallback if not specified at runtime
	```

You can customize model presets and parameters in `src/review_agent/ai_model.py` and the per-type selections in `src/review_agent/config.py`.


## Input and Output

- Input (default ./input)
	- Supports .txt / .md / .pdf / .html / .htm
	- Place a batch in one folder; optionally organize topics into subfolders and enable recursion

- Output (default ./output)
	- raw_responses-YYYYMMDD_HHMM/: raw Markdown per document
	- extracted_texts-YYYYMMDD_HHMM/: cleaned text files for PDF/HTML
	- review-YYYYMMDD_HHMM.csv: consolidated structured CSV
	- logs/: hourly rotated logs

Timestamp naming is controlled by OUTPUT_CONFIG in `src/review_agent/review.py`.


## How the CLI Works

The `review` command will:
1) Discover all supported files in the input folder
2) Extract text (`extract_text.py`); PDF/HTML also save cleaned text
3) Summarize each file using the selected model and prompts (`ai_chat_response.py`, `config.py`)
4) Ask the model to convert all raw Markdown responses into a single CSV with strict field order and escaping rules

Reusing existing raw responses (skip re-summarization):
- Point the input folder to an existing `raw_responses-YYYYMMDD_HHMM/` directory
- The pipeline will bypass summarization and only build the CSV


## Context handling and chunking

To make the CSV consolidation robust on large batches, the pipeline uses conservative context budgeting and chunking:

- Per-file summarization
	- Each file’s text is truncated to about 75% of the selected model’s context length before calling the model.

- CSV consolidation over aggregated responses
	- The aggregated raw responses are split using a file-level delimiter defined as `FILE_DELIMITER` in `src/review_agent/review.py`.
	- Chunking packs multiple md files into one chunk when possible, but never splits a single md file across mixed chunks.
	- If one md file alone exceeds the limit, it is split by lines into dedicated sub-chunks; these sub-chunks are not mixed with other files.
	- Only the first CSV header is kept; subsequent chunk outputs with an identical header have that header removed before merging.

Notes:
- The effective chunk size during CSV consolidation also uses ~75% of the model’s context length as a safety margin.
- You can inspect timestamps, output file names, and the delimiter constant in `src/review_agent/review.py`.


## Code Map (Short)

- `src/review_agent/__main__.py`: interactive CLI entry
- `src/review_agent/review.py`: main pipeline (single folder, recursive mode, CSV generation)
- `src/review_agent/extract_text.py`: text extraction/cleanup for PDF/HTML/TXT/MD
- `src/review_agent/ai_chat_response.py`: LiteLLM wrapper to call models

## CSV → Markdown helper (csv2md)

Convert the exported CSV into a Markdown table file (by default, a same-named .md is created):

```cmd
csv2md -i output\review-20251016_1110.csv -c "Title,Year,Source Type,One-Sentence Summary"
```

Optional flags:
- `-o/--output` specify the output .md file path
- `-c/--columns` choose columns to include, comma-separated
- `--sort-by` / `--desc` sorting
- `--max-rows` limit the number of output rows

- `src/review_agent/ai_model.py`: model presets and context lengths
- `src/review_agent/config.py`: task type, prompts/columns, and selected models

Runtime configuration helper:
- `get_review_config(review_type_id)`: builds the model/prompt/columns for the chosen review type
- `src/review_agent/logger.py`: unified console and file logging
- `examples/`: sample scripts (including simple crawlers)


## Example: Minimal End-to-End

1) Put some .pdf/.html/.txt/.md files into `input/`
2) If using Ollama, pull the model first:

```cmd
ollama pull gpt-oss:20b
```

3) If using Gemini, set env or .env:

```env
GEMINI_API_KEY=your_api_key
```

4) Run:

```cmd
review
```

5) Inspect outputs in `output/`


## FAQ

- CSV is wrapped in ```csv fences?
	- We strip code fences in the CSV step; update to the latest version if needed
- Context length exceeded?
	- Per-file input is truncated at ~75% of the model’s context; the CSV step also checks aggregate length
- PDF extraction empty or garbled?
	- Depends on the PDF structure; consider OCR or converting to text first
- `review` not found on Windows?
	- Ensure `pip install .` succeeded, or run `python -m review_agent`


## Development

Formatting/quality tools: Ruff, pre-commit, commitizen (see `pyproject.toml`).

```cmd
pip install -e .[dev]
ruff check --fix
```

Contributions are welcome. You can extend prompts/columns in `config.py` to adapt to new extraction scenarios.


## License

This project relies on open-source dependencies and local/cloud models; use it in compliance with respective licenses and API terms.
