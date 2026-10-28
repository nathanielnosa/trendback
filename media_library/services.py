"""Validation and processing for uploaded images."""
import uuid
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

MAX_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_DIMENSION = 6000  # pixels, width or height
THUMBNAIL_SIZE = (400, 400)

# Pillow format name -> (content type, file extension)
ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
    "GIF": ("image/gif", ".gif"),
}


def inspect_image(upload):
    """Return the real format of an upload, or raise ValueError with a user message.

    The file is judged by its content, never by its name or the browser's
    content type, so a renamed text file or an SVG is refused.
    """
    if upload.size > MAX_BYTES:
        raise ValueError(f"Image is too large. The limit is {MAX_BYTES // (1024 * 1024)} MB.")

    try:
        upload.seek(0)
        image = Image.open(upload)
        image.verify()
        fmt = image.format
        upload.seek(0)
        width, height = Image.open(upload).size
    except Exception:
        raise ValueError("Upload a valid image.")
    finally:
        upload.seek(0)

    if fmt not in ALLOWED_FORMATS:
        raise ValueError("Only JPEG, PNG, WebP and GIF images are allowed.")

    if max(width, height) > MAX_DIMENSION:
        raise ValueError(f"Image is too large. The maximum is {MAX_DIMENSION} pixels on either side.")

    return fmt


def make_thumbnail(upload):
    """Return a small WebP copy of the upload as a ContentFile."""
    upload.seek(0)
    image = ImageOps.exif_transpose(Image.open(upload))
    image.thumbnail(THUMBNAIL_SIZE)
    image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P", "PA") else "RGB")

    buffer = BytesIO()
    image.save(buffer, "WEBP", quality=82)
    upload.seek(0)
    return ContentFile(buffer.getvalue())


def create_media(user, upload, alt_text=""):
    """Validate, store and record an uploaded image. Returns the Media object."""
    from .models import Media

    fmt = inspect_image(upload)
    content_type, extension = ALLOWED_FORMATS[fmt]
    name = uuid.uuid4().hex

    media = Media(
        uploaded_by=user,
        original_name=(upload.name or "image")[:255],
        alt_text=alt_text,
        content_type=content_type,
        size=upload.size,
    )
    # The stored name is ours; whatever the client called the file is ignored.
    media.file.save(f"{name}{extension}", upload, save=False)
    media.thumbnail.save(f"{name}.webp", make_thumbnail(upload), save=False)
    media.save()
    return media