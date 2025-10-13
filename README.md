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
	- Provide GOOGLE_API_KEY via .env or environment variables

The app loads settings from .env (dotenv). Example:

```env
GOOGLE_API_KEY=your_api_key
OLLAMA_HOST=http://127.0.0.1:11434
# LITELLM_LOG=INFO  # enable LiteLLM debug logs if needed
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


## Code Map (Short)

- `src/review_agent/__main__.py`: interactive CLI entry
- `src/review_agent/review.py`: main pipeline (single folder, recursive mode, CSV generation)
- `src/review_agent/extract_text.py`: text extraction/cleanup for PDF/HTML/TXT/MD
- `src/review_agent/ai_chat_response.py`: LiteLLM wrapper to call models
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
GOOGLE_API_KEY=your_api_key
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

# ReviewAgent —— 学术/行业文献批量评审与结构化导出工具

一个简单好用的批处理工具：批量读取 PDF/HTML/TXT/Markdown，调用本地或云端大模型生成每篇文献的要点摘要（原始 Markdown 存档），再统一整理为结构化 CSV 表格，方便后续分析与引用管理。

适用场景：
- 学术文献综述（Literature Review）
- 行业资料/车型资料信息抽取与对比（Automotive Article）


## 核心功能

- 批量文本抽取与清洗
	- 支持 .pdf / .html / .htm / .txt / .md
	- 对 PDF/HTML 自动额外输出清洗后的文本副本，便于复核
- AI 摘要与要点提炼（逐文件）
	- 可选本地 Ollama 模型或 Gemini 云模型（通过 LiteLLM 统一调用）
	- 产出每篇文献的结构化要点（Markdown）并按文件单独存档
- 统一汇总为 CSV
	- 将所有原始摘要结果二次整理为一份 CSV，便于筛选、排序、导入到 Excel/Notion/数据仓库
- 递归处理
	- 可选择处理子目录；输出目录结构与输入保持一致
- 日志与可追溯性
	- 输出目录自动保存日志、原始响应与中间产物，便于审计与反查


## 安装与环境要求

- Python 3.13 或更高版本
- Windows 下命令行示例均以 cmd 为准

推荐使用虚拟环境：

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
```

安装本项目（普通安装）：

```cmd
pip install .
```

开发安装（可编辑）及可选依赖（爬取示例需要 requests/lxml）：

```cmd
pip install -e .[dev,crawl]
```


## 模型与密钥配置

本项目通过 LiteLLM 适配多种模型，已内置两类供应商：

- 本地 Ollama（默认示例：gpt-oss:20b / gemma3:27b / qwen3:30b-a3b）
	- 需要本机安装并运行 Ollama（参考官方文档安装 Windows 版本）
	- 模型需提前拉取，例如：

		```cmd
		ollama pull gpt-oss:20b
		```

	- 可选环境变量：OLLAMA_HOST（如使用远程/自定义端口）

- Google Gemini（gemini-2.5-flash / flash-lite / pro 等）
	- 需在 .env 或环境变量中配置 GOOGLE_API_KEY

项目会自动读取 .env 文件（dotenv），示例：

```env
GOOGLE_API_KEY=your_api_key
OLLAMA_HOST=http://127.0.0.1:11434
# LITELLM_LOG=INFO  # 如需调试 LiteLLM 日志
```


## 快速开始（交互式 CLI）

安装完成后，命令行直接运行：

```cmd
review
```

或使用模块运行：

```cmd
python -m review_agent
```

按照提示输入：
1) 输入包含文献的目录（默认 ./input）
2) 选择输出目录（默认 ./output）
3) 是否递归处理子目录（y/N）

运行完成后，将生成：
- 原始 AI 响应（每篇一份 Markdown）：output/raw_responses-YYYYMMDD_HHMM/
- 可选的抽取文本（针对 PDF/HTML）：output/extracted_texts-YYYYMMDD_HHMM/
- 汇总 CSV：output/review-YYYYMMDD_HHMM.csv
- 日志：output/logs/YYYYMMDD_HH.log


## 使用前的一个重要设置：任务类型与模型

内置两种任务类型（review type）：

- 0 = `literature_review`
	- 默认使用本地 Ollama（gpt-oss:20b）
	- CSV 字段包括：
		- Title / Author(s) / Year / Source Type / Source Name/Identifier / Affiliation
		- One-Sentence Summary / Abstract / Keywords
		- Innovations/Key Contributions / Main Methodology / Conclusions
		- Motor Type / Topology / Key Performance Metrics

- 1 = `automotive_article`
	- 默认使用 Gemini（gemini-2.5-flash）
	- CSV 字段包括（节选）：
		- Model Name / Body Type / Powertrain / Engine Type / Architecture
		- Total Power / Specific Output / Electric Motor / Electric Only Max Speed
		- Fuel Consumption (WLTP) / CO2 Emissions (WLTP) / Electric Consumption
		- Weight-to-Power Ratio / Year / Innovations / Other Key Performance Metrics

选择方式：

- 交互式 CLI：运行时会询问（默认 1）。
- 代码中调用：向 `review2csv` 传入 `review_type_id`（可为整数或名称）：

	```python
	from review_agent.review import review2csv

	# 0 或 'literature_review'；1 或 'automotive_article'
	review2csv('./input', './output', review_type_id=0)
	# 或
	review2csv('./input', './output', review_type_id='automotive_article')
	```

- 全局默认值：仍可在 `src/review_agent/config.py` 中设置：

	```python
	REVIEW_TYPE_ID = 1  # 如未在运行时指定，则使用此默认
	```

模型清单与参数可在 `src/review_agent/ai_model.py` 和 `src/review_agent/config.py` 中调整。


## 文件输入与输出说明

- 输入（默认 ./input）：
	- 支持 .txt / .md / .pdf / .html / .htm
	- 建议将同一批次的文献放在一个目录下；可按主题分子目录，开启递归处理

- 输出（默认 ./output）：
	- raw_responses-YYYYMMDD_HHMM/：每篇文献一份 .md 原始响应
	- extracted_texts-YYYYMMDD_HHMM/：针对 PDF/HTML 保存的清洗文本（.txt）
	- review-YYYYMMDD_HHMM.csv：最终汇总的结构化表格
	- logs/：按小时滚动的日志文件

命名中的时间戳来自配置：`src/review_agent/review.py` 中 OUTPUT_CONFIG。


## 命令行交互细节

`review` 命令会依次：
1) 读取输入目录下的所有支持文件
2) 先用 `extract_text.py` 抽取文本（PDF/HTML 会额外保存清洗文本）
3) 使用 `config.py` 指定的模型与提示词对每个文件生成要点摘要（`ai_chat_response.py`）
4) 将所有原始响应再次送入模型生成统一 CSV（确保字段顺序与转义规则）

如需复用现有的原始响应（无需重新摘要）：
- 将输入目录指向某个 `raw_responses-YYYYMMDD_HHMM/` 文件夹
- 系统会跳过摘要步骤，直接整理为 CSV


## 代码结构一览（简）

- `src/review_agent/__main__.py`：CLI 入口（交互式）
- `src/review_agent/review.py`：核心流水线（单目录处理、递归处理、汇总 CSV）
- `src/review_agent/extract_text.py`：PDF/HTML/TXT/MD 文本抽取与清洗
- `src/review_agent/ai_chat_response.py`：通过 LiteLLM 调用模型并返回文本
- `src/review_agent/ai_model.py`：内置模型清单与上下文长度设置
- `src/review_agent/config.py`：任务类型、提示词与列名、选用模型
- `src/review_agent/logger.py`：统一日志到控制台与文件
- `examples/`：示例脚本（含简单爬取样例）


## 示例：最小可用流程

1) 准备数据：将若干 .pdf/.html/.txt/.md 放入 `input/` 目录
2) 如果用 Ollama，本地拉取所需模型（示例）：

```cmd
ollama pull gpt-oss:20b
```

3) 若用 Gemini，配置环境变量或 .env：

```env
GOOGLE_API_KEY=your_api_key
```

4) 运行：

```cmd
review
```

5) 在 `output/` 查看生成的 CSV、原始响应与日志


## 常见问题（FAQ）

- 生成的 CSV 被代码块包裹了 ```csv ？
	- 我们在整理阶段做了剥离处理；如仍出现，请更新到最新版本并检查模型输出
- 内容太长导致上下文溢出？
	- 单篇摘要会在接近模型上下文 3/4 时自动截断；合并 CSV 前也会检查长度
- PDF 抽取文本为空或乱码？
	- 取决于 PDF 结构，可尝试先用 OCR 或转为文本再处理
- Windows 下不能识别 `review` 命令？
	- 确认已 `pip install .` 成功，或使用 `python -m review_agent`


## 开发与贡献

格式/质量工具：Ruff、pre-commit、commitizen（见 `pyproject.toml`）

```cmd
pip install -e .[dev]
ruff check --fix
```

欢迎提交 Issue/PR，或根据自身任务在 `config.py` 中扩展列名与提示词，以适配新的信息抽取场景。


## 许可证

本项目采用开源依赖与本地/云端模型，请在遵守相关许可证和 API 条款的前提下使用。
