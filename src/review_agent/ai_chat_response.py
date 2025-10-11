from dotenv import find_dotenv, load_dotenv
from litellm import completion

from .logger import log

load_dotenv(find_dotenv())


def _build_model_string(model_dict: dict) -> str:
    """Return the litellm-style model string.

    If callers pass separate provider via model_dict['provider'] (like 'gemini' or
    'ollama') keep compatibility by joining them with model_name when the
    model_name doesn't already contain a provider (i.e. doesn't contain '/').
    """
    model_name = model_dict.get('model_name')
    provider_name = model_dict.get('provider')

    if not model_name:
        msg = 'model_dict must include model_name'
        raise ValueError(msg)

    # If the model_name already looks like 'provider/model', return as-is.
    if '/' in model_name:
        return model_name

    if provider_name:
        return f'{provider_name}/{model_name}'

    return model_name


def chat_response(model_dict: dict, messages: list[dict]):
    """Send messages to an LLM via litellm.completion and return assistant text.

    model_dict expects keys: 'provider' (optional), 'model_name' (required),
    'think' (optional), and 'options' (optional dict forwarded to completion).
    """
    model = _build_model_string(model_dict)

    try:
        response = completion(model=model, messages=messages, stream=False, **model_dict.get('options', {}))
    except ValueError as e:
        log(f'Model summary request failed: {e}', level='error')
        return None

    assistant_message = response['choices'][0]['message']['content']
    if isinstance(assistant_message, str):
        return assistant_message.strip()
    # If message is a dict-like object, attempt to get 'content'
    return str(assistant_message).strip()
