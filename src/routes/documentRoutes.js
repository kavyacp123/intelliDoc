const express = require('express');
const multer = require('multer');
const path = require('path');
const {
    uploadDocument,
    getDocuments,
    getDocumentById,
} = require('../controllers/documentController');

const router = express.Router();

// ─── Multer Configuration ──────────────────────────────────────────────────────
// Store uploaded files in src/uploads with a unique timestamped filename.
// Only accept PDF files, capped at 10 MB.
// ────────────────────────────────────────────────────────────────────────────────

const storage = multer.diskStorage({
    destination: (_req, _file, cb) => {
        cb(null, path.resolve(__dirname, '..', 'uploads'));
    },
    filename: (_req, file, cb) => {
        const uniqueSuffix = `${Date.now()}-${Math.round(Math.random() * 1e9)}`;
        cb(null, `${uniqueSuffix}-${file.originalname}`);
    },
});

const fileFilter = (_req, file, cb) => {
    if (file.mimetype === 'application/pdf') {
        cb(null, true);
    } else {
        cb(new Error('Only PDF files are allowed.'), false);
    }
};

const upload = multer({
    storage,
    fileFilter,
    limits: { fileSize: 10 * 1024 * 1024 }, // 10 MB
});

// ─── Routes ────────────────────────────────────────────────────────────────────

// Upload a document
router.post('/upload', upload.single('document'), uploadDocument);

// List all documents (paginated)
router.get('/', getDocuments);

// Get a single document by ID
router.get('/:id', getDocumentById);

module.exports = router;
