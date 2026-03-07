"""
IntelliDoc Worker — Main Entry Point

Listens to the Redis queue for document processing jobs pushed by the
Node.js backend via BullMQ. For each job, runs the full 9-stage pipeline
and stores results in PostgreSQL.

BullMQ stores jobs in Redis as JSON. This worker reads from the BullMQ
queue format directly using redis-py.
"""

import os
import sys
import json
import time
import traceback

import redis
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Pipeline stages
from pipeline.pdf_loader import load_pdf, load_image
from pipeline.image_preprocessing import preprocess_image, opencv_to_pil
from pipeline.ocr_engine import run_ocr, get_full_text
from pipeline.layout_detection import detect_layout
from pipeline.key_value_extraction import extract_key_values
from pipeline.table_extraction import extract_tables_from_pdf
from pipeline.normalization import normalize_record
from pipeline.validation import validate_record

load_dotenv()

# ─── Configuration ──────────────────────────────────────────────────────────────

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None
DATABASE_URL = os.getenv("DATABASE_URL")
QUEUE_NAME = "document-processing"
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", 0.7))


# ─── Database Helpers ───────────────────────────────────────────────────────────

def get_db_connection():
    """Create a new PostgreSQL connection."""
    return psycopg2.connect(DATABASE_URL, sslmode="prefer")


def update_document_status(doc_id: str, status: str, page_count: int = None,
                           error_message: str = None):
    """Update the document's status in the database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if page_count is not None:
                cur.execute(
                    'UPDATE documents SET status=%s, page_count=%s, error_message=%s WHERE id=%s',
                    (status, page_count, error_message, doc_id)
                )
            else:
                cur.execute(
                    'UPDATE documents SET status=%s, error_message=%s WHERE id=%s',
                    (status, error_message, doc_id)
                )
        conn.commit()
    finally:
        conn.close()


def store_invoice_record(doc_id: str, page_num: int, record: dict,
                         confidence: float, raw_text: str, line_items: list):
    """Insert an invoice record into the database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO invoice_records
                   (id, document_id, page_number, vendor, invoice_number,
                    invoice_date, subtotal, cgst, sgst, igst, grand_total,
                    confidence_score, raw_ocr_text, line_items, created_at)
                   VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s,
                           %s, %s, %s, %s, NOW())""",
                (
                    doc_id, page_num,
                    record.get("vendor"),
                    record.get("invoice_number"),
                    record.get("invoice_date"),
                    record.get("subtotal"),
                    record.get("cgst"),
                    record.get("sgst"),
                    record.get("igst"),
                    record.get("grand_total"),
                    confidence,
                    raw_text[:10000] if raw_text else None,
                    json.dumps(line_items) if line_items else None,
                )
            )
        conn.commit()
    finally:
        conn.close()


# ─── Pipeline Orchestrator ──────────────────────────────────────────────────────

def process_document(doc_id: str, file_path: str):
    """
    Run the full 9-stage pipeline on a document.

    Stage 1: PDF loader          → page images
    Stage 2: Image preprocessing → cleaned images
    Stage 3: PaddleOCR           → text + bboxes
    Stage 4: Layout detection    → structural regions
    Stage 5: Key-value extract   → invoice fields
    Stage 6: Table extraction    → line items
    Stage 7: Normalization       → clean values
    Stage 8: Validation          → quality check
    Stage 9: Store in DB         → persist results
    """
    print(f"\n{'='*60}")
    print(f"📄 Processing: {os.path.basename(file_path)}")
    print(f"   Document ID: {doc_id}")
    print(f"{'='*60}")

    # Update status to processing
    update_document_status(doc_id, "processing")

    # ── Stage 1: Load document ──────────────────────────────────────────────
    print("\n[Stage 1] Loading document...")
    ext = os.path.splitext(file_path)[1].lower()
    is_pdf = ext == ".pdf"

    if is_pdf:
        pages = load_pdf(file_path, dpi=300)
    else:
        pages = load_image(file_path)

    page_count = len(pages)
    update_document_status(doc_id, "processing", page_count=page_count)
    print(f"  → {page_count} page(s) loaded.")

    final_status = "completed"

    for page_num, page_image in enumerate(pages, start=1):
        print(f"\n--- Page {page_num}/{page_count} ---")

        try:
            # ── Stage 2: Preprocess ─────────────────────────────────────────
            print("[Stage 2] Preprocessing image...")
            preprocessed_cv = preprocess_image(page_image)
            preprocessed_pil = opencv_to_pil(preprocessed_cv)

            # ── Stage 3: OCR ───────────────────────────────────────────────
            print("[Stage 3] Running PaddleOCR...")
            ocr_results = run_ocr(page_image)  # Use original for better colour info
            full_text = get_full_text(ocr_results)
            avg_confidence = (
                sum(r["confidence"] for r in ocr_results) / len(ocr_results)
                if ocr_results else 0.0
            )
            print(f"  → {len(ocr_results)} text blocks, avg confidence: {avg_confidence:.2f}")

            # ── Stage 4: Layout detection ──────────────────────────────────
            print("[Stage 4] Detecting layout...")
            layout_regions = detect_layout(page_image)

            # ── Stage 5: Key-value extraction ──────────────────────────────
            print("[Stage 5] Extracting key-value pairs...")
            raw_fields = extract_key_values(ocr_results)

            # ── Stage 6: Table extraction ──────────────────────────────────
            print("[Stage 6] Extracting tables...")
            line_items = []
            if is_pdf:
                tables = extract_tables_from_pdf(file_path, page_number=page_num)
                for table in tables:
                    line_items.extend(table)

            # ── Stage 7: Normalise ─────────────────────────────────────────
            print("[Stage 7] Normalising data...")
            normalised = normalize_record(raw_fields)

            # ── Stage 8: Validate ──────────────────────────────────────────
            print("[Stage 8] Validating record...")
            validation = validate_record(normalised, confidence=avg_confidence)

            if validation["status"] == "needs_review":
                final_status = "needs_review"

            # ── Stage 9: Store ─────────────────────────────────────────────
            print("[Stage 9] Storing record...")
            store_invoice_record(
                doc_id=doc_id,
                page_num=page_num,
                record=normalised,
                confidence=avg_confidence,
                raw_text=full_text,
                line_items=line_items,
            )

            print(f"  ✅ Page {page_num} complete: {json.dumps(normalised, default=str)}")

        except Exception as page_err:
            print(f"  ❌ Page {page_num} failed: {page_err}")
            traceback.print_exc()
            final_status = "needs_review"

    # Update final document status
    update_document_status(doc_id, final_status)
    print(f"\n{'='*60}")
    print(f"🏁 Document {doc_id} → {final_status}")
    print(f"{'='*60}\n")


# ─── BullMQ Queue Consumer ─────────────────────────────────────────────────────
# BullMQ stores jobs in Redis lists. Active jobs are moved from
# "bull:<queue>:wait" and their data is in "bull:<queue>:<jobId>".
# ────────────────────────────────────────────────────────────────────────────────

def consume_jobs():
    """
    Continuously listen for jobs on the BullMQ Redis queue.
    Uses BRPOPLPUSH to atomically dequeue jobs.
    """
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
    )

    wait_key = f"bull:{QUEUE_NAME}:wait"
    active_key = f"bull:{QUEUE_NAME}:active"

    print(f"🔄 Worker listening on Redis queue: {QUEUE_NAME}")
    print(f"   Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"   DB:    {DATABASE_URL[:50]}...\n")

    while True:
        try:
            # Block until a job ID appears in the wait list
            job_id = r.brpoplpush(wait_key, active_key, timeout=5)

            if job_id is None:
                continue  # Timeout — loop and wait again

            print(f"📨 Received job: {job_id}")

            # Read job data from Redis hash
            job_key = f"bull:{QUEUE_NAME}:{job_id}"
            job_data_raw = r.hget(job_key, "data")

            if not job_data_raw:
                print(f"  ⚠️  No data for job {job_id} — skipping.")
                r.lrem(active_key, 1, job_id)
                continue

            job_data = json.loads(job_data_raw)
            doc_id = job_data.get("documentId")
            file_path = job_data.get("filePath")

            if not doc_id or not file_path:
                print(f"  ⚠️  Invalid job data: {job_data}")
                r.lrem(active_key, 1, job_id)
                continue

            # Process the document
            try:
                process_document(doc_id, file_path)

                # Mark job as completed in BullMQ format
                r.hset(job_key, "finishedOn", str(int(time.time() * 1000)))
                r.hset(job_key, "returnvalue", json.dumps({"status": "completed"}))
                r.lrem(active_key, 1, job_id)
                completed_key = f"bull:{QUEUE_NAME}:completed"
                r.lpush(completed_key, job_id)

            except Exception as proc_err:
                print(f"  ❌ Job {job_id} failed: {proc_err}")
                traceback.print_exc()

                # Check retry count
                attempts_made = int(r.hget(job_key, "attemptsMade") or 0) + 1
                max_attempts = 3

                if attempts_made < max_attempts:
                    r.hset(job_key, "attemptsMade", str(attempts_made))
                    r.lrem(active_key, 1, job_id)
                    r.lpush(wait_key, job_id)  # Re-queue for retry
                    print(f"  🔄 Retry {attempts_made}/{max_attempts}")
                else:
                    # Mark as permanently failed
                    update_document_status(doc_id, "failed",
                                          error_message=str(proc_err))
                    r.hset(job_key, "failedReason", str(proc_err))
                    r.lrem(active_key, 1, job_id)
                    failed_key = f"bull:{QUEUE_NAME}:failed"
                    r.lpush(failed_key, job_id)
                    print(f"  ❌ Permanently failed after {max_attempts} attempts.")

        except KeyboardInterrupt:
            print("\n🛑 Worker shutting down...")
            break
        except Exception as e:
            print(f"⚠️  Worker error: {e}")
            traceback.print_exc()
            time.sleep(5)  # Back off on errors


# ─── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set. Check your .env file.")
        sys.exit(1)

    consume_jobs()
