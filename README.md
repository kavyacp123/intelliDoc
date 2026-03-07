# IntelliDoc — Document AI Pipeline

A production-grade document processing system that extracts structured financial data from invoices. Inspired by AWS Textract and Google Document AI, built entirely with open-source tools.

## Architecture

```
Client / Dashboard
       ↓
  Node.js API (Express + BullMQ)
       ↓
  Redis Job Queue
       ↓
  Python Worker
       ↓
  9-Stage Processing Pipeline
       ↓
  PostgreSQL (Supabase)
```

## Tech Stack

| Layer | Technology |
|---|---|
| **API** | Node.js, Express |
| **Queue** | Redis, BullMQ |
| **OCR** | PaddleOCR |
| **Layout** | LayoutParser (PubLayNet) |
| **KV Extract** | Spatial proximity algorithm |
| **Tables** | Camelot |
| **Image Processing** | OpenCV, Pillow |
| **Database** | PostgreSQL (Supabase) |

## Processing Pipeline

| Stage | Module | Description |
|---|---|---|
| 1 | `pdf_loader.py` | Load PDF → split into page images (300 DPI) |
| 2 | `image_preprocessing.py` | Grayscale → denoise → CLAHE → deskew → binarise |
| 3 | `ocr_engine.py` | PaddleOCR → text + bounding boxes + confidence |
| 4 | `layout_detection.py` | LayoutParser → header, table, paragraph regions |
| 5 | `key_value_extraction.py` | Spatial KV pairing → invoice fields |
| 6 | `table_extraction.py` | Camelot → line items (description, qty, rate, amount) |
| 7 | `normalization.py` | ₹22,222 → 22222.0, 28-08-2025 → 2025-08-28 |
| 8 | `validation.py` | Total consistency, date validity, confidence checks |
| 9 | `main.py` | Store results in PostgreSQL |

## Quick Start

### Option 1: Docker (Recommended)

```bash
# 1. Clone and configure
cp backend/.env.example backend/.env
cp worker/.env.example worker/.env
# Edit both .env files with your DATABASE_URL

# 2. Start everything
docker-compose up --build

# 3. Open dashboard
open http://localhost:3000
```

### Option 2: Local Development

#### Prerequisites
- Node.js 20+
- Python 3.11+
- Redis 7+
- Poppler (`brew install poppler` on macOS)

#### Backend

```bash
cd backend
npm install
cp .env.example .env   # edit with your DATABASE_URL
npm start
```

#### Worker

```bash
cd worker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with your DATABASE_URL
python main.py
```

#### Redis

```bash
# macOS
brew install redis && redis-server

# Docker
docker run -d -p 6379:6379 redis:7-alpine
```

## API Endpoints

### Documents

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/documents/upload` | Upload PDF/image → queue for processing |
| `GET` | `/documents` | List all documents with pagination |
| `GET` | `/documents/:id` | Document with extracted invoice records |

### Analytics

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/analytics/monthly-summary` | Revenue by month |
| `GET` | `/analytics/compare-months` | Last 2 months comparison |
| `GET` | `/analytics/vendor-totals` | Revenue by vendor |

### Upload Example

```bash
curl -X POST http://localhost:3000/documents/upload \
  -F "document=@invoice.pdf"
```

### Response Example

```json
{
  "vendor": "SONAL ENTERPRISES",
  "invoice_number": "107",
  "invoice_date": "2025-08-28",
  "subtotal": 18832.14,
  "cgst": 1694.93,
  "sgst": 1694.93,
  "igst": null,
  "grand_total": 22222.00,
  "confidence_score": 0.94,
  "line_items": [
    {"description": "Widget A", "qty": "10", "rate": "500", "amount": "5000"}
  ]
}
```

## Project Structure

```
intelliDoc/
├── backend/
│   ├── src/
│   │   ├── app.js
│   │   ├── server.js
│   │   ├── config/database.js
│   │   ├── models/
│   │   │   ├── Document.js
│   │   │   └── InvoiceRecord.js
│   │   ├── queues/documentQueue.js
│   │   ├── controllers/
│   │   ├── routes/
│   │   ├── services/
│   │   └── public/index.html
│   ├── package.json
│   └── .env
├── worker/
│   ├── main.py
│   ├── pipeline/
│   │   ├── pdf_loader.py
│   │   ├── image_preprocessing.py
│   │   ├── ocr_engine.py
│   │   ├── layout_detection.py
│   │   ├── key_value_extraction.py
│   │   ├── table_extraction.py
│   │   ├── normalization.py
│   │   └── validation.py
│   ├── requirements.txt
│   └── .env
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.worker
└── README.md
```

## Database Schema

**documents**
| Column | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| filename | VARCHAR | Stored filename |
| original_name | VARCHAR | Original upload name |
| status | ENUM | uploaded/processing/completed/failed/needs_review |
| page_count | INT | Number of pages |
| uploaded_at | TIMESTAMP | Upload time |

**invoice_records**
| Column | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| document_id | UUID | FK → documents |
| page_number | INT | Page this record was extracted from |
| vendor | VARCHAR | Vendor name |
| invoice_number | VARCHAR | Invoice/bill number |
| invoice_date | DATE | Invoice date |
| subtotal | DECIMAL | Subtotal before tax |
| cgst | DECIMAL | Central GST |
| sgst | DECIMAL | State GST |
| igst | DECIMAL | Integrated GST |
| grand_total | DECIMAL | Total with taxes |
| confidence_score | FLOAT | OCR confidence 0-1 |
| line_items | JSONB | Extracted table rows |