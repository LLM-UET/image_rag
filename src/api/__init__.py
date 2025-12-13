"""
API module - FastAPI REST endpoints for third-party integration.
"""

# Conditional import to avoid requiring FastAPI for all uses
try:
    from .telecom_api import app
    __all__ = ["app"]
except ImportError:
    # FastAPI not installed, skip REST API
    __all__ = []
