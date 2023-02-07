from dataclasses import dataclass, field
from os import PathLike
from typing import cast

from network_tracing.common.utilities import DataclassConversionMixin
from network_tracing.daemon.api.server import ApiServerConfig, ApiServer
from network_tracing.daemon.common import BackgroundTask, global_state


@dataclass(kw_only=True)
class ApplicationConfig(DataclassConversionMixin):
    api: ApiServerConfig = field(default_factory=ApiServerConfig)

    def __post_init__(self):
        if isinstance(self.api, dict):
            self.api = ApiServerConfig.from_dict(self.api)

    @classmethod
    def load_file(cls, path: PathLike) -> 'ApplicationConfig':
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
        if global_state.application is None:
            instance = super(Application, cls).__new__(cls)
            instance.__init__(*args, **kwargs)
            global_state.application = instance
        return cast(Application, global_state.application)

    def __init__(self, config: ApplicationConfig) -> None:
        self._config = config
        self._tasks: dict[str, BackgroundTask] = {}
        # API server should run on start
        self._tasks.update(
            Application._create_api_server_task(self._config.api))

    @property
    def tasks(self) -> dict[str, BackgroundTask]:
        return self._tasks

    def start(self) -> None:
        for key, task in self._tasks.items():
            print('Starting task {}'.format(key))
            task.start()
        print('Started all initial/remaining tasks')

    def stop(self) -> None:
        for key, task in self._tasks.items():
            print('Stopping task {}'.format(key))
            task.stop()
        print('Stopped all tasks')

    @staticmethod
    def _create_api_server_task(
            config: ApiServerConfig) -> dict[str, ApiServer]:
        return {'api_server': ApiServer(config)}
