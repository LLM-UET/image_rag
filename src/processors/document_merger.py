"""
Document merger module to combine text and image descriptions by page.
"""
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict
from langchain_core.documents import Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentMerger:
    """Merge text and image descriptions into unified documents."""
    
    @staticmethod
    def merge_text_and_images(
        md_text: List[Dict[str, Any]], 
        image_description_docs: List[Document]
    ) -> List[Document]:
        """
        Merge text content and image descriptions by page number.
        
        Args:
            md_text: List of page dictionaries from PyMuPDF4LLM
            image_description_docs: List of Documents with image descriptions
            
        Returns:
            List of merged Document objects with combined content per page
        """
        logger.info("Merging text and image descriptions...")
        
        # Create a dictionary to collect data by page
        page_contents = defaultdict(list)
        page_metadata = {}
        
        # Process md_text
        for text_item in md_text:
            # Standardize page numbers to integer
            page = int(text_item['metadata']['page'])
            page_contents[page].append(text_item['text'])
            
            # Save metadata for each page
            if page not in page_metadata:
                page_metadata[page] = {
                    'source': text_item['metadata']['file_path'],
                    'page': page
                }
        
        # Process image_description_docs
        for img_doc in image_description_docs:
            # Standardize page numbers to integer
            page = int(img_doc.metadata['page'])
            page_contents[page].append(f"\n[IMAGE DESCRIPTION]\n{img_doc.page_content}\n")
        
        # Create the final list of Document objects
        merged_docs = []
        for page in sorted(page_contents.keys()):
            # Combine all content of the page into a single string
            full_content = '\n\n'.join(page_contents[page])
            
            # Create a Document object
            doc = Document(
                page_content=full_content,
                metadata=page_metadata[page]
            )
            merged_docs.append(doc)
        
        logger.info(f"Merged {len(merged_docs)} pages")
        return merged_docs
    
    @staticmethod
    def merge_multiple_sources(
        text_docs: List[Document],
        image_docs: List[Document],
        table_docs: Optional[List[Document]] = None
    ) -> List[Document]:
        """
        Merge multiple types of documents by page.
        
        Args:
            text_docs: Documents containing text
            image_docs: Documents containing image descriptions
            table_docs: Optional documents containing table descriptions
            
        Returns:
            List of merged Document objects
        """
        logger.info("Merging multiple document sources...")
        
        # Organize by page
        page_contents = defaultdict(lambda: {
            'text': [],
            'images': [],
            'tables': [],
            'metadata': {}
        })
        
        # Process text documents
        for doc in text_docs:
            page = doc.metadata.get('page', 0)
            page_contents[page]['text'].append(doc.page_content)
            if not page_contents[page]['metadata']:
                page_contents[page]['metadata'] = doc.metadata
        
        # Process image documents
        for doc in image_docs:
            page = int(doc.metadata.get('page', 0))
            page_contents[page]['images'].append(doc.page_content)
        
        # Process table documents if provided
        if table_docs:
            for doc in table_docs:
                page = int(doc.metadata.get('page', 0))
                page_contents[page]['tables'].append(doc.page_content)
        
        # Create merged documents
        merged_docs = []
        for page in sorted(page_contents.keys()):
            contents = []
            
            # Add text content
            if page_contents[page]['text']:
                contents.extend(page_contents[page]['text'])
            
            # Add image descriptions
            if page_contents[page]['images']:
                contents.append("\n[IMAGE DESCRIPTIONS]")
                contents.extend(page_contents[page]['images'])
            
            # Add table descriptions
            if page_contents[page]['tables']:
                contents.append("\n[TABLE DESCRIPTIONS]")
                contents.extend(page_contents[page]['tables'])
            
            # Create merged document
            full_content = '\n\n'.join(contents)
            doc = Document(
                page_content=full_content,
                metadata=page_contents[page]['metadata']
            )
            merged_docs.append(doc)
        
        logger.info(f"Merged {len(merged_docs)} pages from multiple sources")
        return merged_docs


def merge_documents(
    text_data: List[Dict[str, Any]],
    image_data: List[Document]
) -> List[Document]:
    """
    Convenience function to merge text and image documents.
    
    Args:
        text_data: Text extraction results from PyMuPDF4LLM
        image_data: Image description documents
        
    Returns:
        List of merged Document objects
    """
    merger = DocumentMerger()
    return merger.merge_text_and_images(text_data, image_data)


if __name__ == "__main__":
    # Example usage
    print("Document Merger Module")
    print("=" * 50)
    print("This module merges text and image descriptions by page number.")
    print("\nUsage:")
    print("  from document_merger import merge_documents")
    print("  merged = merge_documents(text_data, image_data)")
