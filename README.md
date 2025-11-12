# Multimodal RAG: PDF Processing & Information Extraction

A comprehensive Retrieval-Augmented Generation (RAG) system for processing PDF documents with text and images, extracting structured information, and enabling intelligent question-answering.
## 📋 Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [CLI Interface](#cli-interface)
- [Architecture](#architecture)
- [API Keys](#api-keys)

## 🚀 Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager

### Step 1: Clone or Navigate to the Project

```bash
cd "/home/tuanjhg/Project/multimodal rag"
```

### Step 2: Create Virtual Environment (Recommended)

```bash
python -m venv venv

# On Linux/Mac:
source venv/bin/activate

# On Windows:
# venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

## ⚙️ Configuration

### 1. Create Environment File

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

### 2. Edit `.env` File

```env
# Required API Keys
OPENAI_API_KEY=your_openai_api_key_here
GOOGLE_API_KEY=your_google_api_key_here

# Optional API Keys
UPSTAGE_API_KEY=your_upstage_api_key_here
GROQ_API_KEY=your_groq_api_key_here

# LangChain Configuration (Optional)
LANGCHAIN_API_KEY=your_langchain_api_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=multimodal-rag

# Model Settings
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o
VISION_MODEL=gemini-1.5-flash-8b
```

## 🎯 Quick Start

### 1. Process a PDF

```bash
cd src
python main.py process ../data/raw/your_document.pdf
```

### 2. Query the Document

```bash
python main.py query "What are the main topics in this document?"
```

### 3. Interactive Mode

```bash
python main.py interactive
```

## 📖 Usage

### CLI Interface

The application provides several commands:

#### Process a PDF Document

```bash
python main.py process <pdf_path> [--no-upstage] [--no-structured]
```

Options:
- `--no-upstage`: Skip Upstage API for image extraction
- `--no-structured`: Skip structured data extraction

#### Query the System

```bash
python main.py query "Your question here" [--no-sources]
```

Options:
- `--no-sources`: Hide source documents in the response

#### Interactive Chat Mode

```bash
python main.py interactive
```

Commands in interactive mode:
- Type your question and press Enter
- `clear` - Clear chat history
- `quit` or `exit` - Exit interactive mode

#### Load Existing Vector Store

```bash
python main.py load
```

## 🏗️ Architecture

```
┌─────────────────┐
│   PDF Document  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Text Extraction (PyMuPDF4LLM)         │
│  Image Extraction (Upstage/Unstructured)│
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Image Description (Gemini Vision)      │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Document Merger (by page)              │
└────────┬────────────────────────────────┘
         │
         ├──────────────────┬──────────────────┐
         ▼                  ▼                  ▼
┌────────────────┐  ┌──────────────┐  ┌────────────────┐
│ Vector Store   │  │ Structured   │  │  RAG Pipeline  │
│ (ChromaDB)     │  │ Extraction   │  │  (LangGraph)   │
└────────────────┘  └──────────────┘  └────────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
┌────────────────┐  ┌──────────────┐  ┌────────────────┐
│ Similarity     │  │ JSON/CSV     │  │ Q&A Interface  │
│ Search         │  │ Export       │  │                │
└────────────────┘  └──────────────┘  └────────────────┘
```
## 🔑 API Keys

### Required Keys

1. **OpenAI API Key** - For embeddings and LLM
   - Get it from: https://platform.openai.com/api-keys

2. **Google API Key** - For Gemini vision models
   - Get it from: https://makersuite.google.com/app/apikey

### Optional Keys

3. **Upstage API Key** - For advanced document parsing
   - Get it from: https://www.upstage.ai/

4. **LangChain API Key** - For tracing and monitoring
   - Get it from: https://smith.langchain.com/

## 📝 Project Structure

```
multimodal rag/
├── config/
│   └── settings.py          # Configuration management
├── src/
│   ├── __init__.py
│   ├── main.py              # Main application
│   ├── pdf_processor.py     # PDF text extraction
│   ├── image_processor.py   # Image extraction & description
│   ├── document_merger.py   # Document merging
│   ├── vector_store.py      # Vector store management
│   ├── structured_extractor.py  # Smart ETL
│   └── rag_pipeline.py      # RAG implementation
├── data/
│   ├── raw/                 # Input PDF files
│   ├── processed/           # Intermediate data
│   └── structured/          # Extracted structured data
├── vectorstore/             # ChromaDB storage
├── requirements.txt         # Dependencies
├── .env.example            # Environment template
├── .gitignore
└── README.md               # This file
```

Technologies used:
- [LangChain](https://www.langchain.com/)
- [PyMuPDF4LLM](https://pymupdf.readthedocs.io/)
- [Upstage Document AI](https://www.upstage.ai/)
- [ChromaDB](https://www.trychroma.com/)
- [OpenAI](https://openai.com/)
- [Google Gemini](https://deepmind.google/technologies/gemini/)

