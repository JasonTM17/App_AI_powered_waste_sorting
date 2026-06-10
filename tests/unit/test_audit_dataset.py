from app.core.waste_categories import TRAINING_CLASS_ORDER_45
from scripts.audit_dataset import _read_yolo_data_yaml, _training_class_alignment


def _write_training_order_yaml(path):
    lines = ["nc: 45", "names:"]
    lines.extend(f"  {idx}: {name}" for idx, name in enumerate(TRAINING_CLASS_ORDER_45))
    path.write_text("\n".join(lines), encoding="utf-8")


def test_read_yolo_data_yaml_mapping_names(tmp_path):
    data_yaml = tmp_path / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                "path: dataset",
                "train: images/train",
                "val: images/valid",
                "nc: 2",
                "names:",
                "  0: Paper",
                "  1: Plastic bottle",
            ]
        ),
        encoding="utf-8",
    )

    summary = _read_yolo_data_yaml(data_yaml)

    assert summary["exists"] is True
    assert summary["nc"] == 2
    assert summary["class_total"] == 2
    assert summary["names"] == {0: "Paper", 1: "Plastic bottle"}
    assert summary["errors"] == []


def test_training_class_alignment_blocks_catalog_drift(tmp_path):
    data_yaml = tmp_path / "data.yaml"
    _write_training_order_yaml(data_yaml)
    summary = _read_yolo_data_yaml(data_yaml)

    alignment = _training_class_alignment({"Paper": 10, "Mystery class": 3}, summary)

    assert alignment["matches_training_order"] is True
    assert alignment["promotable_class_contract"] is False
    assert alignment["catalog_classes_not_in_training_order"] == ["Mystery class"]
    assert alignment["catalog_classes_not_in_trainset"] == ["Mystery class"]
