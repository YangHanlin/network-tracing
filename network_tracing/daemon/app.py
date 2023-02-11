import logging
import logging.config
from copy import deepcopy
from dataclasses import dataclass, field
from os import PathLike
from typing import Union, cast

from network_tracing.common.utilities import DataclassConversionMixin
from network_tracing.daemon.api.server import ApiServer, ApiServerConfig
from network_tracing.daemon.constants import DEFAULT_LOGGING_CONFIG
from network_tracing.daemon.models import BackgroundTask
from network_tracing.daemon.utilities import global_state

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class LoggingConfig(DataclassConversionMixin):
    level: str = field(default=DEFAULT_LOGGING_CONFIG['root']['level'])


@dataclass(kw_only=True)
class ApplicationConfig(DataclassConversionMixin):
    api: ApiServerConfig = field(default_factory=ApiServerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def __post_init__(self):
        if isinstance(self.api, dict):
            self.api = ApiServerConfig.from_dict(self.api)
        if isinstance(self.logging, dict):
            self.logging = LoggingConfig.from_dict(self.logging)

    @classmethod
    def load_file(cls, path: Union[str, PathLike]) -> 'ApplicationConfig':
        try:
            with open(path, 'r', encoding='utf-8') as fp:
                data = fp.read()
            return ApplicationConfig.from_json(data)
        except:
            return ApplicationConfig()

    def dump_file(self, path: PathLike):
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(self.to_json())


class Application:

    def __new__(cls: type['Application'], *args, **kwargs) -> 'Application':
        # FIXME: It is not elegant to implement singleton by tweaking `__new__`
        if global_state.application is None:
            instance = super(Application, cls).__new__(cls)
            global_state.application = instance
        return cast(Application, global_state.application)

    def __init__(self, config: ApplicationConfig) -> None:
        self._config = config
        self._configure_logging(self._config.logging)
        self._tasks: dict[str, BackgroundTask] = {}
        # API server should run on start
        self._tasks.update(
            Application._create_api_server_task(self._config.api))

    @property
    def tasks(self) -> dict[str, BackgroundTask]:
        return self._tasks

    def start(self) -> None:
        for key, task in self._tasks.items():
            logger.debug('Starting initial task \'%s\'', key)
            task.start()
        logger.debug('Started all initial tasks')

    def stop(self) -> None:
        for key, task in self._tasks.items():
            logger.debug('Stopping task \'%s\'', key)
            task.stop()
        logger.debug('Stopped all tasks')

    @staticmethod
    def _create_api_server_task(
            config: ApiServerConfig) -> dict[str, ApiServer]:
        return {'api_server': ApiServer(config)}

    @staticmethod
    def _configure_logging(config: LoggingConfig) -> None:
        logging_config = deepcopy(DEFAULT_LOGGING_CONFIG)
        logging_config['root']['level'] = config.level
        logging_config['disable_existing_loggers'] = False
        logging.config.dictConfig(logging_config)
