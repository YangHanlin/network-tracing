from flask import Blueprint

from network_tracing.common.models import DaemonInfoResponse
from network_tracing.common.utilities import Metadata

index = Blueprint('index', __name__)


@index.get('/')
def get_daemon_info():
    package_name, package_version = Metadata.get_package_name_and_version()
    name = '{} daemon'.format(package_name)
    return DaemonInfoResponse(name=name, version=package_version).to_dict()
