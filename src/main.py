"""
Main application script for Multimodal RAG system.
Provides CLI interface for processing PDFs and querying.
"""
import sys
import logging
from pathlib import Path
import argparse

# Ensure project root and src are on sys.path so imports like `config` work
# even when running this script from the `src/` directory.
project_root = Path(__file__).resolve().parent.parent
src_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_dir))

from processors.pdf_processor import PDFProcessor
from processors.image_processor import ImageDescriptionGenerator
from processors.document_merger import DocumentMerger
from rag.vector_store import VectorStoreManager
from rag.structured_extractor import StructuredDataExtractor
from rag.rag_pipeline import MultimodalRAGPipeline, ConversationalRAG
from rag.content_manager import ContentManager
from config.settings import settings, validate_api_keys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultimodalRAGApp:
    """Main application class for Multimodal RAG."""
    
    def __init__(self):
        """Initialize the application."""
        self.vector_store_manager = None
        self.rag_pipeline = None
        logger.info("Multimodal RAG Application initialized")
    
    def process_pdf(
        self,
        pdf_path: str,
        use_upstage: bool = True,
        extract_structured: bool = True,
        save_content: bool = True
    ):
        """
        Process a PDF file: extract text, images, and create vector store.
        
        Args:
            pdf_path: Path to the PDF file
            use_upstage: Whether to use Upstage API for image extraction
            extract_structured: Whether to extract structured data
            save_content: Whether to save extracted content for later regeneration
        """
        logger.info(f"Processing PDF: {pdf_path}")
        
        pdf_name = Path(pdf_path).stem
        
        # 1. Extract text from PDF
        logger.info("Step 1: Extracting text...")
        pdf_processor = PDFProcessor(pdf_path)
        md_text = pdf_processor.extract_text_to_markdown(
            page_chunks=True,
            show_progress=True
        )
        
        # 2. Extract and describe images
        logger.info("Step 2: Extracting and describing images...")
        image_processor = ImageDescriptionGenerator(use_upstage=use_upstage)
        
        if use_upstage:
            image_descriptions, upstage_docs = image_processor.process_pdf_images(pdf_path)
        else:
            # Alternative: Use unstructured library (not implemented in this version)
            logger.warning("Non-Upstage extraction not fully implemented. Using Upstage.")
            image_descriptions, upstage_docs = image_processor.process_pdf_images(pdf_path)
        
        # 3. Merge text and image descriptions
        logger.info("Step 3: Merging documents...")
        merger = DocumentMerger()
        merged_docs = merger.merge_text_and_images(md_text, image_descriptions)
        
        logger.info(f"Created {len(merged_docs)} merged documents")
        
        # 3.5. Save extracted content (NEW)
        if save_content:
            logger.info("Step 3.5: Saving extracted content...")
            content_manager = ContentManager(str(settings.processed_data_dir))
            content_file = content_manager.save_extracted_content(
                pdf_name=pdf_name,
                md_text=md_text,
                image_descriptions=image_descriptions,
                merged_docs=merged_docs,
                metadata={
                    "source_pdf": pdf_path,
                    "use_upstage": use_upstage
                }
            )
            logger.info(f"Content saved to {content_file}")
        
        # 4. Create vector store
        logger.info("Step 4: Creating vector store...")
        self.vector_store_manager = VectorStoreManager()
        self.vector_store_manager.create_vector_store(merged_docs, split=True)
        
        logger.info("Vector store created successfully")
        
        # 5. Extract structured data (optional)
        if extract_structured:
            logger.info("Step 5: Extracting structured data...")
            extractor = StructuredDataExtractor()
            structured_data = extractor.extract_structured_data(merged_docs)
            
            # Save structured data
            output_dir = settings.structured_data_dir
            pdf_name = Path(pdf_path).stem
            extractor.save_structured_data(
                structured_data,
                str(output_dir),
                filename=pdf_name
            )
            logger.info(f"Structured data saved to {output_dir}")
        
        # 6. Initialize RAG pipeline
        logger.info("Step 6: Initializing RAG pipeline...")
        self.rag_pipeline = MultimodalRAGPipeline(self.vector_store_manager)
        
        logger.info("✅ PDF processing complete!")
        
        return {
            "num_pages": len(merged_docs),
            "num_images": len(image_descriptions),
            "vector_store": self.vector_store_manager,
            "rag_pipeline": self.rag_pipeline
        }
    
    def load_existing_vector_store(self):
        """Load an existing vector store from disk."""
        logger.info("Loading existing vector store...")
        self.vector_store_manager = VectorStoreManager()
        self.vector_store_manager.load_vector_store()
        self.rag_pipeline = MultimodalRAGPipeline(self.vector_store_manager)
        logger.info("✅ Vector store loaded successfully")
    
    def regenerate_from_saved_content(
        self,
        pdf_name: str,
        extract_structured: bool = True
    ):
        """
        Regenerate vector store and structured data from saved extracted content.
        No need to reprocess the PDF.
        
        Args:
            pdf_name: Name of the PDF (without extension)
            extract_structured: Whether to extract structured data
        """
        logger.info(f"Regenerating from saved content: {pdf_name}")
        
        # 1. Load saved content
        logger.info("Step 1: Loading saved extracted content...")
        content_manager = ContentManager(str(settings.processed_data_dir))
        content = content_manager.load_extracted_content(pdf_name)
        
        merged_docs = content['merged_docs']
        
        logger.info(f"Loaded {len(merged_docs)} documents from saved content")
        logger.info(f"Original extraction date: {content['extraction_date']}")
        
        # 2. Create vector store
        logger.info("Step 2: Creating vector store...")
        self.vector_store_manager = VectorStoreManager()
        self.vector_store_manager.create_vector_store(merged_docs, split=True)
        
        logger.info("Vector store created successfully")
        
        # 3. Extract structured data (optional)
        if extract_structured:
            logger.info("Step 3: Extracting structured data...")
            extractor = StructuredDataExtractor()
            structured_data = extractor.extract_structured_data(merged_docs)
            
            # Save structured data
            output_dir = settings.structured_data_dir
            extractor.save_structured_data(
                structured_data,
                str(output_dir),
                filename=pdf_name
            )
            logger.info(f"Structured data saved to {output_dir}")
        
        # 4. Initialize RAG pipeline
        logger.info("Step 4: Initializing RAG pipeline...")
        self.rag_pipeline = MultimodalRAGPipeline(self.vector_store_manager)
        
        logger.info("✅ Regeneration complete!")
        
        return {
            "num_docs": len(merged_docs),
            "statistics": content['statistics'],
            "vector_store": self.vector_store_manager,
            "rag_pipeline": self.rag_pipeline
        }
    
    def query(self, question: str, show_sources: bool = True):
        """
        Query the RAG system.
        
        Args:
            question: User's question
            show_sources: Whether to show source documents
            
        Returns:
            Answer and optional sources
        """
        if self.rag_pipeline is None:
            raise ValueError("RAG pipeline not initialized. Process a PDF or load vector store first.")
        
        if show_sources:
            result = self.rag_pipeline.query_with_sources(question)
            return result
        else:
            result = self.rag_pipeline.query(question)
            return {"answer": result["answer"]}
    
    def interactive_mode(self):
        """Start interactive Q&A session."""
        if self.rag_pipeline is None:
            raise ValueError("RAG pipeline not initialized. Process a PDF or load vector store first.")
        
        conv_rag = ConversationalRAG(self.rag_pipeline)
        
        print("\n" + "="*60)
        print("🤖 Multimodal RAG - Interactive Mode")
        print("="*60)
        print("Ask questions about your PDF. Type 'quit' to exit, 'clear' to reset history.")
        print("="*60 + "\n")
        
        while True:
            try:
                question = input("You: ").strip()
                
                if not question:
                    continue
                
                if question.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye!")
                    break
                
                if question.lower() == 'clear':
                    conv_rag.reset_history()
                    print("✅ Chat history cleared.\n")
                    continue
                
                # Get answer
                answer = conv_rag.chat(question)
                print(f"\n🤖 Assistant: {answer}\n")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                print(f"\n❌ Error: {e}\n")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Multimodal RAG - Process PDFs and answer questions"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process a PDF file')
    process_parser.add_argument('pdf_path', help='Path to PDF file')
    process_parser.add_argument('--no-upstage', action='store_true', help='Disable Upstage API')
    process_parser.add_argument('--no-structured', action='store_true', help='Skip structured extraction')
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Query the system')
    query_parser.add_argument('question', help='Your question')
    query_parser.add_argument('--no-sources', action='store_true', help='Hide source documents')
    
    # Interactive command
    subparsers.add_parser('interactive', help='Start interactive mode')
    
    # Load command
    subparsers.add_parser('load', help='Load existing vector store')
    
    # Regenerate command (NEW)
    regen_parser = subparsers.add_parser('regenerate', help='Regenerate from saved extracted content')
    regen_parser.add_argument('pdf_name', help='Name of the PDF (without extension)')
    regen_parser.add_argument('--no-structured', action='store_true', help='Skip structured extraction')
    
    # List command (NEW)
    subparsers.add_parser('list', help='List available extracted contents')
    
    # Show command (NEW)
    show_parser = subparsers.add_parser('show', help='Show extracted content info')
    show_parser.add_argument('pdf_name', help='Name of the PDF (without extension)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Validate API keys
    try:
        validate_api_keys()
    except ValueError as e:
        print(f"❌ {e}")
        return
    
    # Initialize app
    app = MultimodalRAGApp()
    
    try:
        if args.command == 'process':
            result = app.process_pdf(
                args.pdf_path,
                use_upstage=not args.no_upstage,
                extract_structured=not args.no_structured
            )
            pdf_name = Path(args.pdf_path).stem
            print(f"\n✅ Successfully processed {result['num_pages']} pages")
            print(f"   Found {result['num_images']} images")
            print(f"\n📁 Extracted content saved to: data/processed/")
            print(f"   - JSON: {pdf_name}_extracted_content.json")
            print(f"   - Readable: {pdf_name}_readable.txt")
            print(f"\n💡 To view extracted content: notepad data\\processed\\{pdf_name}_readable.txt")
            print(f"   To regenerate later: python main.py regenerate {pdf_name}")
            print("\n🔍 You can now query with: python main.py query 'your question'")
            print("   Or start interactive mode: python main.py interactive")
        
        elif args.command == 'load':
            app.load_existing_vector_store()
            print("\n✅ Vector store loaded")
            print("You can now query with: python main.py query 'your question'")
        
        elif args.command == 'query':
            app.load_existing_vector_store()
            result = app.query(args.question, show_sources=not args.no_sources)
            
            print("\n" + "="*60)
            print(f"❓ Question: {args.question}")
            print("="*60)
            print(f"\n🤖 Answer:\n{result['answer']}\n")
            
            if 'sources' in result:
                print("📚 Sources:")
                for source in result['sources']:
                    print(f"  [{source['number']}] Page {source['page']}")
                    print(f"      {source['content_preview']}\n")
        
        elif args.command == 'interactive':
            app.load_existing_vector_store()
            app.interactive_mode()
        
        elif args.command == 'regenerate':
            result = app.regenerate_from_saved_content(
                args.pdf_name,
                extract_structured=not args.no_structured
            )
            print(f"\n✅ Successfully regenerated from saved content")
            print(f"   Processed {result['num_docs']} documents")
            print(f"   Original extraction had {result['statistics']['num_pages']} pages")
            print(f"   and {result['statistics']['num_images']} images")
            print("\nYou can now query with: python main.py query 'your question'")
            print("Or start interactive mode: python main.py interactive")
        
        elif args.command == 'list':
            content_manager = ContentManager(str(settings.processed_data_dir))
            available = content_manager.list_available_contents()
            
            if not available:
                print("\n❌ No saved extracted contents found")
                print(f"   Directory: {settings.processed_data_dir}")
            else:
                print(f"\n📂 Available extracted contents ({len(available)}):")
                print("="*60)
                for pdf_name in available:
                    try:
                        info = content_manager.get_content_info(pdf_name)
                        print(f"\n  📄 {pdf_name}")
                        print(f"     Extracted: {info['extraction_date']}")
                        print(f"     Pages: {info['statistics']['num_pages']}, Images: {info['statistics']['num_images']}")
                    except Exception as e:
                        print(f"\n  📄 {pdf_name} (error reading info: {e})")
                print("\n" + "="*60)
                print("\nTo regenerate: python main.py regenerate <pdf_name>")
        
        elif args.command == 'show':
            content_manager = ContentManager(str(settings.processed_data_dir))
            try:
                info = content_manager.get_content_info(args.pdf_name)
                
                print("\n" + "="*60)
                print(f"📄 Extracted Content Info: {info['pdf_name']}")
                print("="*60)
                print(f"\nExtraction Date: {info['extraction_date']}")
                print(f"\nStatistics:")
                print(f"  - Pages: {info['statistics']['num_pages']}")
                print(f"  - Images: {info['statistics']['num_images']}")
                print(f"  - Merged Documents: {info['statistics']['num_merged_docs']}")
                print(f"\nFile Location: {info['file_path']}")
                
                # Check for readable version
                readable_file = Path(info['file_path']).parent / f"{args.pdf_name}_readable.txt"
                if readable_file.exists():
                    print(f"Readable Version: {readable_file}")
                    print(f"\nTo view content: notepad {readable_file}")
                
                print("\nTo regenerate vector store: python main.py regenerate " + args.pdf_name)
                print("="*60)
            except FileNotFoundError as e:
                print(f"\n❌ {e}")
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
