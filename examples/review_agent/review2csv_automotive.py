from review_agent.config import build_model, build_runtime_config
from review_agent.review import review2csv

OLLAMA_MODELS = {
    'gpt-oss:20b': build_model('ollama', 'gpt-oss:20b', 64000, think='medium'),
}
GEMINI_MODELS = {
    'gemini-2.5-flash': build_model('gemini', 'gemini-2.5-flash', 960000, think='medium'),
}

REVIEW_CONFIG = {
    'ai_models': {
        'summary': GEMINI_MODELS['gemini-2.5-flash'],
        'sort_csv': GEMINI_MODELS['gemini-2.5-flash'],
        # Optional Ollama fallback:
        # 'summary': OLLAMA_MODELS['gpt-oss:20b'],
        # 'sort_csv': OLLAMA_MODELS['gpt-oss:20b'],
    },
    'csv_columns': {
        'Model Name': 'Full Name of the vehicle model',
        'Body Type': 'Vehicle body classification (sedan, SUV, coupe, convertible, etc.)',
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
        'Weight-to-Power Ratio': 'Power-to-weight ratio calculation',
        'Acceleration Performance': 'Lateral and longitudinal acceleration capabilities',
        'Year': 'Year of Release',
        'Innovations': 'Novel aspects and unique features',
        'Other Key Performance Metrics': 'Critical technical indicators (if applicable, otherwise "N/A"; preserve any key numbers or quantitative results)',
    },
}


RUNTIME_CONFIG = build_runtime_config(REVIEW_CONFIG)

review2csv(
    input_folder_path='./input',
    # input_folder_path = r'output/raw_responses-20251016_1248'
    runtime_config=RUNTIME_CONFIG,
)
