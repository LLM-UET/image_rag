"""
Telecom Document Service - Main orchestration module for the ETL pipeline.

This module provides:
- process_document(): End-to-end document processing
- Upstage API integration (or mock for testing)
- Pipeline orchestration: PDF → OCR → Clean → Extract → Structured Data
"""
import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import TelecomPackage, ExtractionResult
from core.cleaner import clean_upstage_json, clean_readable_txt, load_and_clean_json
from core.extractor import TelecomPackageExtractor, extract_package_info
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TelecomDocumentService:
    """
    Main service class for telecom document processing pipeline.
    
    Orchestrates: PDF → Upstage OCR → Data Cleaning → LLM Extraction → Structured Data
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        """
        Initialize the document service.
        
        Args:
            model_name: LLM model for extraction
        """
        self.model_name = model_name
        self.extractor = TelecomPackageExtractor(model_name=model_name)
        self.upstage_api_key = settings.upstage_api_key
        
        logger.info(f"TelecomDocumentService initialized with model: {model_name}")
    
    def process_document(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Process a document end-to-end and return extracted packages.
        
        Supports:
        - PDF files (calls Upstage API or uses existing processed files)
        - JSON files (Upstage output or _extracted_content.json)
        - TXT files (_readable.txt format)
        
        Args:
            file_path: Path to input file (PDF, JSON, or TXT)
            
        Returns:
            List of package dictionaries ready for MongoDB
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        logger.info(f"Processing document: {file_path}")
        
        # Step 1: Get/Load OCR content
        clean_text = self._load_content(file_path)
        
        if not clean_text:
            logger.error("Failed to extract content from document")
            return []
        
        logger.info(f"Loaded content: {len(clean_text)} characters")
        
        # Step 2: Extract packages using LLM
        packages = self.extractor.extract_package_info(clean_text)
        
        if not packages:
            logger.warning("No packages extracted from document")
            return []
        
        # Step 3: Convert to dictionaries with metadata
        result = self._packages_to_dicts(packages, str(file_path))
        
        logger.info(f"Successfully extracted {len(result)} packages")
        return result
    
    def _load_content(self, file_path: Path) -> str:
        """
        Load and clean content based on file type.
        
        Args:
            file_path: Path to file
            
        Returns:
            Cleaned text content
        """
        suffix = file_path.suffix.lower()

        # If suffix is unknown (.bin), try to detect by reading magic bytes
        if suffix == '.bin':
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(512)
                logger.info(f"Inspecting .bin file: {file_path}, header={header[:16]!r}")
                if header.startswith(b'%PDF'):
                    logger.info(f"Detected PDF content in .bin file: {file_path}")
                    return self._process_pdf(file_path)
                # Try to decode as text
                try:
                    text = header.decode('utf-8')
                    # Save renamed temp txt file and process as readable txt
                    tmp_txt = Path(str(file_path) + '.txt')
                    with open(tmp_txt, 'w', encoding='utf-8') as out:
                        # Write full content
                        with open(file_path, 'rb') as f:
                            out.write(f.read().decode('utf-8', errors='ignore'))
                    logger.info(f"Treating .bin as text file: {file_path}")
                    return clean_readable_txt(str(tmp_txt))
                except Exception as te:
                    logger.warning(f"Failed to decode .bin as text: {te}")
                    # Last resort: raise error
                    raise ValueError(f"Unsupported file type: .bin (not PDF, not text)")
            except ValueError:
                raise
            except Exception as e:
                logger.warning(f"Failed to inspect .bin file: {e}")
                raise ValueError(f"Unsupported file type: .bin (inspection failed: {e})")

        if suffix == '.pdf':
            return self._process_pdf(file_path)
        elif suffix == '.json':
            return load_and_clean_json(str(file_path))
        elif suffix == '.txt':
            return clean_readable_txt(str(file_path))
        else:
            raise ValueError(f"Unsupported file type: {suffix}")
    
    def _process_pdf(self, pdf_path: Path) -> str:
        """
        Process PDF file - either via Upstage API or existing processed files.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Cleaned text content
        """
        # Check for existing processed files first
        base_name = pdf_path.stem
        processed_dir = settings.processed_data_dir
        
        # Try to find existing processed content
        readable_file = processed_dir / f"{base_name}_readable.txt"
        json_file = processed_dir / f"{base_name}_extracted_content.json"
        
        if readable_file.exists():
            logger.info(f"Using existing readable file: {readable_file}")
            return clean_readable_txt(str(readable_file))
        
        if json_file.exists():
            logger.info(f"Using existing JSON file: {json_file}")
            return load_and_clean_json(str(json_file))
        
        # Call Upstage API if key is available
        if self.upstage_api_key:
            return self._call_upstage_api(pdf_path)
        else:
            logger.warning("No Upstage API key and no processed files found")
            return self._mock_upstage_response(pdf_path)
    
    def _call_upstage_api(self, pdf_path: Path) -> str:
        """
        Call Upstage Layout Analyzer API.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Cleaned text from API response
        """
        try:
            import requests
            
            url = "https://api.upstage.ai/v1/document-ai/layout-analyzer"
            headers = {"Authorization": f"Bearer {self.upstage_api_key}"}
            
            with open(pdf_path, 'rb') as f:
                files = {"document": f}
                response = requests.post(url, headers=headers, files=files)
            
            if response.status_code == 200:
                json_data = response.json()
                return clean_upstage_json(json_data)
            else:
                logger.error(f"Upstage API error: {response.status_code} - {response.text}")
                return ""
                
        except Exception as e:
            logger.error(f"Failed to call Upstage API: {e}")
            return ""
    
    def _mock_upstage_response(self, pdf_path: Path) -> str:
        """
        Mock Upstage response for testing without API key.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Empty string or mock content
        """
        logger.warning(f"Mock mode: No content extracted for {pdf_path}")
        return ""
    
    def _packages_to_dicts(
        self, 
        packages: List[TelecomPackage], 
        source_file: str
    ) -> List[Dict[str, Any]]:
        """
        Convert TelecomPackage objects to dictionaries.
        
        Args:
            packages: List of extracted packages
            source_file: Source document path
            
        Returns:
            List of dictionaries
        """
        result = []
        for pkg in packages:
            pkg_dict = pkg.model_dump()
            result.append(pkg_dict)
        
        return result


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def process_document(file_path: str, model_name: str = "gemini-2.0-flash-exp") -> List[Dict[str, Any]]:
    """
    Convenience function to process a document.
    
    Args:
        file_path: Path to input file (PDF, JSON, or TXT)
        model_name: LLM model for extraction
        
    Returns:
        List of package dictionaries
    """
    service = TelecomDocumentService(model_name=model_name)
    return service.process_document(file_path)


def process_multiple_documents(
    file_paths: List[str], 
    model_name: str = "gemini-2.0-flash-exp"
) -> List[Dict[str, Any]]:
    """
    Process multiple documents and combine results.
    
    Args:
        file_paths: List of file paths
        model_name: LLM model for extraction
        
    Returns:
        Combined list of package dictionaries
    """
    service = TelecomDocumentService(model_name=model_name)
    all_packages = []
    
    for file_path in file_paths:
        try:
            packages = service.process_document(file_path)
            all_packages.extend(packages)
            logger.info(f"Processed {file_path}: {len(packages)} packages")
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
    
    return all_packages


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        
        print(f"Processing: {input_file}")
        packages = process_document(input_file)
        
        print(f"\n{'='*60}")
        print(f"EXTRACTED {len(packages)} PACKAGES")
        print(f"{'='*60}\n")
        
        for i, pkg in enumerate(packages, 1):
            print(f"{i}. {pkg.get('name', pkg.get('package_name'))} ({pkg['partner_name']})")
            print(f"   Type: {pkg['service_type']}")
            print(f"   Attributes: {json.dumps(pkg['attributes'], ensure_ascii=False)}")
            print()
        
        # Optionally save to file
        if len(sys.argv) > 2:
            output_file = sys.argv[2]
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(packages, f, ensure_ascii=False, indent=2)
            print(f"Results saved to: {output_file}")
    else:
        print("Usage: python telecom_service.py <input_file> [output_file]")
