"""
Validates uploaded bill photos (and PDFs) before they ever reach storage or
Groq. Never trusts the client-supplied Content-Type header alone -- Pillow
actually decodes the image (PyMuPDF actually opens the PDF) to confirm it's
a genuine, undamaged file, not just one with a spoofed extension/header.
"""
import io

import fitz  # PyMuPDF
import pillow_heif
from PIL import Image, UnidentifiedImageError
from flask import current_app

from app.errors import ValidationError

# Registers HEIC/HEIF (the format iPhones save photos in by default) as a
# format Pillow can actually decode. Without this, Pillow has no built-in
# HEIC support at all and every iPhone photo would be rejected outright.
# pillow-heif bundles its own libheif, so this works cross-platform with no
# separate system library install needed.
pillow_heif.register_heif_opener()


def validate_bill_image(file_storage) -> tuple[bytes, str]:
    """
    Returns (normalized_png_bytes, "image/png") or raises ValidationError.
    `file_storage` is a werkzeug FileStorage from request.files.

    Rather than maintaining an allow-list of accepted formats, this accepts
    ANY picture format Pillow (+ the HEIF plugin above) can genuinely
    decode -- JPEG, PNG, WEBP, HEIC/HEIF, GIF, BMP, TIFF, and more -- then
    re-encodes it to a single normalized PNG before it's stored or sent to
    Groq. That re-encoding does double duty: it guarantees Groq's vision
    API always receives a format it supports (some phone/format outputs
    aren't accepted by vision APIs directly), and it strips anything hidden
    in the original file's metadata/structure as a side effect of fully
    decoding and rebuilding the pixel data.
    """
    if file_storage is None or file_storage.filename == "":
        raise ValidationError("No image file was provided.")

    data = file_storage.read()
    max_bytes = current_app.config["MAX_BILL_IMAGE_BYTES"]
    if len(data) == 0:
        raise ValidationError("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise ValidationError(f"Image is too large (max {max_bytes // (1024 * 1024)} MB).")

    try:
        image = Image.open(io.BytesIO(data))
        image.verify()  # raises if not a genuine, undamaged image
        # Re-open after verify() -- verify() leaves the file unusable for further reads.
        image = Image.open(io.BytesIO(data))
        if getattr(image, "is_animated", False):
            image.seek(0)  # only the first frame matters for a bill photo
        image = image.convert("RGB")
    except Image.DecompressionBombError:
        raise ValidationError("This image is too large to process.")
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("That doesn't look like a valid photo. Please upload a real image file (or a PDF).")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), "image/png"


def is_pdf(file_storage) -> bool:
    """Content-sniffs the first bytes rather than trusting the filename or
    Content-Type header. Leaves the stream position reset to 0 either way
    so the caller can still read the full file afterwards."""
    if file_storage is None:
        return False
    file_storage.stream.seek(0)
    header = file_storage.stream.read(5)
    file_storage.stream.seek(0)
    return header == b"%PDF-"


# Groq's vision API accepts at most 5 images in a single request. A bill
# PDF is virtually never longer than this in practice, but if it is, we
# still only send the first 5 pages -- better to extract what we can than
# to fail the whole upload outright.
MAX_PDF_PAGES_FOR_EXTRACTION = 5


def validate_bill_pdf(file_storage) -> tuple[bytes, list[bytes]]:
    """
    Validates an uploaded PDF and rasterizes up to MAX_PDF_PAGES_FOR_EXTRACTION
    of its pages to PNGs for the (image-only) Groq vision extraction
    pipeline. Returns (original_pdf_bytes, [rasterized_page_png_bytes, ...]);
    the original PDF bytes are what get stored (so the user can still
    download their real file later), the PNG bytes are only used for
    extraction. All pages are treated as one document -- see
    groq_client.extract_bills_from_images -- since a single bill's fields
    (or several separate bills) can be split across pages.
    """
    if file_storage is None or file_storage.filename == "":
        raise ValidationError("No file was provided.")

    data = file_storage.read()
    max_bytes = current_app.config["MAX_BILL_IMAGE_BYTES"]
    if len(data) == 0:
        raise ValidationError("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise ValidationError(f"File is too large (max {max_bytes // (1024 * 1024)} MB).")

    try:
        pdf = fitz.open(stream=data, filetype="pdf")
        try:
            if pdf.page_count < 1:
                raise ValueError("PDF has no pages.")
            page_pngs = []
            for page_index in range(min(pdf.page_count, MAX_PDF_PAGES_FOR_EXTRACTION)):
                page = pdf.load_page(page_index)
                # 2x the default 72 DPI so small bill text stays legible to
                # the vision model -- a bare 72 DPI render is often too blurry.
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                page_pngs.append(pixmap.tobytes("png"))
        finally:
            pdf.close()
    except ValidationError:
        raise
    except Exception:
        raise ValidationError("The uploaded file is not a valid PDF.")

    return data, page_pngs
