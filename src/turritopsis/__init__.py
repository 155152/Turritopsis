"""Turritopsis: shared project truth and handoff over MCP."""

from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("turritopsis")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.2.0"

