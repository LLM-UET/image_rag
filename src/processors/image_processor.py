"""
Image extraction and description generation module.
Supports both Upstage Document Parse API and direct multimodal LLM processing.
"""
import base64
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_core.documents import Document
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import optional vision dependencies
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Gemini not available")

try:
    from langchain_upstage import UpstageDocumentParseLoader
    UPSTAGE_AVAILABLE = True
except ImportError:
    UPSTAGE_AVAILABLE = False
    logger.warning("Upstage not available")

try:
    from transformers import BlipProcessor, BlipForConditionalGeneration
    from PIL import Image
    import torch
    LOCAL_VISION_AVAILABLE = True
except ImportError:
    LOCAL_VISION_AVAILABLE = False
    logger.warning("Local vision (BLIP) not available")


class ImageDescriptionGenerator:
    """Generate descriptions for images using multimodal LLMs."""
    
    def __init__(self, model_name: Optional[str] = None, use_upstage: bool = False):
        """
        Initialize image description generator with 3-tier fallback:
        1. Upstage API (if enabled)
        2. Gemini Vision
        3. Local BLIP model
        
        Args:
            model_name: Name of the vision model (default from settings)
            use_upstage: Whether to use Upstage Document Parse API
        """
        self.model_name = model_name or settings.vision_model
        self.use_upstage = use_upstage
        self.vision_model = None
        self.local_vision_model = None
        self.local_vision_processor = None
        
        # Try to initialize Gemini
        if GEMINI_AVAILABLE and settings.google_api_key:
            try:
                self.vision_model = ChatGoogleGenerativeAI(model=self.model_name)
                logger.info(f"Gemini vision initialized: {self.model_name}")
            except Exception as e:
                logger.warning(f"Failed to init Gemini: {e}")
        
        # Initialize local BLIP as fallback
        if LOCAL_VISION_AVAILABLE:
            try:
                model_id = "Salesforce/blip-image-captioning-base"
                logger.info(f"Loading local vision model: {model_id}...")
                self.local_vision_processor = BlipProcessor.from_pretrained(model_id)
                self.local_vision_model = BlipForConditionalGeneration.from_pretrained(model_id)
                
                # Move to GPU if available
                if torch.cuda.is_available():
                    self.local_vision_model = self.local_vision_model.to("cuda")
                    logger.info("Local vision model loaded on GPU")
                else:
                    logger.info("Local vision model loaded on CPU")
            except Exception as e:
                logger.warning(f"Failed to init local vision: {e}")
        
        # Image description prompt
        self.description_prompt = """
Describe only the factual content visible in the image:

1. If decorative/non-informational: output '<---image--->'

2. For content images:
- General Images: List visible objects, text, and measurable attributes
- Charts/Infographics: State all numerical values and labels present
- Tables: Convert to markdown table format with exact data

Rules:
* Include only directly observable information
* Use original numbers and text without modification
* Avoid any interpretation or analysis
* Preserve all labels and measurements exactly as shown
"""
    
    def extract_images_with_upstage(self, pdf_path: str) -> List[Document]:
        """
        Extract images and content using Upstage Document Parse API.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of Document objects with page content and base64 encoded images
        """
        if not UPSTAGE_AVAILABLE:
            logger.error("Upstage not available")
            return []
        
        logger.info(f"Extracting images using Upstage API: {pdf_path}")
        
        try:
            loader = UpstageDocumentParseLoader(
                pdf_path,
                split="page",
                output_format="markdown",
                base64_encoding=["figure", "chart", "table"]
            )
            docs = loader.load_and_split()
            logger.info(f"Extracted {len(docs)} pages with Upstage")
            return docs
        except Exception as e:
            logger.error(f"Upstage extraction failed: {e}")
            return []
    
    def describe_image_from_base64(self, base64_image: str) -> str:
        """
        Generate description for a base64-encoded image with fallback chain:
        1. Gemini Vision (if available)
        2. Local BLIP model
        3. Placeholder
        
        Args:
            base64_image: Base64 encoded image string
            
        Returns:
            Description of the image
        """
        # Try Gemini first
        if self.vision_model:
            try:
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": self.description_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ]
                )
                response = self.vision_model.invoke([message])
                return response.content
            except Exception as e:
                logger.warning(f"Gemini vision failed: {e}, trying local model...")
        
        # Fallback to local BLIP
        if self.local_vision_model and self.local_vision_processor:
            try:
                return self._describe_with_local_model(base64_image)
            except Exception as e:
                logger.error(f"Local vision failed: {e}")
        
        # Final fallback
        return "<---image--->"
    
    def _describe_with_local_model(self, base64_image: str) -> str:
        """
        Use local BLIP model to describe image.
        
        Args:
            base64_image: Base64 encoded image string
            
        Returns:
            Description string
        """
        import base64
        from io import BytesIO
        
        # Decode base64 to PIL Image
        img_data = base64.b64decode(base64_image)
        image = Image.open(BytesIO(img_data)).convert('RGB')
        
        # Process with BLIP
        inputs = self.local_vision_processor(image, return_tensors="pt")
        
        # Move to GPU if model is on GPU
        if next(self.local_vision_model.parameters()).is_cuda:
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
        
        # Generate caption
        with torch.no_grad():
            output = self.local_vision_model.generate(**inputs, max_length=100)
        
        caption = self.local_vision_processor.decode(output[0], skip_special_tokens=True)
        logger.info(f"Local BLIP generated: {caption}")
        return caption
    
    def create_image_descriptions(self, docs: List[Document]) -> List[Document]:
        """
        Generate descriptions for all images in documents.
        
        Args:
            docs: List of Document objects with base64_encodings in metadata
            
        Returns:
            List of new Document objects with image descriptions
        """
        logger.info("Generating image descriptions...")
        image_description_docs = []
        
        for doc in docs:
            # Check if base64_encodings exist in metadata
            if 'base64_encodings' in doc.metadata and len(doc.metadata['base64_encodings']) > 0:
                for idx, img_base64 in enumerate(doc.metadata['base64_encodings']):
                    try:
                        # Generate description
                        description = self.describe_image_from_base64(img_base64)
                        
                        # Create a new Document
                        new_doc = Document(
                            page_content=description,
                            metadata={
                                "page": f"{doc.metadata.get('page', 'unknown')}",
                                "image_index": idx,
                                "type": "image_description"
                            }
                        )
                        
                        image_description_docs.append(new_doc)
                        
                    except Exception as e:
                        logger.error(f"Error processing image on page {doc.metadata.get('page')}: {e}")
                        continue
        
        logger.info(f"Generated {len(image_description_docs)} image descriptions")
        return image_description_docs
    
    def process_pdf_images(self, pdf_path: str) -> List[Document]:
        """
        Complete pipeline to extract and describe images from PDF.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of Document objects with image descriptions
        """
        # Extract images using Upstage
        docs = self.extract_images_with_upstage(pdf_path)
        
        # Generate descriptions
        image_descriptions = self.create_image_descriptions(docs)
        
        return image_descriptions, docs


def decode_and_display_image(base64_string: str, output_path: Optional[str] = None):
    """
    Decode base64 image and optionally save to file.
    
    Args:
        base64_string: Base64 encoded image
        output_path: Optional path to save the decoded image
    """
    img_data = base64.b64decode(base64_string)
    
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'wb') as f:
            f.write(img_data)
        logger.info(f"Image saved to: {output_file}")
    
    return img_data


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        generator = ImageDescriptionGenerator(use_upstage=True)
        descriptions, docs = generator.process_pdf_images(pdf_file)
        
        # Print sample descriptions
        for i, doc in enumerate(descriptions[:3]):
            print(f"\n📄 **Image Description {i + 1}**")
            print(f"Page: {doc.metadata.get('page')}")
            print("=" * 50)
            print(doc.page_content[:300])
    else:
        print("Usage: python image_processor.py <path_to_pdf>")
