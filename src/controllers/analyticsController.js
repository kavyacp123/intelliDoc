const analyticsService = require('../services/analyticsService');

// ─── Analytics Controller ──────────────────────────────────────────────────────

/**
 * getMonthlySummary – handles GET /analytics/monthly-summary
 *
 * Returns aggregated financial data grouped by month.
 */
async function getMonthlySummary(req, res, next) {
    try {
        const summary = await analyticsService.getMonthlySummary();
        return res.json({ success: true, data: summary });
    } catch (error) {
        next(error);
    }
}

/**
 * compareMonths – handles GET /analytics/compare-months
 *
 * Returns the two most recent months of financial data for comparison.
 */
async function compareMonths(req, res, next) {
    try {
        const comparison = await analyticsService.compareLastMonths();
        return res.json({ success: true, data: comparison });
    } catch (error) {
        next(error);
    }
}

/**
 * getVendorTotals – handles GET /analytics/vendor-totals
 *
 * Returns aggregated financial data grouped by vendor.
 */
async function getVendorTotals(req, res, next) {
    try {
        const vendors = await analyticsService.getVendorTotals();
        return res.json({ success: true, data: vendors });
    } catch (error) {
        next(error);
    }
}

module.exports = { getMonthlySummary, compareMonths, getVendorTotals };
