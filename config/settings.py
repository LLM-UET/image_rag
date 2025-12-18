import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    upstage_api_key: str = os.getenv("UPSTAGE_API_KEY", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    
    langchain_api_key: str = os.getenv("LANGCHAIN_API_KEY", "")
    langchain_tracing_v2: str = os.getenv("LANGCHAIN_TRACING_V2", "false")
    langchain_endpoint: str = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    langchain_project: str = os.getenv("LANGCHAIN_PROJECT", "multimodal-rag")
    langsmith_workspace_id: str = os.getenv("LANGSMITH_WORKSPACE_ID", "")
    
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1000"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o")
    vision_model: str = os.getenv("VISION_MODEL", "gemini-2.0-flash")
    
    vector_store_dir: str = os.getenv("VECTOR_STORE_DIR", "./vectorstore")
    collection_name: str = os.getenv("COLLECTION_NAME", "multimodal_docs")
    
    max_pages: int = int(os.getenv("MAX_PAGES", "100"))
    image_dpi: int = int(os.getenv("IMAGE_DPI", "150"))
    image_size_limit: float = float(os.getenv("IMAGE_SIZE_LIMIT", "0.05"))
    local_embeddings: bool = os.getenv("LOCAL_EMBEDDINGS", "false").lower() in ("1", "true", "yes")
    local_llm: bool = os.getenv("LOCAL_LLM", "false").lower() in ("1", "true", "yes")
    local_llm_model: str = os.getenv("LOCAL_LLM_MODEL", "google/flan-t5-base")
    
    # RabbitMQ settings for S15 (File Importing AI Agent)
    rabbitmq_host: str = os.getenv("RABBITMQ_HOST", "localhost")
    rabbitmq_port: str = os.getenv("RABBITMQ_PORT", "5672")
    rabbitmq_user: str = os.getenv("RABBITMQ_USER", "guest")
    rabbitmq_pass: str = os.getenv("RABBITMQ_PASS", "guest")
    file_import_request_queue: str = os.getenv("FILE_IMPORT_REQUEST_QUEUE", "file_import_requests")
    
    # SeaweedFS settings
    seaweed_master: str = os.getenv("SEAWEED_MASTER", "http://localhost:9333")
    # Optional volume URL override (e.g. http://localhost:8080)
    seaweed_volume_url: Optional[str] = os.getenv("SEAWEED_VOLUME_URL", None)
    
    project_root: Path = Path(__file__).parent.parent
    data_dir: Path = project_root / "data"
    raw_data_dir: Path = data_dir / "raw"
    processed_data_dir: Path = data_dir / "processed"
    structured_data_dir: Path = data_dir / "structured"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


def validate_api_keys():
    required_keys = {
        "Gemini": settings.gemini_api_key,
        "Google": settings.google_api_key,
    }
    
    missing_keys = [name for name, key in required_keys.items() if not key]
    
    if missing_keys:
        raise ValueError(
            f"Missing required API keys: {', '.join(missing_keys)}. "
            "Please set them in your .env file."
        )
    
    return True
