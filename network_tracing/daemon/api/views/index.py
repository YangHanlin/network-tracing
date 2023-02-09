from dataclasses import dataclass
import importlib.metadata
from flask import Blueprint

from network_tracing.common.utilities import DataclassConversionMixin

index = Blueprint('index', __name__)


@dataclass
class BasicInformation(DataclassConversionMixin):
    name: str
    version: str


@index.get('/')
def get_basic_information():
    top_package = __package__.split('.', maxsplit=1)[0]
    name = '{} daemon'.format(top_package)
    version = importlib.metadata.version(top_package)
    return BasicInformation(name=name, version=version).to_dict()
