"""
PDF processing module for extracting text and images from PDF documents.
"""
import pymupdf4llm
from typing import List, Dict, Any, Optional
from pathlib import Path
from tqdm import tqdm
import logging

from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFProcessor:
    """Process PDF documents to extract text and metadata."""
    
    def __init__(self, file_path: str):
        """
        Initialize PDF processor.
        
        Args:
            file_path: Path to the PDF file
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        self.md_text = None
        
    def extract_text_to_markdown(
        self,
        page_chunks: bool = True,
        show_progress: bool = True,
        pages: Optional[List[int]] = None,
        write_images: bool = False,
        embed_images: bool = False,
        image_size_limit: Optional[float] = None,
        dpi: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract text content from PDF and convert to markdown format.
        
        Args:
            page_chunks: If True, output is a list of page-specific dictionaries
            show_progress: Display progress bar during processing
            pages: Optional list of 0-based page numbers to process
            write_images: Save images found in the document as files
            embed_images: Embed images directly as base64 in markdown
            image_size_limit: Exclude small images below this size threshold
            dpi: Image resolution in dots per inch
            
        Returns:
            List of dictionaries containing markdown text and metadata per page
        """
        logger.info(f"Extracting text from PDF: {self.file_path}")
        
        # Set default values from settings if not provided
        if image_size_limit is None:
            image_size_limit = settings.image_size_limit
        if dpi is None:
            dpi = settings.image_dpi
        
        self.md_text = pymupdf4llm.to_markdown(
            doc=str(self.file_path),
            page_chunks=page_chunks,
            show_progress=show_progress,
            pages=pages,
            write_images=write_images,
            embed_images=embed_images,
            image_size_limit=image_size_limit,
            dpi=dpi,
        )
        
        logger.info(f"Extracted {len(self.md_text)} pages")
        return self.md_text
    
    def get_page_content(self, page_number: int) -> Optional[str]:
        """
        Get content of a specific page.
        
        Args:
            page_number: Page number (0-based)
            
        Returns:
            Page content as string, or None if page doesn't exist
        """
        if self.md_text is None:
            raise ValueError("Text not extracted yet. Call extract_text_to_markdown first.")
        
        if 0 <= page_number < len(self.md_text):
            return self.md_text[page_number]['text']
        return None
    
    def get_all_pages(self) -> List[Dict[str, Any]]:
        """
        Get all extracted pages.
        
        Returns:
            List of dictionaries containing text and metadata for all pages
        """
        if self.md_text is None:
            raise ValueError("Text not extracted yet. Call extract_text_to_markdown first.")
        
        return self.md_text
    
    def save_markdown(self, output_path: str) -> None:
        """
        Save extracted markdown to a file.
        
        Args:
            output_path: Path to save the markdown file
        """
        if self.md_text is None:
            raise ValueError("Text not extracted yet. Call extract_text_to_markdown first.")
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for page in self.md_text:
                f.write(f"\n{'='*80}\n")
                f.write(f"PAGE {page['metadata']['page']}\n")
                f.write(f"{'='*80}\n\n")
                f.write(page['text'])
                f.write("\n\n")
        
        logger.info(f"Markdown saved to: {output_file}")


def process_pdf_file(pdf_path: str, extract_images: bool = False) -> List[Dict[str, Any]]:
    """
    Convenience function to process a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        extract_images: Whether to extract images
        
    Returns:
        List of page dictionaries with text and metadata
    """
    processor = PDFProcessor(pdf_path)
    md_text = processor.extract_text_to_markdown(
        page_chunks=True,
        show_progress=True,
        write_images=extract_images,
        embed_images=False,
    )
    return md_text


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        processor = PDFProcessor(pdf_file)
        md_text = processor.extract_text_to_markdown()
        
        # Print first 3 pages preview
        for page_num, page_data in enumerate(md_text[:3]):
            print(f"\n📄 **Page {page_num + 1}**")
            print("=" * 50)
            print(page_data['text'][:200] + "...")
    else:
        print("Usage: python pdf_processor.py <path_to_pdf>")
