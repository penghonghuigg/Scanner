import pytest

from app.scanning.scan_service import (
    AdjustmentReasonRequiredError,
    build_adjustment_reason,
)


@pytest.mark.parametrize(
    ("reason_type", "expected"),
    [
        ("ONSITE_VERIFICATION", "现场核对修正"),
        ("SCAN_CORRECTION", "扫码录入纠错"),
        ("LOOSE_PACK_VERIFICATION", "散包数量核对"),
    ],
)
def test_build_adjustment_reason_uses_approved_reason_names(
    reason_type: str,
    expected: str,
) -> None:
    assert build_adjustment_reason(reason_type, None) == expected


def test_build_adjustment_reason_requires_note_for_other() -> None:
    assert build_adjustment_reason("OTHER", " 包装破损复核 ") == "其他：包装破损复核"
    with pytest.raises(AdjustmentReasonRequiredError):
        build_adjustment_reason("OTHER", "  ")


def test_build_adjustment_reason_rejects_missing_or_unknown_type() -> None:
    with pytest.raises(AdjustmentReasonRequiredError):
        build_adjustment_reason(None, None)
    with pytest.raises(AdjustmentReasonRequiredError):
        build_adjustment_reason("INVALID", None)
