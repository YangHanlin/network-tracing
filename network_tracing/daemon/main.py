from argparse import ArgumentParser
import sys
import threading

from network_tracing.daemon.app import Application, ApplicationConfig


def _create_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument('-c',
                        '--config',
                        default='./config.json',
                        metavar='PATH',
                        help='path to configuration file')
    return parser


def main():
    parser = _create_parser()
    args = parser.parse_args()
    config = ApplicationConfig.load_file(args.config)
    application = Application(config)
    application.start()
    print(
        'Daemon started; send SIGINT (run `kill -3` or press Ctrl + C) to stop'
    )
    try:
        forever = threading.Event()
        forever.wait()
    except KeyboardInterrupt:
        print('Stopping')
        application.stop()
        sys.exit(0)


if __name__ == '__main__':
    main()
