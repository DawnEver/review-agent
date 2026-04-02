# ReviewAgent — Batch Review and Structured CSV Export

ReviewAgent is a compact pipeline for turning mixed documents into structured CSV.
It supports local/cloud LLMs, keeps per-file raw markdown for traceability, and produces auditable outputs.

Use cases:
- Academic literature review and evidence extraction
- Batch extraction from reports, specs, and automotive pages


## Core Features

- Multi-format ingestion: `.pdf`, `.html`, `.htm`, `.txt`, `.md`
- Two-stage pipeline: per-file summary -> unified CSV
- Optional recursive processing with mirrored output folder structure
- Raw artifacts preserved for reproducibility:
	- Raw model responses (`.md`)
	- Cleaned extracted text for PDF/HTML (`.txt`)
	- Timestamped logs and final CSV


## Installation and Requirements

- Python `3.13+`
- Command examples below are for Windows `cmd`
- Choose one: `pip` or `uv`

### Option A — pip

```sh
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install .
```

Dev + crawler extras:

```sh
pip install -e .[dev,crawl]
python -m pre-commit install
python -m pre-commit autoupdate
```

### Option B — uv

If `uv` is not installed:

```sh
pipx install uv
```

Create env and install:

```sh
uv venv .venv
.venv\Scripts\activate
uv pip install .
```

Dev + crawler extras:

```sh
uv pip install -e .[dev,crawl]
uv run pre_commit install
uv run pre_commit autoupdate
```


## Models and API Keys

Model calls are routed through LiteLLM.

- Ollama (local)
	- Example model: `gpt-oss:20b`
	- Pull before use:

	```sh
	ollama pull gpt-oss:20b
	```

	- Optional: `OLLAMA_HOST`

- Gemini (cloud)
	- Provide `GEMINI_API_KEY` in environment or `.env`

```env
GEMINI_API_KEY=your_api_key
```


## Quick Start (Interactive CLI)

Current project entry is script-first (via examples). Minimal run:

```sh
python examples\review_agent\review2csv_literature.py
```

Or use the automotive schema:

```sh
python examples\review_agent\review2csv_automotive.py
```

Both scripts read from `./input` and write to `./output`.


## Important: Task Type and Models

Runtime configuration is explicit and passed to `review2csv(...)`.

- Build model configs with `build_model(...)`
- Build runtime config with `build_runtime_config(...)`
- Define extraction schema in `csv_columns`

See:
- `src/review_agent/config.py`
- `examples/review_agent/review2csv_literature.py`
- `examples/review_agent/review2csv_automotive.py`


## Input and Output

- Input (default `./input`)
	- Supported: `.txt`, `.md`, `.pdf`, `.html`, `.htm`
	- Can be a normal source folder or an existing `raw_responses-*` folder

- Output (default `./output`)
	- `raw_responses-YYYYMMDD_HHMM/`: one markdown response per source file
	- `extracted_texts-YYYYMMDD_HHMM/`: cleaned text for PDF/HTML
	- `review-YYYYMMDD_HHMM.csv`: final consolidated CSV
	- `logs/YYYYMMDD_HH.log`: runtime logs


## How the CLI Works

Pipeline behavior (`review2csv`) in order:

1) Discover supported files in the input folder
2) Extract text (`extract_text.py`)
3) Summarize each file via LiteLLM (`ai_chat_response.py`)
4) Convert aggregated raw markdown to strict CSV schema

Raw-response reuse mode:
- If input folder name starts with `raw_responses-`, the pipeline skips re-summarization and only builds CSV


## Context handling and chunking

To reduce context-overflow risk:

- Per-file summarization
	- Input text is truncated to ~75% of model context length

- CSV consolidation
	- Aggregated text is chunked by file boundary delimiter (`FILE_DELIMITER`)
	- One oversized file is split line-wise only for that file
	- Duplicate CSV headers from later chunks are removed during merge


## Code Map (Short)

- `src/review_agent/review.py`: core pipeline and recursive processing
- `src/review_agent/config.py`: model/runtime config builders and prompt templates
- `src/review_agent/extract_text.py`: PDF/HTML/TXT/MD text extraction
- `src/review_agent/ai_chat_response.py`: LiteLLM wrapper
- `src/review_agent/csv2md.py`: CSV -> Markdown utility
- `src/review_agent/logger.py`: logging helper


## CSV → Markdown helper (csv2md)

Convert an exported CSV to a markdown table:

```sh
csv2md -i output\review-20260402_1711.csv -c "Title,Year,Source Type,One-Sentence Summary"
```

Common options:
- `-o, --output`: output markdown path
- `-c, --columns`: comma-separated selected columns
- `--sort-by` + `--desc`: sorting
- `--max-rows`: row limit


## Example: Minimal End-to-End

### A) Review pipeline examples

1) Put files into `input/` (`.pdf/.html/.txt/.md`)
2) Choose one script:

```sh
python examples\review_agent\review2csv_literature.py
```

or

```sh
python examples\review_agent\review2csv_automotive.py
```

3) Check outputs in `output/`

### B) Crawler examples (`examples/crawl_agent`)

Install crawler deps first:

```sh
pip install -e .[crawl]
```

Run crawler scripts:

```sh
python examples\crawl_agent\ferrari_models.py
python examples\crawl_agent\doe_us_reports.py
python examples\crawl_agent\apc_uk_reports.py
```

Typical crawler outputs:
- downloaded pages/reports under `output/`
- metadata CSV under `output/reports_csv/`

### C) Dongchedi multi-step example

```sh
python examples\crawl_agent\dongchedi\step1_brand_ids_to_car_ids.py
python examples\crawl_agent\dongchedi\step2_car_id_to_tables.py
python examples\crawl_agent\dongchedi\step3_post_process.py
```

Note: Dongchedi scripts include some hardcoded local paths; adjust before running.


## FAQ

- Q: CSV output is wrapped in markdown fences?
	- A: Fence stripping is handled during CSV organization.

- Q: Context length exceeded?
	- A: The pipeline applies conservative truncation/chunking (~75% budget).

- Q: PDF extraction is empty/garbled?
	- A: It depends on PDF structure; OCR or pre-converted text often helps.

- Q: How to skip summarization and only build CSV?
	- A: Point input to an existing `raw_responses-*` folder.


## Development

Quality tooling is defined in `pyproject.toml` (Ruff, pre-commit, commitizen).

```sh
pip install -e .[dev]
ruff check --fix
ruff format
```

If you change extraction schema, update `csv_columns` in your example config.


## License

This project is licensed under GNU LGPL v3.0 (`LGPL-3.0-only`).
See `LICENSE` for details.
