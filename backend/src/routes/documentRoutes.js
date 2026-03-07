const express = require('express');
const multer = require('multer');
const { getUploadDir } = require('../services/storageService');
const {
    uploadDocument, getDocuments, getDocumentById,
} = require('../controllers/documentController');

const router = express.Router();

// ─── Multer — PDF uploads, 50 MB max ───────────────────────────────────────────

const storage = multer.diskStorage({
    destination: (_req, _file, cb) => cb(null, getUploadDir()),
    filename: (_req, file, cb) => {
        const unique = `${Date.now()}-${Math.round(Math.random() * 1e9)}`;
        cb(null, `${unique}-${file.originalname}`);
    },
});

const fileFilter = (_req, file, cb) => {
    const allowed = ['application/pdf', 'image/png', 'image/jpeg', 'image/tiff'];
    cb(null, allowed.includes(file.mimetype));
};

const upload = multer({
    storage,
    fileFilter,
    limits: { fileSize: 50 * 1024 * 1024 }, // 50 MB for multi-page docs
});

// ─── Routes ────────────────────────────────────────────────────────────────────

router.post('/upload', upload.single('document'), uploadDocument);
router.get('/', getDocuments);
router.get('/:id', getDocumentById);

module.exports = router;
