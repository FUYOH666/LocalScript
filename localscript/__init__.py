"""LocalScript: local Lua generation agent with validation pipeline."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("localscript")
except PackageNotFoundError:
    __version__ = "0.0.0"
