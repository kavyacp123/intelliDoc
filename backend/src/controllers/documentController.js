const Document = require('../models/Document');
const InvoiceRecord = require('../models/InvoiceRecord');
const { enqueueDocument } = require('../queues/documentQueue');
const { getFilePath } = require('../services/storageService');

// ─── Document Controller ───────────────────────────────────────────────────────

/** POST /documents/upload — upload PDF → DB record → push to Redis queue */
async function uploadDocument(req, res, next) {
    try {
        if (!req.file) {
            return res.status(400).json({
                success: false,
                error: 'No file uploaded. Attach a PDF as form field "document".',
            });
        }

        const { filename, originalname, mimetype, size } = req.file;

        const document = await Document.create({
            filename,
            original_name: originalname,
            mime_type: mimetype,
            file_size: size,
            status: 'uploaded',
        });

        console.log(`📥  Uploaded: ${originalname} → ${filename}`);

        // Push job to Redis queue — Python worker picks it up
        const filePath = getFilePath(filename);
        await enqueueDocument(document.id, filePath);

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

/** GET /documents — paginated list with invoice records */
async function getDocuments(req, res, next) {
    try {
        const page = Math.max(parseInt(req.query.page, 10) || 1, 1);
        const limit = Math.min(Math.max(parseInt(req.query.limit, 10) || 20, 1), 100);
        const offset = (page - 1) * limit;

        const { count, rows } = await Document.findAndCountAll({
            include: [{ model: InvoiceRecord, as: 'invoiceRecords' }],
            order: [['uploaded_at', 'DESC']],
            limit,
            offset,
        });

        return res.json({
            success: true,
            data: rows,
            pagination: { page, limit, total: count, total_pages: Math.ceil(count / limit) },
        });
    } catch (error) {
        next(error);
    }
}

/** GET /documents/:id — single document with invoice records */
async function getDocumentById(req, res, next) {
    try {
        const document = await Document.findByPk(req.params.id, {
            include: [{ model: InvoiceRecord, as: 'invoiceRecords' }],
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
