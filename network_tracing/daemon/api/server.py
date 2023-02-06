from dataclasses import dataclass, field
from threading import Thread, Lock
from wsgiref.simple_server import make_server

from flask import Flask
from flask_cors import CORS

from network_tracing.daemon.api.views import blueprints
from network_tracing.daemon.common import BackgroundTask
from network_tracing.common.utilities import DictConversionMixin


@dataclass
class ApiServerConfig(DictConversionMixin):
    host: str = field(default='0.0.0.0')
    port: int = field(default=10032)
    cors: bool = field(default=False)


class _ServerThread(Thread):
    """See also: https://stackoverflow.com/a/45017691/10108192"""

    def __init__(self, app: Flask, host: str, port: int, **options) -> None:
        super().__init__()
        self._server = make_server(host, port, app, **options)

    def run(self):
        self._server.serve_forever()

    def shutdown(self):
        self._server.shutdown()


class ApiServer(BackgroundTask):

    def __init__(self, config: ApiServerConfig) -> None:
        self._config = config
        self._app = ApiServer._create_app(self._config)
        self._thread: _ServerThread | None = None
        self._lock = Lock()

    @property
    def config(self) -> ApiServerConfig:
        return self._config

    @property
    def app(self) -> Flask:
        return self._app

    def start(self):
        if self._thread is not None:
            return
        with self._lock:
            thread = ApiServer._create_thread(self._app, self._config)
            thread.start()
            self._thread = thread

    def stop(self) -> None:
        if self._thread is None:
            return
        with self._lock:
            thread, self._thread = self._thread, None
            thread.shutdown()

    @staticmethod
    def _create_app(config: ApiServerConfig) -> Flask:
        app = Flask('.'.join(__name__.split('.')[:-1]))
        if config.cors:
            CORS(app)
        for blueprint in blueprints:
            app.register_blueprint(blueprint)
        return app

    @staticmethod
    def _create_thread(app: Flask, config: ApiServerConfig) -> _ServerThread:
        thread = _ServerThread(app, config.host, config.port)
        thread.daemon = True
        return thread
