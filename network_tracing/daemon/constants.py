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
            'stream': 'ext://sys.stdout',
            'formatter': 'default',
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': [
            'console',
        ],
    },
}
