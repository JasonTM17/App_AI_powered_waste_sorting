import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.config import ClassMapping
from app.ui.pages.mapping import MappingPage


def _ms():
    return [
        ClassMapping(class_name="paper", command="P", bin_index=1),
        ClassMapping(class_name="plastic", command="S", bin_index=2),
    ]


def test_mapping_emits_collected_list_on_save(qtbot):
    page = MappingPage(_ms())
    qtbot.addWidget(page)
    captured = []
    page.mappings_saved.connect(lambda lst: captured.append(lst))
    page._save()
    assert captured
    assert len(captured[0]) == 2
    assert captured[0][0].command == "P"


def test_mapping_command_uppercases(qtbot):
    page = MappingPage(_ms())
    qtbot.addWidget(page)
    rows = page._rows()
    rows[0].cmd_edit.setText("z")
    assert rows[0].cmd_edit.text() == "Z"


def test_mapping_preview_updates(qtbot):
    page = MappingPage(_ms())
    qtbot.addWidget(page)
    rows = page._rows()
    rows[0].cmd_edit.setText("X")
    assert "SORT:X" in page.preview_label.text()
