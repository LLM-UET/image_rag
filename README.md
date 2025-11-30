# Multimodal RAG: PDF Processing & Information Extraction

A comprehensive Retrieval-Augmented Generation (RAG) system for processing PDF documents with text and images, extracting structured information (especially Vietnamese telco packages), and enabling intelligent question-answering.

**Current Phase:** Image RAG Service API for telecom package extraction with MySQL storage.
## 📋 Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [CLI Interface](#cli-interface)
  - [API Service](#api-service)
- [Architecture](#architecture)
- [API Keys](#api-keys)

## 🚀 Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager

### Step 1: Clone or Navigate to the Project

```bash
cd "multimodal rag"
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

## 🗄️ Database Setup

This system uses **MySQL** for storing extracted package information and customer data.

### Quick Setup

```powershell
# 1. Install MySQL 8.0+ (if not already installed)
# Download from: https://dev.mysql.com/downloads/installer/

# 2. Create database using provided schema
mysql -u root -p < schema.sql

# 3. Configure environment variables in .env
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=telco_db

# 4. Test connection
cd src
python database.py
```

**Detailed guide:** See [MYSQL_SETUP.md](MYSQL_SETUP.md) for complete setup instructions, troubleshooting, and migration from MongoDB.

## ⚙️ Configuration

### 1. Create Environment File

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

### 2. Edit `.env` File

```env
# MySQL Database Configuration
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=telco_db

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
VISION_MODEL=gemini-2.0-flash

# Local Model Settings (for offline usage)
LOCAL_EMBEDDINGS=true
LOCAL_LLM=true
LOCAL_LLM_MODEL=google/flan-t5-base
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

### API Service (Package Extraction)

Start the FastAPI service for Vietnamese telco package extraction:

```powershell
cd src
python api_service.py
```

Service runs on **http://localhost:8001**

#### API Endpoints

- `GET /` - Service info
- `GET /health` - Health check
- `POST /extract-packages` - Extract packages from single PDF
- `POST /extract-packages-batch` - Extract from multiple PDFs

**Example usage:**

```powershell
# Test with cURL
curl -X POST http://localhost:8001/extract-packages `
  -F "file=@../data/raw/viettel_packages.pdf"

# Interactive docs
# Open browser: http://localhost:8001/docs
```

**Detailed API documentation:** See [API_SERVICE_README.md](API_SERVICE_README.md)

### CLI Interface

The application also provides CLI commands:

#### Process a PDF Document

```bash
cd src
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

#### Content Management

```bash
# List saved extracted content
python main.py list

# Show specific extraction
python main.py show <pdf_name>

# Regenerate from saved content
python main.py regenerate <saved_file>
```

**Content management guide:** See [CONTENT_MANAGEMENT.md](CONTENT_MANAGEMENT.md)

## 🏗️ Architecture

```
┌─────────────────┐
│   PDF Document  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Text Extraction (PyMuPDF4LLM)         │
│  Image Extraction (Upstage/Local BLIP) │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Image Description (3-tier fallback):   │
│  Upstage → Gemini Vision → Local BLIP  │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Document Merger (by page)              │
└────────┬────────────────────────────────┘
         │
         ├──────────────────┬──────────────────┬──────────────────┐
         ▼                  ▼                  ▼                  ▼
┌────────────────┐  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐
│ Vector Store   │  │ Package      │  │  RAG Pipeline  │  │  FastAPI       │
│ (ChromaDB)     │  │ Extraction   │  │  (LangGraph)   │  │  Service       │
└────────────────┘  └──────────────┘  └────────────────┘  └────────────────┘
         │                  │                  │                  │
         ▼                  ▼                  ▼                  ▼
┌────────────────┐  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐
│ Similarity     │  │ MySQL        │  │ Q&A Interface  │  │ REST API       │
│ Search         │  │ Database     │  │                │  │ (Port 8001)    │
└────────────────┘  └──────────────┘  └────────────────┘  └────────────────┘
```

### Key Features

- **Multi-modal Processing**: Extracts both text and images from PDFs
- **Local Model Support**: Can run offline with local embeddings, LLM, and vision models
- **Vietnamese Telco Packages**: Specialized extraction for Vietnamese telecommunication package information
- **MySQL Storage**: Structured data storage with JSON columns for dynamic metadata
- **RESTful API**: FastAPI service for package extraction
- **Content Management**: Save and regenerate extracted content without reprocessing
- **RAG Pipeline**: Intelligent question-answering with source citations
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
multimodal-rag/
├── config/
│   └── settings.py              # Configuration management
├── src/
│   ├── __init__.py
│   ├── main.py                  # CLI application
│   ├── api_service.py           # FastAPI REST service (Port 8001)
│   ├── database.py              # MySQL ORM models & connection
│   ├── pdf_processor.py         # PDF text extraction
│   ├── image_processor.py       # Image extraction & description (3-tier)
│   ├── document_merger.py       # Document merging
│   ├── vector_store.py          # Vector store management
│   ├── structured_extractor.py  # General structured extraction
│   ├── package_extractor.py     # Telco package extraction
│   ├── content_manager.py       # Content save/load/regenerate
│   └── rag_pipeline.py          # RAG implementation
├── data/
│   ├── raw/                     # Input PDF files
│   ├── processed/               # Extracted content (JSON + txt)
│   └── structured/              # CSV exports
├── vectorstore/                 # ChromaDB storage
├── schema.sql                   # MySQL database schema
├── data.md                      # Database entity documentation
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment template
├── README.md                    # This file
├── MYSQL_SETUP.md              # Database setup guide
├── API_SERVICE_README.md        # API documentation
└── CONTENT_MANAGEMENT.md        # Content management guide
```

## 🛠️ Technologies

### Core Stack
- **Python 3.13+**
- **MySQL 8.0+** - Relational database with JSON column support
- **FastAPI** - Modern web framework for API service
- **SQLAlchemy** - ORM for database operations

### AI/ML Libraries
- [LangChain](https://www.langchain.com/) - LLM orchestration framework
- [PyMuPDF4LLM](https://pymupdf.readthedocs.io/) - PDF text extraction
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [Transformers](https://huggingface.co/transformers/) - Local models
- [Sentence-Transformers](https://www.sbert.net/) - Local embeddings

### AI Models
- **Embeddings**: OpenAI text-embedding-3-small OR sentence-transformers/all-MiniLM-L6-v2 (local)
- **LLM**: OpenAI gpt-4o OR google/flan-t5-base (local)
- **Vision**: Upstage Document Parse OR Google Gemini OR Salesforce/blip-image-captioning-base (local)

### External Services (Optional)
- [Upstage Document AI](https://www.upstage.ai/) - Advanced document parsing
- [OpenAI](https://openai.com/) - GPT models
- [Google Gemini](https://deepmind.google/technologies/gemini/) - Vision models
- [LangSmith](https://smith.langchain.com/) - Tracing & monitoring

