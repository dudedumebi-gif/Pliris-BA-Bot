"""Operational monitoring utilities."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pliris.monitoring.events import EventLogger

__all__ = ["EventLogger"]


def __getattr__(name: str) -> Any:
    if name == "EventLogger":
        return import_module("pliris.monitoring.events").EventLogger
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")