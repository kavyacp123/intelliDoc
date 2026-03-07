require('dotenv').config();

const app = require('./app');
const { connectDB } = require('./config/database');
const { setupQueueEvents } = require('./queues/documentQueue');
const { ensureUploadDir } = require('./services/storageService');

const PORT = process.env.PORT || 3000;

(async () => {
    // Ensure upload directory exists
    ensureUploadDir();

    // Connect to PostgreSQL and sync models
    await connectDB();

    // Attach Redis queue event listeners
    setupQueueEvents();

    app.listen(PORT, () => {
        console.log(`\n🚀  IntelliDoc API running on http://localhost:${PORT}`);
        console.log(`    Dashboard : http://localhost:${PORT}`);
        console.log(`    Health    : http://localhost:${PORT}/health\n`);
    });
})();
