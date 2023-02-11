import logging
import random
from typing import Callable, Optional
from urllib.parse import quote, urljoin

import requests

from network_tracing.cli.constants import DEFAULT_BASE_URL
from network_tracing.common.models import (
    CreateTracingTaskRequest, CreateTracingTaskResponse, DaemonInfoResponse,
    ErrorResponse, GetTracingEventsResponse, GetTracingTaskResponse,
    ListTracingTasksResponse, TracingEvent, TracingTaskResponse)
from network_tracing.common.utilities import Metadata

logger = logging.getLogger(__name__)


class ApiClient:
    _instance: Optional['ApiClient'] = None

    def __init__(self, http: 'ApiClient._HttpClient') -> None:
        self._http = http

    def get_daemon_info_raw(self):
        return self.http.get('/')

    def get_daemon_info(self) -> DaemonInfoResponse:
        response = self._call_and_check_response(
            lambda: self.get_daemon_info_raw())
        return DaemonInfoResponse.from_dict(response.json())

    def list_tracing_tasks_raw(self):
        return self.http.get('/tracing_tasks')

    def list_tracing_tasks(self) -> ListTracingTasksResponse:
        response = self._call_and_check_response(
            lambda: self.list_tracing_tasks_raw())
        return list(map(TracingTaskResponse.from_dict, response.json()))

    def get_tracing_task_raw(self, id: str):
        return self.http.get('/tracing_tasks/{}'.format(quote(id)))

    def get_tracing_task(self, id: str) -> GetTracingTaskResponse:
        response = self._call_and_check_response(
            lambda: self.get_tracing_task_raw(id))
        return GetTracingTaskResponse.from_dict(response.json())

    def get_tracing_events_raw(self, task_id: str):
        response = self.http.get('/tracing_tasks/{}/events'.format(
            quote(task_id)),
                                 stream=True)

        if response.encoding is None:
            response.encoding = 'utf-8'

        return response

    def get_tracing_events(self, task_id: str) -> GetTracingEventsResponse:
        response = self._call_and_check_response(
            lambda: self.get_tracing_events_raw(task_id))

        def generate():
            for line in response.iter_lines():
                try:
                    yield TracingEvent.from_json(line)
                except Exception as e:
                    logger.warn(
                        'Dropped an event because an error ocurred while parsing it (maybe malformed)'
                    )
                    logger.debug('Event (before parsing): %s', line)
                    logger.debug(
                        'Exception encountered while parsing the event:',
                        exc_info=e)

        return generate()

    def create_tracing_task_raw(self, payload: CreateTracingTaskRequest):
        return self.http.post('/tracing_tasks', json=payload.to_dict())

    def create_tracing_task(
            self,
            payload: CreateTracingTaskRequest) -> CreateTracingTaskResponse:
        response = self._call_and_check_response(
            lambda: self.create_tracing_task_raw(payload))
        return CreateTracingTaskResponse.from_dict(response.json())

    def remove_tracing_task_raw(self, id: str):
        return self.http.delete('/tracing_tasks/{}'.format(quote(id)))

    def remove_tracing_task(self, id: str) -> None:
        self._call_and_check_response(lambda: self.remove_tracing_task_raw(id))

    @property
    def http(self):
        return self._http

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise RuntimeError(
                'This has not been initialized yet; please call initialize() first'
            )

        return cls._instance

    @classmethod
    def initialize(cls, base_url: str = DEFAULT_BASE_URL):
        if cls._instance is not None:
            raise RuntimeError('This is already initialized')

        http = cls._HttpClient()
        http.base_url = base_url
        http.headers.update(cls._build_default_headers())

        instance = object.__new__(cls)
        instance.__init__(http)
        cls._instance = instance

        return cls._instance

    @staticmethod
    def _call_and_check_response(
        response_provider: Callable[[],
                                    requests.Response]) -> requests.Response:
        try:
            response = response_provider()
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            raise ApiException(e) from e

    @staticmethod
    def _build_default_headers() -> dict[str, str]:
        return {
            'User-Agent':
            '{}-cli/{}'.format(*Metadata.get_package_name_and_version()),
            'Accept':
            'application/json',
        }

    class _HttpClient(requests.Session):

        def __init__(self) -> None:
            super().__init__()
            self._base_url: Optional[str] = None

        @property
        def base_url(self):
            return self._base_url

        @base_url.setter
        def base_url(self, base_url: Optional[str]):
            # Add http:// to base_url if no scheme is found
            for _ in range(1):
                if base_url is None:
                    break
                if len(base_url) < 7:
                    break
                if base_url.lower()[:7] in ('https:/', 'http://'):
                    break
                base_url = 'http://' + base_url

            self._base_url = base_url

        def request(self, method: str, url: str, *args, **kwargs):
            if self.base_url is not None:
                url = urljoin(self.base_url, url)

            debug_enabled = logger.isEnabledFor(logging.DEBUG)
            if debug_enabled:
                id = '{:04x}'.format(random.randint(0, 65535))
                logger.debug('=> [%s] %s %s', id, method, url)

            response = super().request(method, url, *args, **kwargs)

            if debug_enabled:
                logger.debug(
                    '<= [%s] %s %s',
                    id,  # type: ignore
                    response.status_code,
                    response.reason)

            return response


class ApiException(Exception):

    def __init__(self, raw_exception: requests.RequestException,
                 *args: object) -> None:
        self._raw_exception = raw_exception
        self._parsed_response = self._parse_response(
            self._raw_exception.response)

        message = 'Unknown error' if self._parsed_response is None else self._parsed_response.message
        super().__init__(message, *args)

    @property
    def parsed_response(self) -> Optional[ErrorResponse]:
        return self._parsed_response

    @property
    def raw_response(self) -> requests.Response:
        return self._raw_exception.response

    @staticmethod
    def _parse_response(raw_response: requests.Response):
        if raw_response is None:
            return None

        try:
            return ErrorResponse.from_dict(raw_response.json())
        except Exception as e:
            logger.debug(
                'Encountered an exception while parsing error response:',
                exc_info=e)
            return None
