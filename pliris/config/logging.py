import logging
import sys

from loguru import logger

from pliris.config.settings import settings


def setup_logging():
    """Configure application logging using loguru."""

    # Remove default handler
    logger.remove()

    # log format defined
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # Add console handler
    logger.add(
        sys.stderr,
        format=log_format,
        level=settings.log_level,
        colorize=True,
    )

    # Add file handler
    logger.add(
        "logs/app.log",
        rotation="500 MB",
        retention="10 days",
        format=log_format,
        level=settings.log_level,
    )

    # Intercept standard logging
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

    logging.basicConfig(handlers=[InterceptHandler()], level=0)

    return logger
