"""Configuration for review types with runtime selection support.

You can select the review type at runtime via `get_review_config` or pass
`review_type_id` into `review2csv`/CLI. Defaults preserved for backward compatibility.
"""

from .ai_model import GEMINI_MODELS, OLLAMA_MODELS

# Public constants: available review types and default selection
REVIEW_TYPE_NAMES = ['literature_review', 'automotive_article']
REVIEW_TYPE_ID = 0  # Default; can be overridden at runtime


def get_review_config(review_type_id: int | str | None = None) -> dict:
    """Build and return configuration for the given review type.

    Args:
        review_type_id: Either the index (int) into REVIEW_TYPE_NAMES, the
            name (str) from REVIEW_TYPE_NAMES, or None to use the default REVIEW_TYPE_ID.

    Returns:
        Dict with keys: 'review_type', 'AI_MODELS_IN_USE', 'PROMPTS_IN_USE',
        'csv_column_dict', 'extra_column_keys'.

    """
    # Resolve review type string
    if review_type_id is None:
        review_type = REVIEW_TYPE_NAMES[REVIEW_TYPE_ID]
    elif isinstance(review_type_id, int):
        review_type = REVIEW_TYPE_NAMES[review_type_id]
    else:
        # accept exact string; raise if invalid
        if review_type_id not in REVIEW_TYPE_NAMES:
            msg = f'Unknown review_type_id: {review_type_id}. Valid: {REVIEW_TYPE_NAMES}'
            raise ValueError(msg)
        review_type = review_type_id

    # Build per-type model selection and columns
    if review_type == 'literature_review':
        ai_models_in_use = {
            # 'summary': GEMINI_MODELS['gemini-2.5-flash-lite'],
            # 'sort_csv': GEMINI_MODELS['gemini-2.5-flash-lite'],
            'summary': OLLAMA_MODELS['gpt-oss:20b'],
            'sort_csv': OLLAMA_MODELS['gpt-oss:20b'],
        }
        csv_column_dict = {
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
        }
    else:  # automotive_article
        ai_models_in_use = {
            # 'summary': GEMINI_MODELS['gemini-2.5-flash-lite'],'sort_csv': GEMINI_MODELS['gemini-2.5-flash-lite'],
            'summary': GEMINI_MODELS['gemini-2.5-flash'],
            'sort_csv': GEMINI_MODELS['gemini-2.5-flash'],
            # 'summary': OLLAMA_MODELS['gpt-oss:20b'], 'sort_csv': OLLAMA_MODELS['gpt-oss:20b']
        }
        csv_column_dict = {
            'Model Name': 'Full Name of the vehicle model',
            'Body Type': 'Vehicle body classification (sedan, SUV, coupe, convertible, etc.)',
            # 'Seating Capacity/Roof Type': 'Number of seats and roof configuration',
            'Powertrain': 'Engine type, electric, hybrid, etc.',
            'Engine Type': 'Internal combustion engine configuration and specifications',
            'Architecture': 'Vehicle platform and structural design approach',
            'Total Power': 'Combined power output from all power sources',
            'Specific Output': 'Power-to-displacement or power-to-weight ratio',
            'Electric Motor': 'Type, configuration, and specifications of electric motor(s)',
            'Electric Only Max Speed': 'Maximum speed in pure electric mode',
            'Fuel Consumption (WLTP)': 'Fuel efficiency measured under WLTP testing cycle',
            'CO2 Emissions (WLTP)': 'Carbon dioxide emissions under WLTP testing cycle',
            'Electric Consumption': 'Energy consumption in electric mode',
            # 'Wheelbase': 'Distance between front and rear axles',
            # 'Torsional Rigidity/Beam Stiffness': 'Structural stiffness and chassis rigidity metrics',
            # 'Active Aero Device/Aero Function': 'Active aerodynamic systems and their functions',
            # 'Front Aero Feature': 'Specific aerodynamic features at the front',
            # 'Downforce Metrics': 'Active downforce increase, maximum downforce, and low-drag downforce values',
            'Weight-to-Power Ratio': 'Power-to-weight ratio calculation',
            # 'Weight Reduction/Dampers': 'Lightweighting measures and suspension damper specifications',
            'Acceleration Performance': 'Lateral and longitudinal acceleration capabilities',
            # 'Gear Shifting/Braking': 'Transmission shifting characteristics and braking system performance',
            'Year': 'Year of Release',
            'Innovations': 'Novel aspects and unique features',
            'Other Key Performance Metrics': 'Critical technical indicators (if applicable, otherwise "N/A"; preserve any key numbers or quantitative results)',
        }

    extra_column_keys = [
        'File Name',
        #  'File Path',
        'Character Count',
        'Processing Time (s)',
        'Status',
    ]

    prompts_in_use = {
        'system': 'You are a large language model for academic use. Keep responses concise, structured, and citation-aware.',
        'summary': f"""
        Analyze the following academic paper and extract key information. Provide a comprehensive summary that includes:
        {'\n'.join(csv_column_dict.values())}

        Please provide the information in a clear, structured format using Markdown headers for each section.
        Do NOT output in CSV format - just provide well-structured text that can be parsed later.

        /think
        """,
        'sort_csv': f"""
        Convert the provided raw data from multiple sources into a single, well-formatted CSV file.

        **CSV Format Requirements:**
        1. First line MUST be the header row with these exact column names (in quotes):
        {', '.join(list(csv_column_dict.keys()) + extra_column_keys)}

        2. Each subsequent line represents one source's data
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
    }

    return {
        'review_type': review_type,
        'AI_MODELS_IN_USE': ai_models_in_use,
        'PROMPTS_IN_USE': prompts_in_use,
        'csv_column_dict': csv_column_dict,
        'extra_column_keys': extra_column_keys,
    }


# Backward-compatible exports using the default REVIEW_TYPE_ID
_defaults = get_review_config(REVIEW_TYPE_ID)
AI_MODELS_IN_USE = _defaults['AI_MODELS_IN_USE']
PROMPTS_IN_USE = _defaults['PROMPTS_IN_USE']
