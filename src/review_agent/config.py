"""Configuration file for Literature Processing Tool

Modify these settings according to your needs
"""

# Output Configuration
OUTPUT_CONFIG = {
    'output_folder': 'output',  # Default output folder
    'log_folder': 'output/logs',  # Log files folder
    'csv_filename_prefix': 'review',
    'raw_responses_filename_prefix': 'raw_responses',
    'timestamp_format': '%Y%m%d_%H%M',
}

MODEL_TYPES = ['ollama']  # Supported model types
OLLAMA_MODELS = ['qwen3:30b-a3b', 'gpt-oss:20b', 'gemma3:27b']

ollama_context_length = 64000  # 64k context

AI_MODELS_IN_USE = {
    # 'summary':{'type':'ollama','model_name':"qwen3:30b-a3b", 'options':{'temperature':0.1},'context_length':ollama_context_length},
    'summary': {
        'type': 'ollama',
        'model_name': 'gpt-oss:20b',
        'options': {'temperature': 0.1},
        'context_length': ollama_context_length,
    },
    'sort_csv': {
        'type': 'ollama',
        'model_name': 'gpt-oss:20b',
        'options': {'temperature': 0.1},
        'think': 'medium',
        'context_length': ollama_context_length,
    },
}

PROMPTS_IN_USE = {
    'summary': """
Analyze the following academic paper and extract key information. Provide a comprehensive summary that includes:

- **Title**: Full title of the paper
- **Author(s)**: List all authors, separated by commas
- **Year**: Year of publication
- **Source Type**: Journal article, conference paper, patent, technical report, etc.
- **Source Name/Identifier**: Journal name, conference name, patent number, etc.
- **Affiliation**: Institution, university, company, or research lab
- **One-Sentence Summary**: Core contribution in one concise sentence
- **Abstract**: Research objectives, methods, and key findings
- **Keywords**: 3-5 relevant key terms
- **Innovations/Key Contributions**: Novel aspects and unique features
- **Main Methodology**: Primary approach, modeling technique, or experimental setup
- **Conclusions**: Main conclusions and significance
- **Motor Type / Topology**: Type of electric motor and topological structure (if applicable, otherwise "N/A")
- **Key Performance Metrics**: Critical technical indicators (if applicable, otherwise "N/A"; preserve any key numbers or quantitative results)

Please provide the information in a clear, structured format using Markdown headers for each section.
Do NOT output in CSV format - just provide well-structured text that can be parsed later.

/think
""",
    'sort_csv': """
Convert the provided raw data from multiple papers into a single, well-formatted CSV file.

**CSV Format Requirements:**
1. First line MUST be the header row with these exact column names (in quotes):
   "Title","Author(s)","Year","Source Type","Source Name/Identifier","Affiliation","One-Sentence Summary","Abstract","Keywords","Innovations/Key Contributions","Main Methodology","Conclusions","Motor Type / Topology","Key Performance Metrics","File Name","File Path","Character Count","Processing Time (s)","Status"

2. Each subsequent line represents one paper's data
3. Each field MUST be wrapped in double quotes
4. If a field contains double quotes, escape them by doubling ("")
5. If a field contains commas or newlines, keep them inside the quotes
6. Use commas to separate fields
7. Each row should be on a single line (no line breaks within a row)
8. If information is missing, use "N/A"
9. For "Key Performance Metrics", preserve any key numbers or quantitative results

**Important:**
- Output ONLY the CSV content
- Do NOT include markdown code blocks (no ```csv)
- Do NOT include any explanatory text
- Start directly with the header row
- Extract information from each "=== File" section in the raw data
- Each file should become one row in the CSV

/no_think
""",
    'system': 'You are a large language model for academic use. Keep responses concise, structured, and citation-aware.',
}
