import json
from uuid import uuid4

from flask import Blueprint, request
from network_tracing.common.utilities import DictConversionMixin
from network_tracing.daemon import utilities

from network_tracing.daemon.tracing.task import TracingTask, TracingTaskOptions

tracing_tasks = Blueprint('tracing_tasks',
                          __name__,
                          url_prefix='/tracing_tasks')

TRACING_TASK_PREFIX = 'tracing_tasks/'


@tracing_tasks.get('')
@tracing_tasks.get('/')
def list_tracing_tasks():
    if utilities.current_app is None:
        raise RuntimeError('Cannot get application instance')

    response_body = []

    for key, task in utilities.current_app.tasks.items():
        if key.startswith(TRACING_TASK_PREFIX):
            response_body.append({
                'id': key[len(TRACING_TASK_PREFIX):],
                'options': task.options.to_dict()  # type: ignore
            })

    return response_body


@tracing_tasks.get('/<id>')
def get_tracing_task(id):
    if utilities.current_app is None:
        raise RuntimeError('Cannot get application instance')

    task = utilities.current_app.tasks.get(TRACING_TASK_PREFIX + id, None)
    if task is None:
        return {'message': 'Cannot find task with id \'{}\''.format(id)}, 404

    return {
        'id': id,
        'options': task.options.to_dict()  # type: ignore
    }


@tracing_tasks.get('/<id>/events')
def get_tracing_task_events(id):
    if utilities.current_app is None:
        raise RuntimeError('Cannot get application instance')

    task = utilities.current_app.tasks.get(TRACING_TASK_PREFIX + id, None)
    if task is None:
        return {'message': 'Cannot find task with id \'{}\''.format(id)}, 404

    def generate():
        while True:
            event = task.poll_event(blocking=True)  # type: ignore
            if isinstance(event, DictConversionMixin):
                event = event.to_dict()
            yield json.dumps(event) + '\n'

    return generate(), 200, {
        'Content-Type': 'application/json-lines+json; encoding=utf-8',
    }


@tracing_tasks.post('')
@tracing_tasks.post('/')
def create_tracing_task():
    if utilities.current_app is None:
        raise RuntimeError('Cannot get application instance')

    task = TracingTask(TracingTaskOptions.from_dict(
        request.json))  # type: ignore
    task.start()
    id = uuid4().hex
    task_key = TRACING_TASK_PREFIX + id

    utilities.current_app.tasks[task_key] = task

    return {
        'id': id,
    }


@tracing_tasks.delete('/<id>')
def remove_tracing_task(id):
    if utilities.current_app is None:
        raise RuntimeError('Cannot get application instance')

    task_key = TRACING_TASK_PREFIX + id
    task = utilities.current_app.tasks.get(task_key, None)
    if task is None:
        return {'message': 'Cannot find task with id \'{}\''.format(id)}, 404

    task.stop()
    del utilities.current_app.tasks[task_key]

    return '', 204
