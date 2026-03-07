const path = require('path');
const Document = require('../models/Document');
const FinancialRecord = require('../models/FinancialRecord');
const { processDocument } = require('../services/extractionService');

// ─── Document Controller ───────────────────────────────────────────────────────

/**
 * uploadDocument – handles POST /documents/upload
 *
 * 1. Validates that a file was attached
 * 2. Creates a Document record in the DB
 * 3. Fires the async extraction pipeline (non-blocking)
 * 4. Returns a 201 with the new document metadata
 */
async function uploadDocument(req, res, next) {
    try {
        // multer places the file object on req.file
        if (!req.file) {
            return res.status(400).json({
                success: false,
                error: 'No file uploaded. Attach a PDF as form field "document".',
            });
        }

        const { filename, originalname, mimetype, size } = req.file;

        // Create the document record
        const document = await Document.create({
            filename,
            original_name: originalname,
            mime_type: mimetype,
            file_size: size,
            status: 'uploaded',
        });

        console.log(`📥  Uploaded: ${originalname} → ${filename}`);

        // Fire-and-forget: kick off extraction pipeline asynchronously.
        // We intentionally do NOT await this so the upload response is fast.
        processDocument(document.id).catch((err) =>
            console.error('❌  Background processing error:', err)
        );

        return res.status(201).json({
            success: true,
            data: {
                id: document.id,
                filename: document.original_name,
                status: document.status,
                uploaded_at: document.uploaded_at,
            },
        });
    } catch (error) {
        next(error);
    }
}

/**
 * getDocuments – handles GET /documents
 *
 * Returns a paginated list of all uploaded documents with their processing
 * status and associated financial records.
 */
async function getDocuments(req, res, next) {
    try {
        const page = Math.max(parseInt(req.query.page, 10) || 1, 1);
        const limit = Math.min(Math.max(parseInt(req.query.limit, 10) || 20, 1), 100);
        const offset = (page - 1) * limit;

        const { count, rows } = await Document.findAndCountAll({
            include: [{ model: FinancialRecord, as: 'financialRecords' }],
            order: [['uploaded_at', 'DESC']],
            limit,
            offset,
        });

        return res.json({
            success: true,
            data: rows,
            pagination: {
                page,
                limit,
                total: count,
                total_pages: Math.ceil(count / limit),
            },
        });
    } catch (error) {
        next(error);
    }
}

/**
 * getDocumentById – handles GET /documents/:id
 *
 * Returns a single document with its financial records.
 */
async function getDocumentById(req, res, next) {
    try {
        const document = await Document.findByPk(req.params.id, {
            include: [{ model: FinancialRecord, as: 'financialRecords' }],
        });

        if (!document) {
            return res.status(404).json({ success: false, error: 'Document not found.' });
        }

        return res.json({ success: true, data: document });
    } catch (error) {
        next(error);
    }
}

module.exports = { uploadDocument, getDocuments, getDocumentById };
