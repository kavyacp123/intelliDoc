const express = require('express');
const path = require('path');
const cors = require('cors');
const morgan = require('morgan');
const documentRoutes = require('./routes/documentRoutes');
const analyticsRoutes = require('./routes/analyticsRoutes');

const app = express();

// ─── Middleware ────────────────────────────────────────────────────────────────

app.use(cors());
app.use(morgan('dev'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// ─── Health Check ──────────────────────────────────────────────────────────────

app.get('/health', (_req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// ─── API Routes ────────────────────────────────────────────────────────────────

app.use('/documents', documentRoutes);
app.use('/analytics', analyticsRoutes);

// ─── 404 ───────────────────────────────────────────────────────────────────────

app.use((_req, res) => {
    res.status(404).json({ success: false, error: 'Route not found.' });
});

// ─── Error Handler ─────────────────────────────────────────────────────────────

app.use((err, _req, res, _next) => {
    console.error('🔥  Error:', err);

    if (err.code === 'LIMIT_FILE_SIZE')
        return res.status(413).json({ success: false, error: 'File too large. Max 50 MB.' });

    if (err.message?.includes('Only'))
        return res.status(400).json({ success: false, error: err.message });

    res.status(500).json({
        success: false,
        error: process.env.NODE_ENV === 'development' ? err.message : 'Internal server error.',
    });
});

module.exports = app;
