from flask import Blueprint

index = Blueprint('index', __name__)


@index.get('/')
def greet():
    return {
        'message': 'Hello from network tracing daemon',
    }
