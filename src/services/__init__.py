"""
Services module - Business logic and orchestration.
"""
from .telecom_service import (
    TelecomDocumentService,
    process_document
)

__all__ = [
    "TelecomDocumentService",
    "process_document",
]
