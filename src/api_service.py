"""
FastAPI Service for Image RAG - Package Extraction from PDF
Endpoint: POST /extract-packages
Port: 8001
"""
import logging
import tempfile
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from pdf_processor import PDFProcessor
from package_extractor import PackageExtractor, TelcoPackage
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Telco Package Extraction API",
    description="AI-powered PDF analysis for telecommunication package extraction",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Pydantic Models (matching MySQL schema in data.md)
# ============================================================================

class PackageMetadataField(BaseModel):
    """Single field definition for package metadata interpretation"""
    fieldName: str = Field(..., description="Key used in metadata JSON (e.g., 'data_limit')")
    fieldLocalName: str = Field(..., description="Human-readable name (Vietnamese, e.g., 'Lưu lượng data')")
    fieldInterpretation: str = Field(..., description="Detailed semantic meaning for LLM reasoning")


class PackageData(BaseModel):
    """
    Extracted package information matching Package entity in MySQL.
    Maps to: packages table
    """
    id: Optional[int] = Field(None, description="MySQL AUTO_INCREMENT id (generated if null)")
    name: str = Field(..., description="Package name (e.g., 'SD70', 'V120')")
    metadata: dict = Field(
        default_factory=dict,
        description="Dynamic JSON containing package details (data_limit, voice_minutes, price, etc.)"
    )
    metadataInterpretations: Optional[List[PackageMetadataField]] = Field(
        default=None,
        description="Optional: definitions of metadata keys for AI reasoning"
    )
    createdAt: Optional[datetime] = Field(
        default_factory=datetime.now,
        description="Extraction timestamp"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "SD70",
                "metadata": {
                    "price": "70000",
                    "data_limit": "3",
                    "data_unit": "GB/day",
                    "voice_minutes": "unlimited",
                    "validity_days": "30",
                    "sms_count": "50"
                },
                "metadataInterpretations": [
                    {
                        "fieldName": "data_limit",
                        "fieldLocalName": "Lưu lượng data",
                        "fieldInterpretation": "Amount of high-speed 4G/5G data per day in gigabytes"
                    }
                ]
            }
        }


class ExtractionResponse(BaseModel):
    """Response wrapper for extraction results"""
    success: bool
    packages: List[PackageData]
    totalPackages: int
    sourceFileName: str
    extractedAt: datetime = Field(default_factory=datetime.now)
    warnings: Optional[List[str]] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str
    localLLM: bool
    localEmbeddings: bool


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_model=HealthResponse)
async def root():
    """Service info and health check"""
    return HealthResponse(
        status="healthy",
        service="Telco Package Extraction API",
        version="1.0.0",
        localLLM=settings.local_llm,
        localEmbeddings=settings.local_embeddings
    )


@app.get("/health")
async def health_check():
    """Lightweight health check"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/extract-packages", response_model=ExtractionResponse)
async def extract_packages(
    file: UploadFile = File(..., description="PDF file containing package information")
):
    """
    Extract telecommunication package information from uploaded PDF.
    
    Process:
    1. Receive PDF file
    2. Extract text using PDFProcessor (markdown format)
    3. Use AI (StructuredDataExtractor) to identify packages
    4. Return structured JSON matching MySQL packages table schema
    
    Args:
        file: PDF file upload
        
    Returns:
        ExtractionResponse with list of PackageData objects
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    temp_path = None
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            content = await file.read()
            tmp.write(content)
            temp_path = Path(tmp.name)
        
        logger.info(f"Processing PDF: {file.filename} ({len(content)} bytes)")
        
        # Step 1: Extract text from PDF
        pdf_processor = PDFProcessor(str(temp_path))
        md_text = pdf_processor.extract_text_to_markdown(
            page_chunks=True,
            show_progress=False
        )
        
        logger.info(f"Extracted {len(md_text)} pages from PDF")
        
        # Step 2: Extract package information using AI
        package_extractor = PackageExtractor()
        packages = package_extractor.extract_packages_from_pages(md_text)
        
        logger.info(f"Extracted {len(packages)} packages")
        
        # Step 3: Build response
        warnings = []
        if not packages:
            warnings.append("No packages detected in the PDF. Check if the document contains package information.")
        
        return ExtractionResponse(
            success=True,
            packages=packages,
            totalPackages=len(packages),
            sourceFileName=file.filename,
            warnings=warnings if warnings else None
        )
        
    except Exception as e:
        logger.error(f"Error processing PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")
    
    finally:
        # Cleanup temporary file
        if temp_path and temp_path.exists():
            temp_path.unlink()


@app.post("/extract-packages-batch")
async def extract_packages_batch(
    files: List[UploadFile] = File(..., description="Multiple PDF files")
):
    """
    Extract packages from multiple PDFs in batch.
    Returns aggregated results.
    """
    all_packages = []
    results = []
    
    for file in files:
        try:
            result = await extract_packages(file)
            results.append({
                "filename": file.filename,
                "success": True,
                "packageCount": result.totalPackages
            })
            all_packages.extend(result.packages)
        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
    
    return {
        "success": True,
        "totalFiles": len(files),
        "totalPackages": len(all_packages),
        "packages": all_packages,
        "fileResults": results
    }


# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Telco Package Extraction API on port 8001...")
    logger.info(f"Local LLM: {settings.local_llm}, Local Embeddings: {settings.local_embeddings}")
    
    uvicorn.run(
        "api_service:app",
        host="0.0.0.0",
        port=8001,
        reload=True,  # Enable auto-reload during development
        log_level="info"
    )
