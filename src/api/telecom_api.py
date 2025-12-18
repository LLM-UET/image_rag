import io
import os
import sys
import json
import logging
import tempfile
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# === Adjust sys.path BEFORE any local imports ===
_api_dir = Path(__file__).parent
_src_dir = _api_dir.parent
_project_root = _src_dir.parent
sys.path.insert(0, str(_project_root))  # for config
sys.path.insert(0, str(_src_dir))        # for core, processors, etc.
# ================================================

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

from core.extractor import TelecomPackageExtractor
from processors.pdf_processor import PDFProcessor
from processors.image_processor import ImageDescriptionGenerator
from processors.document_merger import DocumentMerger
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: str
    gemini_configured: bool


class PackageAttributes(BaseModel):
    """Package attributes."""
    price: Optional[int] = None
    billing_cycle: Optional[str] = None
    payment_type: Optional[str] = None
    data_limit: Optional[str] = None
    speed: Optional[str] = None
    channels: Optional[int] = None
    voice_minutes: Optional[str] = None
    sms_count: Optional[int] = None
    bonus_codes: Optional[int] = None
    promotion: Optional[str] = None
    notes: Optional[str] = None
    
    model_config = ConfigDict(extra="allow")


class TelecomPackage(BaseModel):
    """Telecom package: internal field `name`, serialized as `Mã dịch vụ`."""
    name: str = Field(..., alias="Mã dịch vụ")
        
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        # Always use alias when serializing to JSON
        use_alias_by_default=True
    )


class ExtractionResponse(BaseModel):
    """Response for extraction endpoint."""
    id: str = Field(..., description="Unique request ID")
    extraction_date: str = Field(..., description="ISO 8601 timestamp")
    total_packages: int = Field(..., description="Number of packages extracted")
    packages: List[TelecomPackage] = Field(default_factory=list)



app = FastAPI(
    title="Telecom Package Extraction API",
    description="""
## API for third-party integration

### Endpoints:
- `POST /api/v1/extract` - Upload PDF → Extract packages → Returns JSON response
- `GET /api/v1/health` - Health check

### Response Format:
```json
{
  "id": "a1b2c3d4",
  "extraction_date": "2025-11-30T10:30:00.000000",
  "total_packages": 5,
  "packages": [...]
}
```
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        gemini_configured=bool(settings.gemini_api_key)
    )


@app.post("/api/v1/extract", response_model=ExtractionResponse, response_model_by_alias=True, tags=["Extraction"])
async def extract_packages(
    file: UploadFile = File(..., description="PDF file to process"),
    use_upstage: bool = Query(True, description="Use Upstage API for image extraction"),
    model: str = Query(settings.llm_model, description="LLM model (Gemini) for package extraction")
):
    """
    Process PDF and extract telecom packages.
    
    This endpoint:
    1. Extracts text from PDF
    2. Extracts and describes images
    3. Merges content into readable text
    4. Uses LLM to extract structured package data
    
    Returns JSON response with extracted packages.
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = datetime.now()
    
    try:
        filename = file.filename or "document.pdf"
        if not filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files supported")
        
        pdf_name = Path(filename).stem
        
        # Save temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            logger.info(f"[{request_id}] Processing PDF: {filename}")
            
            # Extract text from PDF
            pdf_processor = PDFProcessor(tmp_path)
            md_text = pdf_processor.extract_text_to_markdown(page_chunks=True)
            
            # Extract and describe images
            image_processor = ImageDescriptionGenerator(use_upstage=use_upstage)
            image_descriptions, _ = image_processor.process_pdf_images(tmp_path)
            
            #  Merge text and images into readable content
            merger = DocumentMerger()
            merged_docs = merger.merge_text_and_images(md_text, image_descriptions)
            
            # Build readable text (like process endpoint did)
            readable_lines = []
            for i, doc in enumerate(merged_docs):
                readable_lines.append(f"## Page {i + 1}")
                readable_lines.append("")
                readable_lines.append(doc.page_content)
                readable_lines.append("")
            
            readable_text = "\n".join(readable_lines)
            
            logger.info(f"[{request_id}] PDF processed: {len(merged_docs)} pages, {len(image_descriptions)} images")
            
            # Extract packages using LLM
            extractor = TelecomPackageExtractor(model_name=model)
            packages = extractor.extract_package_info(readable_text)
            
            # Convert to dict format (support new TelecomPackage schema: ma_dich_vu + attributes)
            packages_list = []
            for idx, pkg in enumerate(packages, 1):
                # Service identifier: prefer `ma_dich_vu`, fall back to `name` or `package_name`
                service_id = getattr(pkg, 'ma_dich_vu', None) or getattr(pkg, 'name', None) or getattr(pkg, 'package_name', None)

                # Normalize attributes: support dict or Pydantic model
                if isinstance(pkg.attributes, dict):
                    attrs = pkg.attributes
                elif hasattr(pkg.attributes, 'model_dump'):
                    # prefer by_alias so aliases like 'Nhà mạng' are preserved
                    try:
                        attrs = pkg.attributes.model_dump(exclude_none=True, by_alias=True)
                    except TypeError:
                        attrs = pkg.attributes.model_dump(exclude_none=True)
                else:
                    attrs = {}

                # Try to extract service_id from attributes if top-level extraction failed
                if not service_id or service_id.strip() == "":
                    if isinstance(attrs, dict):
                        service_id = attrs.get('Mã dịch vụ') or attrs.get('ma_dich_vu') or attrs.get('package_name')
                
                # Final fallback: generate auto ID
                if not service_id or service_id.strip() == "":
                    service_id = f"PACKAGE_{idx:03d}"
                    logger.warning(f"[{request_id}] Package {idx} missing service ID, using auto-generated: {service_id}")

                # Do not include 'Nhà mạng' or 'Loại dịch vụ' in output; promote other attributes
                pkg_flat: Dict[str, Any] = {
                    "name": service_id,
                }

                # Promote attribute keys to top-level, skipping keys already present
                if isinstance(attrs, dict):
                    for k, v in attrs.items():
                        # skip keys that duplicate primary fields
                        if k in ("name", "partner_name", "service_type", "attributes", "Mã dịch vụ", "ma_dich_vu", "Nhà mạng", "Loại dịch vụ"):
                            continue
                        # if key already exists at top-level, do not overwrite
                        if k in pkg_flat and pkg_flat[k] is not None:
                            continue
                        pkg_flat[k] = v

                packages_list.append(pkg_flat)
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"[{request_id}] Extracted {len(packages_list)} packages in {elapsed_ms:.0f}ms")
            
            # Return JSON response
            return ExtractionResponse(
                id=request_id,
                extraction_date=datetime.now().isoformat(),
                total_packages=len(packages_list),
                packages=[TelecomPackage(**pkg) for pkg in packages_list]
            )
            
        finally:
            os.unlink(tmp_path)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{request_id}] Extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser(description="Telecom API")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--reload", action="store_true")
    
    args = parser.parse_args()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║       Telecom Package Extraction API                         ║
╠══════════════════════════════════════════════════════════════╣
║  Server: http://{args.host}:{args.port}                      ║
║  Docs:   http://{args.host}:{args.port}/docs                 ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "telecom_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )
