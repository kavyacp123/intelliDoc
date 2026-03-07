const fs = require('fs');
const path = require('path');

// ─── Storage Service ───────────────────────────────────────────────────────────
// Manages the uploads directory and file path resolution.
// ────────────────────────────────────────────────────────────────────────────────

const UPLOAD_DIR = path.resolve(process.env.UPLOAD_DIR || path.join(__dirname, '..', 'uploads'));

/** Ensure the uploads directory exists. */
function ensureUploadDir() {
    if (!fs.existsSync(UPLOAD_DIR)) {
        fs.mkdirSync(UPLOAD_DIR, { recursive: true });
        console.log(`📁  Created upload directory: ${UPLOAD_DIR}`);
    }
}

/** Get the absolute path for a stored file. */
function getFilePath(filename) {
    return path.join(UPLOAD_DIR, filename);
}

/** Get the upload directory path. */
function getUploadDir() {
    return UPLOAD_DIR;
}

module.exports = { ensureUploadDir, getFilePath, getUploadDir };
