"""
Smart ETL module for converting unstructured PDF data into structured format.
Extracts entities, tables, and key information from documents.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings

# Prefer local LLM when configured; otherwise use ChatOpenAI
if settings.local_llm:
    try:
        from transformers import pipeline
    except Exception:
        pipeline = None

    class LocalLLM:
        """Minimal LLM wrapper using HuggingFace transformers pipelines.

        Exposes invoke(messages) and returns an object with a `content` attribute.
        """
        def __init__(self, *args, **kwargs):
            # Accept either model or model_name kwarg, or first positional arg
            model_name = kwargs.get("model") or kwargs.get("model_name") or (args[0] if args else settings.local_llm_model)
            if pipeline is None:
                raise RuntimeError("transformers is not installed. Install it or set LOCAL_LLM=false")
            # use text2text-generation pipeline for seq2seq models like flan-t5
            try:
                self.pipe = pipeline("text2text-generation", model=model_name)
            except Exception:
                self.pipe = pipeline("text-generation", model=model_name)

        def invoke(self, messages):
            # messages may be a string or list/dict; convert to a single prompt string
            if isinstance(messages, (list, tuple)):
                prompt = "\n".join(str(m) for m in messages)
            else:
                prompt = str(messages)
            # Use truncation to avoid exceeding model max length and limit generated tokens
            out = self.pipe(prompt, truncation=True, max_new_tokens=128)
            # pipeline returns list of dicts
            text = out[0].get("generated_text") or out[0].get("summary_text") or str(out[0])

            class Resp:
                def __init__(self, content: str):
                    self.content = content

            return Resp(content=text)

    # use LocalLLM class as replacement for ChatOpenAI
    ChatOpenAI = LocalLLM
else:
    from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define schema for structured extraction
class ExtractedEntity(BaseModel):
    """Schema for an extracted entity."""
    name: str = Field(description="Name of the entity")
    type: str = Field(description="Type of entity (person, organization, location, date, etc.)")
    context: str = Field(description="Context where the entity appears")


class ExtractedTable(BaseModel):
    """Schema for an extracted table."""
    title: str = Field(description="Title or description of the table")
    headers: List[str] = Field(description="Column headers")
    rows: List[List[str]] = Field(description="Table rows")
    page: int = Field(description="Page number where table appears")


class StructuredData(BaseModel):
    """Schema for complete structured extraction."""
    title: Optional[str] = Field(description="Document title")
    summary: str = Field(description="Brief summary of the document")
    entities: List[ExtractedEntity] = Field(description="List of extracted entities")
    key_facts: List[str] = Field(description="List of key facts from the document")
    tables: List[ExtractedTable] = Field(description="List of extracted tables")
    metadata: Dict[str, Any] = Field(description="Additional metadata")


class StructuredDataExtractor:
    """Extract structured data from unstructured PDF content."""
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize the structured data extractor.
        
        Args:
            model_name: Name of the LLM model to use
        """
        self.model_name = model_name or settings.llm_model
        # If local LLM is enabled, force the configured local model name to avoid attempting
        # to load remote/private models (e.g., gpt-4o) from HuggingFace.
        if settings.local_llm:
            self.llm = ChatOpenAI(settings.local_llm_model)
        else:
            self.llm = ChatOpenAI(model=self.model_name, temperature=0)
        
        # Setup output parser
        self.parser = JsonOutputParser(pydantic_object=StructuredData)

        # Create extraction prompt with strict JSON instructions and example to improve parseability
        self.extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at extracting structured information from documents.
Extract the following information from the provided text and RETURN ONLY valid JSON that matches the schema below.
Do NOT include any extra explanation, commentary, or markdown — only valid JSON.

Required output JSON schema (fields):
{{
    "title": string or null,
    "summary": string,
    "entities": [ {{ "name": string, "type": string, "context": string }} ],
    "key_facts": [ string ],
    "tables": [ {{ "title": string, "headers": [string], "rows": [[string]], "page": int }} ],
    "metadata": {{ /* arbitrary key/value pairs */ }}
}}

Example output (must be valid JSON):
{{
    "title": "Example Document",
    "summary": "A one-paragraph summary of the document.",
    "entities": [ {{ "name": "Alice", "type": "PERSON", "context": "mentioned in introduction" }} ],
    "key_facts": [ "Fact one.", "Fact two." ],
    "tables": [ {{ "title": "Sample Table", "headers": ["Col1","Col2"], "rows": [["a","b"],["c","d"]], "page": 2 }} ],
    "metadata": {{ "source": "page 2" }}
}}

Now extract from the provided content and output ONLY JSON that conforms to the schema above. {{format_instructions}}"""),
            ("human", "Document content:\n\n{{content}}")
        ])
        
        # Create entity extraction prompt for focused extraction
        self.entity_prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract all named entities from the text.
For each entity, provide:
- name: The entity text
- type: The type (PERSON, ORGANIZATION, LOCATION, DATE, MONEY, etc.)
- context: A brief context where it appears

Return as a JSON array of objects."""),
            ("human", "{content}")
        ])
    
    def extract_structured_data(self, documents: List[Document]) -> StructuredData:
        """
        Extract comprehensive structured data from documents.
        
        Args:
            documents: List of document chunks
            
        Returns:
            StructuredData object with all extracted information
        """
        logger.info("Extracting structured data from documents (chunked)...")

        # Helper: robust JSON parsing with simple repair attempts
        def _safe_parse_json(text: str):
            # Try direct parse
            try:
                return json.loads(text)
            except Exception:
                pass

            # Attempt to extract a JSON object substring between the first '{' and last '}'
            try:
                first = text.find('{')
                last = text.rfind('}')
                if first != -1 and last != -1 and last > first:
                    sub = text[first:last+1]
                    return json.loads(sub)
            except Exception:
                pass

            # Try to replace single quotes with double quotes (naive)
            try:
                alt = text.replace("\'", '"')
                return json.loads(alt)
            except Exception:
                pass

            # Give up
            return None

        # Process documents in small chunks (per-document) to avoid exceeding model context
        aggregated = {
            "title": None,
            "summary": [],
            "entities": [],
            "key_facts": [],
            "tables": [],
            "metadata": {}
        }

        # Limit number of documents processed to settings.max_pages to avoid huge runs
        docs_to_process = documents[: settings.max_pages]

        for i, doc in enumerate(docs_to_process):
            try:
                prompt_messages = self.extraction_prompt.invoke({
                    "content": doc.page_content,
                    "format_instructions": self.parser.get_format_instructions()
                })

                # Extract content from message objects properly
                if isinstance(prompt_messages, (list, tuple)):
                    # Extract .content from each message object if available
                    parts = []
                    for m in prompt_messages:
                        if hasattr(m, 'content'):
                            parts.append(m.content)
                        else:
                            parts.append(str(m))
                    prompt_text = "\n".join(parts)
                elif hasattr(prompt_messages, 'content'):
                    prompt_text = prompt_messages.content
                else:
                    prompt_text = str(prompt_messages)

                response = self.llm.invoke(prompt_text)
                out_text = response.content

                # Robust parse attempts
                parsed = None
                # 1) Try direct json.loads
                parsed = _safe_parse_json(out_text)
                # 2) If that failed, try the JsonOutputParser (langchain)
                if parsed is None:
                    try:
                        parsed_candidate = self.parser.parse(out_text)
                        # parser.parse may return a string; if so try to json-parse it
                        if isinstance(parsed_candidate, str):
                            parsed = _safe_parse_json(parsed_candidate)
                        else:
                            parsed = parsed_candidate
                    except Exception as e:
                        logger.debug(f"JsonOutputParser failed for doc {i}: {e}")

                if parsed is None or not isinstance(parsed, dict):
                    logger.error(f"Failed to parse LLM output for doc {i}; skipping chunk. Raw output preview: {out_text[:200]!r}")
                    continue

                # Aggregate results safely (use dict.get with defaults)
                title = parsed.get("title") if isinstance(parsed.get("title"), str) else None
                if title and not aggregated["title"]:
                    aggregated["title"] = title

                summary_val = parsed.get("summary")
                if summary_val:
                    aggregated["summary"].append(summary_val)

                entities_val = parsed.get("entities")
                if isinstance(entities_val, list):
                    aggregated["entities"].extend(entities_val)

                facts_val = parsed.get("key_facts")
                if isinstance(facts_val, list):
                    aggregated["key_facts"].extend(facts_val)

                tables_val = parsed.get("tables")
                if isinstance(tables_val, list):
                    aggregated["tables"].extend(tables_val)

            except Exception as e:
                logger.error(f"Error processing document chunk {i}: {e}")
                continue

        # Compose final summary by joining per-chunk summaries
        final_summary = "\n\n".join(aggregated["summary"]) if aggregated["summary"] else ""

        logger.info("Structured extraction complete (aggregated from chunks)")
        return StructuredData(
            title=aggregated["title"] or "",
            summary=final_summary,
            entities=aggregated["entities"],
            key_facts=aggregated["key_facts"],
            tables=aggregated["tables"],
            metadata=aggregated["metadata"]
        )
    
    def extract_entities(self, text: str) -> List[ExtractedEntity]:
        """
        Extract named entities from text.
        
        Args:
            text: Text content
            
        Returns:
            List of extracted entities
        """
        # Manual flow for entity extraction to support local LLM
        try:
            messages = self.entity_prompt.invoke({"content": text})
            
            # Extract content from message objects properly
            if isinstance(messages, (list, tuple)):
                parts = []
                for m in messages:
                    if hasattr(m, 'content'):
                        parts.append(m.content)
                    else:
                        parts.append(str(m))
                prompt_text = "\n".join(parts)
            elif hasattr(messages, 'content'):
                prompt_text = messages.content
            else:
                prompt_text = str(messages)

            response = self.llm.invoke(prompt_text)
            out_text = response.content

            # Try parse JSON
            try:
                items = json.loads(out_text)
            except Exception:
                try:
                    items = JsonOutputParser().parse(out_text)
                except Exception as e:
                    logger.error(f"Error parsing entity extraction output: {e}")
                    return []

            return [ExtractedEntity(**item) for item in items]
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []
    
    def extract_tables_to_dataframe(
        self,
        documents: List[Document]
    ) -> List[pd.DataFrame]:
        """
        Extract tables and convert to pandas DataFrames.
        
        Args:
            documents: List of documents
            
        Returns:
            List of DataFrames representing tables
        """
        structured_data = self.extract_structured_data(documents)
        
        dataframes = []
        for table in structured_data.tables:
            try:
                df = pd.DataFrame(table.rows, columns=table.headers)
                df.attrs['title'] = table.title
                df.attrs['page'] = table.page
                dataframes.append(df)
            except Exception as e:
                logger.error(f"Error converting table to DataFrame: {e}")
                continue
        
        return dataframes
    
    def save_structured_data(
        self,
        structured_data: StructuredData,
        output_dir: str,
        filename: str = "extracted_data"
    ):
        """
        Save structured data to files.
        
        Args:
            structured_data: StructuredData object
            output_dir: Output directory
            filename: Base filename (without extension)
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save as JSON
        json_path = output_path / f"{filename}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(structured_data.dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"Saved JSON to {json_path}")
        
        # Save entities as CSV
        if structured_data.entities:
            entities_df = pd.DataFrame([e.dict() for e in structured_data.entities])
            csv_path = output_path / f"{filename}_entities.csv"
            entities_df.to_csv(csv_path, index=False)
            logger.info(f"Saved entities to {csv_path}")
        
        # Save tables as separate CSV files
        for i, table in enumerate(structured_data.tables):
            try:
                df = pd.DataFrame(table.rows, columns=table.headers)
                table_path = output_path / f"{filename}_table_{i+1}.csv"
                df.to_csv(table_path, index=False)
                logger.info(f"Saved table {i+1} to {table_path}")
            except Exception as e:
                logger.error(f"Error saving table {i+1}: {e}")
        
        # Save summary as text
        summary_path = output_path / f"{filename}_summary.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(f"Title: {structured_data.title}\n\n")
            f.write(f"Summary:\n{structured_data.summary}\n\n")
            f.write("Key Facts:\n")
            for i, fact in enumerate(structured_data.key_facts, 1):
                f.write(f"{i}. {fact}\n")
        logger.info(f"Saved summary to {summary_path}")


def extract_and_save(
    documents: List[Document],
    output_dir: str,
    filename: str = "extracted_data"
) -> StructuredData:
    """
    Convenience function to extract and save structured data.
    
    Args:
        documents: List of documents
        output_dir: Output directory
        filename: Base filename
        
    Returns:
        StructuredData object
    """
    extractor = StructuredDataExtractor()
    structured_data = extractor.extract_structured_data(documents)
    extractor.save_structured_data(structured_data, output_dir, filename)
    return structured_data


if __name__ == "__main__":
    # Example usage
    print("Structured Data Extractor Module")
    print("=" * 50)
    print("This module extracts structured information from PDF documents.")
    print("\nFeatures:")
    print("  - Entity extraction (people, organizations, locations, etc.)")
    print("  - Table extraction and conversion to DataFrames")
    print("  - Key facts extraction")
    print("  - Export to JSON, CSV formats")
    print("\nUsage:")
    print("  from structured_extractor import StructuredDataExtractor")
    print("  extractor = StructuredDataExtractor()")
    print("  data = extractor.extract_structured_data(documents)")
