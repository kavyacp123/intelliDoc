"""
IntelliDoc Worker — Image Preprocessing (Stage 2)

OpenCV pipeline to improve OCR accuracy on scanned documents.
Steps: grayscale → denoise → contrast normalise → deskew → binarise.
"""

import cv2
import numpy as np
from PIL import Image


def preprocess_image(pil_image: Image.Image) -> np.ndarray:
    """
    Apply a full preprocessing pipeline to a PIL image.

    Returns a cleaned OpenCV image (numpy array) ready for OCR.
    """
    # Convert PIL → OpenCV (RGB → BGR)
    img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    # Step 1 — Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Step 2 — Remove noise (non-local means denoising)
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    # Step 3 — Normalise contrast (CLAHE — adaptive histogram equalisation)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    normalised = clahe.apply(denoised)

    # Step 4 — Deskew (correct tilt from scanning)
    deskewed = _deskew(normalised)

    # Step 5 — Binarise (adaptive thresholding for mixed lighting)
    binary = cv2.adaptiveThreshold(
        deskewed, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=15,
        C=8,
    )

    return binary


def _deskew(image: np.ndarray) -> np.ndarray:
    """
    Detect and correct skew angle using Hough line transform.
    Only corrects angles within ±15° to avoid flipping the image.
    """
    # Detect edges
    edges = cv2.Canny(image, 50, 150, apertureSize=3)

    # Find lines using Hough transform
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100,
                            minLineLength=100, maxLineGap=10)

    if lines is None or len(lines) == 0:
        return image

    # Calculate the median angle of detected lines
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if -15 < angle < 15:  # Only consider near-horizontal lines
            angles.append(angle)

    if not angles:
        return image

    median_angle = np.median(angles)

    # Skip correction if the skew is negligible
    if abs(median_angle) < 0.5:
        return image

    # Rotate to correct the skew
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h),
                             flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_REPLICATE)

    return rotated


def opencv_to_pil(cv_image: np.ndarray) -> Image.Image:
    """Convert an OpenCV grayscale/binary image back to PIL (for downstream use)."""
    return Image.fromarray(cv_image)
