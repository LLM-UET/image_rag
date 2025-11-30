## Mục lục
- [Cài đặt](#-cài-đặt)
- [Cấu trúc dự án](#-cấu-trúc-dự-án)
- [Sử dụng](#-sử-dụng)
  - [CLI Commands](#cli-commands)
  - [REST API](#rest-api)
- [Cấu hình](#-cấu-hình)

## Cài đặt

### Yêu cầu
- Python 3.9+
- (Tùy chọn) MySQL 8.0+ hoặc MongoDB cho lưu trữ

### Cài đặt nhanh

```bash
# Clone repository
git clone https://github.com/LLM-UET/image_rag.git
cd image_rag

# Tạo virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# Cài đặt dependencies
pip install -r requirements.txt

# Cấu hình environment
copy .env.example .env  # Windows
# Sửa .env để thêm API keys (OPENAI_API_KEY, UPSTAGE_API_KEY nếu dùng)
```

## Cấu trúc dự án

```
image_rag/
├── config/
│   └── settings.py              # Cấu hình ứng dụng
├── src/
│   ├── main.py                  # CLI chính cho RAG
│   ├── telecom_cli.py           # CLI cho trích xuất gói cước
│   ├── api/                     # REST API
│   │   └── telecom_api.py       # FastAPI endpoints
│   ├── core/                    # Core telecom extraction
│   │   ├── models.py            # Pydantic models (TelecomPackage)
│   │   ├── cleaner.py           # Data cleaning utilities
│   │   └── extractor.py         # LLM-based extractor
│   ├── services/                # Business logic
│   ├── processors/              # Document processors
│   ├── rag/                     # RAG pipeline components
│   ├── db/                      # Database
│   └── ui/                      # User interfaces
├── data/
│   ├── raw/                     # Input PDFs
│   ├── processed/               # Extracted content
│   └── structured/              # Structured output
├── API_DOCUMENTATION.md         # Chi tiết API
└── requirements.txt
```

## Sử dụng

### CLI Commands (ví dụ)

```bash
cd src

# Xử lý PDF mới
python main.py process ../data/raw/document.pdf

# Liệt kê nội dung đã trích xuất
python main.py list

# Trích xuất gói cước từ file readable.txt
python telecom_cli.py extract --input ../data/processed/tv360-01_readable.txt --output packages.json
```

### REST API (phát triển / chạy nhanh)

```bash
cd src/api

# Khởi động server
python telecom_api.py --port 8002

# Hoặc với uvicorn
uvicorn telecom_api:app --host 0.0.0.0 --port 8002 --reload
```

Endpoints chính:
- `GET /api/v1/health` - Health check
- `POST /api/v1/extract` - Trích xuất gói cước từ file (hỗ trợ .pdf, .json, .txt)

Ví dụ curl (PowerShell):

```powershell
curl.exe -s -X POST "http://localhost:8002/api/v1/extract" `
  -F "file=@C:\path\to\sample.pdf" `
  -o packages.json
```

Swagger UI: http://localhost:8002/docs

## Cấu hình

Tạo file `.env` trong thư mục gốc (tham khảo `.env.example`):

```env
# Required
OPENAI_API_KEY=your_openai_key

# Optional
UPSTAGE_API_KEY=your_upstage_key

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

## Workflow (tổng quan)

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  PDF Input  │ ──▶ │ Text + Image     │ ──▶ │ LLM Extraction  │
└─────────────┘     │ Extraction       │     │ (GPT-4o-mini)   │
                    └──────────────────┘     └────────┬────────┘
                                                      │
                    ┌──────────────────┐              ▼
                    │  Vector Store    │     ┌─────────────────┐
                    │  (ChromaDB)      │ ◀── │ Structured Data │
                    └────────┬─────────┘     │ (JSON/DB)       │
                             │               └─────────────────┘
                             ▼
                    ┌──────────────────┐
                    │  RAG Query       │
                    │  Q&A Interface   │
                    └──────────────────┘
```
