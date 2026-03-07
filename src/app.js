const express = require('express');
const path = require('path');
const cors = require('cors');
const morgan = require('morgan');
const documentRoutes = require('./routes/documentRoutes');
const analyticsRoutes = require('./routes/analyticsRoutes');

// ─── Express Application ──────────────────────────────────────────────────────

const app = express();

// ─── Middleware ────────────────────────────────────────────────────────────────

app.use(cors());
app.use(morgan('dev'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// ─── Static Files (Testing Dashboard) ─────────────────────────────────────────

app.use(express.static(path.join(__dirname, 'public')));

// ─── Health Check ──────────────────────────────────────────────────────────────

app.get('/health', (_req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// ─── API Routes ────────────────────────────────────────────────────────────────

app.use('/documents', documentRoutes);
app.use('/analytics', analyticsRoutes);

// ─── 404 Handler ───────────────────────────────────────────────────────────────

app.use((_req, res) => {
    res.status(404).json({ success: false, error: 'Route not found.' });
});

// ─── Global Error Handler ──────────────────────────────────────────────────────

app.use((err, _req, res, _next) => {
    console.error('🔥  Unhandled error:', err);

    // Handle multer-specific errors (file too large, wrong type, etc.)
    if (err.code === 'LIMIT_FILE_SIZE') {
        return res.status(413).json({
            success: false,
            error: 'File too large. Maximum allowed size is 10 MB.',
        });
    }

    if (err.message === 'Only PDF files are allowed.') {
        return res.status(400).json({ success: false, error: err.message });
    }

    return res.status(500).json({
        success: false,
        error:
            process.env.NODE_ENV === 'development'
                ? err.message
                : 'Internal server error.',
    });
});

module.exports = app;
