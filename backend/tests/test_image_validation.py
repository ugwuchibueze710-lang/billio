import io

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.errors import ValidationError
from app.services.image_validation import validate_bill_image


def _fake_png_file(size=(10, 10)):
    buf = io.BytesIO()
    Image.new("RGB", size, color=(255, 0, 0)).save(buf, format="PNG")
    buf.seek(0)
    return FileStorage(stream=buf, filename="bill.png", content_type="image/png")


def test_validate_bill_image_accepts_real_png(app):
    with app.app_context():
        data, content_type = validate_bill_image(_fake_png_file())
        assert content_type == "image/png"
        assert len(data) > 0


def test_validate_bill_image_rejects_non_image_disguised_as_image(app):
    fake = FileStorage(stream=io.BytesIO(b"not actually an image, just text"), filename="bill.png", content_type="image/png")
    with app.app_context():
        with pytest.raises(ValidationError):
            validate_bill_image(fake)


def test_validate_bill_image_rejects_empty_file(app):
    fake = FileStorage(stream=io.BytesIO(b""), filename="bill.png", content_type="image/png")
    with app.app_context():
        with pytest.raises(ValidationError):
            validate_bill_image(fake)


def test_validate_bill_image_rejects_missing_file(app):
    with app.app_context():
        with pytest.raises(ValidationError):
            validate_bill_image(None)


def test_validate_bill_image_rejects_oversized_file(app):
    big = FileStorage(stream=io.BytesIO(b"\x00" * (11 * 1024 * 1024)), filename="bill.png", content_type="image/png")
    with app.app_context():
        with pytest.raises(ValidationError):
            validate_bill_image(big)
