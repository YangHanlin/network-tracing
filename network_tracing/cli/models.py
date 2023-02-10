from dataclasses import dataclass, field

from network_tracing.cli.constants import (DEFAULT_BASE_URL,
                                           DEFAULT_CONFIG_FILE_PATH,
                                           DEFAULT_LOGGING_LEVEL)
from network_tracing.common.utilities import DataclassConversionMixin


@dataclass
class BaseOptions(DataclassConversionMixin):
    subcommand: str
    config: str = field(default=DEFAULT_CONFIG_FILE_PATH)
    base_url: str = field(default=DEFAULT_BASE_URL)
    logging_level: str = field(default=DEFAULT_LOGGING_LEVEL)
