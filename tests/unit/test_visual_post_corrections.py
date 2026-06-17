import cv2
import numpy as np

from app.core.events import Detection
from app.core.visual_post_corrections import apply_visual_post_corrections


def test_visual_correction_relabels_low_conf_organic_wooden_utensil():
    frame = np.full((260, 360, 3), 235, dtype=np.uint8)
    cv2.line(frame, (40, 220), (210, 80), (150, 185, 215), 28)
    cv2.ellipse(frame, (245, 55), (52, 38), -25, 0, 360, (150, 185, 215), -1)
    detection = Detection(17, "Organic", 0.51, (25, 20, 305, 245))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Wood"
    assert corrected[0].operator_label == "Thia go"


def test_visual_correction_relabels_round_warm_unknown_as_eggshell():
    frame = np.full((240, 320, 3), 232, dtype=np.uint8)
    cv2.ellipse(frame, (165, 125), (58, 52), 0, 0, 360, (170, 195, 220), -1)
    cv2.ellipse(frame, (148, 111), (24, 17), -20, 0, 360, (195, 215, 232), -1)
    detection = Detection(-1, "Unknown object", 0.14, (95, 65, 230, 190))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Eggshell"


def test_visual_correction_relabels_crumpled_gray_paper_unknown_as_paper():
    frame = np.full((260, 360, 3), 228, dtype=np.uint8)
    paper = np.array(
        [
            [82, 76],
            [268, 50],
            [314, 145],
            [236, 218],
            [94, 199],
            [46, 126],
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(frame, [paper], (218, 220, 222))
    cv2.line(frame, (72, 123), (286, 87), (56, 56, 58), 18)
    cv2.line(frame, (94, 176), (250, 188), (74, 74, 76), 14)
    cv2.line(frame, (112, 88), (210, 210), (190, 190, 192), 7)
    detection = Detection(-1, "Unknown object", 0.77, (42, 45, 318, 224))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Paper"
    assert corrected[0].source == "visual_correction:crumpled_paper"
    assert corrected[0].operator_label == "Giay vo"


def test_visual_correction_relabels_clear_bottle_with_red_label_from_aluminum_can():
    frame = np.full((320, 460, 3), 226, dtype=np.uint8)
    body = np.array(
        [
            [48, 222],
            [118, 102],
            [312, 56],
            [408, 98],
            [356, 212],
            [142, 262],
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(frame, [body], (218, 222, 226))
    cv2.polylines(frame, [body], True, (156, 160, 166), 5)
    cv2.ellipse(frame, (350, 88), (72, 34), 12, 0, 360, (232, 235, 238), -1)
    label = np.array([[144, 166], [278, 130], [322, 206], [176, 238]], dtype=np.int32)
    cv2.fillPoly(frame, [label], (38, 58, 186))
    cv2.line(frame, (166, 188), (300, 154), (232, 232, 232), 5)
    cv2.line(frame, (190, 215), (316, 182), (224, 224, 224), 4)
    cv2.circle(frame, (382, 104), 11, (250, 250, 250), -1)
    detection = Detection(2, "Aluminum can", 0.45, (38, 46, 418, 272))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Plastic bottle"
    assert corrected[0].source == "visual_correction:plastic_bottle"
    assert corrected[0].operator_label == "Chai nhua PET"


def test_visual_correction_keeps_compact_red_aluminum_can():
    frame = np.full((260, 360, 3), 225, dtype=np.uint8)
    cv2.rectangle(frame, (128, 55), (228, 205), (36, 45, 182), -1)
    cv2.rectangle(frame, (128, 55), (228, 205), (82, 82, 86), 4)
    cv2.ellipse(frame, (178, 55), (50, 16), 0, 0, 360, (178, 180, 184), -1)
    cv2.ellipse(frame, (178, 205), (50, 16), 0, 0, 360, (150, 152, 156), -1)
    cv2.line(frame, (148, 88), (210, 88), (230, 230, 230), 5)
    detection = Detection(2, "Aluminum can", 0.52, (118, 38, 238, 224))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Aluminum can"


def test_visual_correction_expands_tiny_unknown_fold_to_crumpled_paper():
    frame = np.full((260, 360, 3), 228, dtype=np.uint8)
    paper = np.array(
        [
            [82, 76],
            [268, 50],
            [314, 145],
            [236, 218],
            [94, 199],
            [46, 126],
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(frame, [paper], (218, 220, 222))
    cv2.line(frame, (72, 123), (286, 87), (56, 56, 58), 18)
    cv2.line(frame, (94, 176), (250, 188), (74, 74, 76), 14)
    cv2.line(frame, (112, 88), (210, 210), (190, 190, 192), 7)
    detection = Detection(-1, "Unknown object", 0.39, (156, 94, 186, 168))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Paper"
    assert corrected[0].source == "visual_correction:crumpled_paper"
    assert corrected[0].xyxy[0] < detection.xyxy[0]
    assert corrected[0].xyxy[2] > detection.xyxy[2]


def test_visual_correction_keeps_elongated_metal_unknown_from_becoming_paper():
    frame = np.full((260, 360, 3), 228, dtype=np.uint8)
    cv2.line(frame, (35, 210), (245, 70), (92, 92, 92), 24)
    cv2.ellipse(frame, (280, 48), (54, 36), -24, 0, 360, (70, 70, 72), -1)
    detection = Detection(-1, "Unknown object", 0.62, (24, 22, 338, 230))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Unknown object"


def test_visual_correction_does_not_claim_low_conf_glass_bottle():
    frame = np.full((240, 320, 3), 230, dtype=np.uint8)
    detection = Detection(12, "Glass bottle", 0.38, (40, 35, 275, 215))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Unknown object"
    assert corrected[0].source == "visual_correction:low_conf_glass"
