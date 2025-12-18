"""
Image RAG - Multimodal RAG system for PDF documents with image understanding.

Organized into submodules:
- core: Data models, cleaners, extractors
- services: Business logic orchestration  
- processors: PDF/image processing
- rag: Vector store, RAG pipeline
- db: Database handlers (MongoDB)
- api: REST API endpoints
- ui: Streamlit apps
"""

# Import from processors submodule for backward compatibility
try:
    from .processors.pdf_processor import PDFProcessor, process_pdf_file
except ImportError:
    PDFProcessor = None
    process_pdf_file = None

try:
    from .processors.image_processor import ImageDescriptionGenerator
except ImportError:
    ImageDescriptionGenerator = None

try:
    from .processors.document_merger import DocumentMerger, merge_documents
except ImportError:
    DocumentMerger = None
    merge_documents = None

try:
    from .rag.vector_store import VectorStoreManager, create_vector_store_from_documents
except ImportError:
    VectorStoreManager = None
    create_vector_store_from_documents = None

try:
    from .rag.structured_extractor import StructuredDataExtractor
except ImportError:
    StructuredDataExtractor = None

try:
    from .rag.rag_pipeline import MultimodalRAGPipeline, ConversationalRAG, create_rag_pipeline
except ImportError:
    MultimodalRAGPipeline = None
    ConversationalRAG = None
    create_rag_pipeline = None

# Telecom module exports
from .core import (
    TelecomPackage,
    TelecomPackageStrict,
    PackageAttributes,
    ExtractionResult,
    clean_upstage_json,
    clean_readable_txt,
    load_and_clean_json,
    TelecomPackageExtractor,
    extract_package_info,
)

from .services import TelecomDocumentService, process_document
from .db import MongoHandler

__version__ = "0.2.0"

__all__ = [
    # RAG components
    "PDFProcessor",
    "process_pdf_file",
    "ImageDescriptionGenerator",
    "DocumentMerger",
    "merge_documents",
    "VectorStoreManager",
    "create_vector_store_from_documents",
    "StructuredDataExtractor",
    "MultimodalRAGPipeline",
    "ConversationalRAG",
    "create_rag_pipeline",
    # Telecom components
    "TelecomPackage",
    "TelecomPackageStrict",
    "PackageAttributes",
    "ExtractionResult",
    "clean_upstage_json",
    "clean_readable_txt",
    "load_and_clean_json",
    "TelecomPackageExtractor",
    "extract_package_info",
    "TelecomDocumentService",
    "process_document",
    "MongoHandler",
]
