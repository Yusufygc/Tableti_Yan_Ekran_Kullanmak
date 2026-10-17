"""İdempotent dosya loglama ve yakalanmayan istisna (excepthook) yapılandırması."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading
from types import TracebackType

_HANDLER_TAG = "tabscreen_rotating_file_handler"


def log_dir() -> Path:
    """Kullanıcı log klasörünü döndürür (testlerde conftest ile yalıtılır)."""
    return Path.home() / ".tabscreen_usb" / "logs"


def resolve_log_level(level_arg: str | None = None) -> int:
    """Log düzeyini argüman -> ortam değişkeni -> varsayılan (INFO) sırasıyla çözer."""
    raw = (level_arg or os.environ.get("TABSCREEN_LOG_LEVEL") or "INFO").upper().strip()
    return getattr(logging, raw, logging.INFO)


def setup_logging(level_arg: str | None = None) -> Path:
    """Dönen dosya loglamasını (1 MB x 3) ve istisna kancalarını idempotent olarak kurar."""
    target_dir = log_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / "tabscreen.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(resolve_log_level(level_arg))

    existing = [
        h for h in root_logger.handlers if getattr(h, "_tabscreen_tag", None) == _HANDLER_TAG
    ]
    for handler in existing:
        if Path(getattr(handler, "baseFilename", "")) != log_file.resolve():
            root_logger.removeHandler(handler)
            handler.close()

    has_active_handler = any(
        getattr(h, "_tabscreen_tag", None) == _HANDLER_TAG for h in root_logger.handlers
    )
    if not has_active_handler:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        setattr(file_handler, "_tabscreen_tag", _HANDLER_TAG)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    install_exception_hooks()
    return log_file


def _handle_uncaught_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.getLogger("tabscreen.uncaught").critical(
        "Yakalanmayan istisna oluştu",
        exc_info=(exc_type, exc_value, exc_traceback),
    )


def _handle_thread_exception(args: threading.ExceptHookArgs) -> None:
    if args.exc_value is None:
        return
    logging.getLogger("tabscreen.thread").critical(
        "İş parçacığında yakalanmayan istisna (%s)",
        args.thread.name if args.thread else "bilinmeyen",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def install_exception_hooks() -> None:
    """sys.excepthook ve threading.excepthook kancalarını kurar."""
    sys.excepthook = _handle_uncaught_exception
    threading.excepthook = _handle_thread_exception
