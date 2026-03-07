"""
IntelliDoc Worker — Layout Detection (Stage 4)

Uses LayoutParser with PubLayNet model to detect document structure:
headers, tables, paragraphs, titles, footers.

This allows the pipeline to understand WHERE different content types
are on the page, improving extraction accuracy.
"""

import numpy as np
from PIL import Image

try:
    import layoutparser as lp
    LAYOUTPARSER_AVAILABLE = True
except ImportError:
    LAYOUTPARSER_AVAILABLE = False
    print("  ⚠️  LayoutParser not available — skipping layout detection.")


# ─── Layout Model ──────────────────────────────────────────────────────────────
# PubLayNet-trained Detectron2 model: detects 5 region types.
# ────────────────────────────────────────────────────────────────────────────────

_layout_model = None

LABEL_MAP = {0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"}


def _get_model():
    """Lazy-load the layout detection model."""
    global _layout_model
    if _layout_model is None and LAYOUTPARSER_AVAILABLE:
        print("  🔧 Loading LayoutParser PubLayNet model...")
        _layout_model = lp.Detectron2LayoutModel(
            config_path="lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config",
            extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.5],
            label_map=LABEL_MAP,
        )
    return _layout_model


def detect_layout(image) -> list[dict]:
    """
    Detect document layout regions in an image.

    Args:
        image: PIL Image or numpy array.

    Returns:
        List of dicts with:
            - type:       region type (Text, Title, Table, etc.)
            - bbox:       [x1, y1, x2, y2]
            - confidence: float 0-1
    """
    if not LAYOUTPARSER_AVAILABLE:
        return []

    model = _get_model()
    if model is None:
        return []

    if isinstance(image, Image.Image):
        image = np.array(image)

    layout = model.detect(image)

    regions = []
    for block in layout:
        regions.append({
            "type": block.type,
            "bbox": [
                block.block.x_1, block.block.y_1,
                block.block.x_2, block.block.y_2,
            ],
            "confidence": float(block.score),
        })

    print(f"  🏗️  Detected {len(regions)} layout regions: "
          f"{[r['type'] for r in regions]}")

    return regions


def get_table_regions(layout_regions: list[dict]) -> list[dict]:
    """Filter and return only table regions from layout detection."""
    return [r for r in layout_regions if r["type"] == "Table"]


def get_text_regions(layout_regions: list[dict]) -> list[dict]:
    """Filter and return text/title/list regions."""
    text_types = {"Text", "Title", "List"}
    return [r for r in layout_regions if r["type"] in text_types]
