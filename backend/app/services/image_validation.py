"""
Validates uploaded bill photos before they ever reach storage or Groq.
Never trusts the client-supplied Content-Type header alone -- Pillow
actually decodes the image to confirm it's a real image of a supported
format and to reject disguised/malicious files.
"""
import io

from PIL import Image, UnidentifiedImageError
from flask import current_app

from app.errors import ValidationError

_PIL_FORMAT_TO_CONTENT_TYPE = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "HEIF": "image/heic",
    "MPO": "image/jpeg",  # some phone JPEGs decode as MPO (multi-picture)
}


def validate_bill_image(file_storage) -> tuple[bytes, str]:
    """
    Returns (validated_bytes, canonical_content_type) or raises
    ValidationError. `file_storage` is a werkzeug FileStorage from
    request.files.
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
        image_format = (image.format or "").upper()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("The uploaded file is not a valid image.")

    content_type = _PIL_FORMAT_TO_CONTENT_TYPE.get(image_format)
    if content_type is None or content_type not in current_app.config["ALLOWED_IMAGE_CONTENT_TYPES"]:
        raise ValidationError(
            "Unsupported image format. Please upload a JPEG, PNG, WEBP, or HEIC photo."
        )

    return data, content_type
