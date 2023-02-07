from dataclasses import dataclass
from flask import Blueprint

from network_tracing.common.utilities import DataclassConversionMixin

index = Blueprint('index', __name__)


@dataclass
class Greeting(DataclassConversionMixin):
    message: str


@index.get('/')
def greet():
    return Greeting(message='Hello from network tracing daemon').to_dict()
