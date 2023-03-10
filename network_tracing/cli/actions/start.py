import json
import logging
import sys
from argparse import ArgumentParser, _SubParsersAction
from dataclasses import dataclass, field
from typing import Any, Union

from network_tracing.cli.api import ApiClient
from network_tracing.cli.constants import DEFAULT_PROGRAM_NAME
from network_tracing.cli.models import BaseOptions
from network_tracing.common.models import CreateTracingTaskRequest

logger = logging.getLogger(__name__)


@dataclass
class Options(BaseOptions):
    options: list[str] = field(default_factory=list)

    def to_request_dict(self) -> dict[str, Any]:
        request_dict: dict[str, Any] = {}
        for option in self.options:
            key, value = Options._convert_option(option)
            request_dict = Options._set(request_dict, key, value)

        logger.debug(
            'Request payload (as dictionary): {}'.format(request_dict))
        return request_dict

    def to_request(self) -> CreateTracingTaskRequest:
        return CreateTracingTaskRequest.from_dict(self.to_request_dict())

    @staticmethod
    def _set(dest: dict[str, Any], key: str, value: Any) -> dict[str, Any]:
        """Set `key = value` in `dest`, and return `dest`. A small subset of JSONPath is supported for `key`."""

        if not key:
            raise Exception('Key must not be empty')

        if key == '$':
            if isinstance(value, dict):
                return value
            else:
                raise Exception('Root value must be a dictionary')

        if key.startswith('$[') or key.startswith('['):
            raise Exception('Root value must be a dictionary')

        if key.startswith('$.'):
            Options._set_root_unchecked(dest, key[1:], value)
        elif key.startswith('.'):
            Options._set_root_unchecked(dest, key, value)
        else:
            Options._set_root_unchecked(dest, '.' + key, value)

        return dest

    @staticmethod
    def _set_root_unchecked(dest: Union[dict[str, Any], list[Any]], key: str,
                            value: Any):
        if key.startswith('.'):
            if not isinstance(dest, dict):
                raise RuntimeError(
                    'Type of `dest` {} and `key` {} mismatch'.format(
                        type(dest),
                        key,
                    ))

            for i in range(1, len(key)):
                if key[i] in ('.', '['):
                    segment_key, next_key = key[1:i], key[i:]
                    if segment_key not in dest:
                        dest[segment_key] = {} if key[i] == '.' else []
                    next_dest = dest[segment_key]
                    Options._set_root_unchecked(next_dest, next_key, value)
                    return
            else:
                dest[key[1:]] = value
                return

        elif key.startswith('['):
            if not isinstance(dest, list):
                raise RuntimeError(
                    'Type of `dest` {} and `key` {} mismatch'.format(
                        type(dest),
                        key,
                    ))

            try:
                closing_bracket = key.index(']')
            except ValueError:
                raise Exception('Missing closing bracket in {}'.format(key))

            segment_index_str = key[1:closing_bracket]
            try:
                segment_index = int(segment_index_str)
            except ValueError:
                raise Exception('Invalid index {}'.format(segment_index_str))
            if segment_index < 0:
                raise Exception('Invalid index {}'.format(segment_index_str))

            if closing_bracket == len(key) - 1:
                if len(dest) <= segment_index:
                    dest.extend([None] * (segment_index + 1 - len(dest)))
                dest[segment_index] = value
                return
            else:
                if len(dest) <= segment_index:
                    dest.extend([None] * (segment_index + 1 - len(dest)))
                if dest[segment_index] is None:
                    dest[segment_index] = {} if key[closing_bracket +
                                                    1] == '.' else []
                next_dest = dest[segment_index]
                next_key = key[closing_bracket + 1:]
                Options._set_root_unchecked(next_dest, next_key, value)
                return

        else:
            raise RuntimeError('Invalid key {}'.format(key))

    @staticmethod
    def _convert_option(option: str) -> tuple[str, Any]:
        try:
            equals_sign = option.index('=')
            key, value_str = option[:equals_sign], option[equals_sign + 1:]
            try:
                return key, json.loads(value_str)
            except json.JSONDecodeError:
                return key, value_str
        except ValueError:
            return option, None


def configure_subparsers(subparsers: _SubParsersAction):
    parser: ArgumentParser = subparsers.add_parser(
        'start', aliases=['create'], help='create and start a tracing task')

    parser.add_argument(
        'options',
        metavar='OPTIONS',
        nargs='+',
        help='options of the task being created, in the format KEY=VALUE')


def run(options: Union[dict[str, Any], Options]):
    if isinstance(options, dict):
        options = Options.from_dict(options)

    try:
        request = options.to_request()
        response = ApiClient.get_instance().create_tracing_task(request)
        print(response.id)
    except Exception as e:
        print('{}: error: failed to create and start tracing task: {}'.format(
            DEFAULT_PROGRAM_NAME,
            e,
        ),
              file=sys.stderr)
        logger.debug('Exception information:', exc_info=e)
        return 1
