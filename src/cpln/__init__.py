"""CPLN Python SDK - Control Plane API client library.

This package provides a Python interface for interacting with the Control Plane (CPLN) API.
It includes functionality for managing workloads, GVCs, images, and other CPLN resources.

Example:
    >>> import cpln
    >>> client = cpln.CPLNClient.from_env()
    >>> workloads = client.workloads.list(gvc="my-gvc")
"""

__version__ = "0.1.18"  # This version will be read by PDM
from .client import CPLNClient
from . import templates

__all__ = ["CPLNClient", "templates"]
