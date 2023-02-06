import json

from flask import Blueprint

tracing_tasks = Blueprint('tracing_tasks',
                          __name__,
                          url_prefix='/tracing-tasks')


@tracing_tasks.get('')
def list_tracing_tasks():
    return {'message': 'This feature has not been implemented yet'}, 501


@tracing_tasks.get('/<id>')
def get_tracing_task(id):
    return {'message': 'This feature has not been implemented yet'}, 501


@tracing_tasks.get('/<id>/events')
def get_tracing_task_events(id):

    def generate():
        while True:
            yield json.dumps({
                'message':
                'This feature has not been implemented yet',
            }) + '\n'

    return generate(), 501, {'Content-Type': 'application/json;encoding=utf-8'}


@tracing_tasks.post('')
def create_tracing_task():
    return {'message': 'This feature has not been implemented yet'}, 501


@tracing_tasks.delete('/<id>')
def remove_tracing_task(id):
    return {'message': 'This feature has not been implemented yet'}, 501
