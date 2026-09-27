import uuid
from functools import lru_cache

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import status
from fastapi.exceptions import HTTPException

from .config import settings

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}

MAX_IMAGE_BYTES = 5 * 1024 * 1024

ALLOWED_AUDIO_TYPES = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/aac": "aac",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
    "audio/aiff": "aiff",
    "audio/x-aiff": "aiff",
}

MAX_AUDIO_BYTES = 100 * 1024 * 1024

PRESIGN_EXPIRES_IN = 300  # seconds


@lru_cache
def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def public_url_for(key: str) -> str:
    """Build the public URL for a stored object key."""
    return f"{settings.R2_PUBLIC_URL.rstrip('/')}/{key}"


def _presigned_put(content_type: str, extension: str, folder: str) -> dict:
    """Return a presigned PUT URL for a direct browser upload to R2.

    Stores the object under ``folder/``. The content type is baked into the
    signature, so the client must send the same ``Content-Type`` header when it
    PUTs the file to ``upload_url``.
    """
    key = f"{folder.strip('/')}/{uuid.uuid4().hex}.{extension}"

    try:
        upload_url = get_r2_client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.R2_BUCKET_NAME,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=PRESIGN_EXPIRES_IN,
        )
    except (BotoCoreError, ClientError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not prepare the upload.",
        )

    return {
        "upload_url": upload_url,
        "key": key,
        "public_url": public_url_for(key),
        "expires_in": PRESIGN_EXPIRES_IN,
    }


def create_image_upload(content_type: str, folder: str) -> dict:
    """Presigned PUT for a browser image upload."""
    extension = ALLOWED_IMAGE_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported image type. Use JPEG, PNG, WEBP or GIF.",
        )
    return _presigned_put(content_type, extension, folder)


def create_audio_upload(content_type: str, folder: str) -> dict:
    """Presigned PUT for a browser audio upload.

    The stored object gets a public URL that AssemblyAI (batch) and ffmpeg
    (streaming) can fetch directly when the file is transcribed.
    """
    extension = ALLOWED_AUDIO_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported audio type. Use WAV, MP3, M4A, AAC, OGG, WEBM or FLAC.",
        )
    return _presigned_put(content_type, extension, folder)
