// ─── Currency Parser ───────────────────────────────────────────────────────────
// Converts human-readable currency strings to numeric values.
//
//   ₹1,20,000.50  →  120000.50
//   Rs. 50,000     →  50000
//   $1,234.56      →  1234.56
//   21600           →  21600
// ────────────────────────────────────────────────────────────────────────────────

/**
 * parseCurrency – strips currency symbols, commas, and whitespace, then
 * returns the numeric value as a float.
 *
 * @param  {string} str  Raw currency string (e.g. "₹1,20,000.50")
 * @return {number|null} Parsed number or null if input is invalid
 */
function parseCurrency(str) {
    if (!str || typeof str !== 'string') return null;

    // Remove currency symbols (₹, $, Rs, INR), commas, and whitespace
    const cleaned = str
        .replace(/[₹$]/g, '')
        .replace(/Rs\.?/gi, '')
        .replace(/INR/gi, '')
        .replace(/,/g, '')
        .replace(/\s/g, '')
        .trim();

    if (!cleaned || cleaned.length === 0) return null;

    const value = parseFloat(cleaned);
    return isNaN(value) ? null : value;
}

module.exports = { parseCurrency };
