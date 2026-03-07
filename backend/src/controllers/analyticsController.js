const analyticsService = require('../services/analyticsService');

// ─── Analytics Controller ──────────────────────────────────────────────────────

async function getMonthlySummary(req, res, next) {
    try {
        return res.json({ success: true, data: await analyticsService.getMonthlySummary() });
    } catch (error) { next(error); }
}

async function compareMonths(req, res, next) {
    try {
        return res.json({ success: true, data: await analyticsService.compareLastMonths() });
    } catch (error) { next(error); }
}

async function getVendorTotals(req, res, next) {
    try {
        return res.json({ success: true, data: await analyticsService.getVendorTotals() });
    } catch (error) { next(error); }
}

module.exports = { getMonthlySummary, compareMonths, getVendorTotals };
