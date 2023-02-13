import logging

from network_tracing.cli.api import ApiClient, ApiException
from network_tracing.common.utilities import Metadata

logger = logging.getLogger(__name__)


def run(_=None):
    cli_version, get_cli_version_success = _get_cli_version()
    daemon_version, get_daemon_version_success = _get_daemon_version()

    print('CLI: {}\nDeamon: {}'.format(cli_version, daemon_version))

    if get_cli_version_success and get_daemon_version_success:
        return 0
    else:
        return 1


def _get_cli_version() -> tuple[str, bool]:
    try:
        return '{} cli {}'.format(
            *Metadata.get_package_name_and_version()), True
    except Exception as e:
        logger.debug('Encountered an error while getting CLI version',
                     exc_info=e)
        return '<failed to retrieve>', False


def _get_daemon_version() -> tuple[str, bool]:
    api = ApiClient.get_instance()
    try:
        daemon_info = api.get_daemon_info()
        daemon_version = '{} {}'.format(daemon_info.name, daemon_info.version)
        success = True
    except ApiException as e:
        logger.debug('Encountered an error while getting daemon version',
                     exc_info=e)
        if e.parsed_response is None:
            daemon_version = '<failed to retrieve>'
        else:
            daemon_version = '<failed to retrieve: {}>'.format(
                e.parsed_response.message)
        success = False
    return '{} (using API at {})'.format(daemon_version,
                                         api.http.base_url), success
