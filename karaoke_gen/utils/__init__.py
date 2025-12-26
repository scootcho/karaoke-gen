import re

# Unicode character replacements for ASCII-safe filenames
# These characters cause issues with HTTP headers (latin-1 encoding) and some filesystems
UNICODE_REPLACEMENTS = {
    # Curly/smart quotes -> straight quotes
    "\u2018": "'",  # LEFT SINGLE QUOTATION MARK
    "\u2019": "'",  # RIGHT SINGLE QUOTATION MARK (the one causing the bug)
    "\u201A": "'",  # SINGLE LOW-9 QUOTATION MARK
    "\u201B": "'",  # SINGLE HIGH-REVERSED-9 QUOTATION MARK
    "\u201C": '"',  # LEFT DOUBLE QUOTATION MARK
    "\u201D": '"',  # RIGHT DOUBLE QUOTATION MARK
    "\u201E": '"',  # DOUBLE LOW-9 QUOTATION MARK
    "\u201F": '"',  # DOUBLE HIGH-REVERSED-9 QUOTATION MARK
    # Other common problematic characters
    "\u2013": "-",  # EN DASH
    "\u2014": "-",  # EM DASH
    "\u2026": "...",  # HORIZONTAL ELLIPSIS
    "\u00A0": " ",  # NON-BREAKING SPACE
}


def sanitize_filename(filename):
    """Replace or remove characters that are unsafe for filenames."""
    if filename is None:
        return None

    # First, normalize Unicode characters that cause HTTP header encoding issues
    # (e.g., curly quotes from macOS/Word that can't be encoded in latin-1)
    for unicode_char, ascii_replacement in UNICODE_REPLACEMENTS.items():
        filename = filename.replace(unicode_char, ascii_replacement)

    # Replace problematic characters with underscores
    for char in ["\\", "/", ":", "*", "?", '"', "<", ">", "|"]:
        filename = filename.replace(char, "_")
    # Remove any trailing periods or spaces
    filename = filename.rstrip(". ") # Added period here as well
    # Remove any leading periods or spaces
    filename = filename.lstrip(". ")
    # Replace multiple underscores with a single one
    filename = re.sub(r'_+', '_', filename)
    # Replace multiple spaces with a single one
    filename = re.sub(r' +', ' ', filename)
    return filename
