const express = require('express');
const {
    getMonthlySummary, compareMonths, getVendorTotals,
} = require('../controllers/analyticsController');

const router = express.Router();

router.get('/monthly-summary', getMonthlySummary);
router.get('/compare-months', compareMonths);
router.get('/vendor-totals', getVendorTotals);

module.exports = router;
