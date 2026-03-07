require('dotenv').config();

const app = require('./app');
const { connectDB } = require('./config/database');

// ─── Server Startup ────────────────────────────────────────────────────────────
// 1. Connect to PostgreSQL and sync models
// 2. Start the Express HTTP server
// ────────────────────────────────────────────────────────────────────────────────

const PORT = process.env.PORT || 3000;

(async () => {
    // Connect to the database first — exits the process on failure
    await connectDB();

    app.listen(PORT, () => {
        console.log(`\n🚀  IntelliDoc server running on http://localhost:${PORT}`);
        console.log(`    Environment : ${process.env.NODE_ENV || 'development'}`);
        console.log(`    Health check: http://localhost:${PORT}/health\n`);
    });
})();
