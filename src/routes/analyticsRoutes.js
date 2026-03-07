const express = require('express');
const {
    getMonthlySummary,
    compareMonths,
    getVendorTotals,
} = require('../controllers/analyticsController');

const router = express.Router();

// ─── Analytics Routes ──────────────────────────────────────────────────────────

// Aggregated monthly financial summary
router.get('/monthly-summary', getMonthlySummary);

// Compare the two most recent months
router.get('/compare-months', compareMonths);

// Financial totals grouped by vendor
router.get('/vendor-totals', getVendorTotals);

module.exports = router;
