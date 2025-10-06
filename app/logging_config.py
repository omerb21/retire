"""
Logging configuration for the application
Provides structured logging for monitoring and alerting
"""
import os
import logging
import logging.config
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Environment-based configuration
ENV = os.getenv("APP_ENV", "development").lower()

# Default level based on environment
if ENV == "production":
    DEFAULT_LEVEL = "INFO"
elif ENV == "staging":
    DEFAULT_LEVEL = "DEBUG"
else:
    DEFAULT_LEVEL = "DEBUG"

# Allow override via environment variable
LOG_LEVEL = os.getenv("LOG_LEVEL", DEFAULT_LEVEL).upper()

# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "json": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "json_ensure_ascii": False,  # Important for Hebrew characters
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": LOG_LEVEL,
            "formatter": "standard",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": LOG_LEVEL,
            "formatter": "standard",
            "filename": "logs/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "encoding": "utf8"
        },
        "json_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": LOG_LEVEL,
            "formatter": "json",
            "filename": "logs/app.json",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "encoding": "utf8"
        },
        "fixation_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": LOG_LEVEL,
            "formatter": "standard",
            "filename": "logs/fixation.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "encoding": "utf8"
        }
    },
    "loggers": {
        "": {  # Root logger
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
        },
        "app.routers.fixation": {
            "handlers": ["console", "fixation_file", "json_file"],
            "level": LOG_LEVEL,
            "propagate": False
        },
        "app.integrations.fixation_forms": {
            "handlers": ["console", "fixation_file", "json_file"],
            "level": LOG_LEVEL,
            "propagate": False
        },
        "uvicorn": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False
        }
    }
}


def setup_logging():
    """
    Set up logging configuration for the application
    """
    try:
        # Try to use python-json-logger if available
        import pythonjsonlogger  # noqa
    except ImportError:
        # Fall back to standard formatter if not available
        LOGGING_CONFIG["handlers"]["json_file"]["formatter"] = "standard"
        print("python-json-logger not found, using standard formatter for JSON logs")
    
    logging.config.dictConfig(LOGGING_CONFIG)
    logging.info(f"Logging initialized with level {LOG_LEVEL} in {ENV} environment")


def get_logger(name):
    """
    Get a logger with the given name
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

