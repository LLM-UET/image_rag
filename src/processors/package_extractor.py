"""
Package Extractor - Specialized extractor for Telecom Package Information
Extends StructuredDataExtractor with telco-specific prompts and models.
"""
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag.structured_extractor import StructuredDataExtractor
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pydantic models for package extraction
class PackageMetadataField(BaseModel):
    """Definition of a metadata field"""
    fieldName: str = Field(description="Technical field name (snake_case)")
    fieldLocalName: str = Field(description="Vietnamese display name")
    fieldInterpretation: str = Field(description="Semantic meaning for AI reasoning")


class TelcoPackage(BaseModel):
    """Telecommunication package structure matching MySQL schema"""
    name: str = Field(description="Package code/name (e.g., 'SD70', 'V120')")
    metadata: Dict[str, Any] = Field(
        description="Dynamic package attributes (price, data_limit, validity_days, etc.)"
    )
    metadataInterpretations: Optional[List[PackageMetadataField]] = Field(
        default=None,
        description="Field definitions for AI context"
    )


class PackageExtractor(StructuredDataExtractor):
    """Specialized extractor for telecommunication packages"""
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize package extractor with telco-optimized prompts.
        
        Args:
            model_name: LLM model name (uses parent class initialization)
        """
        super().__init__(model_name)
        
        # Package-specific extraction prompt
        self.package_extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at extracting telecommunication package information from Vietnamese documents.

TASK: Extract ALL data packages, voice packages, and combo packages from the provided text.

REQUIRED OUTPUT FORMAT (JSON only):
{{
  "packages": [
    {{
      "name": "PACKAGE_CODE",
      "metadata": {{
        "price": "monthly_price_in_VND",
        "data_limit": "data_amount",
        "data_unit": "GB/day or GB/month",
        "voice_minutes": "number or 'unlimited'",
        "validity_days": "30 or 365",
        "sms_count": "number",
        "description": "brief_description",
        "special_features": "any_special_notes"
      }},
      "metadataInterpretations": [
        {{
          "fieldName": "price",
          "fieldLocalName": "Giá gói cước",
          "fieldInterpretation": "Monthly subscription fee in Vietnamese Dong (VND)"
        }},
        {{
          "fieldName": "data_limit",
          "fieldLocalName": "Lưu lượng data",
          "fieldInterpretation": "Amount of high-speed 4G/5G data included in the package"
        }},
        {{
          "fieldName": "validity_days",
          "fieldLocalName": "Chu kỳ",
          "fieldInterpretation": "Package validity period in days (30 = monthly, 365 = yearly)"
        }}
      ]
    }}
  ]
}}

EXTRACTION RULES:
1. Extract package code/name exactly as written (e.g., "SD70", "V120", "MAX200")
2. Parse price: remove currency symbols, keep only numbers
3. Data amounts: convert to standardized units (GB/day or GB/month)
4. Voice minutes: use "unlimited" if text indicates no limit
5. Validity: extract cycle period (usually 30 days for monthly)
6. Include special features like "Miễn phí cuộc gọi nội mạng", "Data tốc độ cao", etc.
7. If a field is not mentioned, omit it from metadata
8. Generate metadataInterpretations for ALL fields you extract

IMPORTANT: Return ONLY the JSON object. No explanations, no markdown code fences."""),
            ("human", "Text to analyze:\n\n{{content}}")
        ])
    
    def extract_packages_from_pages(
        self,
        md_text: List[Dict[str, Any]],
        max_pages: Optional[int] = None
    ) -> List[TelcoPackage]:
        """
        Extract packages from PDF pages (markdown format from PDFProcessor).
        
        Args:
            md_text: List of page dictionaries from PDFProcessor.extract_text_to_markdown()
            max_pages: Limit number of pages to process
            
        Returns:
            List of TelcoPackage objects
        """
        logger.info("Extracting telecommunication packages from document...")
        
        all_packages = []
        pages_to_process = md_text[:max_pages] if max_pages else md_text
        
        for i, page_dict in enumerate(pages_to_process):
            try:
                page_content = page_dict.get('text', '')
                if not page_content.strip():
                    continue
                
                # Format prompt
                messages = self.package_extraction_prompt.format_messages(
                    content=page_content
                )
                
                # Invoke LLM (handle local vs remote)
                if hasattr(self.llm, 'pipe'):  # LocalLLM
                    prompt_text = "\n\n".join([m.content for m in messages])
                    response = self.llm.invoke(prompt_text)
                else:
                    response = self.llm.invoke(messages)
                
                output = response.content
                
                # Parse JSON output
                parsed_data = self._safe_parse_json(output)
                
                if parsed_data and 'packages' in parsed_data:
                    page_packages = parsed_data['packages']
                    logger.info(f"Page {i+1}: Found {len(page_packages)} packages")
                    
                    # Convert to TelcoPackage objects
                    for pkg_data in page_packages:
                        try:
                            package = TelcoPackage(**pkg_data)
                            all_packages.append(package)
                        except Exception as e:
                            logger.warning(f"Failed to parse package: {e}, data: {pkg_data}")
                else:
                    logger.debug(f"Page {i+1}: No packages found or parse failed")
                    
            except Exception as e:
                logger.error(f"Error processing page {i+1}: {e}")
                continue
        
        # Deduplicate packages by name
        unique_packages = self._deduplicate_packages(all_packages)
        
        logger.info(f"Total packages extracted: {len(unique_packages)}")
        return unique_packages
    
    def _safe_parse_json(self, text: str) -> Optional[Dict]:
        """
        Safely parse JSON with multiple fallback strategies.
        
        Args:
            text: Raw text that might contain JSON
            
        Returns:
            Parsed dict or None
        """
        # Try direct parse
        try:
            return json.loads(text)
        except:
            pass
        
        # Try extracting JSON between first { and last }
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = text[start:end+1]
                return json.loads(json_str)
        except:
            pass
        
        # Try replacing single quotes with double quotes (naive fix)
        try:
            fixed = text.replace("'", '"')
            return json.loads(fixed)
        except:
            pass
        
        logger.warning(f"Failed to parse JSON from LLM output: {text[:200]}")
        return None
    
    def _deduplicate_packages(self, packages: List[TelcoPackage]) -> List[TelcoPackage]:
        """
        Remove duplicate packages (same name).
        Keep the first occurrence.
        
        Args:
            packages: List of packages
            
        Returns:
            Deduplicated list
        """
        seen_names = set()
        unique = []
        
        for pkg in packages:
            if pkg.name not in seen_names:
                seen_names.add(pkg.name)
                unique.append(pkg)
            else:
                logger.debug(f"Skipping duplicate package: {pkg.name}")
        
        return unique
    
    def extract_packages_from_text(self, text: str) -> List[TelcoPackage]:
        """
        Convenience method to extract packages from plain text.
        
        Args:
            text: Raw text content
            
        Returns:
            List of TelcoPackage objects
        """
        # Convert plain text to the expected format
        md_text = [{"text": text, "metadata": {"page": 1}}]
        return self.extract_packages_from_pages(md_text)


# Convenience function
def extract_packages_from_pdf(pdf_path: str, max_pages: Optional[int] = None) -> List[TelcoPackage]:
    """
    End-to-end extraction: PDF → packages.
    
    Args:
        pdf_path: Path to PDF file
        max_pages: Limit processing to N pages
        
    Returns:
        List of TelcoPackage objects
    """
    from pdf_processor import PDFProcessor
    
    logger.info(f"Processing PDF: {pdf_path}")
    
    # Extract text
    processor = PDFProcessor(pdf_path)
    md_text = processor.extract_text_to_markdown(page_chunks=True, show_progress=True)
    
    # Extract packages
    extractor = PackageExtractor()
    packages = extractor.extract_packages_from_pages(md_text, max_pages=max_pages)
    
    return packages


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        packages = extract_packages_from_pdf(pdf_file)
        
        print(f"\n{'='*60}")
        print(f"EXTRACTED {len(packages)} PACKAGES")
        print(f"{'='*60}\n")
        
        for i, pkg in enumerate(packages, 1):
            print(f"{i}. {pkg.name}")
            print(f"   Metadata: {json.dumps(pkg.metadata, ensure_ascii=False, indent=6)}")
            print()
    else:
        print("Usage: python package_extractor.py <path_to_pdf>")
