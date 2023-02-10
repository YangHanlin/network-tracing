import logging
import logging.config
import sys
import threading
from argparse import ArgumentParser
from signal import SIGINT, SIGTERM, signal
from typing import Callable

from network_tracing.daemon.app import Application, ApplicationConfig
from network_tracing.daemon.constants import DEFAULT_LOGGING_CONFIG

logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)

logger = logging.getLogger(__name__)


def _create_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument('-c',
                        '--config',
                        default='/etc/network_tracing/ntd_config.json',
                        metavar='PATH',
                        help='path to configuration file')
    return parser


def _parse_args():
    parser = _create_parser()
    args = parser.parse_args()
    return args


def _create_start_app(config_file_path: str) -> Application:
    logger.info('Loading config file %s', config_file_path)
    config = ApplicationConfig.load_file(config_file_path)

    app = Application(config)
    app.start()

    signal_handler = _create_signal_handler(app)
    signal(SIGINT, signal_handler)
    signal(SIGTERM, signal_handler)

    logger.info(
        'Application started; press Ctrl + C or send SIGINT/SIGTERM to exit')

    return app


def _wait_forever():
    forever = threading.Event()
    forever.wait()


def _create_signal_handler(app: Application) -> Callable:
    ignore = lambda sig, stack: None

    def signal_handler(sig, stack):
        logger.info('Gracefully shutting down')
        signal(SIGINT, ignore)
        signal(SIGTERM, ignore)
        try:
            app.stop()
            sys.exit(0)
        except Exception:
            logger.error('Graceful shutdown failed', exc_info=True)
            sys.exit(1)

    return signal_handler


def main():
    args = _parse_args()
    _create_start_app(args.config)
    _wait_forever()


if __name__ == '__main__':
    main()
