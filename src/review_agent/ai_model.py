ollama_context_length = 64000  # 64k context
OLLAMA_MODELS = {
    'qwen3:30b-a3b': {
        'provider': 'ollama',
        'model_name': 'qwen3:30b-a3b',
        'options': {'temperature': 0.1},
        'context_length': ollama_context_length,
    },
    'gpt-oss:20b': {
        'provider': 'ollama',
        'model_name': 'gpt-oss:20b',
        'options': {'temperature': 0.1},
        'think': 'medium',
        'context_length': ollama_context_length,
    },
    'gemma3:27b': {
        'provider': 'ollama',
        'model_name': 'gemma3:27b',
        'options': {'temperature': 0.1},
        'think': 'medium',
        'context_length': ollama_context_length,
    },
}

GEMINI_MODELS = {
    'gemini-2.5-flash-lite': {
        'provider': 'gemini',
        'model_name': 'gemini-2.5-flash-lite',
        'options': {'temperature': 0.1},
        'think': 'medium',
        'context_length': 128000,  # 128k context
    },
    'gemini-2.5-flash': {
        'provider': 'gemini',
        'model_name': 'gemini-2.5-flash',
        'options': {'temperature': 0.1},
        'think': 'medium',
        'context_length': 128000,  # 128k context
    },
    'gemini-2.5-pro': {
        'provider': 'gemini',
        'model_name': 'gemini-2.5-pro',
        'options': {'temperature': 0.1},
        'think': 'medium',
        'context_length': 128000,  # 128k context
    },
}
