const { QueryTypes } = require('sequelize');
const { sequelize } = require('../config/database');

// ─── Analytics Service ─────────────────────────────────────────────────────────
// SQL aggregation queries against the invoice_records table.
// ────────────────────────────────────────────────────────────────────────────────

async function getMonthlySummary() {
    return sequelize.query(
        `SELECT
       TO_CHAR(COALESCE(invoice_date, created_at::date), 'YYYY-MM') AS month,
       COUNT(*)::int                          AS total_invoices,
       COALESCE(SUM(grand_total), 0)::float   AS total_revenue,
       COALESCE(SUM(cgst), 0)::float          AS total_cgst,
       COALESCE(SUM(sgst), 0)::float          AS total_sgst,
       COALESCE(SUM(igst), 0)::float          AS total_igst
     FROM invoice_records
     GROUP BY month
     ORDER BY month DESC`,
        { type: QueryTypes.SELECT }
    );
}

async function compareLastMonths() {
    return sequelize.query(
        `SELECT
       TO_CHAR(COALESCE(invoice_date, created_at::date), 'YYYY-MM') AS month,
       COUNT(*)::int                          AS total_invoices,
       COALESCE(SUM(grand_total), 0)::float   AS total_revenue,
       COALESCE(SUM(cgst), 0)::float          AS total_cgst,
       COALESCE(SUM(sgst), 0)::float          AS total_sgst,
       COALESCE(SUM(igst), 0)::float          AS total_igst
     FROM invoice_records
     GROUP BY month
     ORDER BY month DESC
     LIMIT 2`,
        { type: QueryTypes.SELECT }
    );
}

async function getVendorTotals() {
    return sequelize.query(
        `SELECT
       COALESCE(vendor, 'Unknown')            AS vendor,
       COUNT(*)::int                          AS total_invoices,
       COALESCE(SUM(grand_total), 0)::float   AS total_revenue,
       COALESCE(SUM(cgst + sgst + igst), 0)::float AS total_tax
     FROM invoice_records
     GROUP BY vendor
     ORDER BY total_revenue DESC`,
        { type: QueryTypes.SELECT }
    );
}

module.exports = { getMonthlySummary, compareLastMonths, getVendorTotals };
