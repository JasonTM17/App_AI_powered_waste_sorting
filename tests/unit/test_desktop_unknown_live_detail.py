from app.__main__ import UNKNOWN_REVIEW_DETAIL, _unknown_review_detail


def test_unknown_live_detail_never_claims_a_bin_route():
    detail = _unknown_review_detail("Unknown object", "Unknown object")

    assert detail == UNKNOWN_REVIEW_DETAIL
    assert "chưa phân loại" in detail
    assert "bin" not in detail.casefold()
    assert "vô cơ" not in detail.casefold()


def test_known_class_does_not_use_unknown_review_detail():
    assert _unknown_review_detail("Electronics", "Unknown object") is None
