import json
import logging
import logging.config
from datetime import datetime
from pathlib import Path

from yaml import safe_load


def getLogger(name: str = "snow-search-mcp") -> logging.Logger:
    """Configures logging and returns a logger with the specified name.

    Parameters:
    name (str): The name of the logger.

    Returns:
    logging.Logger: The logger with the specified name.
    """
    log_config_path = Path(__file__).resolve().parents[2] / "logconf.yaml"
    with open(log_config_path, "r", encoding="utf-8") as file:
        log_config = safe_load(file)

    logging.config.dictConfig(log_config)
    return logging.getLogger(name)


class JsonFormatter(logging.Formatter):
    """A custom JSON formatter for logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Formats the log record as a JSON string.

        Parameters:
        record (logging.LogRecord): The log record to format.

        Returns:
        str: The log record as a JSON string.
        """
        log_data = {
            "time": datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
        }

        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = str(record.exc_info)

        # Standard LogRecord attributes to exclude from extra fields.
        standard_attrs: set[str] = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "getMessage",
            "message",
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_data[key] = value

        return json.dumps(log_data)
