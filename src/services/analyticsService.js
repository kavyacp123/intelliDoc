const { QueryTypes } = require('sequelize');
const { sequelize } = require('../config/database');

// ─── Analytics Service ─────────────────────────────────────────────────────────
// Provides aggregated financial insights by running SQL queries against the
// financial_records table. All functions return plain objects / arrays.
// ────────────────────────────────────────────────────────────────────────────────

/**
 * getMonthlySummary – returns one row per month with total bills, total
 * amount, and total GST for all processed financial records.
 *
 * Rows are sorted newest-first.
 *
 * @return {Array<{ month: string, total_bills: number, total_amount: number, total_gst: number }>}
 */
async function getMonthlySummary() {
    const results = await sequelize.query(
        `
    SELECT
      TO_CHAR(
        COALESCE(invoice_date, created_at::date),
        'YYYY-MM'
      )                                   AS month,
      COUNT(*)::int                       AS total_bills,
      COALESCE(SUM(total_amount), 0)::float AS total_amount,
      COALESCE(SUM(gst), 0)::float        AS total_gst
    FROM financial_records
    GROUP BY month
    ORDER BY month DESC;
    `,
        { type: QueryTypes.SELECT }
    );

    return results;
}

/**
 * compareLastMonths – returns the same aggregation as getMonthlySummary
 * but limited to the two most recent months, making it easy for the caller
 * to compute deltas.
 *
 * @return {Array} Up to 2 monthly summary rows (newest first)
 */
async function compareLastMonths() {
    const results = await sequelize.query(
        `
    SELECT
      TO_CHAR(
        COALESCE(invoice_date, created_at::date),
        'YYYY-MM'
      )                                   AS month,
      COUNT(*)::int                       AS total_bills,
      COALESCE(SUM(total_amount), 0)::float AS total_amount,
      COALESCE(SUM(gst), 0)::float        AS total_gst
    FROM financial_records
    GROUP BY month
    ORDER BY month DESC
    LIMIT 2;
    `,
        { type: QueryTypes.SELECT }
    );

    return results;
}

/**
 * getVendorTotals – returns total amount and bill count grouped by vendor.
 * Nulls are coalesced to "Unknown Vendor".
 *
 * @return {Array<{ vendor: string, total_bills: number, total_amount: number, total_gst: number }>}
 */
async function getVendorTotals() {
    const results = await sequelize.query(
        `
    SELECT
      COALESCE(vendor, 'Unknown Vendor')  AS vendor,
      COUNT(*)::int                       AS total_bills,
      COALESCE(SUM(total_amount), 0)::float AS total_amount,
      COALESCE(SUM(gst), 0)::float        AS total_gst
    FROM financial_records
    GROUP BY vendor
    ORDER BY total_amount DESC;
    `,
        { type: QueryTypes.SELECT }
    );

    return results;
}

module.exports = { getMonthlySummary, compareLastMonths, getVendorTotals };
