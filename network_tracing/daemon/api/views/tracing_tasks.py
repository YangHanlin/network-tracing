from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

from flask import Blueprint, request
from network_tracing.common.utilities import DataclassConversionMixin
from network_tracing.daemon.api.common import ApiException
from network_tracing.daemon.common import global_state

from network_tracing.daemon.tracing.task import TracingTask, TracingTaskOptions

TRACING_TASK_PREFIX = 'tracing_tasks/'

tracing_tasks = Blueprint('tracing_tasks',
                          __name__,
                          url_prefix='/tracing_tasks')


def find_tracing_task(id: str) -> tuple[str, TracingTask]:
    if global_state.application is None:
        raise RuntimeError('Cannot get current application instance')

    task_key = TRACING_TASK_PREFIX + id
    task = global_state.application.tasks.get(task_key, None)

    if task is None:
        raise ApiException(
            'Cannot find tracing task with id \'{}\''.format(id), 404)

    if not isinstance(task, TracingTask):
        raise RuntimeError('Task with key {} is not an instance of {}'.format(
            task_key, TracingTask))

    return task_key, task


def find_all_tracing_tasks() -> dict[str, TracingTask]:
    if global_state.application is None:
        raise RuntimeError('Cannot get current application instance')

    tasks = {}
    for task_key, task in global_state.application.tasks.items():
        if task_key.startswith(TRACING_TASK_PREFIX):
            tasks[task_key[len(TRACING_TASK_PREFIX):]] = task

    return tasks


def insert_tracing_task(task: TracingTask) -> str:
    if global_state.application is None:
        raise RuntimeError('Cannot get current application instance')

    id = uuid4().hex
    task_key = TRACING_TASK_PREFIX + id
    global_state.application.tasks[task_key] = task

    return id


@dataclass
class TracingTaskResponse(DataclassConversionMixin):
    id: str
    options: TracingTaskOptions


@dataclass
class TracingTaskIdResponse(DataclassConversionMixin):
    id: str


@tracing_tasks.get('')
@tracing_tasks.get('/')
def list_tracing_tasks():
    return [
        TracingTaskResponse(id=id, options=task.options)
        for id, task in find_all_tracing_tasks().items()
    ]


@tracing_tasks.get('/<id>')
def get_tracing_task(id: str):
    _, task = find_tracing_task(id)
    # .to_dict() is added here only to make type checker happy
    return TracingTaskResponse(id=id, options=task.options).to_dict()


@tracing_tasks.get('/<id>/events')
def get_tracing_task_events(id: str):
    _, task = find_tracing_task(id)
    event_poller = task.get_event_poller()

    def generate():
        with event_poller:
            while True:
                event = event_poller.poll_event(block=True)
                yield event.to_json() + '\n'

    return generate(), {
        'Content-Type': 'application/json-lines+json; encoding=utf-8',
    }


@tracing_tasks.post('')
@tracing_tasks.post('/')
def create_tracing_task():
    task = TracingTask(
        TracingTaskOptions.from_dict(cast(dict[str, Any], request.json)))
    task.start()
    id = insert_tracing_task(task)

    return TracingTaskIdResponse(id=id).to_dict()


@tracing_tasks.delete('/<id>')
def remove_tracing_task(id: str):
    task_key, task = find_tracing_task(id)
    task.stop()
    del global_state.application.tasks[task_key]  # type: ignore

    return '', 204
