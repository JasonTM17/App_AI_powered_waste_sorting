from app.core.dataset_trust import DatasetTrustState, classify_dataset_item, is_trainable_meta


def _meta(source: str = "manual_import", cls_name: str = "Paper", **extra):
    data = {
        "source": source,
        "boxes": [{"cls_id": 18, "cls_name": cls_name, "conf": 1.0, "xyxy": [1, 2, 30, 40]}],
    }
    data.update(extra)
    return data


def test_manual_import_alias_becomes_trainable_canonical_class():
    decision = classify_dataset_item(_meta(cls_name="hop nhua"))

    assert decision.state is DatasetTrustState.TRAINABLE
    assert decision.class_names == ("Plastic canister",)
    assert is_trainable_meta(_meta(cls_name="hop nhua")) is True


def test_review_required_camera_sample_waits_for_review():
    decision = classify_dataset_item(_meta("manual_camera_capture", "Pen", reviewed=False))

    assert decision.state is DatasetTrustState.NEEDS_REVIEW
    assert "review_required" in decision.reasons


def test_review_required_phone_import_waits_for_bbox_review():
    decision = classify_dataset_item(_meta("manual_phone_import", "Pen", reviewed=False, bbox_reviewed=False))

    assert decision.state is DatasetTrustState.NEEDS_REVIEW
    assert "review_required" in decision.reasons


def test_review_required_source_needs_bbox_review_flag():
    decision = classify_dataset_item(_meta("manual_camera_capture", "Pen", reviewed=True))

    assert decision.state is DatasetTrustState.NEEDS_REVIEW
    assert "review_required" in decision.reasons


def test_web_import_missing_manifest_is_quarantined():
    decision = classify_dataset_item(_meta("manual_web_import", "Pen", reviewed=True, bbox_reviewed=True))

    assert decision.state is DatasetTrustState.QUARANTINE
    assert "source_license_issue" in decision.reasons


def test_unknown_label_is_quarantined():
    decision = classify_dataset_item(_meta(cls_name="Mystery trash"))

    assert decision.state is DatasetTrustState.QUARANTINE
    assert "off_taxonomy" in decision.reasons


def test_hard_negative_and_holdout_are_eval_only_not_trainable():
    negative = classify_dataset_item({"source": "hard_negative", "hard_negative": True, "boxes": []})
    holdout = classify_dataset_item(_meta(holdout=True, split="test"))

    assert negative.state is DatasetTrustState.HARD_NEGATIVE
    assert holdout.state is DatasetTrustState.HOLDOUT
    assert negative.trainable is False
    assert holdout.trainable is False


def test_generated_source_is_trainable_only_when_manifest_is_valid_train_split():
    meta = _meta(
        "manual_web_import",
        "Pen",
        reviewed=True,
        bbox_reviewed=True,
        generated=True,
        recognition_enabled=False,
        split="train",
        source_url="https://example.test/pen.jpg",
        source_license="generated-training-only",
        source_author="local-generator",
        source_type="generated",
        canonical_class="Pen",
    )

    decision = classify_dataset_item(meta)

    assert decision.state is DatasetTrustState.TRAINABLE
