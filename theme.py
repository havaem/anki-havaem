"""Apple-style look: colour tokens, stylesheet, and a few custom-drawn controls
(switch, segmented control, inset groups, sidebar icons). Follows the light /
dark appearance of Anki."""

import os

from aqt.qt import *

ICON_DIR = os.path.join(os.path.dirname(__file__), "icons").replace("\\", "/")
FONT_FAMILIES = [
    "SF Pro Text",
    "-apple-system",
    "Segoe UI Variable Text",
    "Segoe UI",
    "Helvetica Neue",
    "Ubuntu",
]


def is_dark() -> bool:
    return QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128


def tokens() -> dict:
    if is_dark():
        return dict(
            bg="#1c1c1e", side="#242426", group="#2c2c2e", sep="#3d3d40", fill="#3a3a3d",
            seg_on="#636366", label="#f5f5f7", secondary="#98989f", accent="#0a84ff",
            ok="#30d158", bad="#ff453a", switch_off="#48484a",
        )
    return dict(
        bg="#f2f2f7", side="#e8e8ed", group="#ffffff", sep="#e1e1e6", fill="#e9e9ee",
        seg_on="#ffffff", label="#1d1d1f", secondary="#86868b", accent="#007aff",
        ok="#34c759", bad="#ff3b30", switch_off="#d1d1d6",
    )


def build_style() -> str:
    t = tokens()
    return f"""
QDialog#hub, QDialog#progress {{ background: {t['bg']}; }}
QWidget#side {{ background: {t['side']}; }}
QWidget#pageInner {{ background: transparent; }}
QScrollArea {{ background: transparent; border: none; }}

QLabel {{ color: {t['label']}; font-size: 13px; }}
QLabel#pageTitle {{ font-size: 28px; font-weight: 700; }}
QLabel#appName {{ font-size: 12px; font-weight: 600; color: {t['secondary']}; padding: 2px 6px; }}
QLabel#secondary {{ color: {t['secondary']}; font-size: 12px; }}
QLabel#groupHeader {{ color: {t['secondary']}; font-size: 12px; font-weight: 500; padding-left: 16px; }}
QLabel#groupFooter {{ color: {t['secondary']}; font-size: 12px; padding: 0 16px; }}
QLabel#rowSub {{ color: {t['secondary']}; font-size: 11px; }}
QLabel#metricValue {{ font-size: 24px; font-weight: 700; }}
QLabel#headline {{ font-size: 20px; font-weight: 700; }}

QFrame#group {{ background: {t['group']}; border-radius: 12px; }}

QListWidget#nav {{ background: transparent; border: none; outline: none; font-size: 13px; }}
QListWidget#nav::item {{ padding: 7px 8px; margin: 1px 0; border-radius: 8px; color: {t['label']}; }}
QListWidget#nav::item:selected {{ background: {t['accent']}; color: white; }}
QListWidget#nav::item:hover:!selected {{ background: {t['fill']}; }}

QComboBox {{
    background: {t['fill']}; color: {t['label']}; border: none; border-radius: 7px;
    padding: 5px 10px; min-width: 190px; font-size: 13px;
}}
QComboBox:disabled {{ color: {t['secondary']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url("{ICON_DIR}/chevron.svg"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background: {t['group']}; color: {t['label']}; border: 1px solid {t['sep']};
    selection-background-color: {t['accent']}; selection-color: white; outline: none;
}}

QLineEdit {{
    background: {t['fill']}; color: {t['label']}; border: none; border-radius: 7px;
    padding: 6px 10px; font-size: 13px; selection-background-color: {t['accent']};
}}
QPlainTextEdit {{
    background: transparent; color: {t['label']}; border: none; font-size: 13px;
    selection-background-color: {t['accent']};
}}
QTextEdit {{
    background: {t['group']}; color: {t['label']}; border: none; border-radius: 10px; padding: 8px;
}}

QPushButton {{
    background: {t['fill']}; color: {t['accent']}; border: none; border-radius: 7px;
    padding: 6px 14px; font-size: 13px; font-weight: 500;
}}
QPushButton:hover {{ background: {t['sep']}; }}
QPushButton:disabled {{ color: {t['secondary']}; }}
QPushButton#primary {{
    background: {t['accent']}; color: white; border-radius: 10px;
    padding: 11px 32px; font-size: 14px; font-weight: 600; min-width: 160px;
}}
QPushButton#primary:hover {{ background: {t['accent']}; border: 2px solid rgba(255,255,255,70); }}
QPushButton#primary:disabled {{ background: {t['switch_off']}; color: {t['secondary']}; }}

QProgressBar {{ background: {t['fill']}; border: none; border-radius: 3px; min-height: 6px; max-height: 6px; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 3px; }}

QTableWidget {{
    background: transparent; border: none; gridline-color: transparent; color: {t['label']};
    font-size: 13px; alternate-background-color: transparent; outline: none;
}}
QTableWidget::indicator {{
    width: 16px; height: 16px; border-radius: 5px; border: 1.5px solid {t['switch_off']}; background: transparent;
}}
QTableWidget::indicator:checked {{
    background: {t['accent']}; border: 1.5px solid {t['accent']}; image: url("{ICON_DIR}/check.svg");
}}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: transparent; color: {t['secondary']}; border: none;
    border-bottom: 1px solid {t['sep']}; padding: 8px 10px; font-size: 12px; font-weight: 500;
}}

QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['switch_off']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}
"""


# --------------------------------------------------------------------------- #
# Switch
# --------------------------------------------------------------------------- #


class Switch(QAbstractButton):
    """iOS-style toggle with the QCheckBox API (isChecked / setChecked / toggled)."""

    def __init__(self, checked: bool = False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46, 28)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def paintEvent(self, _event):
        t = tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(1.0 if self.isEnabled() else 0.45)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t["ok"] if self.isChecked() else t["switch_off"]))
        p.drawRoundedRect(QRectF(0, 0, 46, 28), 14, 14)
        x = 20.0 if self.isChecked() else 2.0
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, 2, 24, 24))


# --------------------------------------------------------------------------- #
# Segmented control
# --------------------------------------------------------------------------- #


class Segmented(QWidget):
    valueChanged = pyqtSignal(object)

    def __init__(self, options=()):
        super().__init__()
        self._options: list = []
        self._index = 0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set_options(options)

    def set_options(self, options) -> None:
        self._options = list(options)
        self._index = min(self._index, max(len(self._options) - 1, 0))
        self.updateGeometry()
        self.update()

    def value(self):
        return self._options[self._index][1] if self._options else None

    def set_value(self, value) -> None:
        for i, (_, v) in enumerate(self._options):
            if v == value:
                self._index = i
                self.update()
                return

    def _seg_width(self) -> int:
        fm = QFontMetrics(self.font())
        widest = max((fm.horizontalAdvance(label) for label, _ in self._options), default=40)
        return widest + 28

    def sizeHint(self) -> QSize:
        return QSize(self._seg_width() * max(len(self._options), 1) + 4, 32)

    def _select(self, index: int) -> None:
        if 0 <= index < len(self._options) and index != self._index:
            self._index = index
            self.update()
            self.valueChanged.emit(self.value())

    def mousePressEvent(self, event):
        if self.isEnabled() and self._options:
            seg = (self.width() - 4) / len(self._options)
            pos = event.position() if hasattr(event, "position") else event.pos()
            self._select(int((pos.x() - 2) // seg))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            self._select(self._index - 1)
        elif event.key() == Qt.Key.Key_Right:
            self._select(self._index + 1)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        if not self._options:
            return
        t = tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(1.0 if self.isEnabled() else 0.45)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t["fill"]))
        p.drawRoundedRect(QRectF(self.rect()), 9, 9)
        n = len(self._options)
        seg = (self.width() - 4) / n
        p.setBrush(QColor(t["seg_on"]))
        p.drawRoundedRect(QRectF(2 + seg * self._index, 2, seg, self.height() - 4), 7, 7)
        font = self.font()
        font.setPixelSize(13)
        p.setFont(font)
        for i, (label, _) in enumerate(self._options):
            font.setWeight(QFont.Weight.DemiBold if i == self._index else QFont.Weight.Normal)
            p.setFont(font)
            p.setPen(QColor(t["label"]))
            p.drawText(QRectF(2 + seg * i, 0, seg, self.height()), Qt.AlignmentFlag.AlignCenter, label)


# --------------------------------------------------------------------------- #
# Inset group (the rounded "settings list" block)
# --------------------------------------------------------------------------- #


class Row(QWidget):
    def __init__(self, label: str, control=None, sublabel: str = "", expand: bool = False, separator: bool = True):
        super().__init__()
        self._separator = separator
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(12)
        self.setMinimumHeight(44)

        text = QVBoxLayout()
        text.setSpacing(1)
        self.label = QLabel(label)
        text.addWidget(self.label)
        if sublabel:
            sub = QLabel(sublabel)
            sub.setObjectName("rowSub")
            sub.setWordWrap(True)
            text.addWidget(sub)
        lay.addLayout(text, 0 if expand else 1)
        if control is not None:
            if expand:
                lay.addWidget(control, 1)
            else:
                lay.addWidget(control, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.control = control

    def paintEvent(self, _event):
        if self._separator:
            p = QPainter(self)
            p.fillRect(QRect(16, 0, self.width() - 16, 1), QColor(tokens()["sep"]))


class Group(QWidget):
    def __init__(self, header: str = "", footer: str = ""):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        if header:
            head = QLabel(header)
            head.setObjectName("groupHeader")
            outer.addWidget(head)
        self.frame = QFrame()
        self.frame.setObjectName("group")
        self._rows = QVBoxLayout(self.frame)
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(0)
        outer.addWidget(self.frame)
        self.footer = QLabel(footer)
        self.footer.setObjectName("groupFooter")
        self.footer.setWordWrap(True)
        self.footer.setVisible(bool(footer))
        outer.addWidget(self.footer)
        self._count = 0

    def add_row(self, label: str, control=None, sublabel: str = "", expand: bool = False) -> Row:
        row = Row(label, control, sublabel, expand, separator=self._count > 0)
        self._rows.addWidget(row)
        self._count += 1
        return row

    def add_widget(self, widget: QWidget, margins=(0, 0, 0, 0), separator: bool = True) -> QWidget:
        """Full-width content (a table, a text box) inside the group."""
        holder = Row("", None, separator=separator and self._count > 0)
        lay = holder.layout()
        while lay.count():
            lay.takeAt(0)
        lay.setContentsMargins(*margins)
        lay.addWidget(widget)
        holder.setMinimumHeight(0)
        self._rows.addWidget(holder)
        self._count += 1
        return widget

    def set_footer(self, text: str) -> None:
        self.footer.setText(text)
        self.footer.setVisible(bool(text))


# --------------------------------------------------------------------------- #
# Sidebar icons: coloured rounded square with a white glyph
# --------------------------------------------------------------------------- #


def badge_icon(kind: str, color: str, size: int = 26) -> QIcon:
    scale = 2
    px = QPixmap(size * scale, size * scale)
    px.setDevicePixelRatio(scale)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(0, 0, size, size), 6.5, 6.5)

    pen = QPen(QColor("white"), 2.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    c = size / 2
    if kind == "plus":
        p.drawLine(QPointF(c, 7), QPointF(c, size - 7))
        p.drawLine(QPointF(7, c), QPointF(size - 7, c))
    elif kind == "spark":
        path = QPainterPath()
        r, k = 8.0, 2.2
        path.moveTo(c, c - r)
        for (x1, y1), (x2, y2) in [
            ((c + k, c - k), (c + r, c)),
            ((c + k, c + k), (c, c + r)),
            ((c - k, c + k), (c - r, c)),
            ((c - k, c - k), (c, c - r)),
        ]:
            path.lineTo(x1, y1)
            path.lineTo(x2, y2)
        p.setBrush(QColor("white"))
        p.drawPath(path)
    elif kind == "backup":
        p.drawLine(QPointF(c, 6.5), QPointF(c, 16))
        p.drawLine(QPointF(c - 4, 12.5), QPointF(c, 16.5))
        p.drawLine(QPointF(c + 4, 12.5), QPointF(c, 16.5))
        p.drawLine(QPointF(7, size - 7), QPointF(size - 7, size - 7))
    elif kind == "sliders":
        for y, x in ((8.5, 9.5), (13, 16.5), (17.5, 11)):
            p.drawLine(QPointF(6.5, y), QPointF(size - 6.5, y))
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(x, y), 2.4, 2.4)
    p.end()
    icon = QIcon()
    for mode in (QIcon.Mode.Normal, QIcon.Mode.Selected, QIcon.Mode.Active):
        icon.addPixmap(px, mode)  # same pixmap, so selection doesn't tint the badge
    return icon
