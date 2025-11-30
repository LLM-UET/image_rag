"""
Data Cleaner - Utilities for cleaning and preprocessing Upstage OCR output.

This module provides functions to clean and normalize Upstage Layout Analyzer
JSON output into clean Markdown text suitable for LLM processing.
"""
import json
import logging
import re
from typing import Dict, Any, Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_upstage_json(json_data: Dict[str, Any]) -> str:
    """
    Clean and extract text content from Upstage Layout Analyzer JSON output.
    
    Priority order:
    1. Try to access merged_documents.content (Markdown format) - preferred
    2. Fallback to elements array and join text fields
    3. Fallback to raw_text array if available
    
    Args:
        json_data: Raw JSON dictionary from Upstage Layout Analyzer
        
    Returns:
        Clean Markdown string with extracted content
        
    Example:
        >>> with open('document.json', 'r') as f:
        ...     data = json.load(f)
        >>> clean_text = clean_upstage_json(data)
    """
    content_parts = []
    
    # Strategy 1: Check for merged_documents (highest priority)
    if 'merged_documents' in json_data:
        merged_docs = json_data['merged_documents']
        if isinstance(merged_docs, list):
            for doc in merged_docs:
                if isinstance(doc, dict) and 'content' in doc:
                    content_parts.append(doc['content'])
                elif isinstance(doc, str):
                    content_parts.append(doc)
        elif isinstance(merged_docs, dict) and 'content' in merged_docs:
            content_parts.append(merged_docs['content'])
        
        if content_parts:
            logger.info("Extracted content from merged_documents")
            return _clean_markdown('\n\n'.join(content_parts))
    
    # Strategy 2: Check for elements array
    if 'elements' in json_data and isinstance(json_data['elements'], list):
        for element in json_data['elements']:
            if isinstance(element, dict):
                # Extract text from various possible fields
                text = element.get('text') or element.get('content') or ''
                if text.strip():
                    content_parts.append(text.strip())
        
        if content_parts:
            logger.info(f"Extracted content from {len(content_parts)} elements")
            return _clean_markdown('\n\n'.join(content_parts))
    
    # Strategy 3: Check for raw_text array (common in our processed files)
    if 'raw_text' in json_data and isinstance(json_data['raw_text'], list):
        for page_data in json_data['raw_text']:
            if isinstance(page_data, dict):
                text = page_data.get('text', '')
                if text.strip():
                    content_parts.append(text.strip())
        
        if content_parts:
            logger.info(f"Extracted content from {len(content_parts)} raw_text pages")
            return _clean_markdown('\n\n'.join(content_parts))
    
    # Strategy 4: Check for pages array
    if 'pages' in json_data and isinstance(json_data['pages'], list):
        for page in json_data['pages']:
            if isinstance(page, dict):
                text = page.get('text') or page.get('content') or ''
                if text.strip():
                    content_parts.append(text.strip())
        
        if content_parts:
            logger.info(f"Extracted content from {len(content_parts)} pages")
            return _clean_markdown('\n\n'.join(content_parts))
    
    # Strategy 5: Check for image_descriptions (additional context)
    image_descriptions = []
    if 'image_descriptions' in json_data:
        for img in json_data.get('image_descriptions', []):
            if isinstance(img, dict) and 'content' in img:
                image_descriptions.append(img['content'])
    
    # If we have image descriptions but no main content, use them
    if not content_parts and image_descriptions:
        logger.info(f"Using {len(image_descriptions)} image descriptions as content")
        return _clean_markdown('\n\n'.join(image_descriptions))
    
    # Append image descriptions to main content if both exist
    if content_parts and image_descriptions:
        content_parts.extend(image_descriptions)
    
    if content_parts:
        return _clean_markdown('\n\n'.join(content_parts))
    
    logger.warning("No content found in JSON data")
    return ""


def _clean_markdown(text: str) -> str:
    """
    Clean and normalize Markdown text.
    
    Args:
        text: Raw markdown text
        
    Returns:
        Cleaned markdown text
    """
    if not text:
        return ""
    
    # Remove excessive newlines (more than 2 consecutive)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Clean up table formatting issues
    # Fix malformed table cells with <br> tags
    text = re.sub(r'<br\s*/?>', ' ', text)
    
    # Remove empty table cells markers
    text = re.sub(r'\|\s*\|', '| |', text)
    
    # Normalize whitespace within table cells
    text = re.sub(r'\|\s+', '| ', text)
    text = re.sub(r'\s+\|', ' |', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def clean_readable_txt(file_path: str) -> str:
    """
    Read and clean a _readable.txt file (our processed format).
    
    Args:
        file_path: Path to the _readable.txt file
        
    Returns:
        Cleaned text content
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return _clean_markdown(content)
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return ""


def load_and_clean_json(file_path: str) -> str:
    """
    Load JSON file and clean its content.
    
    Args:
        file_path: Path to JSON file (Upstage output or extracted_content.json)
        
    Returns:
        Cleaned text content
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        return clean_upstage_json(json_data)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {file_path}: {e}")
        return ""
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return ""


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison and matching.
    
    Args:
        text: Input text
        
    Returns:
        Normalized text
    """
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Strip
    text = text.strip()
    
    return text


def extract_document_metadata(json_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract metadata from Upstage JSON for document context.
    
    Args:
        json_data: Raw JSON from Upstage or our processed format
        
    Returns:
        Dictionary with document metadata
    """
    metadata = {
        'pdf_name': json_data.get('pdf_name', ''),
        'extraction_date': json_data.get('extraction_date', ''),
        'num_pages': 0,
        'num_images': 0,
    }
    
    # Extract statistics if available
    if 'statistics' in json_data:
        stats = json_data['statistics']
        metadata['num_pages'] = stats.get('num_pages', 0)
        metadata['num_images'] = stats.get('num_images', 0)
    
    # Check for page count in raw_text
    if 'raw_text' in json_data:
        metadata['num_pages'] = len(json_data['raw_text'])
    
    return metadata


if __name__ == "__main__":
    # Test with a sample file
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        
        if file_path.endswith('.json'):
            content = load_and_clean_json(file_path)
        else:
            content = clean_readable_txt(file_path)
        
        print("=" * 60)
        print("CLEANED CONTENT")
        print("=" * 60)
        print(content[:2000] if len(content) > 2000 else content)
        print(f"\n... Total length: {len(content)} characters")
    else:
        print("Usage: python cleaner.py <path_to_json_or_txt>")
