import os
import logging
from aurora.config import config
from aurora.state import state_manager

class StateLogHandler(logging.Handler):
    """
    Custom logging handler that intercepts logs and pipes them into
    the global StateManager to be displayed in the TUI in real-time.
    """
    def emit(self, record):
        try:
            log_entry = self.format(record)
            state_manager.add_tool_log(log_entry)
        except Exception:
            self.handleError(record)

def setup_logger():
    # Make sure logs directory exists
    logs_dir = config.logs_dir
    os.makedirs(logs_dir, exist_ok=True)

    logger = logging.getLogger("aurora")
    logger.setLevel(logging.DEBUG)

    # Prevent adding handlers multiple times if setup is called repeatedly
    if logger.handlers:
        return logger

    # 1. File Handler (captures all debug + info logs)
    file_handler = logging.FileHandler(config.log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # 2. State Interceptor Handler (sends warnings, info and errors to TUI log panel)
    state_handler = StateLogHandler()
    state_handler.setLevel(logging.INFO)
    state_formatter = logging.Formatter("%(levelname)s: %(message)s")
    state_handler.setFormatter(state_formatter)
    logger.addHandler(state_handler)

    return logger

# Initialize logging
logger = setup_logger()
