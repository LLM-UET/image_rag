"""
RAG Pipeline using LangGraph for multimodal question-answering.
"""
import logging
from typing import List, TypedDict, Optional

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import settings
if settings.local_llm:
    try:
        from transformers import pipeline
    except Exception:
        pipeline = None

    class LocalLLM:
        def __init__(self, *args, **kwargs):
            model_name = kwargs.get("model") or kwargs.get("model_name") or (args[0] if args else settings.local_llm_model)
            if pipeline is None:
                raise RuntimeError("transformers is not installed. Install it or set LOCAL_LLM=false")
            try:
                self.pipe = pipeline("text2text-generation", model=model_name)
            except Exception:
                self.pipe = pipeline("text-generation", model=model_name)

        def invoke(self, messages):
            if isinstance(messages, (list, tuple)):
                prompt = "\n".join(str(m) for m in messages)
            else:
                prompt = str(messages)
            # Use truncation to avoid exceeding model max length and limit generated tokens
            out = self.pipe(prompt, truncation=True, max_new_tokens=128)
            text = out[0].get("generated_text") or out[0].get("summary_text") or str(out[0])

            class Resp:
                def __init__(self, content: str):
                    self.content = content

            return Resp(content=text)

    # expose LocalLLM class as ChatOpenAI replacement
    ChatOpenAI = LocalLLM
else:
    from langchain_openai import ChatOpenAI
from langgraph.graph import START, StateGraph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define state for the RAG pipeline
class RAGState(TypedDict):
    """State for RAG pipeline."""
    question: str
    context: List[Document]
    answer: str


class MultimodalRAGPipeline:
    """RAG pipeline for multimodal document question-answering."""
    
    def __init__(
        self,
        vector_store_manager,
        model_name: Optional[str] = None,
        retrieval_k: int = 4
    ):
        """
        Initialize the RAG pipeline.
        
        Args:
            vector_store_manager: VectorStoreManager instance
            model_name: Name of the LLM model
            retrieval_k: Number of documents to retrieve
        """
        self.vector_store_manager = vector_store_manager
        self.model_name = model_name or settings.llm_model
        self.retrieval_k = retrieval_k
        
        # Initialize LLM
        # If local LLM is enabled, force the configured local model name to avoid
        # attempting to download gated/remote models (e.g., gpt-4o).
        if settings.local_llm:
            self.llm = ChatOpenAI(settings.local_llm_model)
        else:
            self.llm = ChatOpenAI(model=self.model_name)
        
        # Create QA prompt
        self.qa_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an assistant for question-answering tasks.
Use the following pieces of retrieved context to answer the question.
The context may include text content and image descriptions from a PDF document.

If you don't know the answer based on the provided context, just say that you don't know.
Be concise and accurate in your response.

Context: {context}"""),
            ("human", "{question}")
        ])
        
        # Build the graph
        self.graph = self._build_graph()
        
        logger.info("Initialized MultimodalRAGPipeline")
    
    def _retrieve(self, state: RAGState) -> dict:
        """
        Retrieve relevant documents for the question.
        
        Args:
            state: Current state
            
        Returns:
            Updated state with context
        """
        logger.info(f"Searching documents for: {state['question'][:50]}...")
        
        retrieved_docs = self.vector_store_manager.similarity_search(
            state["question"],
            k=self.retrieval_k
        )
        
        logger.info(f"Retrieved {len(retrieved_docs)} documents")
        return {"context": retrieved_docs}
    
    def _generate(self, state: RAGState) -> dict:
        """
        Generate answer based on retrieved context.
        
        Args:
            state: Current state with context
            
        Returns:
            Updated state with answer
        """
        logger.info("Generating answer...")
        
        # Format context
        docs_content = "\n\n".join(
            f"[Document {i+1}] (Page {doc.metadata.get('page', 'unknown')})\n{doc.page_content}"
            for i, doc in enumerate(state["context"])
        )
        
        # Create messages
        messages = self.qa_prompt.format_messages(
            question=state["question"],
            context=docs_content
        )
        
        # Generate response - handle local vs remote LLM
        if hasattr(self.llm, 'pipe'):  # LocalLLM
            prompt_text = "\n\n".join([m.content for m in messages])
            response = self.llm.invoke(prompt_text)
        else:
            response = self.llm.invoke(messages)
        
        logger.info("Answer generated")
        return {"answer": response.content}
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph pipeline.
        
        Returns:
            Compiled StateGraph
        """
        # Create graph
        graph_builder = StateGraph(RAGState)
        
        # Add nodes
        graph_builder.add_node("retrieve", self._retrieve)
        graph_builder.add_node("generate", self._generate)
        
        # Add edges
        graph_builder.add_edge(START, "retrieve")
        graph_builder.add_edge("retrieve", "generate")
        
        # Compile
        graph = graph_builder.compile()
        
        return graph
    
    def query(self, question: str) -> dict:
        """
        Query the RAG pipeline with a question.
        
        Args:
            question: User's question
            
        Returns:
            Dictionary with question, context, and answer
        """
        logger.info(f"Processing query: {question}")
        
        # Run the pipeline
        result = self.graph.invoke({"question": question})
        
        return result
    
    def query_with_sources(self, question: str) -> dict:
        """
        Query and return answer with source documents.
        
        Args:
            question: User's question
            
        Returns:
            Dictionary with answer and sources
        """
        result = self.query(question)
        
        # Format sources
        sources = []
        for i, doc in enumerate(result["context"]):
            sources.append({
                "number": i + 1,
                "page": doc.metadata.get("page", "unknown"),
                "content_preview": doc.page_content[:200] + "...",
                "source": doc.metadata.get("source", "unknown")
            })
        
        return {
            "question": result["question"],
            "answer": result["answer"],
            "sources": sources
        }


class ConversationalRAG:
    """Conversational RAG with chat history."""
    
    def __init__(self, rag_pipeline: MultimodalRAGPipeline):
        """
        Initialize conversational RAG.
        
        Args:
            rag_pipeline: MultimodalRAGPipeline instance
        """
        self.rag_pipeline = rag_pipeline
        self.chat_history = []
    
    def chat(self, message: str) -> str:
        """
        Send a message and get a response.
        
        Args:
            message: User message
            
        Returns:
            Assistant response
        """
        # Incorporate chat history into the question
        context_message = message
        if self.chat_history:
            recent_history = self.chat_history[-3:]  # Last 3 exchanges
            history_str = "\n".join([
                f"User: {h['user']}\nAssistant: {h['assistant']}"
                for h in recent_history
            ])
            context_message = f"Previous conversation:\n{history_str}\n\nCurrent question: {message}"
        
        # Get response
        result = self.rag_pipeline.query(context_message)
        answer = result["answer"]
        
        # Update history
        self.chat_history.append({
            "user": message,
            "assistant": answer
        })
        
        return answer
    
    def reset_history(self):
        """Clear chat history."""
        self.chat_history = []
        logger.info("Chat history cleared")


def create_rag_pipeline(vector_store_manager) -> MultimodalRAGPipeline:
    """
    Convenience function to create a RAG pipeline.
    
    Args:
        vector_store_manager: VectorStoreManager instance
        
    Returns:
        MultimodalRAGPipeline instance
    """
    return MultimodalRAGPipeline(vector_store_manager)


if __name__ == "__main__":
    # Example usage
    print("Multimodal RAG Pipeline Module")
    print("=" * 50)
    print("This module implements a RAG pipeline using LangGraph.")
    print("\nFeatures:")
    print("  - Document retrieval from vector store")
    print("  - Answer generation with LLM")
    print("  - Source attribution")
    print("  - Conversational interface")
    print("\nUsage:")
    print("  from rag_pipeline import MultimodalRAGPipeline")
    print("  pipeline = MultimodalRAGPipeline(vector_store_manager)")
    print("  result = pipeline.query('What is the document about?')")
