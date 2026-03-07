"""
IntelliDoc Worker — OCR Engine (Stage 3)

Uses AWS Textract as the primary OCR engine.
Returns structured results: text + bounding boxes + confidence scores.
"""

import os
import io
import boto3
import numpy as np
from PIL import Image

# ─── Singleton OCR Instance ─────────────────────────────────────────────────────
# We reuse a single client instance for performance.
# ────────────────────────────────────────────────────────────────────────────────

_textract_client = None


def _get_client():
    """Lazy-initialise and return the AWS Textract Client."""
    global _textract_client
    if _textract_client is None:
        print("  🔧 Initialising AWS Textract client...")
        _textract_client = boto3.client(
            'textract',
            region_name=os.getenv("AWS_REGION_NAME", "us-east-1")
            # Uses AWS_ACCESS_KEY_ID & AWS_SECRET_ACCESS_KEY from env automatically
        )
    return _textract_client


def run_ocr(image) -> list[dict]:
    """
    Run AWS Textract on an image and return structured results.

    Args:
        image: PIL Image, numpy array, or file path.

    Returns:
        List of dicts, each with:
            - text:       recognised string
            - bbox:       [x1, y1, x2, y2]
            - confidence: float 0-1
    """
    client = _get_client()

    # We need image width and height to convert Textract's relative
    # bounding boxes back to absolute pixels
    img_width, img_height = 0, 0

    # Convert PIL Image or numpy array to bytes for AWS Textract
    if isinstance(image, str) and os.path.isfile(image):
        with Image.open(image) as pil_img:
            img_width, img_height = pil_img.size
        with io.open(image, 'rb') as image_file:
            content = image_file.read()
    else:
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        # It's a PIL Image
        img_width, img_height = image.size
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        content = img_byte_arr.getvalue()

    response = client.detect_document_text(Document={'Bytes': content})

    structured = []

    # Parse the Textract LINE blocks
    for block in response.get('Blocks', []):
        if block['BlockType'] == 'LINE':
            text = block.get('Text', '')
            confidence = block.get('Confidence', 0) / 100.0  # Convert 0-100 to 0-1
            
            # Textract returns:
            # Width, Height, Left, Top as float ratios (0 to 1)
            box = block['Geometry']['BoundingBox']
            
            x1 = box['Left'] * img_width
            y1 = box['Top'] * img_height
            x2 = x1 + (box['Width'] * img_width)
            y2 = y1 + (box['Height'] * img_height)

            structured.append({
                "text": text,
                "bbox": [x1, y1, x2, y2],
                "confidence": confidence,
            })

    return structured


def get_full_text(ocr_results: list[dict]) -> str:
    """Concatenate all OCR text blocks into a single string."""
    return "\n".join(r["text"] for r in ocr_results)
