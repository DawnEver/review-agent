from review_agent.config import build_model, build_runtime_config
from review_agent.review import review2csv

OLLAMA_MODELS = {
    'gpt-oss:20b': build_model('ollama', 'gpt-oss:20b', 64000, think='medium'),
}

REVIEW_CONFIG = {
    'ai_models': {
        'summary': OLLAMA_MODELS['gpt-oss:20b'],
        'sort_csv': OLLAMA_MODELS['gpt-oss:20b'],
    },
    'csv_columns': {
        'Title': 'Full title of the paper',
        'Author(s)': 'List all authors, separated by commas',
        'Year': 'Year of publication',
        'Source Type': 'Journal article, conference paper, patent, technical report, etc.',
        'Source Name/Identifier': 'Journal name, conference name, patent number, etc.',
        'Affiliation': 'Institution, university, company, or research lab',
        'One-Sentence Summary': 'Core contribution in one concise sentence',
        'Abstract': 'Research objectives, methods, and key findings',
        'Keywords': '3-5 relevant key terms',
        'Innovations/Key Contributions': 'Novel aspects and unique features',
        'Main Methodology': 'Primary approach, modeling technique, or experimental setup',
        'Conclusions': 'Main conclusions and significance',
        'Motor Type / Topology': 'Type of electric motor and topological structure (if applicable, otherwise "N/A")',
        'Key Performance Metrics': 'Critical technical indicators (if applicable, otherwise "N/A"; preserve any key numbers or quantitative results)',
    },
}

RUNTIME_CONFIG = build_runtime_config(REVIEW_CONFIG)

review2csv(
    input_folder_path='./input',
    runtime_config=RUNTIME_CONFIG,
)
