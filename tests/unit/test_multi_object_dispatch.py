from app.core.events import Detection, TrackedDetection
from app.core.multi_object_dispatch import evaluate_single_class_dispatch


def _tracked(cls_name: str, track_id: int) -> TrackedDetection:
    return TrackedDetection(
        track_id=track_id,
        detection=Detection(track_id, cls_name, 0.9, (0, 0, 10, 10)),
        stable_frames=1,
        first_seen_ts=0.0,
    )


def test_multi_object_dispatch_allows_single_class():
    decision = evaluate_single_class_dispatch(
        [_tracked("Pen", 1), _tracked("Pen", 2)],
        in_roi=lambda _bbox: True,
        max_classes=1,
    )

    assert decision.allowed is True
    assert decision.class_names == ("Pen",)


def test_multi_object_dispatch_blocks_multiple_classes_in_roi():
    decision = evaluate_single_class_dispatch(
        [_tracked("Pen", 1), _tracked("Textile", 2)],
        in_roi=lambda _bbox: True,
        max_classes=1,
    )

    assert decision.allowed is False
    assert decision.class_names == ("Pen", "Textile")
    assert decision.reason == "multiple waste types"
