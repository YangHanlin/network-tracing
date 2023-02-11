from network_tracing.cli.api import ApiClient, ApiException
from network_tracing.common.utilities import Metadata


def run(*_):
    print('CLI: {}'.format(_get_cli_version()))
    print('Daemon: {}'.format(_get_daemon_version()))


def _get_cli_version() -> str:
    return '{} cli {}'.format(*Metadata.get_package_name_and_version())


def _get_daemon_version() -> str:
    api = ApiClient.get_instance()
    try:
        daemon_info = api.get_daemon_info()
        daemon_version = '{} {}'.format(daemon_info.name, daemon_info.version)
    except ApiException as e:
        if e.parsed_response is None:
            daemon_version = '<failed to retrieve>'
        else:
            daemon_version = '<failed to retrieve: {}>'.format(
                e.parsed_response.message)
    return '{} (using API at {})'.format(daemon_version, api.http.base_url)
