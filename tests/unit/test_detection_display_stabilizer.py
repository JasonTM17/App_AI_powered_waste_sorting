from app.core.detection_display_stabilizer import DetectionDisplayStabilizer
from app.core.events import Detection


def _detection(
    cls_id: int,
    cls_name: str,
    conf: float = 0.7,
    xyxy: tuple[int, int, int, int] = (10, 10, 200, 180),
) -> Detection:
    return Detection(cls_id, cls_name, conf, xyxy)


def test_display_stabilizer_requires_three_frames_to_acquire_label():
    stabilizer = DetectionDisplayStabilizer()
    organic = _detection(17, "Organic")

    assert stabilizer.update([organic]) == []
    assert stabilizer.update([organic]) == []
    assert stabilizer.update([organic])[0].cls_name == "Organic"


def test_display_stabilizer_ignores_single_frame_label_jump():
    stabilizer = DetectionDisplayStabilizer()
    organic = _detection(17, "Organic")
    paper_bag = _detection(19, "Paper bag", 0.9)
    for _ in range(3):
        visible = stabilizer.update([organic])

    visible = stabilizer.update([paper_bag])

    assert visible[0].cls_name == "Organic"


def test_display_stabilizer_switches_after_sustained_new_label():
    stabilizer = DetectionDisplayStabilizer()
    organic = _detection(17, "Organic")
    paper_bag = _detection(19, "Paper bag")
    for _ in range(3):
        stabilizer.update([organic])
    for _ in range(4):
        visible = stabilizer.update([paper_bag])
        assert visible[0].cls_name == "Organic"

    visible = stabilizer.update([paper_bag])

    assert visible[0].cls_name == "Paper bag"


def test_display_stabilizer_keeps_exact_organic_for_generic_organic_route():
    stabilizer = DetectionDisplayStabilizer()
    organic = _detection(17, "Organic", 0.62)
    generic = _detection(-301, "Kaggle 3-bin O", 0.75)
    for _ in range(3):
        stabilizer.update([organic])

    visible = stabilizer.update([generic])

    assert visible[0].cls_name == "Organic"


def test_display_stabilizer_clears_after_empty_frames():
    stabilizer = DetectionDisplayStabilizer(max_missed_frames=2)
    organic = _detection(17, "Organic")
    for _ in range(3):
        stabilizer.update([organic])

    assert stabilizer.update([])[0].cls_name == "Organic"
    assert stabilizer.update([])[0].cls_name == "Organic"
    assert stabilizer.update([]) == []


def test_route_stabilizer_keeps_route_when_exact_recyclable_label_jumps():
    stabilizer = DetectionDisplayStabilizer(
        group_by_route=True,
        exact_acquire_frames=4,
    )
    bottle = _detection(24, "Plastic bottle", 0.65)
    can = _detection(1, "Aluminum can", 0.7)

    stabilizer.update([bottle])
    stabilizer.update([can])
    visible = stabilizer.update([bottle])

    assert visible[0].cls_name == "Kaggle 3-bin I"


def test_route_stabilizer_requires_sustained_route_before_switching():
    stabilizer = DetectionDisplayStabilizer(group_by_route=True)
    bottle = _detection(24, "Plastic bottle", 0.7)
    organic = _detection(17, "Organic", 0.8)
    for _ in range(4):
        visible = stabilizer.update([bottle])

    visible = stabilizer.update([organic])

    assert visible[0].cls_name == "Plastic bottle"
