"""
IntelliDoc Worker — PDF Loader (Stage 1)

Loads PDF files and splits them into per-page PIL images.
Uses pdf2image (poppler-based) for high-quality rasterisation.
"""

from pdf2image import convert_from_path
from PIL import Image
import os


def load_pdf(file_path: str, dpi: int = 300) -> list[Image.Image]:
    """
    Convert a PDF file into a list of PIL Images (one per page).

    Args:
        file_path: Absolute path to the PDF file.
        dpi: Resolution for rendering. Higher = better OCR but slower.

    Returns:
        List of PIL Image objects, one per page.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        RuntimeError: If pdf2image / poppler fails.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF not found: {file_path}")

    print(f"  📄 Loading PDF: {os.path.basename(file_path)} at {dpi} DPI...")

    pages = convert_from_path(
        file_path,
        dpi=dpi,
        fmt="png",
        thread_count=os.cpu_count() or 2,
    )

    print(f"  📄 Rendered {len(pages)} page(s).")
    return pages


def load_image(file_path: str) -> list[Image.Image]:
    """
    Load a single image file (PNG, JPEG, TIFF) as a list
    with one element — keeps the interface consistent with load_pdf.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Image not found: {file_path}")

    img = Image.open(file_path).convert("RGB")
    return [img]
