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
