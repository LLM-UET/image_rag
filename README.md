##  Mục lục
- [Cài đặt](#-cài-đặt)
- [Cấu trúc dự án](#-cấu-trúc-dự-án)
- [Sử dụng](#-sử-dụng)
  - [CLI Commands](#cli-commands)
  - [REST API](#rest-api)
- [Cấu hình](#-cấu-hình)

##  Cài đặt

### Yêu cầu
- Python 3.9+
- MySQL 8.0+ (optional, cho lưu trữ)

### Cài đặt

```bash
# Clone repository
git clone https://github.com/LLM-UET/image_rag.git
cd image_rag

# Tạo virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Cài đặt dependencies
pip install -r requirements.txt

# Cấu hình environment
cp .env.example .env
# Sửa .env với API keys của bạn
```

##  Cấu trúc dự án

```
image_rag/
├── config/
│   └── settings.py              # Cấu hình ứng dụng
├── src/
│   ├── main.py                  # CLI chính cho RAG
│   ├── telecom_cli.py           # CLI cho trích xuất gói cước
│   │
│   ├── api/                     # REST API
│   │   └── telecom_api.py       # FastAPI endpoints
│   │
│   ├── core/                    # Core telecom extraction
│   │   ├── models.py            # Pydantic models (TelecomPackage)
│   │   ├── cleaner.py           # Data cleaning utilities
│   │   └── extractor.py         # LLM-based extractor
│   │
│   ├── services/                # Business logic
│   │   └── telecom_service.py   # Document processing service
│   │
│   ├── processors/              # Document processors
│   │   ├── pdf_processor.py     # PDF text extraction
│   │   ├── image_processor.py   # Image description (Upstage/Gemini/BLIP)
│   │   ├── document_merger.py   # Merge text & images
│   │   └── package_extractor.py # Specialized package extractor
│   │
│   ├── rag/                     # RAG pipeline components
│   │   ├── vector_store.py      # ChromaDB vector store
│   │   ├── rag_pipeline.py      # Query pipeline
│   │   ├── content_manager.py   # Content save/load
│   │   └── structured_extractor.py
│   │
│   ├── db/                      # Database
│   │   └── mongo.py             # MongoDB handler
│   │
│   └── ui/                      # User interfaces
│       └── streamlit_app.py     # Review UI
│
├── data/
│   ├── raw/                     # Input PDFs
│   ├── processed/               # Extracted content
│   └── structured/              # Structured output
│
├── API_DOCUMENTATION.md         # Chi tiết API
└── requirements.txt
```

##  Sử dụng

### CLI Commands

### REST API

```bash
cd src/api

# Khởi động server
python telecom_api.py --port 8002

# Hoặc với uvicorn
uvicorn telecom_api:app --host 0.0.0.0 --port 8002 --reload
```

**Endpoints:**
- `GET /api/v1/health` - Health check
- `POST /api/v1/extract` - Trích xuất gói cước từ file

curl.exe -s -X POST "http://localhost:8002/api/v1/extract" `
  -F "file=@C:\path\to\sample.pdf" `
  -o packages.json
  
**Swagger UI:** http://localhost:8002/docs

#### 1. RAG Pipeline (main.py)

```bash
cd src

# Xử lý PDF mới
python main.py process ../data/raw/document.pdf

# Liệt kê nội dung đã trích xuất
python main.py list

# Tái tạo từ nội dung đã lưu
python main.py regenerate <pdf_name>

# Hỏi đáp
python main.py query "Câu hỏi của bạn?"

# Chế độ tương tác
python main.py interactive
```

#### 2. Telecom Package Extraction (telecom_cli.py)

```bash
cd src

# Trích xuất từ 1 file
python telecom_cli.py extract --input ../data/processed/tv360-01_readable.txt --output packages.json

# Xử lý nhiều file
python telecom_cli.py batch --input-dir ../data/processed --output all_packages.json

# Kiểm tra kết quả
python telecom_cli.py validate --input packages.json
```


##  Cấu hình

Tạo file `.env` trong thư mục gốc:

```env
# Required
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key

# Optional
UPSTAGE_API_KEY=your_upstage_key
GROQ_API_KEY=your_groq_key

# Database (optional)
MYSQL_USER=root
MYSQL_PASSWORD=password
MYSQL_HOST=localhost
MYSQL_DATABASE=telco_db

# Model Settings
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o-mini
VISION_MODEL=gemini-2.0-flash
```

##  Workflow

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  PDF Input  │ ──▶ │ Text + Image     │ ──▶ │ LLM Extraction  │
└─────────────┘     │ Extraction       │     │ (GPT-4o-mini)   │
                    └──────────────────┘     └────────┬────────┘
                                                      │
                    ┌──────────────────┐              ▼
                    │  Vector Store    │     ┌─────────────────┐
                    │  (ChromaDB)      │ ◀── │ Structured Data │
                    └────────┬─────────┘     │ (JSON/MySQL)    │
                             │               └─────────────────┘
                             ▼
                    ┌──────────────────┐
                    │  RAG Query       │
                    │  Q&A Interface   │
                    └──────────────────┘
```
