import numpy as np

from app.core.detection_filtering import (
    collapse_duplicate_physical_detections,
    collapse_single_object_scene_detections,
    find_ambiguous_organic_candidate,
    is_low_detail_empty_tray,
    is_uniform_empty_tray_artifact,
    is_verified_empty_tray,
    merge_fragmented_same_label_detections,
    suppress_camera_edge_artifacts,
    suppress_overlapping_detections,
)
from app.core.events import Detection


def test_suppress_overlapping_detections_keeps_strongest_label():
    detections = [
        Detection(0, "Aluminum can", 0.62, (20, 20, 220, 220)),
        Detection(1, "Plastic bottle", 0.16, (22, 21, 219, 222)),
    ]

    filtered = suppress_overlapping_detections(detections)

    assert [(item.cls_name, item.conf) for item in filtered] == [("Aluminum can", 0.62)]


def test_suppress_overlapping_detections_keeps_separate_objects():
    detections = [
        Detection(0, "Aluminum can", 0.62, (20, 20, 100, 100)),
        Detection(1, "Plastic bottle", 0.55, (160, 20, 260, 120)),
    ]

    filtered = suppress_overlapping_detections(detections)

    assert [item.cls_name for item in filtered] == ["Aluminum can", "Plastic bottle"]


def test_suppress_overlapping_detections_handles_large_container_box():
    detections = [
        Detection(0, "Aluminum can", 0.53, (202, 95, 515, 478)),
        Detection(1, "Plastic bottle", 0.14, (158, 11, 640, 478)),
    ]

    filtered = suppress_overlapping_detections(detections)

    assert [item.cls_name for item in filtered] == ["Aluminum can"]


def test_collapse_duplicate_physical_detections_prefers_known_label_over_unknown():
    detections = [
        Detection(999, "Unknown object", 0.77, (24, 22, 338, 230)),
        Detection(18, "Paper", 0.52, (42, 45, 318, 224)),
    ]

    filtered = collapse_duplicate_physical_detections(detections)

    assert [item.cls_name for item in filtered] == ["Paper"]


def test_collapse_duplicate_physical_detections_keeps_far_objects_separate():
    detections = [
        Detection(42, "Pen", 0.77, (10, 20, 140, 60)),
        Detection(18, "Paper", 0.72, (210, 70, 320, 190)),
    ]

    filtered = collapse_duplicate_physical_detections(detections)

    assert [item.cls_name for item in filtered] == ["Pen", "Paper"]


def test_collapse_duplicate_physical_detections_merges_shifted_labels_on_one_object():
    detections = [
        Detection(42, "Pen", 0.45, (70, 80, 520, 190)),
        Detection(1, "Plastic bottle", 0.36, (46, 68, 542, 210)),
        Detection(2, "Aluminum can", 0.18, (190, 92, 430, 182)),
    ]

    filtered = collapse_duplicate_physical_detections(detections)

    assert [(item.cls_name, item.conf) for item in filtered] == [("Pen", 0.45)]


def test_collapse_duplicate_physical_detections_keeps_nearby_real_objects_separate():
    detections = [
        Detection(42, "Pen", 0.77, (40, 80, 180, 130)),
        Detection(18, "Paper", 0.72, (198, 78, 338, 132)),
    ]

    filtered = collapse_duplicate_physical_detections(detections)

    assert [item.cls_name for item in filtered] == ["Pen", "Paper"]


def test_large_closeup_object_collapses_nested_body_and_label_boxes():
    frame = np.full((480, 640, 3), 180, dtype=np.uint8)
    detections = [
        Detection(24, "Plastic bottle", 0.61, (35, 25, 560, 455)),
        Detection(1, "Aluminum can", 0.38, (410, 95, 625, 420)),
        Detection(26, "Plastic caps", 0.29, (470, 70, 610, 190)),
    ]

    filtered = collapse_single_object_scene_detections(frame, detections)

    assert [(item.cls_name, item.conf) for item in filtered] == [("Plastic bottle", 0.61)]


def test_large_scene_collapse_keeps_two_side_by_side_objects_separate():
    frame = np.full((480, 640, 3), 180, dtype=np.uint8)
    detections = [
        Detection(24, "Plastic bottle", 0.78, (25, 70, 280, 430)),
        Detection(1, "Aluminum can", 0.73, (360, 65, 620, 435)),
    ]

    filtered = collapse_single_object_scene_detections(frame, detections)

    assert [item.cls_name for item in filtered] == ["Plastic bottle", "Aluminum can"]


def test_large_scene_collapse_drops_false_pen_label_on_bottle_neck_at_frame_edge():
    frame = np.full((540, 800, 3), 180, dtype=np.uint8)
    detections = [
        Detection(24, "Plastic bottle", 0.79, (100, 140, 460, 520)),
        Detection(42, "Pen", 0.74, (710, 190, 800, 390)),
    ]

    filtered = collapse_single_object_scene_detections(frame, detections)

    assert [(item.cls_name, item.conf, item.xyxy) for item in filtered] == [
        ("Plastic bottle", 0.79, (100, 140, 800, 520))
    ]


def test_fragmented_same_label_merges_even_when_foreground_splits_one_long_object():
    parts = [
        Detection(42, "Pen", 0.72, (20, 90, 210, 128)),
        Detection(42, "Pen", 0.84, (235, 92, 510, 130)),
    ]

    merged = merge_fragmented_same_label_detections(parts, foreground_object_count=1)
    split_foreground = merge_fragmented_same_label_detections(parts, foreground_object_count=2)

    assert [(item.cls_name, item.xyxy) for item in merged] == [("Pen", (20, 90, 510, 130))]
    assert [(item.cls_name, item.xyxy) for item in split_foreground] == [("Pen", (20, 90, 510, 130))]


def test_fragmented_pen_merges_two_aligned_boxes_across_transparent_body_gap():
    parts = [
        Detection(42, "Pen", 0.86, (266, 489, 548, 557), operator_label="Bút bi"),
        Detection(42, "Pen", 0.91, (836, 497, 1045, 536), operator_label="Bút bi"),
    ]

    merged = merge_fragmented_same_label_detections(parts, foreground_object_count=2)

    assert len(merged) == 1
    assert merged[0].cls_name == "Pen"
    assert merged[0].operator_label == "Bút bi"
    assert merged[0].conf == 0.91
    assert merged[0].xyxy == (266, 489, 1045, 557)


def test_fragmented_pen_merges_offset_boxes_from_real_camera_frame():
    parts = [
        Detection(42, "Pen", 0.90, (376, 481, 634, 588), operator_label="Bút bi"),
        Detection(42, "Pen", 0.88, (913, 449, 1139, 493), operator_label="Bút bi"),
    ]

    merged = merge_fragmented_same_label_detections(parts, foreground_object_count=2)

    assert len(merged) == 1
    assert merged[0].cls_name == "Pen"
    assert merged[0].operator_label == "Bút bi"
    assert merged[0].conf == 0.90
    assert merged[0].xyxy == (376, 449, 1139, 588)


def test_fragmented_bottle_merges_even_when_operator_sub_label_fluctuates():
    parts = [
        Detection(
            12,
            "Glass bottle",
            0.78,
            (40, 120, 260, 190),
            operator_label="Chai thủy tinh",
        ),
        Detection(
            12,
            "Glass bottle",
            0.84,
            (282, 124, 510, 194),
            operator_label="Lọ thủy tinh",
        ),
    ]

    merged = merge_fragmented_same_label_detections(parts, foreground_object_count=2)

    assert len(merged) == 1
    assert merged[0].cls_name == "Glass bottle"
    assert merged[0].operator_label == "Lọ thủy tinh"
    assert merged[0].xyxy == (40, 120, 510, 194)


def test_fragmented_vertical_battery_merges_two_aligned_boxes():
    parts = [
        Detection(43, "Battery", 0.80, (180, 30, 235, 220), operator_label="Pin AA/AAA"),
        Detection(43, "Battery", 0.88, (184, 245, 238, 480), operator_label="Pin AA/AAA"),
    ]

    merged = merge_fragmented_same_label_detections(parts, foreground_object_count=2)

    assert len(merged) == 1
    assert merged[0].cls_name == "Battery"
    assert merged[0].xyxy == (180, 30, 238, 480)


def test_fragmented_same_label_keeps_far_same_label_objects_separate():
    parts = [
        Detection(42, "Pen", 0.72, (20, 90, 160, 128)),
        Detection(42, "Pen", 0.84, (360, 92, 510, 130)),
    ]

    filtered = merge_fragmented_same_label_detections(parts, foreground_object_count=2)

    assert filtered == parts


def test_uniform_empty_tray_rejects_full_frame_false_positive():
    frame = np.full((240, 320, 3), 175, dtype=np.uint8)
    detections = [Detection(18, "Paper", 0.54, (2, 2, 318, 238))]

    assert is_uniform_empty_tray_artifact(frame, detections)


def test_camera_edge_strip_is_not_treated_as_a_pen():
    frame = np.full((720, 1280, 3), 205, dtype=np.uint8)
    detections = [Detection(42, "Pen", 0.39, (0, 0, 34, 715))]

    assert suppress_camera_edge_artifacts(frame, detections) == []


def test_camera_edge_filter_keeps_compact_object_near_the_edge():
    frame = np.full((720, 1280, 3), 205, dtype=np.uint8)
    detections = [Detection(42, "Pen", 0.71, (4, 260, 190, 330))]

    assert suppress_camera_edge_artifacts(frame, detections) == detections


def test_uniform_empty_tray_keeps_colored_bagasse_material():
    frame = np.full((240, 320, 3), 175, dtype=np.uint8)
    frame[70:180, 50:270] = (95, 145, 185)
    detections = [Detection(19, "Paper bag", 0.17, (2, 2, 318, 238))]

    assert not is_uniform_empty_tray_artifact(frame, detections)


def test_low_detail_empty_tray_blocks_border_fallback_box():
    frame = np.full((480, 640, 3), 176, dtype=np.uint8)
    frame += np.linspace(0, 20, 640, dtype=np.uint8)[None, :, None]
    detections = [Detection(-1, "Unknown object", 0.2, (500, 455, 610, 480))]

    assert is_low_detail_empty_tray(frame, detections)


def test_low_detail_empty_tray_keeps_leaf_material():
    frame = np.full((480, 640, 3), 176, dtype=np.uint8)
    frame[90:390, 160:520] = (55, 95, 130)

    assert not is_low_detail_empty_tray(frame, [Detection(17, "Organic", 0.6, (160, 90, 520, 390))])


def test_low_detail_frame_keeps_compact_center_object_detection():
    frame = np.full((240, 320, 3), 176, dtype=np.uint8)
    detections = [Detection(42, "Pen", 0.7, (90, 100, 230, 140))]

    assert not is_low_detail_empty_tray(frame, detections)


def test_verified_empty_tray_ignores_dark_side_rails_and_full_frame_false_positive():
    frame = np.full((720, 1280, 3), 210, dtype=np.uint8)
    frame[:, :80] = 25
    frame[:, -80:] = 25
    detections = [Detection(18, "Paper", 0.08, (22, 0, 1250, 719))]

    assert is_verified_empty_tray(frame, detections, roi_xyxy=(0, 0, 1280, 720))


def test_verified_empty_tray_keeps_transparent_bottle_with_colored_label():
    frame = np.full((720, 1280, 3), 210, dtype=np.uint8)
    frame[170:650, 170:760] = (45, 55, 155)
    detections = [Detection(24, "Plastic bottle", 0.58, (130, 120, 980, 700))]

    assert not is_verified_empty_tray(frame, detections, roi_xyxy=(0, 0, 1280, 720))


def test_ambiguous_paper_and_organic_candidate_requires_close_scores():
    close = [
        Detection(19, "Paper bag", 0.17, (10, 10, 300, 220)),
        Detection(17, "Organic", 0.16, (12, 11, 299, 219)),
    ]
    far = [
        Detection(19, "Paper bag", 0.65, (10, 10, 300, 220)),
        Detection(17, "Organic", 0.08, (12, 11, 299, 219)),
    ]

    assert find_ambiguous_organic_candidate(close, max_primary_confidence=0.7)
    assert find_ambiguous_organic_candidate(far, max_primary_confidence=0.7) is None
