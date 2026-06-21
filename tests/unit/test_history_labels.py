from app.core.history_labels import infer_history_label


def test_known_class_gets_vietnamese_model_label():
    result = infer_history_label(cls_name="Plastic bottle", confidence=0.81)
    assert result.display_label == "Chai nhựa PET"
    assert result.label_status == "model_inferred"
    assert result.label_confidence == 0.81


def test_unknown_without_image_is_no_evidence():
    result = infer_history_label(cls_name="Unknown object", confidence=0.2)
    assert result.display_label == "Chưa xác định vật"
    assert result.label_status == "no_evidence"


def test_unknown_with_image_requires_review():
    result = infer_history_label(
        cls_name="Unknown object",
        confidence=0.2,
        image_available=True,
    )
    assert result.label_status == "needs_review"
