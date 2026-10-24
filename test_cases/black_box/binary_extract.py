"""Binary file text extraction utilities.

Used to extract readable text from binary files for evidence reporting.
"""

from pathlib import Path
from typing import Tuple


def extract_text(file_path: str, max_bytes: int = 1024) -> str:
    """Extract readable text from a binary file.

    Args:
        file_path: Path to the binary file
        max_bytes: Maximum bytes to read for text extraction

    Returns:
        Extracted text or size info for non-text files
    """
    path = Path(file_path)

    if not path.exists():
        return f"[File not found: {file_path}]"

    size = path.stat().st_size

    # For small files, try to read as text
    if size <= max_bytes:
        try:
            content = path.read_text(encoding='utf-8', errors='replace')
            # Filter out non-printable characters
            return ''.join(c for c in content if c.isprintable() or c.isspace())
        except Exception as e:
            return f"[Binary file: {size} bytes, error: {type(e).__name__}]"

    # For large files, report size only
    return f"[Large binary file: {size} bytes]"


def supported(file_path: str) -> bool:
    """Check if text extraction is supported for this file.

    Args:
        file_path: Path to check

    Returns:
        True if extraction is supported (file exists)
    """
    return Path(file_path).exists()


def extract_with_limit(file_path: str, max_bytes: int = 1024) -> Tuple[str, int]:
    """Extract text and return actual file size.

    Args:
        file_path: Path to the file
        max_bytes: Maximum bytes to extract

    Returns:
        Tuple of (extracted_text, actual_file_size)
    """
    path = Path(file_path)

    if not path.exists():
        return f"[File not found: {file_path}]", 0

    size = path.stat().st_size
    text = extract_text(file_path, max_bytes)

    return text, size
