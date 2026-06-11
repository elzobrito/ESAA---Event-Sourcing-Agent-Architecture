"""ESAA core package."""

from .constants import ESAA_VERSION, PACKAGE_VERSION, SCHEMA_VERSION

__version__ = PACKAGE_VERSION

__all__ = ["SCHEMA_VERSION", "ESAA_VERSION", "PACKAGE_VERSION", "__version__"]
