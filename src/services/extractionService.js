const fs = require('fs');
const path = require('path');
const pdfParse = require('pdf-parse');
const Document = require('../models/Document');
const FinancialRecord = require('../models/FinancialRecord');
const { extractTextFromPDFBuffer } = require('./ocrService');
const { extractFinancialFields } = require('./financialExtractionService');

// ─── Extraction Service ────────────────────────────────────────────────────────
// Orchestrates the full document processing pipeline:
//   PDF file → text extraction → (optional OCR) → field parsing → DB storage
//
// This runs asynchronously AFTER the upload response has been sent so the
// user isn't blocked waiting for potentially slow OCR.
// ────────────────────────────────────────────────────────────────────────────────

// Minimum character threshold – if pdf-parse returns fewer chars than this
// we assume the PDF is image-based and fall back to OCR.
const MIN_TEXT_LENGTH = 500;

/**
 * processDocument – main pipeline entry point.
 *
 * @param {string} documentId  UUID of the document record to process
 */
async function processDocument(documentId) {
    let document;

    try {
        // ── Step 1: Load the document record ────────────────────────────────────
        document = await Document.findByPk(documentId);
        if (!document) {
            console.error(`❌  Document ${documentId} not found in database.`);
            return;
        }

        // Mark the document as "processing"
        await document.update({ status: 'processing' });
        console.log(`⚙️  Processing document: ${document.original_name}`);

        // ── Step 2: Read the PDF file from disk ─────────────────────────────────
        const filePath = path.resolve(__dirname, '..', 'uploads', document.filename);

        if (!fs.existsSync(filePath)) {
            throw new Error(`File not found on disk: ${filePath}`);
        }

        const pdfBuffer = fs.readFileSync(filePath);

        // ── Step 3: Extract text using pdf-parse ────────────────────────────────
        let extractedText = '';
        let extractionMethod = 'pdf-parse';

        try {
            const pdfData = await pdfParse(pdfBuffer);
            extractedText = pdfData.text || '';
            console.log(`  📄 pdf-parse extracted ${extractedText.length} characters.`);
        } catch (parseError) {
            console.warn('  ⚠️  pdf-parse failed:', parseError.message);
            extractedText = '';
        }

        // ── Step 4: OCR fallback if text is too short ───────────────────────────
        if (extractedText.length < MIN_TEXT_LENGTH) {
            console.log('  🔄 Text too short — falling back to OCR...');
            extractionMethod = 'ocr';

            const ocrText = await extractTextFromPDFBuffer(pdfBuffer);
            if (ocrText && ocrText.length > extractedText.length) {
                extractedText = ocrText;
            }
            console.log(`  🔍 OCR extracted ${extractedText.length} characters.`);
        }

        // ── Step 5: Extract financial fields using regex ────────────────────────
        const fields = extractFinancialFields(extractedText);

        // ── Step 6: Store the financial record ──────────────────────────────────
        await FinancialRecord.create({
            document_id: documentId,
            invoice_date: fields.invoice_date,
            vendor: fields.vendor,
            total_amount: fields.total_amount,
            gst: fields.gst,
            raw_text: extractedText.substring(0, 10000), // cap stored text
            extraction_method: extractionMethod,
        });

        // ── Step 7: Mark document as completed ──────────────────────────────────
        await document.update({ status: 'completed' });
        console.log(`✅  Document ${document.original_name} processed successfully.`);
    } catch (error) {
        console.error(`❌  Processing failed for document ${documentId}:`, error.message);

        // Persist the failure state so it's visible via the API
        if (document) {
            await document
                .update({ status: 'failed', error_message: error.message })
                .catch(() => { });
        }
    }
}

module.exports = { processDocument };
