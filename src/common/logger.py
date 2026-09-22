import logging
from pathlib import Path


# Create a logger configured for a specific component.
def get_logger(
    name: str,
    *,
    level: str = "INFO",
    log_file: str | None = None,
) -> logging.Logger:
    # Get or create the logger for this component.
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Reuse an existing logger instead of creating duplicate handlers.
    if logger.handlers:
        return logger

    # Use one shared format for both console and file output.
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Send log messages to the terminal while the app is running.
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optionally write logs to disk if a file path is supplied.
    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent duplicate messages from parent loggers.
    logger.propagate = False
    return logger