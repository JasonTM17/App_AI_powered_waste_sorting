import cv2
import numpy as np

from app.core.events import Detection
from app.core.visual_post_corrections import apply_visual_post_corrections


def _leafy_frame() -> np.ndarray:
    frame = np.full((300, 420, 3), 232, dtype=np.uint8)
    cv2.line(frame, (35, 178), (390, 164), (44, 82, 42), 8)
    for index, x in enumerate(range(58, 370, 32)):
        angle = -22 if index % 2 == 0 else 20
        center_y = 143 if index % 2 == 0 else 197
        color = (38, 94, 48) if index % 3 else (44, 78, 38)
        cv2.ellipse(frame, (x, center_y), (18, 48), angle, 0, 360, color, -1)
        cv2.ellipse(frame, (x + 10, center_y + 2), (8, 36), angle, 0, 360, (52, 112, 58), -1)
    return frame


def test_visual_correction_relabels_low_conf_organic_wooden_utensil():
    frame = np.full((260, 360, 3), 235, dtype=np.uint8)
    cv2.line(frame, (40, 220), (210, 80), (150, 185, 215), 28)
    cv2.ellipse(frame, (245, 55), (52, 38), -25, 0, 360, (150, 185, 215), -1)
    detection = Detection(17, "Organic", 0.51, (25, 20, 305, 245))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Wood"
    assert corrected[0].operator_label == "Thia go"


def test_visual_correction_relabels_leafy_unknown_as_organic():
    detection = Detection(-1, "Unknown object", 0.39, (25, 74, 398, 248))

    corrected = apply_visual_post_corrections(_leafy_frame(), [detection])

    assert corrected[0].cls_name == "Organic"
    assert corrected[0].source == "visual_correction:leafy_organic"
    assert corrected[0].operator_label == "La cay"


def test_visual_correction_marks_leafy_organic_operator_label():
    detection = Detection(17, "Organic", 0.87, (25, 74, 398, 248))

    corrected = apply_visual_post_corrections(_leafy_frame(), [detection])

    assert corrected[0].cls_name == "Organic"
    assert corrected[0].source == "visual_correction:leafy_organic"
    assert corrected[0].operator_label == "La cay"


def test_visual_correction_keeps_green_plastic_bottle_label():
    frame = np.full((280, 420, 3), 232, dtype=np.uint8)
    cv2.rectangle(frame, (96, 112), (330, 176), (48, 128, 52), -1)
    cv2.rectangle(frame, (330, 126), (380, 160), (48, 128, 52), -1)
    cv2.rectangle(frame, (180, 116), (252, 172), (220, 220, 225), -1)
    detection = Detection(3, "Plastic bottle", 0.72, (80, 98, 388, 190))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Plastic bottle"


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


def test_visual_correction_relabels_clear_labeled_unknown_as_plastic_bottle():
    frame = np.full((360, 480, 3), 230, dtype=np.uint8)
    body = np.array(
        [
            [150, 312],
            [126, 118],
            [188, 62],
            [302, 62],
            [360, 118],
            [334, 312],
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(frame, [body], (224, 228, 232))
    cv2.polylines(frame, [body], True, (158, 162, 168), 4)
    cv2.rectangle(frame, (146, 132), (338, 218), (194, 125, 42), -1)
    cv2.rectangle(frame, (154, 146), (330, 202), (210, 150, 58), -1)
    cv2.line(frame, (162, 190), (326, 170), (246, 246, 246), 5)
    cv2.rectangle(frame, (142, 222), (178, 246), (34, 52, 188), -1)
    cv2.circle(frame, (194, 86), 13, (252, 252, 252), -1)
    cv2.circle(frame, (286, 270), 18, (248, 248, 248), -1)
    detection = Detection(-1, "Unknown object", 0.82, (118, 54, 370, 322))

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


def test_visual_correction_relabels_elongated_metal_unknown_as_iron_utensils():
    frame = np.full((260, 360, 3), 228, dtype=np.uint8)
    cv2.line(frame, (35, 210), (245, 70), (92, 92, 92), 24)
    cv2.ellipse(frame, (280, 48), (54, 36), -24, 0, 360, (70, 70, 72), -1)
    detection = Detection(-1, "Unknown object", 0.62, (24, 22, 338, 230))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Iron utensils"
    assert corrected[0].source == "visual_correction:metal_utensil"


def test_visual_correction_relabels_shiny_metal_spoon_unknown_as_iron_utensils():
    frame = np.full((260, 420, 3), 230, dtype=np.uint8)
    cv2.line(frame, (22, 174), (258, 142), (82, 82, 82), 34)
    cv2.line(frame, (22, 160), (258, 130), (168, 168, 166), 14)
    cv2.ellipse(frame, (312, 128), (74, 56), -8, 0, 360, (76, 76, 78), -1)
    cv2.ellipse(frame, (292, 122), (46, 28), -10, 0, 360, (168, 168, 166), -1)
    cv2.circle(frame, (330, 94), 12, (250, 250, 250), -1)
    cv2.circle(frame, (350, 96), 8, (245, 245, 245), -1)
    detection = Detection(-1, "Unknown object", 0.14, (8, 54, 394, 220))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Iron utensils"
    assert corrected[0].source == "visual_correction:metal_utensil"
    assert corrected[0].operator_label == "Muong kim loai"


def test_visual_correction_relabels_blue_pen_like_unknown_as_pen():
    frame = np.full((260, 420, 3), 230, dtype=np.uint8)
    cv2.line(frame, (28, 176), (372, 142), (92, 92, 92), 28)
    cv2.line(frame, (32, 160), (360, 130), (166, 166, 164), 10)
    cv2.rectangle(frame, (86, 158), (160, 190), (210, 70, 20), -1)
    cv2.rectangle(frame, (330, 126), (394, 158), (210, 70, 20), -1)
    detection = Detection(-1, "Unknown object", 0.15, (18, 106, 404, 216))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Pen"
    assert corrected[0].source == "visual_correction:pen"
    assert corrected[0].operator_label == "But bi"


def test_visual_correction_relabels_pen_like_plastic_bottle_as_pen():
    frame = np.full((260, 420, 3), 230, dtype=np.uint8)
    cv2.line(frame, (28, 176), (372, 142), (92, 92, 92), 28)
    cv2.line(frame, (32, 160), (360, 130), (166, 166, 164), 10)
    cv2.rectangle(frame, (86, 158), (160, 190), (210, 70, 20), -1)
    detection = Detection(24, "Plastic bottle", 0.82, (18, 106, 404, 216))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Pen"
    assert corrected[0].source == "visual_correction:pen"


def test_visual_correction_keeps_high_conf_upright_plastic_bottle():
    frame = np.full((320, 300, 3), 230, dtype=np.uint8)
    cv2.rectangle(frame, (108, 68), (192, 272), (190, 198, 205), -1)
    cv2.rectangle(frame, (128, 38), (172, 78), (175, 182, 190), -1)
    cv2.rectangle(frame, (112, 132), (188, 206), (205, 100, 35), -1)
    detection = Detection(24, "Plastic bottle", 0.91, (96, 28, 204, 284))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Plastic bottle"
    assert corrected[0].source == detection.source


def test_visual_correction_keeps_plain_dark_bar_unknown():
    frame = np.full((240, 320, 3), 240, dtype=np.uint8)
    cv2.rectangle(frame, (80, 90), (220, 130), (20, 20, 20), -1)
    detection = Detection(-1, "Unknown object", 0.39, (62, 70, 238, 150))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Unknown object"


def test_visual_correction_does_not_claim_low_conf_glass_bottle():
    frame = np.full((240, 320, 3), 230, dtype=np.uint8)
    detection = Detection(12, "Glass bottle", 0.38, (40, 35, 275, 215))

    corrected = apply_visual_post_corrections(frame, [detection])

    assert corrected[0].cls_name == "Unknown object"
    assert corrected[0].source == "visual_correction:low_conf_glass"
