// ─── Regex Patterns for Financial Field Extraction ─────────────────────────────
// Each pattern is designed to capture common Indian invoice formats as well as
// international standards. Patterns return the captured value in group 1.
// ────────────────────────────────────────────────────────────────────────────────

/**
 * Invoice date patterns — matches formats like:
 *   Date: 15/03/2024  |  Invoice Date: 2024-03-15  |  Dated: 15 Mar 2024
 */
const INVOICE_DATE_PATTERNS = [
    /(?:invoice\s*date|date|dated|inv\.?\s*date)\s*[:\-–]?\s*(\d{1,2}[\/.]\d{1,2}[\/.]\d{2,4})/i,
    /(?:invoice\s*date|date|dated)\s*[:\-–]?\s*(\d{4}[\-\/]\d{1,2}[\-\/]\d{1,2})/i,
    /(?:invoice\s*date|date|dated)\s*[:\-–]?\s*(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})/i,
];

/**
 * Vendor / payee patterns — tries common invoice header labels:
 *   From: Acme Corp  |  Vendor: Acme Corp  |  Bill From: Acme Corp
 */
const VENDOR_PATTERNS = [
    /(?:vendor|supplier|from|bill\s*from|sold\s*by|company)\s*[:\-–]?\s*([A-Za-z0-9][^\n\r]{2,60}?)(?:\s*\n|\s{2,}|$)/i,
    /(?:M\/s\.?|Messrs\.?)\s+([A-Za-z0-9][^\n\r]{2,60}?)(?:\s*\n|\s{2,}|$)/i,
];

/**
 * Total amount patterns — handles Indian ₹ notation and commas:
 *   Total: ₹1,20,000.00  |  Grand Total ₹ 50,000  |  Amount Due: Rs. 1,00,000
 */
const TOTAL_AMOUNT_PATTERNS = [
    /(?:total\s*amount|grand\s*total|total|amount\s*due|net\s*amount|balance\s*due)\s*[:\-–]?\s*[₹$]?\s*([\d,]+(?:\.\d{1,2})?)/i,
    /(?:total\s*amount|grand\s*total|total|amount\s*due)\s*[:\-–]?\s*(?:Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)/i,
];

/**
 * GST / Tax patterns:
 *   GST: ₹21,600  |  IGST @18% ₹21,600  |  Tax Amount: 21600
 */
const GST_PATTERNS = [
    /(?:gst|sgst|cgst|igst|tax\s*amount|total\s*tax|vat)\s*(?:@\s*\d+%?)?\s*[:\-–]?\s*[₹$]?\s*([\d,]+(?:\.\d{1,2})?)/i,
    /(?:gst|tax)\s*(?:@\s*\d+%?)?\s*[:\-–]?\s*(?:Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)/i,
];

module.exports = {
    INVOICE_DATE_PATTERNS,
    VENDOR_PATTERNS,
    TOTAL_AMOUNT_PATTERNS,
    GST_PATTERNS,
};
