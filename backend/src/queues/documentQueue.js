const { Queue, QueueEvents } = require('bullmq');
const Document = require('../models/Document');

// ─── Redis Connection ──────────────────────────────────────────────────────────

const redisConnection = {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT, 10) || 6379,
    password: process.env.REDIS_PASSWORD || undefined,
    maxRetriesPerRequest: null,
};

// ─── BullMQ Queue ──────────────────────────────────────────────────────────────
// Jobs are consumed by the Python worker (via Redis directly).
// ────────────────────────────────────────────────────────────────────────────────

const documentQueue = new Queue('document-processing', {
    connection: redisConnection,
    defaultJobOptions: {
        attempts: 3,
        backoff: { type: 'exponential', delay: 5000 },
        removeOnComplete: { count: 100 },
        removeOnFail: { count: 200 },
    },
});

/**
 * enqueueDocument – push a processing job onto the Redis queue.
 *
 * @param {string} documentId  UUID of the document to process
 * @param {string} filePath    Absolute path to the uploaded file
 */
async function enqueueDocument(documentId, filePath) {
    const job = await documentQueue.add('process-document', {
        documentId,
        filePath,
        enqueuedAt: new Date().toISOString(),
    });

    console.log(`📨  Job ${job.id} enqueued for document ${documentId}`);
    return job;
}

// ─── Queue Event Listeners ─────────────────────────────────────────────────────
// Update document status as jobs progress through the queue.
// ────────────────────────────────────────────────────────────────────────────────

function setupQueueEvents() {
    const queueEvents = new QueueEvents('document-processing', {
        connection: redisConnection,
    });

    queueEvents.on('completed', async ({ jobId, returnvalue }) => {
        console.log(`✅  Job ${jobId} completed.`);
    });

    queueEvents.on('failed', async ({ jobId, failedReason }) => {
        console.error(`❌  Job ${jobId} failed: ${failedReason}`);
    });

    queueEvents.on('stalled', async ({ jobId }) => {
        console.warn(`⚠️   Job ${jobId} stalled — will be retried.`);
    });

    console.log('📡  Queue event listeners attached.');
    return queueEvents;
}

module.exports = { documentQueue, enqueueDocument, setupQueueEvents, redisConnection };
