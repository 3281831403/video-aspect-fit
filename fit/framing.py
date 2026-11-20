"""Pixel geometry for fitting a source video frame onto a destination canvas.

Coordinates use the half-open rectangle convention: a rectangle
``{"x": x, "y": y, "w": w, "h": h}`` covers columns ``[x, x + w)`` and rows
``[y, y + h)``.  All rectangle coordinates and sizes are integer pixels.
Display aspect ratios (DAR) are computed from storage dimensions and the
sample aspect ratio (SAR); floating-point comparisons use a tolerance of
``1e-6`` unless stated otherwise.
"""

import math

_MODES = ("letterbox", "pillarbox", "crop", "stretch")
_RECT_KEYS = ("x", "y", "w", "h")


class FitError(ValueError):
    """Raised when a frame, rectangle, aspect or batch cannot be fitted."""


def _round_half_up(value):
    """Round a finite value to the nearest integer, halves upward."""
    return int(math.floor(value + 0.5))


def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _positive_number(value):
    return _is_number(value) and value > 0


def _as_int(value):
    """Return ``value`` as an int when it is an integral number, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return None


def _positive_int(value):
    number = _as_int(value)
    if number is None or number <= 0:
        return None
    return number


def _read_rect(rect):
    """Validate a rectangle dict and return ``(x, y, w, h)`` ints.

    Raises :class:`FitError` when the rectangle is malformed or has a
    non-positive size.
    """
    if not isinstance(rect, dict):
        raise FitError("rectangle must be a mapping")
    values = []
    for key in _RECT_KEYS:
        if key not in rect:
            raise FitError("rectangle is missing %r" % key)
        number = _as_int(rect[key])
        if number is None:
            raise FitError("rectangle %r must be an integer pixel value" % key)
        values.append(number)
    x, y, w, h = values
    if w <= 0 or h <= 0:
        raise FitError("rectangle width and height must be positive")
    return x, y, w, h


def display_aspect(w, h, sar=1.0):
    """Return the display aspect ratio (DAR) for a ``w`` x ``h`` frame.

    ``DAR = (w / h) * sar``.  ``w`` and ``h`` are positive storage pixel
    counts and ``sar`` is the positive sample aspect ratio (default ``1.0``,
    i.e. square pixels).  The returned float is compared with a tolerance of
    ``1e-6``.  Raises :class:`FitError` when any input is not a positive
    finite number.
    """
    if not _positive_number(w) or not _positive_number(h):
        raise FitError("frame dimensions must be positive finite numbers")
    if not _positive_number(sar):
        raise FitError("sample aspect ratio must be a positive finite number")
    return (float(w) / float(h)) * float(sar)


def fit_letterbox(src_w, src_h, dst_w, dst_h, mode="letterbox"):
    """Fit a source frame into a destination canvas.

    ``src_w``, ``src_h``, ``dst_w`` and ``dst_h`` are positive pixel counts.
    ``mode`` is one of ``"letterbox"``, ``"pillarbox"``, ``"crop"`` or
    ``"stretch"``.

    The contain modes preserve the source aspect ``src_w / src_h`` and center
    the whole frame inside the destination, leaving neutral bars:

    * ``"letterbox"`` and ``"pillarbox"`` both use contain geometry.  The two
      names are accepted because callers use "letterbox" for top/bottom bars
      and "pillarbox" for left/right bars.
    * ``"crop"`` fills the destination, preserves the source aspect and
      center-crops the overflow.
    * ``"stretch"`` fills the destination exactly, scaling x and y
      independently, so it never adds bars.

    Returns ``{"rect": {"x", "y", "w", "h"}, "scale": {"sx", "sy"}}``.
    ``rect`` is the visible frame rectangle in integer destination pixels and
    lies fully inside the canvas.  For the contain modes it is the fitted
    image; for ``"crop"`` it is the whole canvas and the overflow is implied
    by the scale.  ``scale`` holds positive x/y scale factors.  Integer
    geometry may differ from the exact floating-point result by at most one
    pixel.  Raises :class:`FitError` for non-positive dimensions or an unknown
    mode.
    """
    source = []
    for name, value in (("src_w", src_w), ("src_h", src_h)):
        number = _positive_int(value)
        if number is None:
            raise FitError("%s must be a positive integer pixel count" % name)
        source.append(number)
    dest = []
    for name, value in (("dst_w", dst_w), ("dst_h", dst_h)):
        number = _positive_int(value)
        if number is None:
            raise FitError("%s must be a positive integer pixel count" % name)
        dest.append(number)
    if mode not in _MODES:
        raise FitError("unknown fit mode %r" % (mode,))

    src_w, src_h = source
    dst_w, dst_h = dest

    if mode == "stretch":
        return {
            "rect": {"x": 0, "y": 0, "w": dst_w, "h": dst_h},
            "scale": {
                "sx": float(dst_w) / float(src_w),
                "sy": float(dst_h) / float(src_h),
            },
        }

    if mode == "crop":
        scale = max(float(dst_w) / float(src_w), float(dst_h) / float(src_h))
        return {
            "rect": {"x": 0, "y": 0, "w": dst_w, "h": dst_h},
            "scale": {"sx": scale, "sy": scale},
        }

    # Contain geometry: the same uniform scale for both axes, then center.
    scale = min(float(dst_w) / float(src_w), float(dst_h) / float(src_h))
    w = min(_round_half_up(src_w * scale), dst_w)
    h = min(_round_half_up(src_h * scale), dst_h)
    w = max(w, 1)
    h = max(h, 1)
    x = (dst_w - w) // 2
    y = (dst_h - h) // 2
    return {
        "rect": {"x": x, "y": y, "w": w, "h": h},
        "scale": {"sx": scale, "sy": scale},
    }


def apply_sar(w, h, sar):
    """Return square-pixel display dimensions for non-square source pixels.

    Non-square pixels change only the horizontal extent.  The result is
    ``(round_half_up(w * sar), h)`` as a tuple of integers, where
    ``round_half_up(x) = floor(x + 0.5)``.  Each returned dimension is within
    one pixel of the exact scaled value.  ``w``, ``h`` and ``sar`` must be
    positive; otherwise :class:`FitError` is raised.
    """
    width = _positive_int(w)
    height = _positive_int(h)
    if width is None or height is None:
        raise FitError("frame dimensions must be positive integers")
    if not _positive_number(sar):
        raise FitError("sample aspect ratio must be a positive finite number")
    return (_round_half_up(width * float(sar)), height)


def safe_area(rect, overscan):
    """Shrink a rectangle by an overscan fraction on every side.

    ``rect`` is a ``{"x", "y", "w", "h"}`` dict in integer pixels.
    ``overscan`` is the per-side fraction of width/height, clamped to the
    inclusive range ``[0.0, 0.1]``; values below or above that range use the
    nearest bound.  Each side is inset by ``round_half_up(size * overscan)``
    pixels, so ``overscan=0.0`` returns an equal rectangle.  The result stays
    inside the input rectangle and has non-negative width and height.

    Returns a fresh ``{"x", "y", "w", "h"}`` dict; the input is not mutated.
    Raises :class:`FitError` when ``rect`` is malformed or has non-positive
    size.
    """
    x, y, w, h = _read_rect(rect)
    if not _is_number(overscan):
        raise FitError("overscan must be a finite number")
    fraction = min(max(float(overscan), 0.0), 0.1)
    inset_x = _round_half_up(w * fraction)
    inset_y = _round_half_up(h * fraction)
    return {
        "x": x + inset_x,
        "y": y + inset_y,
        "w": max(w - 2 * inset_x, 0),
        "h": max(h - 2 * inset_y, 0),
    }


def crop_to_aspect(w, h, target):
    """Center-crop a ``w`` x ``h`` source frame to ``target`` aspect.

    ``target`` is a ``(numerator, denominator)`` pair of positive numbers.
    The largest integer-pixel rectangle with the target aspect that fits
    inside the source is kept and centered.  When one spare pixel remains it
    is placed on the right or bottom.  A source that already has the target
    aspect is returned unchanged.

    Returns ``{"rect": {"x", "y", "w", "h"}}`` in source pixel coordinates.
    Raises :class:`FitError` for non-positive dimensions or an invalid target
    aspect.
    """
    width = _positive_int(w)
    height = _positive_int(h)
    if width is None or height is None:
        raise FitError("frame dimensions must be positive integers")
    if not isinstance(target, (tuple, list)) or len(target) != 2:
        raise FitError("target aspect must be a (numerator, denominator) pair")
    numerator, denominator = target
    if not _positive_number(numerator) or not _positive_number(denominator):
        raise FitError("target aspect terms must be positive finite numbers")
    target_aspect = float(numerator) / float(denominator)

    source_aspect = float(width) / float(height)
    if math.isclose(source_aspect, target_aspect, rel_tol=1e-12, abs_tol=0.0):
        crop_w, crop_h = width, height
    elif source_aspect > target_aspect:
        # The source is wider: keep the full height and trim the sides.
        crop_h = height
        crop_w = min(_round_half_up(height * target_aspect), width)
    else:
        # The source is taller: keep the full width and trim top/bottom.
        crop_w = width
        crop_h = min(_round_half_up(width / target_aspect), height)

    return {
        "rect": {
            "x": (width - crop_w) // 2,
            "y": (height - crop_h) // 2,
            "w": crop_w,
            "h": crop_h,
        }
    }


def snap_even(rect):
    """Snap a rectangle to even pixel dimensions without moving its far edges.

    An odd width or height is rounded up to the next even value.  ``x`` and
    ``y`` are decreased by the added amount, so ``x + w`` and ``y + h`` are
    preserved exactly and an extra column or row is never introduced on the
    right or bottom.  An already-even dimension is unchanged.

    Returns a fresh ``{"x", "y", "w", "h"}`` dict; the input is not mutated.
    Raises :class:`FitError` when ``rect`` is malformed or has non-positive
    size.
    """
    x, y, w, h = _read_rect(rect)
    even_w = w if w % 2 == 0 else w + 1
    even_h = h if h % 2 == 0 else h + 1
    return {
        "x": x - (even_w - w),
        "y": y - (even_h - h),
        "w": even_w,
        "h": even_h,
    }


def validate_fit(fit, dst):
    """Validate a fit result against a destination canvas.

    ``fit`` is a dict containing a ``rect`` dict and may carry an optional
    expected display aspect ratio under ``"aspect"``.  ``dst`` is a
    ``{"w", "h"}`` dict.  The function returns a list of human-readable issue
    strings; an empty list means the fit is valid.  It does not raise for
    ordinary malformed values, but reports them as issues.

    Checked conditions are: positive destination dimensions; a present,
    positive integer-pixel rectangle; no part of the rectangle outside
    ``[0, dst_w] x [0, dst_h]``; even width and height; and, when ``"aspect"``
    is provided, a rectangle DAR matching it within a relative tolerance of
    ``1e-6``.
    """
    issues = []

    dst_w = dst_h = None
    if not isinstance(dst, dict):
        issues.append("destination must be a mapping with positive width and height")
    else:
        dest_width = _positive_int(dst.get("w"))
        dest_height = _positive_int(dst.get("h"))
        if dest_width is None or dest_height is None:
            issues.append("destination dimensions must be positive integers")
        else:
            dst_w, dst_h = dest_width, dest_height

    fit_dict = fit if isinstance(fit, dict) else {}
    rect = fit_dict.get("rect")

    if not isinstance(rect, dict):
        issues.append("fit is missing a rectangle")
        return issues

    values = {}
    malformed = False
    for key in _RECT_KEYS:
        number = _as_int(rect.get(key))
        if number is None:
            issues.append("rectangle %r must be an integer pixel value" % key)
            malformed = True
        else:
            values[key] = number
    if malformed:
        return issues

    x, y, w, h = (values[key] for key in _RECT_KEYS)
    if w <= 0 or h <= 0:
        issues.append("rectangle width and height must be positive")
        return issues

    if dst_w is not None and dst_h is not None:
        if x < 0 or y < 0 or x + w > dst_w or y + h > dst_h:
            issues.append(
                "rectangle lies outside destination bounds "
                "[0, %d] x [0, %d]" % (dst_w, dst_h)
            )

    if w % 2 != 0 or h % 2 != 0:
        issues.append("rectangle width and height must be even")

    if "aspect" in fit_dict and fit_dict["aspect"] is not None:
        expected = fit_dict["aspect"]
        if not _positive_number(expected):
            issues.append("expected aspect ratio must be a positive finite number")
        else:
            actual = float(w) / float(h)
            if not math.isclose(actual, float(expected), rel_tol=1e-6):
                issues.append(
                    "rectangle aspect ratio %.9f does not match expected %.9f"
                    % (actual, float(expected))
                )

    return issues


def fit_batch(jobs, config):
    """Fit many jobs atomically and preserve their input order.

    ``jobs`` is a list of dicts with ``"id"``, ``"src_w"``, ``"src_h"``,
    ``"dst_w"``, ``"dst_h"`` and an optional ``"mode"`` (default
    ``"letterbox"``).  ``config`` is a dict with an optional positive ``"sar"``
    (default ``1.0``) applied to each source before fitting.

    Every job receives its own ``rect`` and ``scale`` objects; no canvas
    rectangle is shared between jobs.  Returns
    ``{"fits": [{"id", "rect", "scale"}, ...], "count": len(jobs)}`` in the
    same order as ``jobs``.

    The batch is all-or-nothing: every job is validated before any result is
    returned, and if any job is invalid the function raises :class:`FitError`
    with no partial result exposed.
    """
    if not isinstance(jobs, list):
        raise FitError("jobs must be a list")
    if not isinstance(config, dict):
        raise FitError("config must be a mapping")

    sar = config.get("sar", 1.0)
    if not _positive_number(sar):
        raise FitError("sample aspect ratio must be a positive finite number")
    sar = float(sar)

    # First pass: validate every job before fitting anything, so a bad job
    # cannot leave a partially fitted batch behind.
    prepared = []
    for index, job in enumerate(jobs):
        if not isinstance(job, dict):
            raise FitError("job %d must be a mapping" % index)
        if "id" not in job:
            raise FitError("job %d is missing an id" % index)
        for name in ("src_w", "src_h", "dst_w", "dst_h"):
            if _positive_int(job.get(name)) is None:
                raise FitError(
                    "job %r has an invalid %s" % (job.get("id"), name)
                )
        mode = job.get("mode", "letterbox")
        if mode not in _MODES:
            raise FitError("job %r has an unknown mode %r" % (job.get("id"), mode))
        prepared.append(
            (
                job["id"],
                _positive_int(job["src_w"]),
                _positive_int(job["src_h"]),
                _positive_int(job["dst_w"]),
                _positive_int(job["dst_h"]),
                mode,
            )
        )

    # Second pass: fit each job with its own fresh geometry objects.
    fits = []
    for job_id, src_w, src_h, dst_w, dst_h, mode in prepared:
        display_w, display_h = apply_sar(src_w, src_h, sar)
        fit = fit_letterbox(display_w, display_h, dst_w, dst_h, mode)
        fits.append(
            {
                "id": job_id,
                "rect": dict(fit["rect"]),
                "scale": dict(fit["scale"]),
            }
        )

    return {"fits": fits, "count": len(jobs)}
