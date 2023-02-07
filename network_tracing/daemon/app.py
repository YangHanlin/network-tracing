from dataclasses import dataclass, field
import json
from json import JSONEncoder
from os import PathLike
from typing import Any, Optional

from network_tracing.common.utilities import DictConversionMixin
from network_tracing.daemon import utilities
from network_tracing.daemon.api.server import ApiServerConfig, ApiServer
from network_tracing.daemon.common import BackgroundTask


@dataclass(kw_only=True)
class ApplicationConfig(DictConversionMixin):
    api: ApiServerConfig = field(default_factory=ApiServerConfig)

    def __post_init__(self):
        if type(self.api) == dict:
            self.api = ApiServerConfig.from_dict(self.api)  # type: ignore

    class _Encoder(JSONEncoder):

        def default(self, o: Any) -> Any:
            if isinstance(o, DictConversionMixin):
                return o.to_dict()
            else:
                return super().default(o)

    @classmethod
    def load_file(cls, path: PathLike) -> 'ApplicationConfig':
        try:
            with open(path, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            return ApplicationConfig.from_dict(data)
        except:
            return ApplicationConfig()

    def dump_file(self, path: PathLike):
        with open(path, 'w', encoding='utf-8') as fp:
            json.dump(self, fp, cls=ApplicationConfig._Encoder)


class Application:
    instance: Optional['Application'] = None

    def __new__(cls: type['Application'], *args, **kwargs) -> 'Application':
        if Application.instance is None:
            instance = super(Application, cls).__new__(cls)
            instance.__init__(*args, **kwargs)
            Application.instance = instance
            utilities.current_app = instance
        return Application.instance

    def __init__(self, config: ApplicationConfig) -> None:
        self.config = config
        self.tasks: dict[str, BackgroundTask] = {}
        # API server should run on start
        self.tasks.update(Application._create_api_server_task(self.config.api))

    def start(self) -> None:
        for key, task in self.tasks.items():
            print('Starting task {}'.format(key))
            task.start()
        print('Started all initial/remaining tasks')

    def stop(self) -> None:
        for key, task in self.tasks.items():
            print('Stopping task {}'.format(key))
            task.stop()
        print('Stopped all tasks')

    @staticmethod
    def _create_api_server_task(
            config: ApiServerConfig) -> dict[str, ApiServer]:
        return {'api_server': ApiServer(config)}
