from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=-1, h_spacing=-1, v_spacing=-1):
        super().__init__(parent)
        self._item_list = []
        if margin > -1:
            self.setContentsMargins(margin, margin, margin, margin)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):  # noqa: N802
        self._item_list.append(item)

    def horizontalSpacing(self):  # noqa: N802
        if self._h_spacing >= 0:
            return self._h_spacing
        else:
            return self.smartSpacing(QSizePolicy.ControlTypes(QSizePolicy.ControlType.PushButton))

    def verticalSpacing(self):  # noqa: N802
        if self._v_spacing >= 0:
            return self._v_spacing
        else:
            return self.smartSpacing(QSizePolicy.ControlTypes(QSizePolicy.ControlType.PushButton))

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):  # noqa: N802
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):  # noqa: N802
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientations(0)

    def hasHeightForWidth(self):  # noqa: N802
        return True

    def heightForWidth(self, width):  # noqa: N802
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, test_only):  # noqa: N802
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.horizontalSpacing()

        for item in self._item_list:
            space_x = spacing
            space_y = self.verticalSpacing()
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()

    def smartSpacing(self, pm):  # noqa: N802
        parent = self.parent()
        if not parent:
            return -1
        elif parent.isWidgetType():
            return self.parentWidget().style().pixelMetric(
                pm, None, self.parentWidget()
            )
        else:
            return self.parent().layout().spacing()
