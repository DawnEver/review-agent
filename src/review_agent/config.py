"""Minimal fallback configuration.

Most user-facing, large configuration blocks are moved to:
examples/review_agent/review2csv_literature.py
examples/review_agent/review2csv_automotive.py
"""

__all__ = ['build_model', 'build_runtime_config']


def build_model(provider: str, model_name: str, context_length: int, think: str | None = None) -> dict:
    model = {
        'provider': provider,
        'model_name': model_name,
        'options': {'temperature': 0.1},
        'context_length': context_length,
    }
    if think is not None:
        model['think'] = think
    return model


def build_runtime_config(
    review_config: dict,
) -> dict:
    """Build a normalized runtime config used directly by review pipeline.

    Callers pass this object explicitly to review functions. No module-level
    mutable state is used.
    """
    selected = review_config
    if not selected:
        msg = 'review_config cannot be empty'
        raise ValueError(msg)
    if not isinstance(selected, dict) or 'ai_models' not in selected or 'csv_columns' not in selected:
        msg = 'Invalid review_config. Required keys: ai_models, csv_columns'
        raise ValueError(msg)

    csv_column_dict = selected['csv_columns']

    return {
        'AI_MODELS_IN_USE': selected['ai_models'],
        'PROMPTS_IN_USE': _build_prompts(csv_column_dict),
        'csv_column_dict': csv_column_dict,
    }


def _build_prompts(csv_column_dict: dict) -> dict:
    return {
        'system': 'You are a large language model for academic use. Keep responses concise, structured, and citation-aware.',
        'summary': f"""
        Analyze the following source and extract key information. Include:
        {'\n'.join(csv_column_dict.values())}

        Provide structured Markdown headings.
        Do NOT output CSV.

        /think
        """,
        'sort_csv': f"""
        Convert raw data into CSV.
        Header columns (quoted, exact order):
        {', '.join(list(csv_column_dict.keys()))}

        Output only CSV text.
        /no_think
        """,
    }
