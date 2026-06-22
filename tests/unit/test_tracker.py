from app.core.events import Detection
from app.core.tracker import Tracker


def _det(cls=0, conf=0.9, xyxy=(10, 10, 100, 100)):
    return Detection(cls_id=cls, cls_name=f"c{cls}", conf=conf, xyxy=xyxy)


def test_new_object_gets_id():
    tr = Tracker(iou_threshold=0.3, max_age=30)
    out = tr.update([_det()])
    assert len(out) == 1
    assert out[0].track_id >= 1
    assert out[0].stable_frames == 1


def test_same_object_keeps_id_across_frames():
    tr = Tracker()
    a = tr.update([_det(xyxy=(10, 10, 100, 100))])[0]
    b = tr.update([_det(xyxy=(12, 12, 102, 102))])[0]
    assert a.track_id == b.track_id
    assert b.stable_frames == 2


def test_same_object_keeps_id_when_bbox_jitters_and_resizes():
    tr = Tracker()
    first = tr.update([_det(xyxy=(90, 120, 360, 245))])[0]
    second = tr.update([_det(xyxy=(40, 98, 410, 282))])[0]
    third = tr.update([_det(xyxy=(112, 130, 335, 238))])[0]

    assert second.track_id == first.track_id
    assert third.track_id == first.track_id
    assert third.stable_frames == 3


def test_resized_bbox_does_not_match_far_object():
    tr = Tracker()
    first = tr.update([_det(xyxy=(20, 20, 150, 130))])[0]
    second = tr.update([_det(xyxy=(270, 210, 430, 350))])[0]

    assert second.track_id != first.track_id
    assert second.stable_frames == 1


def test_different_object_gets_different_id():
    tr = Tracker()
    out_a = tr.update([_det(xyxy=(10, 10, 50, 50))])
    out_b = tr.update([_det(xyxy=(200, 200, 250, 250))])
    assert out_a[0].track_id != out_b[0].track_id


def test_track_expires_after_max_age():
    tr = Tracker(max_age=3)
    a = tr.update([_det()])[0]
    for _ in range(4):
        tr.update([])
    b = tr.update([_det()])[0]
    assert b.track_id != a.track_id


def test_already_emitted_filter():
    tr = Tracker()
    out = tr.update([_det()])[0]
    assert tr.should_emit(out.track_id) is True
    tr.mark_emitted(out.track_id)
    assert tr.should_emit(out.track_id) is False


def test_same_object_resets_stability_when_exact_label_changes_within_route():
    tr = Tracker()
    bottle = Detection(24, "Plastic bottle", 0.7, (10, 10, 100, 100))
    can = Detection(1, "Aluminum can", 0.7, (12, 12, 102, 102))

    first = tr.update([bottle])[0]
    second = tr.update([can])[0]

    assert second.track_id == first.track_id
    assert second.stable_frames == 1


def test_same_class_resets_stability_when_operator_label_changes():
    tr = Tracker()
    organic = Detection(17, "Organic", 0.7, (10, 10, 100, 100), operator_label="")
    leaf = Detection(17, "Organic", 0.7, (12, 12, 102, 102), operator_label="La cay")

    first = tr.update([organic])[0]
    second = tr.update([leaf])[0]

    assert second.track_id == first.track_id
    assert second.stable_frames == 1


def test_same_visible_label_keeps_stability_when_internal_source_changes():
    tr = Tracker()
    yolo = Detection(17, "Organic", 0.7, (10, 10, 100, 100), source="YOLO")
    corrected = Detection(
        17,
        "Organic",
        0.72,
        (12, 12, 102, 102),
        source="visual_correction:leafy_organic",
    )

    first = tr.update([yolo])[0]
    second = tr.update([corrected])[0]

    assert second.track_id == first.track_id
    assert second.stable_frames == 2


def test_same_object_resets_stability_when_route_changes():
    tr = Tracker()
    bottle = Detection(24, "Plastic bottle", 0.7, (10, 10, 100, 100))
    organic = Detection(17, "Organic", 0.7, (12, 12, 102, 102))

    first = tr.update([bottle])[0]
    second = tr.update([organic])[0]

    assert second.track_id == first.track_id
    assert second.stable_frames == 1


def test_emitted_track_becomes_eligible_when_route_changes():
    tr = Tracker()
    organic = Detection(17, "Organic", 0.9, (10, 10, 100, 100))
    pen = Detection(42, "Pen", 0.9, (12, 12, 102, 102))

    first = tr.update([organic])[0]
    tr.mark_emitted(first.track_id)
    second = tr.update([pen])[0]

    assert second.track_id == first.track_id
    assert tr.should_emit(second.track_id) is True


def test_emitted_track_stays_emitted_when_label_changes_within_same_route():
    tr = Tracker()
    pen = Detection(42, "Pen", 0.9, (10, 10, 100, 100))
    utensil = Detection(32, "Iron utensils", 0.9, (12, 12, 102, 102))

    first = tr.update([pen])[0]
    tr.mark_emitted(first.track_id)
    second = tr.update([utensil])[0]

    assert second.track_id == first.track_id
    assert tr.should_emit(second.track_id) is False
