import logging
from pathlib import Path


# Build and configure a logger for a specific module or component.
def get_logger(
    name: str,
    *,
    level: str = "INFO",
    log_file: str | None = None,
) -> logging.Logger:
    # Get or create the Python logger for this component.
    logger = logging.getLogger(name)

    # Set the minimum logging level to display.
    logger.setLevel(level)

    # Reuse an existing logger so the same component does not create duplicate handlers.
    if logger.handlers:
        return logger

    # Create a shared log format for console and file output.
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Send log messages to the terminal so they are visible during development.
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # If a file path is provided, create the folder and write logs to that file too.
    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Write log records to disk in UTF-8 encoding.
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent duplicate logs from parent logger propagation.
    logger.propagate = False

    return logger