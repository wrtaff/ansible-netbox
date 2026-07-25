# ==============================================================================
# pdf_filler/text_layout.py -- Smart Text Sizing
# Trac #4042
#
# Best-effort text width estimation for AcroForm fields. Uses approximate
# character widths for Helvetica (the standard AcroForm default font) to
# determine if text will overflow a field's rectangle, and recommends a
# font size adjustment.
#
# This is NOT a full font metrics engine -- it's sufficient for government
# forms where field widths are generous. For pixel-perfect layout, add
# reportlab or fonttools (Ansible-provisioned).
# ==============================================================================

from typing import Optional, Tuple


# Approximate average character width as a fraction of font size (points)
# for Helvetica. Real widths vary per glyph, but 0.52 * font_size is a
# reasonable average for mixed-case English text.
_HELVETICA_AVG_WIDTH_RATIO = 0.52

# Narrower ratio for uppercase-heavy text (initials, abbreviations)
_HELVETICA_UPPER_WIDTH_RATIO = 0.62


def estimate_text_width(text: str, font_size: float, uppercase_heavy: bool = False) -> float:
    """Estimate text width in PDF points for Helvetica at given font size."""
    ratio = _HELVETICA_UPPER_WIDTH_RATIO if uppercase_heavy else _HELVETICA_AVG_WIDTH_RATIO
    return len(text) * ratio * font_size


def fit_text_to_width(
    text: str,
    field_width_pts: float,
    max_font_size: float = 12.0,
    min_font_size: float = 6.0,
    uppercase_heavy: bool = False,
) -> Tuple[float, bool, Optional[str]]:
    """Determine the best font size to fit text in a field.

    Returns:
        (recommended_font_size, fits_without_truncation, warning_message)
    """
    if not text or field_width_pts <= 0:
        return max_font_size, True, None

    # Try the max font size first
    width = estimate_text_width(text, max_font_size, uppercase_heavy)
    if width <= field_width_pts:
        return max_font_size, True, None

    # Binary search for the best font size
    best_size = max_font_size
    for size in [max_font_size * f for f in [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]]:
        if size < min_font_size:
            break
        w = estimate_text_width(text, size, uppercase_heavy)
        if w <= field_width_pts:
            best_size = size
            return best_size, True, f"Auto-sized to {best_size:.1f}pt (from {max_font_size}pt)"

    # Even at min_font_size it overflows
    min_width = estimate_text_width(text, min_font_size, uppercase_heavy)
    if min_width <= field_width_pts:
        return min_font_size, True, f"Auto-sized to floor {min_font_size}pt"

    # Truncation needed
    ratio = _HELVETICA_UPPER_WIDTH_RATIO if uppercase_heavy else _HELVETICA_AVG_WIDTH_RATIO
    max_chars = int(field_width_pts / (ratio * min_font_size))
    if max_chars < 3:
        max_chars = 3
    truncated = text[:max_chars - 1] + "\u2026"  # ellipsis
    return min_font_size, False, (
        f"OVERFLOW: '{text}' ({len(text)} chars) exceeds field width "
        f"({field_width_pts:.0f}pt) even at {min_font_size}pt. "
        f"Truncated to {max_chars} chars: '{truncated}'"
    )


def get_field_rect_width(field_obj: dict) -> Optional[float]:
    """Extract field width in points from a pypdf field object's /Rect.

    Args:
        field_obj: A field dict from pypdf's get_fields() with /Rect key.

    Returns:
        Width in points, or None if /Rect is not available.
    """
    rect = field_obj.get("/Rect")
    if rect and len(rect) >= 4:
        try:
            # /Rect = [x1, y1, x2, y2] -- width = x2 - x1
            return float(rect[2]) - float(rect[0])
        except (TypeError, ValueError, IndexError):
            pass
    return None


def check_field_overflow(
    text: str,
    field_obj: dict,
    max_font_size: float = 12.0,
    min_font_size: float = 6.0,
) -> Tuple[bool, Optional[str]]:
    """Check if text will overflow a field and return a warning if so.

    Returns:
        (fits, warning_message)
    """
    width = get_field_rect_width(field_obj)
    if width is None:
        return True, None  # Can't check without rect info
    _, fits, warning = fit_text_to_width(text, width, max_font_size, min_font_size)
    return fits, warning
