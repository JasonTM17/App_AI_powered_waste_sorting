from app.core.detection_display_stabilizer import DetectionDisplayStabilizer
from app.core.events import Detection


def _detection(
    cls_id: int,
    cls_name: str,
    conf: float = 0.7,
    xyxy: tuple[int, int, int, int] = (10, 10, 200, 180),
    operator_label: str = "",
) -> Detection:
    return Detection(cls_id, cls_name, conf, xyxy, operator_label=operator_label)


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


def test_route_stabilizer_holds_trusted_bagasse_label_through_generic_organic_frames():
    stabilizer = DetectionDisplayStabilizer(
        window_size=9,
        group_by_route=True,
        exact_acquire_frames=4,
    )
    bagasse = _detection(17, "Organic", 0.62, operator_label="Ba mia")
    generic = _detection(-301, "Kaggle 3-bin O", 0.52, xyxy=(12, 12, 202, 182))
    latest_generic = _detection(-301, "Kaggle 3-bin O", 0.52, xyxy=(14, 14, 204, 184))

    assert stabilizer.update([bagasse]) == []
    assert stabilizer.update([generic]) == []
    visible = stabilizer.update([latest_generic])

    assert [(item.cls_name, item.operator_label) for item in visible] == [
        ("Organic", "Ba mia")
    ]
    assert visible[0].xyxy == latest_generic.xyxy


def test_route_stabilizer_keeps_pure_generic_organic_non_specific():
    stabilizer = DetectionDisplayStabilizer(group_by_route=True)
    generic = _detection(-301, "Kaggle 3-bin O", 0.52)

    assert stabilizer.update([generic]) == []
    assert stabilizer.update([generic]) == []
    visible = stabilizer.update([generic])

    assert [(item.cls_name, item.operator_label) for item in visible] == [
        ("Kaggle 3-bin O", "")
    ]


def test_route_stabilizer_requires_sustained_frames_before_switching_trusted_label():
    stabilizer = DetectionDisplayStabilizer(
        group_by_route=True,
        exact_acquire_frames=1,
        exact_switch_frames=3,
        exact_switch_consecutive_frames=3,
    )
    bagasse = _detection(17, "Organic", 0.62, operator_label="Ba mia")
    generic = _detection(-301, "Kaggle 3-bin O", 0.52)
    leaf = _detection(17, "Organic", 0.92, operator_label="La cay")

    stabilizer.update([bagasse])
    stabilizer.update([generic])
    visible = stabilizer.update([generic])
    assert visible[0].operator_label == "Ba mia"

    visible = stabilizer.update([leaf])
    assert visible[0].operator_label == "Ba mia"

    stabilizer.update([leaf])
    visible = stabilizer.update([leaf])
    assert visible[0].operator_label == "La cay"


def test_route_stabilizer_requires_sustained_route_before_switching():
    stabilizer = DetectionDisplayStabilizer(group_by_route=True)
    bottle = _detection(24, "Plastic bottle", 0.7)
    organic = _detection(17, "Organic", 0.8)
    for _ in range(4):
        visible = stabilizer.update([bottle])

    visible = stabilizer.update([organic])

    assert visible[0].cls_name == "Plastic bottle"
