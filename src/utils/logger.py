"""Central logging module for the investment bot.

Usage:
    from src.utils.logger import get_logger, timed

    log = get_logger("tools.market")
    log.debug("get_ticker_status called: AAPL")

    with timed(log, "yfinance.Ticker(AAPL)"):
        info = yf.Ticker("AAPL").info

Log level is controlled by the LOG_LEVEL environment variable (default: warning).
Set LOG_LEVEL=debug in .env to see all tool calls, API calls, and timings.
The level is applied at FastAPI startup — before that, standard WARNING applies.
"""
import logging
import time


def get_logger(name: str) -> logging.Logger:
    """Return a named logger; level is inherited from the root logger.

    The root logger is configured at FastAPI startup (backend/main.py) based
    on LOG_LEVEL from .env.  Loggers propagate to root by default so no
    duplicate handlers are needed here.
    """
    return logging.getLogger(name)


class timed:
    """Context manager that logs elapsed time at DEBUG level.

    Example::

        with timed(log, "yfinance.Ticker(AAPL)"):
            info = yf.Ticker("AAPL").info
        # -> [DEBUG] tools.market | → START  yfinance.Ticker(AAPL)
        # -> [DEBUG] tools.market | ← DONE   yfinance.Ticker(AAPL)  [312ms]
    """

    def __init__(self, logger: logging.Logger, label: str):
        self.logger = logger
        self.label = label

    def __enter__(self):
        self._start = time.perf_counter()
        self.logger.debug(f"→ START  {self.label}")
        return self

    def __exit__(self, *_):
        ms = (time.perf_counter() - self._start) * 1000
        self.logger.debug(f"← DONE   {self.label}  [{ms:.0f}ms]")
