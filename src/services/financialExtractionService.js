const {
    INVOICE_DATE_PATTERNS,
    VENDOR_PATTERNS,
    TOTAL_AMOUNT_PATTERNS,
    GST_PATTERNS,
} = require('../utils/regexPatterns');
const { parseCurrency } = require('../utils/currencyParser');

// ─── Financial Extraction Service ──────────────────────────────────────────────
// Applies regex patterns against raw text to pull out structured financial
// fields: invoice_date, vendor, total_amount, gst.
// ────────────────────────────────────────────────────────────────────────────────

/**
 * matchFirst – tries each pattern in order and returns the first capture
 * group match found, or null.
 */
function matchFirst(text, patterns) {
    for (const pattern of patterns) {
        const match = text.match(pattern);
        if (match && match[1]) {
            return match[1].trim();
        }
    }
    return null;
}

/**
 * normalizeDate – attempts to convert the various captured date strings
 * into a standard YYYY-MM-DD format suitable for DATEONLY storage.
 *
 * @param  {string} raw  e.g. "15/03/2024", "2024-03-15", "15 Mar 2024"
 * @return {string|null} ISO date string or null
 */
function normalizeDate(raw) {
    if (!raw) return null;

    // Try native Date parsing first (handles ISO & many common formats)
    const parsed = new Date(raw);
    if (!isNaN(parsed.getTime())) {
        return parsed.toISOString().split('T')[0]; // YYYY-MM-DD
    }

    // Handle DD/MM/YYYY or DD.MM.YYYY (common Indian format)
    const ddmmyyyy = raw.match(/(\d{1,2})[\/.](\d{1,2})[\/.](\d{2,4})/);
    if (ddmmyyyy) {
        let [, day, month, year] = ddmmyyyy;
        if (year.length === 2) year = '20' + year;
        const d = new Date(`${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`);
        if (!isNaN(d.getTime())) return d.toISOString().split('T')[0];
    }

    return null;
}

/**
 * extractFinancialFields – main entry point. Extracts and normalises
 * financial data from raw document text.
 *
 * @param  {string} text  Full text extracted from the document
 * @return {object}       { invoice_date, vendor, total_amount, gst }
 */
function extractFinancialFields(text) {
    if (!text || typeof text !== 'string') {
        return { invoice_date: null, vendor: null, total_amount: null, gst: null };
    }

    // Extract raw matches using regex patterns
    const rawDate = matchFirst(text, INVOICE_DATE_PATTERNS);
    const rawVendor = matchFirst(text, VENDOR_PATTERNS);
    const rawTotal = matchFirst(text, TOTAL_AMOUNT_PATTERNS);
    const rawGst = matchFirst(text, GST_PATTERNS);

    // Normalise into storage-ready values
    const invoice_date = normalizeDate(rawDate);
    const vendor = rawVendor ? rawVendor.replace(/\s+/g, ' ').trim() : null;
    const total_amount = parseCurrency(rawTotal);
    const gst = parseCurrency(rawGst);

    console.log('  📊 Extracted fields:', { invoice_date, vendor, total_amount, gst });

    return { invoice_date, vendor, total_amount, gst };
}

module.exports = { extractFinancialFields, normalizeDate, matchFirst };
