"""Regression tests for pixel-accurate aspect fitting.

The initial implementation is deliberately stubbed, so every test currently
fails with ``NotImplementedError``.  The tests are the specification and must
not be modified while fixing ``fit/framing.py``.
"""

import pytest

from fit.framing import (
    FitError,
    apply_sar,
    crop_to_aspect,
    display_aspect,
    fit_batch,
    fit_letterbox,
    safe_area,
    snap_even,
    validate_fit,
)


def test_display_aspect_includes_sar():
    # 1440x1080 storage with 4:3 SAR displays as 16:9, not 4:3.
    dar = display_aspect(1440, 1080, 4 / 3)
    assert dar == pytest.approx(16 / 9, abs=1e-6)


def test_letterbox_centers_content_with_offsets():
    fit = fit_letterbox(1440, 1080, 1920, 1080, "letterbox")
    assert fit["rect"] == {"x": 240, "y": 0, "w": 1440, "h": 1080}
    assert fit["scale"]["sx"] == pytest.approx(1.0, abs=1e-6)
    assert fit["scale"]["sy"] == pytest.approx(1.0, abs=1e-6)


def test_crop_to_aspect_uses_center_not_top_left():
    fit = crop_to_aspect(1920, 1080, (4, 3))
    assert fit["rect"] == {"x": 240, "y": 0, "w": 1440, "h": 1080}


def test_snap_even_keeps_right_and_bottom_edges():
    rect = snap_even({"x": 11, "y": 7, "w": 101, "h": 99})
    assert rect == {"x": 10, "y": 6, "w": 102, "h": 100}
    assert rect["x"] + rect["w"] == 11 + 101
    assert rect["y"] + rect["h"] == 7 + 99


def test_safe_area_clamps_overscan():
    rect = safe_area({"x": 0, "y": 0, "w": 1000, "h": 500}, 0.5)
    assert rect == {"x": 100, "y": 50, "w": 800, "h": 400}


def test_stretch_fills_canvas_without_bars():
    fit = fit_letterbox(640, 480, 1920, 1080, "stretch")
    assert fit["rect"] == {"x": 0, "y": 0, "w": 1920, "h": 1080}
    assert fit["scale"]["sx"] == pytest.approx(3.0, abs=1e-6)
    assert fit["scale"]["sy"] == pytest.approx(2.25, abs=1e-6)


def test_apply_sar_rounds_half_up_without_drift():
    widths = [apply_sar(w, 480, 1.5)[0] for w in (851, 853)]
    assert widths == [1277, 1280]
    assert sum(widths) == 2557


def test_validate_fit_flags_out_of_bounds_rect():
    issues = validate_fit(
        {"rect": {"x": 40, "y": 0, "w": 1000, "h": 500}},
        {"w": 1024, "h": 576},
    )
    assert issues
    assert any("outside" in issue.lower() or "bound" in issue.lower() for issue in issues)


def test_fit_batch_keeps_jobs_isolated():
    result = fit_batch(
        [
            {
                "id": "wide",
                "src_w": 1920,
                "src_h": 1080,
                "dst_w": 640,
                "dst_h": 360,
                "mode": "letterbox",
            },
            {
                "id": "square",
                "src_w": 1080,
                "src_h": 1080,
                "dst_w": 640,
                "dst_h": 360,
                "mode": "letterbox",
            },
        ],
        {"sar": 1.0},
    )
    assert [item["id"] for item in result["fits"]] == ["wide", "square"]
    assert result["fits"][0]["rect"]["w"] == 640
    assert result["fits"][1]["rect"]["w"] == 360
    assert result["fits"][0]["rect"] is not result["fits"][1]["rect"]


def test_fit_batch_rejects_zero_width_without_partial_state():
    with pytest.raises(FitError):
        fit_batch(
            [
                {
                    "id": "bad",
                    "src_w": 640,
                    "src_h": 480,
                    "dst_w": 0,
                    "dst_h": 360,
                    "mode": "letterbox",
                }
            ],
            {"sar": 1.0},
        )


def test_same_aspect_has_no_bars():
    fit = fit_letterbox(1920, 1080, 1280, 720, "letterbox")
    assert fit["rect"] == {"x": 0, "y": 0, "w": 1280, "h": 720}
    assert fit["scale"]["sx"] == pytest.approx(2 / 3, abs=1e-6)
    assert fit["scale"]["sy"] == pytest.approx(2 / 3, abs=1e-6)


def test_unit_sar_display_aspect_equals_width_over_height():
    dar = display_aspect(1920, 1080, 1.0)
    assert dar == pytest.approx(1920 / 1080, abs=1e-6)


def test_letterbox_zero_destination_width_raises_fit_error():
    with pytest.raises(FitError):
        fit_letterbox(640, 480, 0, 360, "letterbox")


def test_safe_area_zero_overscan_is_identity():
    rect = {"x": 10, "y": 20, "w": 300, "h": 200}
    result = safe_area(rect, 0.0)
    assert result == rect
    assert result is not rect


def test_fit_batch_preserves_input_order():
    result = fit_batch(
        [
            {
                "id": "first",
                "src_w": 640,
                "src_h": 480,
                "dst_w": 640,
                "dst_h": 360,
                "mode": "letterbox",
            },
            {
                "id": "second",
                "src_w": 1920,
                "src_h": 1080,
                "dst_w": 640,
                "dst_h": 360,
                "mode": "letterbox",
            },
            {
                "id": "third",
                "src_w": 320,
                "src_h": 240,
                "dst_w": 640,
                "dst_h": 360,
                "mode": "letterbox",
            },
        ],
        {"sar": 1.0},
    )
    assert [item["id"] for item in result["fits"]] == ["first", "second", "third"]
