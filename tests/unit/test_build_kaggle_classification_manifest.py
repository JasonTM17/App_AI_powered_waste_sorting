from scripts import build_kaggle_classification_manifest as manifest


def test_default_kaggle_cache_is_local_to_repo(monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_KAGGLE_CACHE", raising=False)

    assert manifest.default_kaggle_cache_root() == manifest.ROOT / ".local" / "kagglehub-cache"


def test_kaggle_cache_can_be_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("TRASH_SORTER_KAGGLE_CACHE", str(tmp_path))

    assert manifest.default_kaggle_cache_root() == tmp_path


def test_dataset_version_uses_cache_root(tmp_path):
    expected = tmp_path / "datasets" / "owner" / "dataset" / "versions" / "3"

    assert manifest._dataset_version(tmp_path, "owner", "dataset", 3) == expected
