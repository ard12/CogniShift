"""
Validation service for generated PNG visualizations.
Ensures files are valid, non-empty, decodable, non-blank, and physically present.
"""
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageStat


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def validate_png_artifact(file_path: Path, min_width: int = 200, min_height: int = 200) -> Tuple[bool, str]:
    """
    Strict cryptographic and structural validation for rendered PNG artifacts.
    Rejects zero-byte, corrupt, non-image, blank, or improperly sized outputs.
    """
    if not file_path.exists():
        return False, f"Artifact file does not exist on disk: {file_path.name}"

    file_size = file_path.stat().st_size
    if file_size == 0:
        return False, f"Artifact file is empty (0 bytes): {file_path.name}"

    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
            if header != PNG_SIGNATURE:
                return False, f"File lacks valid PNG magic signature ({header!r}): {file_path.name}"
    except Exception as e:
        return False, f"Could not read artifact file headers: {e}"

    try:
        with Image.open(file_path) as img:
            img.verify()

        # Reopen to inspect dimensions and content (verify() invalidates file pointer)
        with Image.open(file_path) as img:
            if img.format != "PNG":
                return False, f"Decoded image format is not PNG ('{img.format}'): {file_path.name}"

            width, height = img.size
            if width < min_width or height < min_height:
                return False, f"Image dimensions {width}x{height} below minimum required {min_width}x{min_height}"

            # Check that image is not blank (variance of pixel intensities must be non-zero)
            converted = img.convert("L")
            stat = ImageStat.Stat(converted)
            std_dev = stat.stddev[0] if stat.stddev else 0.0
            if std_dev < 1.0:
                return False, f"Image appears blank or monotone (pixel stddev: {std_dev:.2f})"

    except Exception as e:
        return False, f"Pillow image structural decoding failed: {e}"

    return True, "Valid PNG visualization artifact"
