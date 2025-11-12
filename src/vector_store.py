"""
Vector store management for storing and retrieving document embeddings.
"""
import logging
from typing import List, Optional
from pathlib import Path

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None
try:
    from langchain_openai import OpenAIEmbeddings
except Exception:
    OpenAIEmbeddings = None

from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Manage vector store operations for document embeddings."""
    
    def __init__(
        self,
        collection_name: Optional[str] = None,
        persist_directory: Optional[str] = None,
        embedding_model: Optional[str] = None
    ):
        """
        Initialize vector store manager.
        
        Args:
            collection_name: Name of the collection
            persist_directory: Directory to persist the vector store
            embedding_model: Name of the embedding model
        """
        self.collection_name = collection_name or settings.collection_name
        self.persist_directory = persist_directory or settings.vector_store_dir
        self.embedding_model_name = embedding_model or settings.embedding_model
        
        # Initialize embeddings according to settings: if local_embeddings is True, force local model
        if settings.local_embeddings:
            if SentenceTransformer is None:
                raise RuntimeError(
                    "sentence-transformers is not installed. Install it or set LOCAL_EMBEDDINGS=false to use OpenAI."
                )

            class LocalEmbeddings:
                def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
                    self.model_name = model_name
                    self.model = SentenceTransformer(model_name)

                def embed_documents(self, texts):
                    embs = self.model.encode(texts, show_progress_bar=False)
                    return [list(map(float, e)) for e in embs]

                def embed_query(self, text):
                    emb = self.model.encode([text], show_progress_bar=False)[0]
                    return list(map(float, emb))

            logger.info("Using local sentence-transformers embeddings (all-MiniLM-L6-v2)")
            self.embeddings = LocalEmbeddings(model_name="all-MiniLM-L6-v2")
        else:
            if OpenAIEmbeddings is None:
                raise RuntimeError("langchain_openai is not installed; install it or set LOCAL_EMBEDDINGS=true to use local embeddings.")
            # Use OpenAI embeddings by default
            self.embeddings = OpenAIEmbeddings(model=self.embedding_model_name)
        
        # Initialize vector store (will be created when documents are added)
        self.vector_store = None
        
        logger.info(f"Initialized VectorStoreManager with collection: {self.collection_name}")
    
    def split_documents(
        self,
        documents: List[Document],
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> List[Document]:
        """
        Split documents into chunks for better retrieval.
        
        Args:
            documents: List of documents to split
            chunk_size: Size of each chunk
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of split documents
        """
        chunk_size = chunk_size or settings.chunk_size
        chunk_overlap = chunk_overlap or settings.chunk_overlap
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        splits = text_splitter.split_documents(documents)
        logger.info(f"Split {len(documents)} documents into {len(splits)} chunks")
        
        return splits
    
    def create_vector_store(
        self,
        documents: List[Document],
        split: bool = True
    ) -> Chroma:
        """
        Create a new vector store from documents.
        
        Args:
            documents: List of documents to add
            split: Whether to split documents into chunks
            
        Returns:
            Chroma vector store instance
        """
        logger.info("Creating vector store...")
        
        # Split documents if requested
        if split:
            documents = self.split_documents(documents)
        
        # Create vector store
        self.vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            collection_name=self.collection_name,
            persist_directory=self.persist_directory
        )
        
        logger.info(f"Vector store created with {len(documents)} document chunks")
        return self.vector_store
    
    def load_vector_store(self) -> Chroma:
        """
        Load an existing vector store from disk.
        
        Returns:
            Chroma vector store instance
        """
        logger.info(f"Loading vector store from {self.persist_directory}")
        
        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )
        
        logger.info("Vector store loaded successfully")
        return self.vector_store
    
    def add_documents(
        self,
        documents: List[Document],
        split: bool = True
    ) -> List[str]:
        """
        Add documents to existing vector store.
        
        Args:
            documents: List of documents to add
            split: Whether to split documents into chunks
            
        Returns:
            List of document IDs
        """
        if self.vector_store is None:
            raise ValueError("Vector store not initialized. Create or load one first.")
        
        # Split documents if requested
        if split:
            documents = self.split_documents(documents)
        
        ids = self.vector_store.add_documents(documents)
        logger.info(f"Added {len(documents)} documents to vector store")
        
        return ids
    
    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None
    ) -> List[Document]:
        """
        Search for similar documents.
        
        Args:
            query: Query string
            k: Number of results to return
            filter: Optional metadata filter
            
        Returns:
            List of similar documents
        """
        if self.vector_store is None:
            raise ValueError("Vector store not initialized. Create or load one first.")
        
        results = self.vector_store.similarity_search(
            query=query,
            k=k,
            filter=filter
        )
        
        logger.info(f"Found {len(results)} similar documents for query")
        return results
    
    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None
    ) -> List[tuple[Document, float]]:
        """
        Search for similar documents with relevance scores.
        
        Args:
            query: Query string
            k: Number of results to return
            filter: Optional metadata filter
            
        Returns:
            List of tuples (document, score)
        """
        if self.vector_store is None:
            raise ValueError("Vector store not initialized. Create or load one first.")
        
        results = self.vector_store.similarity_search_with_score(
            query=query,
            k=k,
            filter=filter
        )
        
        return results
    
    def delete_collection(self):
        """Delete the vector store collection."""
        if self.vector_store is not None:
            self.vector_store.delete_collection()
            logger.info(f"Deleted collection: {self.collection_name}")
            self.vector_store = None
    
    def get_retriever(self, k: int = 4):
        """
        Get a retriever interface for the vector store.
        
        Args:
            k: Number of documents to retrieve
            
        Returns:
            Retriever instance
        """
        if self.vector_store is None:
            raise ValueError("Vector store not initialized. Create or load one first.")
        
        return self.vector_store.as_retriever(search_kwargs={"k": k})


def create_vector_store_from_documents(
    documents: List[Document],
    collection_name: Optional[str] = None,
    persist_directory: Optional[str] = None
) -> VectorStoreManager:
    """
    Convenience function to create a vector store from documents.
    
    Args:
        documents: List of documents
        collection_name: Name of the collection
        persist_directory: Directory to persist the store
        
    Returns:
        VectorStoreManager instance
    """
    manager = VectorStoreManager(
        collection_name=collection_name,
        persist_directory=persist_directory
    )
    manager.create_vector_store(documents)
    return manager


if __name__ == "__main__":
    # Example usage
    print("Vector Store Manager Module")
    print("=" * 50)
    print("This module manages vector store operations for document retrieval.")
    print("\nUsage:")
    print("  from vector_store import VectorStoreManager")
    print("  manager = VectorStoreManager()")
    print("  manager.create_vector_store(documents)")
    print("  results = manager.similarity_search('your query')")
