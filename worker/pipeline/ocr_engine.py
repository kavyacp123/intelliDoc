"""
IntelliDoc Worker — OCR Engine (Stage 3)

Uses PaddleOCR as the primary OCR engine.
Returns structured results: text + bounding boxes + confidence scores.
"""

from paddleocr import PaddleOCR
import numpy as np
from PIL import Image

# ─── Singleton OCR Instance ─────────────────────────────────────────────────────
# PaddleOCR is expensive to initialise (~2s). We reuse a single instance
# across all page invocations for performance.
# ────────────────────────────────────────────────────────────────────────────────

_ocr_instance = None


def _get_ocr():
    """Lazy-initialise and return the PaddleOCR singleton."""
    global _ocr_instance
    if _ocr_instance is None:
        print("  🔧 Initialising PaddleOCR engine...")
        _ocr_instance = PaddleOCR(
            use_angle_cls=True,   # auto-detect text rotation
            lang="en",
        )
    return _ocr_instance


def run_ocr(image) -> list[dict]:
    """
    Run PaddleOCR on an image and return structured results.

    Args:
        image: PIL Image, numpy array, or file path.

    Returns:
        List of dicts, each with:
            - text:       recognised string
            - bbox:       [x1, y1, x2, y2] bounding box
            - confidence: float 0-1
    """
    ocr = _get_ocr()

    # Convert PIL Image to numpy array if needed
    if isinstance(image, Image.Image):
        image = np.array(image)

    results = ocr.ocr(image)

    if not results or not results[0]:
        return []

    structured = []
    for line in results[0]:
        bbox_points = line[0]   # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        text = line[1][0]
        confidence = float(line[1][1])

        # Convert 4-point polygon to simple [x1, y1, x2, y2] rectangle
        xs = [p[0] for p in bbox_points]
        ys = [p[1] for p in bbox_points]
        bbox = [min(xs), min(ys), max(xs), max(ys)]

        structured.append({
            "text": text.strip(),
            "bbox": bbox,
            "confidence": confidence,
        })

    return structured


def get_full_text(ocr_results: list[dict]) -> str:
    """Concatenate all OCR text blocks into a single string."""
    return "\n".join(r["text"] for r in ocr_results)
