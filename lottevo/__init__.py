"""A thin Python client for the Lottevo lottery data API."""

from .client import DEFAULT_BASE_URL, Client, LottevoError, __version__

__all__ = ["Client", "LottevoError", "DEFAULT_BASE_URL", "__version__"]
