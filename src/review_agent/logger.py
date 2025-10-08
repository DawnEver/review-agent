import datetime
import logging
from pathlib import Path

from .config import OUTPUT_CONFIG

# --------------------------------------------------------------------------------------
# Logger Initialization (idempotent)  -  concise + file & console
# --------------------------------------------------------------------------------------
logger = logging.getLogger()
if not logger.handlers:  # Prevent duplicate handlers on reload
    logger.setLevel(logging.DEBUG)

    current_time = datetime.datetime.now()
    log_dir = Path(OUTPUT_CONFIG['log_folder'])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_filename = current_time.strftime('%Y%m%d_%H') + '.log'
    log_path = log_dir / log_filename

    log_file_format: str = '%(asctime)s %(levelname)s %(message)s \tlocation: %(filename)s:%(lineno)d'
    log_console_format: str = '%(levelname)s | %(message)s'
    log_date_format: str = '%Y-%m-%d %H:%M:%S'

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(fmt=log_file_format, datefmt=log_date_format))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(fmt=log_console_format, datefmt=log_date_format))
    logger.addHandler(console_handler)


def log(msg: str, level: str = 'INFO', **kv) -> None:
    """Concise logging helper.

    Extra keyword arguments are appended as key=value pairs for quick structured context.
    """
    if kv:
        extra_str = ' ' + ' '.join(f'{k}={v}' for k, v in kv.items())
    else:
        extra_str = ''
    level = (level or 'INFO').upper()
    log_func = getattr(logging, level.lower(), logging.info)
    if not hasattr(logging, level.lower()):  # Unknown level fallback
        logging.warning('Unknown log level provided: %s (fallback=INFO)', level)
    log_func(f'{msg}{extra_str}')


def info(msg: str, **kv):  # Convenience shortcuts
    log(msg, 'INFO', **kv)


def debug(msg: str, **kv):
    log(msg, 'DEBUG', **kv)


def warning(msg: str, **kv):
    log(msg, 'WARNING', **kv)


def error(msg: str, **kv):
    log(msg, 'ERROR', **kv)


def critical(msg: str, **kv):
    log(msg, 'CRITICAL', **kv)
