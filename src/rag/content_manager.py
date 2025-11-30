import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from langchain_core.documents import Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    
    def default(self, obj):
        # Handle common non-serializable types
        if hasattr(obj, '__dict__'):
            return str(obj)
        elif hasattr(obj, 'to_dict'):
            return obj.to_dict()
        elif isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


def clean_for_json(data: Any) -> Any:
    """
    Recursively clean data structure to make it JSON serializable.
    
    Args:
        data: Data to clean
        
    Returns:
        Cleaned data safe for JSON serialization
    """
    if isinstance(data, dict):
        return {k: clean_for_json(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [clean_for_json(item) for item in data]
    elif isinstance(data, (str, int, float, bool, type(None))):
        return data
    elif hasattr(data, 'to_dict'):
        return clean_for_json(data.to_dict())
    elif hasattr(data, '__dict__'):
        return str(data)
    else:
        # For any other type, convert to string
        return str(data)


class ContentManager:
    """Manage extracted content from PDFs - save and load capabilities."""
    
    def __init__(self, output_dir: str = "data/processed"):
        """
        Initialize ContentManager.
        
        Args:
            output_dir: Directory to save/load extracted content
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def save_extracted_content(
        self,
        pdf_name: str,
        md_text: List[Dict[str, Any]],
        image_descriptions: List[Document],
        merged_docs: List[Document],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save all extracted content to a JSON file.
        
        Args:
            pdf_name: Name of the source PDF (without extension)
            md_text: Raw markdown text extracted from PDF
            image_descriptions: Image description documents
            merged_docs: Final merged documents
            metadata: Optional additional metadata
            
        Returns:
            Path to the saved file
        """
        logger.info(f"Saving extracted content for {pdf_name}...")
        
        # Prepare data structure and clean for JSON serialization
        content_data = {
            "pdf_name": pdf_name,
            "extraction_date": datetime.now().isoformat(),
            "metadata": clean_for_json(metadata or {}),
            "statistics": {
                "num_pages": len(md_text),
                "num_images": len(image_descriptions),
                "num_merged_docs": len(merged_docs)
            },
            "raw_text": clean_for_json(md_text),
            "image_descriptions": [
                {
                    "content": doc.page_content,
                    "metadata": clean_for_json(doc.metadata)
                }
                for doc in image_descriptions
            ],
            "merged_documents": [
                {
                    "content": doc.page_content,
                    "metadata": clean_for_json(doc.metadata)
                }
                for doc in merged_docs
            ]
        }
        
        # Save to JSON file with custom encoder
        output_file = self.output_dir / f"{pdf_name}_extracted_content.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(content_data, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
        
        logger.info(f"✅ Saved extracted content to {output_file}")
        
        # Also save a human-readable text version
        self._save_readable_version(pdf_name, content_data)
        
        return str(output_file)
    
    def _save_readable_version(self, pdf_name: str, content_data: Dict[str, Any]):
        """
        Save a human-readable text version of the extracted content.
        
        Args:
            pdf_name: Name of the PDF
            content_data: Extracted content data
        """
        output_file = self.output_dir / f"{pdf_name}_readable.txt"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write(f"EXTRACTED CONTENT: {pdf_name}\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Extraction Date: {content_data['extraction_date']}\n")
            f.write(f"Total Pages: {content_data['statistics']['num_pages']}\n")
            f.write(f"Total Images: {content_data['statistics']['num_images']}\n")
            f.write(f"Merged Documents: {content_data['statistics']['num_merged_docs']}\n\n")
            
            f.write("="*80 + "\n")
            f.write("CONTENT BY PAGE\n")
            f.write("="*80 + "\n\n")
            
            # Write merged content (text + image descriptions combined by page)
            for i, doc in enumerate(content_data['merged_documents'], 1):
                f.write(f"\n{'='*80}\n")
                f.write(f"PAGE {doc['metadata'].get('page', i)}\n")
                f.write(f"{'='*80}\n\n")
                f.write(doc['content'])
                f.write("\n\n")
            
            f.write("\n" + "="*80 + "\n")
            f.write("IMAGE DESCRIPTIONS (DETAILED)\n")
            f.write("="*80 + "\n\n")
            
            for i, img_doc in enumerate(content_data['image_descriptions'], 1):
                f.write(f"\n--- Image {i} (Page {img_doc['metadata'].get('page', 'N/A')}) ---\n")
                f.write(img_doc['content'])
                f.write("\n")
        
        logger.info(f"✅ Saved readable version to {output_file}")
    
    def load_extracted_content(self, pdf_name: str) -> Dict[str, Any]:
        """
        Load previously extracted content from JSON file.
        
        Args:
            pdf_name: Name of the PDF (without extension)
            
        Returns:
            Dictionary with extracted content and reconstructed Documents
        """
        logger.info(f"Loading extracted content for {pdf_name}...")
        
        input_file = self.output_dir / f"{pdf_name}_extracted_content.json"
        
        if not input_file.exists():
            raise FileNotFoundError(f"Extracted content file not found: {input_file}")
        
        # Load JSON data
        with open(input_file, 'r', encoding='utf-8') as f:
            content_data = json.load(f)
        
        # Reconstruct Document objects
        image_descriptions = [
            Document(
                page_content=doc["content"],
                metadata=doc["metadata"]
            )
            for doc in content_data["image_descriptions"]
        ]
        
        merged_docs = [
            Document(
                page_content=doc["content"],
                metadata=doc["metadata"]
            )
            for doc in content_data["merged_documents"]
        ]
        
        logger.info(f"✅ Loaded {len(merged_docs)} documents for {pdf_name}")
        
        return {
            "pdf_name": content_data["pdf_name"],
            "extraction_date": content_data["extraction_date"],
            "metadata": content_data["metadata"],
            "statistics": content_data["statistics"],
            "raw_text": content_data["raw_text"],
            "image_descriptions": image_descriptions,
            "merged_docs": merged_docs
        }
    
    def list_available_contents(self) -> List[str]:
        """
        List all available extracted content files.
        
        Returns:
            List of PDF names with saved content
        """
        json_files = list(self.output_dir.glob("*_extracted_content.json"))
        pdf_names = [f.stem.replace("_extracted_content", "") for f in json_files]
        return sorted(pdf_names)
    
    def get_content_info(self, pdf_name: str) -> Dict[str, Any]:
        """
        Get information about extracted content without loading full data.
        
        Args:
            pdf_name: Name of the PDF
            
        Returns:
            Dictionary with content statistics and metadata
        """
        input_file = self.output_dir / f"{pdf_name}_extracted_content.json"
        
        if not input_file.exists():
            raise FileNotFoundError(f"Extracted content file not found: {input_file}")
        
        with open(input_file, 'r', encoding='utf-8') as f:
            content_data = json.load(f)
        
        return {
            "pdf_name": content_data["pdf_name"],
            "extraction_date": content_data["extraction_date"],
            "statistics": content_data["statistics"],
            "metadata": content_data["metadata"],
            "file_path": str(input_file)
        }


def save_content(
    pdf_name: str,
    md_text: List[Dict[str, Any]],
    image_descriptions: List[Document],
    merged_docs: List[Document],
    output_dir: str = "data/processed"
) -> str:
    """
    Convenience function to save extracted content.
    
    Args:
        pdf_name: Name of the PDF
        md_text: Raw text extraction
        image_descriptions: Image description documents
        merged_docs: Merged documents
        output_dir: Output directory
        
    Returns:
        Path to saved file
    """
    manager = ContentManager(output_dir)
    return manager.save_extracted_content(
        pdf_name, md_text, image_descriptions, merged_docs
    )


def load_content(pdf_name: str, output_dir: str = "data/processed") -> Dict[str, Any]:
    """
    Convenience function to load extracted content.
    
    Args:
        pdf_name: Name of the PDF
        output_dir: Directory with saved content
        
    Returns:
        Dictionary with loaded content
    """
    manager = ContentManager(output_dir)
    return manager.load_extracted_content(pdf_name)


if __name__ == "__main__":
    # Example usage
    print("Content Manager Module")
    print("=" * 50)
    print("This module saves and loads extracted PDF content.")
    print("\nFeatures:")
    print("  - Save extracted text and image descriptions to JSON")
    print("  - Load content without reprocessing PDF")
    print("  - Generate human-readable text versions")
    print("  - List available extracted contents")
    print("\nUsage:")
    print("  from content_manager import ContentManager")
    print("  manager = ContentManager()")
    print("  manager.save_extracted_content(pdf_name, text, images, merged)")
    print("  content = manager.load_extracted_content(pdf_name)")
