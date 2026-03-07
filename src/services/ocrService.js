const Tesseract = require('tesseract.js');
const sharp = require('sharp');
const { pdfToPng } = require('pdf-to-png-converter');

// ─── OCR Service ───────────────────────────────────────────────────────────────
// Provides Optical Character Recognition as a fallback when pdf-parse cannot
// extract sufficient text (< 500 chars).
//
// Pipeline:
//   PDF buffer → pdf-to-png-converter (renders pages as PNGs)
//              → sharp (grayscale / normalize / sharpen / threshold)
//              → tesseract.js (text recognition)
// ────────────────────────────────────────────────────────────────────────────────

/**
 * preprocessImage – applies image transformations to maximise OCR accuracy.
 *
 * Pipeline: grayscale → normalize → sharpen → threshold (binarise)
 *
 * @param  {Buffer} imageBuffer  Raw PNG buffer
 * @return {Buffer}              Preprocessed PNG buffer
 */
async function preprocessImage(imageBuffer) {
    return sharp(imageBuffer)
        .grayscale()
        .normalize()
        .sharpen({ sigma: 1.5 })
        .threshold(160)
        .png()
        .toBuffer();
}

/**
 * extractTextFromImage – runs Tesseract OCR on a single image buffer
 * after preprocessing.
 *
 * @param  {Buffer} imageBuffer  Raw image buffer
 * @return {string}              Recognised text
 */
async function extractTextFromImage(imageBuffer) {
    const processed = await preprocessImage(imageBuffer);

    const {
        data: { text },
    } = await Tesseract.recognize(processed, 'eng', {
        logger: (info) => {
            if (info.status === 'recognizing text') {
                console.log(`  🔍 OCR progress: ${(info.progress * 100).toFixed(0)}%`);
            }
        },
    });

    return text || '';
}

/**
 * extractTextFromPDFBuffer – converts each page of a PDF to a PNG image
 * using pdf-to-png-converter (pure JS, no native deps), then runs OCR
 * on every page and concatenates the results.
 *
 * @param  {Buffer} pdfBuffer  Raw PDF file contents
 * @return {string}            Full recognised text across all pages
 */
async function extractTextFromPDFBuffer(pdfBuffer) {
    try {
        console.log('  📄 Converting PDF pages to images...');

        // Render all pages at 300 DPI as PNG buffers
        const pages = await pdfToPng(pdfBuffer, {
            viewportScale: 2.0, // higher scale = better OCR quality
        });

        console.log(`  📄 Rendered ${pages.length} page(s). Running OCR...`);

        const texts = [];
        for (let i = 0; i < pages.length; i++) {
            console.log(`  📝 Page ${i + 1}/${pages.length}...`);
            const pageText = await extractTextFromImage(pages[i].content);
            texts.push(pageText);
        }

        return texts.join('\n\n--- Page Break ---\n\n');
    } catch (error) {
        console.error('⚠️  OCR pipeline failed:', error.message);
        return '';
    }
}

module.exports = {
    preprocessImage,
    extractTextFromImage,
    extractTextFromPDFBuffer,
};
