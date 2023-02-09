from dataclasses import dataclass, field
import logging
from threading import Thread, Lock
from typing import Optional
from werkzeug.exceptions import HTTPException
from werkzeug.serving import make_server

from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from network_tracing.daemon.api.common import ApiException

from network_tracing.daemon.api.views import blueprints
from network_tracing.daemon.common import BackgroundTask
from network_tracing.common.utilities import DataclassConversionMixin

logger = logging.getLogger(__name__)


@dataclass
class ApiServerConfig(DataclassConversionMixin):
    host: str = field(default='0.0.0.0')
    port: int = field(default=10032)
    cors: bool = field(default=False)


@dataclass
class _GeneralErrorResponse(DataclassConversionMixin):
    message: Optional[str] = field(default=None)


class _ServerThread(Thread):
    """See also: https://stackoverflow.com/a/45017691/10108192"""

    def __init__(self, app: Flask, host: str, port: int, **options) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._app = app
        self._server = make_server(self._host, self._port, self._app,
                                   **options)

    def run(self):
        self._app.logger.info('API service listening on %s:%d', self._host,
                              self._port)
        self._server.serve_forever()

    def shutdown(self):
        self._server.shutdown()


class _ServerJsonProvider(DefaultJSONProvider):

    def __init__(self, app: Flask) -> None:
        super().__init__(app)
        self.default = lambda o: o.to_dict() if isinstance(
            o, DataclassConversionMixin) else super().default(o)


class ApiServer(BackgroundTask):

    def __init__(self, config: ApiServerConfig) -> None:
        self._config = config
        self._app = ApiServer._create_app(self._config)
        self._thread: _ServerThread | None = None
        self._lock = Lock()
        ApiServer._configure_werkzeug_logging()

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
        app.json = _ServerJsonProvider(app)
        if config.cors:
            CORS(app)
        for blueprint in blueprints:
            app.register_blueprint(blueprint)
        app.register_error_handler(
            HTTPException, ApiServer._http_exception_handler)  # type: ignore
        return app

    @staticmethod
    def _create_thread(app: Flask, config: ApiServerConfig) -> _ServerThread:
        thread = _ServerThread(app, config.host, config.port, threaded=True)
        thread.daemon = True
        return thread

    @staticmethod
    def _configure_werkzeug_logging() -> None:
        """Configure the logger used by Werkzeug to stay consistent with other loggers."""
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.INFO)
        werkzeug_logger.handlers = logging.root.handlers
        werkzeug_logger.propagate = False

    @staticmethod
    def _http_exception_handler(exception: HTTPException):
        logger.debug('Encountered an HTTPException', exc_info=exception)
        response = exception.get_response()
        response.data = _GeneralErrorResponse(  # type: ignore
            message=exception.description).to_json()
        response.content_type = 'application/json; encoding=utf-8'
        return response
