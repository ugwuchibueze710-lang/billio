"""
Object storage (Cloudflare R2, S3-compatible) for uploaded bill photos.
Postgres never stores image bytes -- only the metadata + storage key
(see app/models/document.py). Every read/write here requires the caller to
have already verified the requesting user owns the associated document;
this module does not perform authorization itself.
"""
import logging
import mimetypes
import uuid

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from flask import current_app

from app.errors import UpstreamServiceError

logger = logging.getLogger("billio.storage")

_EXTENSION_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
}


def _client():
    cfg = current_app.config
    if not all([cfg.get("S3_ENDPOINT_URL"), cfg.get("S3_ACCESS_KEY_ID"), cfg.get("S3_SECRET_ACCESS_KEY")]):
        raise UpstreamServiceError("File storage is not configured.")
    return boto3.client(
        "s3",
        endpoint_url=cfg["S3_ENDPOINT_URL"],
        aws_access_key_id=cfg["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["S3_SECRET_ACCESS_KEY"],
        region_name=cfg.get("S3_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


def build_storage_key(user_id, content_type: str) -> str:
    ext = _EXTENSION_BY_CONTENT_TYPE.get(content_type, "bin")
    # Namespaced by user id so a leaked/guessed key from one user's
    # object can never collide with, or be confused for, another user's.
    return f"users/{user_id}/bills/{uuid.uuid4()}.{ext}"


def upload_bytes(storage_key: str, data: bytes, content_type: str) -> None:
    bucket = current_app.config.get("S3_BUCKET_NAME")
    if not bucket:
        raise UpstreamServiceError("File storage is not configured.")
    try:
        _client().put_object(Bucket=bucket, Key=storage_key, Body=data, ContentType=content_type)
    except (BotoCoreError, ClientError) as exc:
        logger.error("storage_upload_failed", exc_info=exc)
        raise UpstreamServiceError("Failed to upload file. Please try again.") from exc


def generate_download_url(storage_key: str, expires_in: int = 300) -> str:
    bucket = current_app.config.get("S3_BUCKET_NAME")
    if not bucket:
        raise UpstreamServiceError("File storage is not configured.")
    try:
        return _client().generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": storage_key}, ExpiresIn=expires_in
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("storage_presign_failed", exc_info=exc)
        raise UpstreamServiceError("Failed to access file. Please try again.") from exc


def delete_object(storage_key: str) -> None:
    bucket = current_app.config.get("S3_BUCKET_NAME")
    if not bucket:
        return
    try:
        _client().delete_object(Bucket=bucket, Key=storage_key)
    except (BotoCoreError, ClientError) as exc:
        logger.error("storage_delete_failed", exc_info=exc)
        # Deletion failures should not block the surrounding operation
        # (e.g. account deletion) -- log and continue.
