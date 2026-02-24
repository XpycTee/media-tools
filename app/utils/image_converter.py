from PIL import Image, ImageColor
import io
import zipfile
import re
import hashlib
from typing import List, Tuple

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    pillow_heif.register_avif_opener()
except Exception:
    # pillow-heif optional
    pass


def _normalize_format(fmt: str) -> str:
    fmt = fmt.strip().lower()
    if fmt in ("jpg", "jpeg"):
        return "JPEG"
    return fmt.upper()


def convert_images(files, target_format: str, quality: int = 85):
    """Convert uploaded file objects to `target_format`.

    files: iterable of objects with `.filename` and `.stream` or `.read()` (Flask `FileStorage`).
    Returns: (bytes, content_type, filename)
    """
    pil_format = _normalize_format(target_format)

    if pil_format == 'HEIF':
        content_type = 'image/heif'
    elif pil_format == 'AVIF':
        content_type = 'image/avif'
    else:
        content_type = f'image/{target_format.lower()}'

    result_files = []

    for f in files:
        original_name = getattr(f, 'filename', 'image')
        out_name = re.sub(r"\.[^.]+$", f".{target_format}", original_name)
        # Flask FileStorage exposes .stream; also support raw file-like
        stream = getattr(f, 'stream', None)
        if stream is None:
            # try reading bytes
            raw = f.read()
            stream = io.BytesIO(raw)

        with Image.open(stream) as img:
            if img.mode in ('RGBA', 'LA') and pil_format == 'JPEG':
                background = Image.new('RGB', img.size, ImageColor.getrgb("white"))
                background.paste(img, img.split()[-1])
                img = background

            if pil_format in ('JPEG', 'BMP') and img.mode != 'RGB':
                img = img.convert('RGB')

            save_kwargs = {}
            if pil_format in ('JPEG', 'WEBP'):
                save_kwargs['quality'] = quality

            with io.BytesIO() as out_buf:
                img.save(out_buf, pil_format, **save_kwargs)
                result_files.append((out_buf.getvalue(), out_name))

    if not result_files:
        raise ValueError('No images to convert')

    if len(result_files) == 1:
        data, fname = result_files[0]
        return data, content_type, fname

    # multiple files -> zip
    file_names = []
    with io.BytesIO() as zip_buf:
        with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as z:
            for file_bytes, fname in result_files:
                z.writestr(fname, file_bytes)
                file_names.append(re.sub(r"\.[^.]+$", '', fname))
        data = zip_buf.getvalue()

    zip_name = f"{'+'.join(file_names)}_{hashlib.md5(data).hexdigest()[:12]}.zip"
    return data, 'application/zip', zip_name

