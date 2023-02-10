import os.path

DEFAULT_CONFIG_FILE_PATH = os.path.normpath(
    os.path.expanduser('~/.config/network_tracing/ntctl_config.json'))
DEFAULT_BASE_URL = 'http://localhost:10032'
DEFAULT_LOGGING_LEVEL = 'INFO'
DEFAULT_LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'default': {
            'format': '[{asctime} {levelname:1.1}] {module:6}: {message}',
            'style': '{',
            'validate': True,
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stderr',
            'formatter': 'default',
        }
    },
    'root': {
        'level': DEFAULT_LOGGING_LEVEL,
        'handlers': [
            'console',
        ],
    },
}
