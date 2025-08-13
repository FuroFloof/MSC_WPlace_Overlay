import os
import sys
import platform
import ctypes

from PyQt6.QtCore import Qt, QPoint, QRectF
from PyQt6.QtGui import QImage, QPainter, QPen, QAction
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QMessageBox, QGroupBox,
    QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QFormLayout,
    QSlider, QCheckBox, QDoubleSpinBox, QSpinBox, QLabel
)

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    user32 = ctypes.windll.user32
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_LAYERED = 0x00080000

    GetWindowLongPtrW = getattr(user32, "GetWindowLongPtrW", None)
    SetWindowLongPtrW = getattr(user32, "SetWindowLongPtrW", None)
    if GetWindowLongPtrW is None:
        GetWindowLongPtrW = user32.GetWindowLongW
    if SetWindowLongPtrW is None:
        SetWindowLongPtrW = user32.SetWindowLongW


def find_pngs(folder: str):
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, n) for n in sorted(os.listdir(folder)) if n.lower().endswith(".png")]


class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle("Pixel Overlay")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        if hasattr(Qt.WindowType, "WindowDoesNotAcceptFocus"):
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)

        self._img = None
        self._scale_x = 10.0
        self._scale_y = 10.0
        self._opacity = 0.8
        self._grid_alpha = 140
        self._grid_width = 1
        self._show_grid = True

        self._show_holes = True
        self._hole_percent = 40.0 

        self._offset_x = 0.0
        self._offset_y = 0.0

        self._click_through = True
        self._apply_click_through()

        self._dragging = False
        self._drag_pos = QPoint()

        self.update_window_opacity()

    def load_image(self, qimage: QImage, scale_x: float, scale_y: float):
        if qimage.isNull():
            return
        self._img = qimage
        self._scale_x = max(0.01, float(scale_x))
        self._scale_y = max(0.01, float(scale_y))
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._resize_to_image_scale()

    def set_scales(self, scale_x: float, scale_y: float):
        self._scale_x = max(0.01, float(scale_x))
        self._scale_y = max(0.01, float(scale_y))
        self._resize_to_image_scale()
        self.update()

    def set_overlay_opacity(self, op: float):
        self._opacity = min(1.0, max(0.05, float(op)))
        self.update_window_opacity()

    def set_always_on_top(self, enabled: bool):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        self._reapply_flags()

    def set_show_grid(self, enabled: bool):
        self._show_grid = bool(enabled)
        self.update()

    def set_grid_alpha(self, a: int):
        self._grid_alpha = max(0, min(255, int(a)))
        self.update()

    def set_grid_width(self, w: int):
        self._grid_width = max(1, int(w))
        self.update()

    def set_offsets(self, ox: float, oy: float):
        self._offset_x = float(ox)
        self._offset_y = float(oy)
        self.update()

    def set_click_through(self, enabled: bool):
        self._click_through = bool(enabled)
        self._apply_click_through()

    def set_holes_enabled(self, enabled: bool):
        self._show_holes = bool(enabled)
        self.update()

    def set_hole_percent(self, pct: float):
        self._hole_percent = max(0.0, min(100.0, float(pct)))
        self.update()

    def _resize_to_image_scale(self):
        if not self._img:
            return
        w = int(self._img.width() * self._scale_x)
        h = int(self._img.height() * self._scale_y)
        self.setMinimumSize(50, 50)
        self.resize(max(50, w), max(50, h))

    def update_window_opacity(self):
        self.setWindowOpacity(self._opacity)

    def _reapply_flags(self):
        visible = self.isVisible()
        if visible:
            self.hide()
        self.show()

        self._apply_click_through()

    def _apply_click_through(self):
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, self._click_through)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        if not IS_WINDOWS:
            return

        hwnd = int(self.winId()) 
        exstyle = GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        exstyle |= WS_EX_LAYERED
        if self._click_through:
            exstyle |= WS_EX_TRANSPARENT
        else:
            exstyle &= ~WS_EX_TRANSPARENT
        SetWindowLongPtrW(hwnd, GWL_EXSTYLE, exstyle)

    def mousePressEvent(self, e):
        if self._click_through:
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._click_through:
            return
        if self._dragging:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        if self._click_through:
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def keyPressEvent(self, e):
        step = 10 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        if e.key() == Qt.Key.Key_Left:
            self.move(self.x() - step, self.y())
        elif e.key() == Qt.Key.Key_Right:
            self.move(self.x() + step, self.y())
        elif e.key() == Qt.Key.Key_Up:
            self.move(self.x(), self.y() - step)
        elif e.key() == Qt.Key.Key_Down:
            self.move(self.x(), self.y() + step)
        else:
            super().keyPressEvent(e)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = e.angleDelta().y()
            step = 0.01 if delta > 0 else -0.01
            self._scale_x = max(0.01, self._scale_x + step)
            self._scale_y = max(0.01, self._scale_y + step)
            self._resize_to_image_scale()
            self.update()
        else:
            super().wheelEvent(e)

    def paintEvent(self, _):
        if not self._img:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        p.translate(self._offset_x, self._offset_y)
        p.scale(self._scale_x, self._scale_y)

        p.drawImage(0, 0, self._img)

        if self._show_holes and self._hole_percent > 0.0:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            w = self._img.width()
            h = self._img.height()
            d = (self._hole_percent / 100.0)
            r = d * 0.5  
            size = 2 * r
            for y in range(h):
                cy = y + 0.5
                top = cy - r
                for x in range(w):
                    cx = x + 0.5
                    left = cx - r
                    p.drawEllipse(QRectF(left, top, size, size))
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        if self._show_grid:
            pen = QPen()
            pen.setWidth(self._grid_width)
            pen.setColor(Qt.GlobalColor.black)
            c = pen.color()
            c.setAlpha(self._grid_alpha)
            pen.setColor(c)
            pen.setCosmetic(True) 
            p.setPen(pen)
            w = self._img.width()
            h = self._img.height()
            for x in range(w + 1):
                p.drawLine(x, 0, x, h)
            for y in range(h + 1):
                p.drawLine(0, y, w, y)

        p.end()


class ControlWindow(QMainWindow):
    def __init__(self, image_paths):
        super().__init__()
        self.setWindowTitle("Pixel Overlay Controller")
        self.overlay = OverlayWindow()
        self.overlay.hide()

        self.images = image_paths
        self._lock_aspect = True  

        self._build_ui()

        if not self.images:
            QMessageBox.warning(self, "No PNGs found", "Put some PNG files in ./pix and restart.")
        else:
            self.load_selected_image()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        pick_box = QGroupBox("Image")
        pick_row = QHBoxLayout()
        self.combo = QComboBox()
        self.combo.setMinimumContentsLength(30)
        self.combo.addItems([os.path.basename(p) for p in self.images])
        self.combo.currentIndexChanged.connect(self.load_selected_image)

        btn_reload = QPushButton("Rescan ./pix")
        btn_reload.clicked.connect(self.rescan_images)
        btn_show = QPushButton("Show Overlay")
        btn_show.clicked.connect(self.show_overlay)
        btn_hide = QPushButton("Hide Overlay")
        btn_hide.clicked.connect(self.hide_overlay)

        pick_row.addWidget(self.combo, 1)
        pick_row.addWidget(btn_reload)
        pick_row.addWidget(btn_show)
        pick_row.addWidget(btn_hide)
        pick_box.setLayout(pick_row)
        root.addWidget(pick_box)

        ctl_box = QGroupBox("Overlay Controls")
        form = QFormLayout()

        self.chk_lock = QCheckBox("Lock aspect")
        self.chk_lock.setChecked(True)
        self.chk_lock.toggled.connect(self.on_lock_aspect)

        self.chk_click = QCheckBox("Click-through overlay")
        self.chk_click.setChecked(True)
        self.chk_click.toggled.connect(self.on_click_through)

        self.scale_x_spin = QDoubleSpinBox()
        self.scale_x_spin.setDecimals(3)
        self.scale_x_spin.setRange(0.01, 200.0)
        self.scale_x_spin.setSingleStep(0.01)
        self.scale_x_spin.setValue(10.0)
        self.scale_x_spin.valueChanged.connect(self.on_scale_x)

        self.scale_x_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_x_slider.setRange(1, 20000)   
        self.scale_x_slider.setValue(1000)
        self.scale_x_slider.valueChanged.connect(self.on_scale_x_slider)

        self.scale_y_spin = QDoubleSpinBox()
        self.scale_y_spin.setDecimals(3)
        she = self.scale_y_spin  
        self.scale_y_spin.setRange(0.01, 200.0)
        self.scale_y_spin.setSingleStep(0.01)
        self.scale_y_spin.setValue(10.0)
        self.scale_y_spin.valueChanged.connect(self.on_scale_y)

        self.scale_y_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_y_slider.setRange(1, 20000)
        self.scale_y_slider.setValue(1000)
        self.scale_y_slider.valueChanged.connect(self.on_scale_y_slider)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(5, 100)
        self.opacity_slider.setValue(80)
        self.opacity_slider.valueChanged.connect(self.on_opacity)

        self.chk_top = QCheckBox("Always on top")
        self.chk_top.setChecked(True)
        self.chk_top.toggled.connect(self.on_top)

        self.chk_grid = QCheckBox("Show grid")
        self.chk_grid.setChecked(True)
        self.chk_grid.toggled.connect(self.on_grid)

        self.grid_alpha = QSpinBox()
        self.grid_alpha.setRange(0, 255)
        self.grid_alpha.setValue(140)
        self.grid_alpha.valueChanged.connect(self.on_grid_alpha)

        self.grid_width = QSpinBox()
        self.grid_width.setRange(1, 5)
        self.grid_width.setValue(1)
        self.grid_width.valueChanged.connect(self.on_grid_width)

        self.chk_holes = QCheckBox("Center holes in pixels")
        self.chk_holes.setChecked(True)
        self.chk_holes.toggled.connect(self.on_holes_enabled)

        self.hole_percent = QDoubleSpinBox()
        self.hole_percent.setDecimals(1)
        self.hole_percent.setRange(0.0, 100.0)
        self.hole_percent.setSingleStep(1.0)
        self.hole_percent.setValue(40.0)
        self.hole_percent.valueChanged.connect(self.on_hole_percent)

        self.offset_x = QDoubleSpinBox()
        self.offset_x.setDecimals(3)
        self.offset_x.setRange(-2.0, 2.0)
        self.offset_x.setSingleStep(0.05)
        self.offset_x.setValue(0.0)
        self.offset_x.valueChanged.connect(self.on_offsets)

        self.offset_y = QDoubleSpinBox()
        self.offset_y.setDecimals(3)
        self.offset_y.setRange(-2.0, 2.0)
        self.offset_y.setSingleStep(0.05)
        self.offset_y.setValue(0.0)
        self.offset_y.valueChanged.connect(self.on_offsets)

        form.addRow(self.chk_lock)
        form.addRow(self.chk_click)
        form.addRow("Scale X (px per pixel)", self.scale_x_spin)
        form.addRow("Scale X slider", self.scale_x_slider)
        form.addRow("Scale Y (px per pixel)", self.scale_y_spin)
        form.addRow("Scale Y slider", self.scale_y_slider)
        form.addRow("Opacity", self.opacity_slider)
        form.addRow(self.chk_top)
        form.addRow(self.chk_grid)
        form.addRow("Grid alpha", self.grid_alpha)
        form.addRow("Grid width", self.grid_width)
        form.addRow(self.chk_holes)
        form.addRow("Hole size (% of pixel)", self.hole_percent)
        form.addRow("Offset X (px)", self.offset_x)
        form.addRow("Offset Y (px)", self.offset_y)

        ctl_box.setLayout(form)
        root.addWidget(ctl_box)

        foot = QHBoxLayout()
        btn_center = QPushButton("Center Overlay")
        btn_center.clicked.connect(self.center_overlay)
        btn_quit = QPushButton("Quit")
        btn_quit.clicked.connect(QApplication.instance().quit)
        foot.addWidget(btn_center)
        foot.addStretch(1)
        foot.addWidget(QLabel("Tips: Ctrl+Wheel scales uniformly. Toggle Click-through to drag the overlay."))
        foot.addWidget(btn_quit)
        root.addLayout(foot)

        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(QApplication.instance().quit)
        self.menuBar().addAction(act_quit)

    def current_image_path(self):
        if not self.images:
            return None
        idx = max(0, self.combo.currentIndex())
        return self.images[idx]

    def load_selected_image(self):
        path = self.current_image_path()
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            QMessageBox.critical(self, "Load failed", f"Could not load: {path}")
            return
        self.overlay.load_image(img, self.scale_x_spin.value(), self.scale_y_spin.value())

    def show_overlay(self):
        if not self.overlay.isVisible():
            self.overlay.show()
            self.overlay.raise_()
            self.overlay._apply_click_through()

    def hide_overlay(self):
        self.overlay.hide()

    def rescan_images(self):
        self.images = find_pngs("./pix")
        self.combo.clear()
        self.combo.addItems([os.path.basename(p) for p in self.images])
        if self.images:
            self.load_selected_image()
        else:
            QMessageBox.information(self, "No images", "No PNGs found in ./pix.")

    def on_lock_aspect(self, enabled: bool):
        self._lock_aspect = bool(enabled)
        if self._lock_aspect:
            v = self.scale_x_spin.value()
            sval = int(max(1.0, min(20000.0, round(v * 100))))
            self.scale_y_spin.blockSignals(True)
            self.scale_y_slider.blockSignals(True)
            self.scale_y_spin.setValue(v)
            self.scale_y_slider.setValue(sval)
            self.scale_y_spin.blockSignals(False)
            self.scale_y_slider.blockSignals(False)
            self.overlay.set_scales(v, v)

    def on_click_through(self, enabled: bool):
        self.overlay.set_click_through(enabled)

    def on_scale_x(self, v: float):
        sval = int(max(1.0, min(20000.0, round(v * 100))))
        self.scale_x_slider.blockSignals(True)
        self.scale_x_slider.setValue(sval)
        self.scale_x_slider.blockSignals(False)
        if self._lock_aspect:
            self.scale_y_spin.blockSignals(True)
            self.scale_y_slider.blockSignals(True)
            self.scale_y_spin.setValue(v)
            self.scale_y_slider.setValue(sval)
            self.scale_y_spin.blockSignals(False)
            self.scale_y_slider.blockSignals(False)
            self.overlay.set_scales(v, v)
        else:
            self.overlay.set_scales(v, self.scale_y_spin.value())

    def on_scale_x_slider(self, sval: int):
        v = sval / 100.0
        self.scale_x_spin.blockSignals(True)
        self.scale_x_spin.setValue(v)
        self.scale_x_spin.blockSignals(False)
        if self._lock_aspect:
            self.scale_y_spin.blockSignals(True)
            self.scale_y_slider.blockSignals(True)
            self.scale_y_spin.setValue(v)
            self.scale_y_slider.setValue(sval)
            self.scale_y_spin.blockSignals(False)
            self.scale_y_slider.blockSignals(False)
            self.overlay.set_scales(v, v)
        else:
            self.overlay.set_scales(v, self.scale_y_spin.value())

    def on_scale_y(self, v: float):
        sval = int(max(1.0, min(20000.0, round(v * 100))))
        self.scale_y_slider.blockSignals(True)
        self.scale_y_slider.setValue(sval)
        self.scale_y_slider.blockSignals(False)
        if self._lock_aspect:
            self.scale_x_spin.blockSignals(True)
            self.scale_x_slider.blockSignals(True)
            self.scale_x_spin.setValue(v)
            self.scale_x_slider.setValue(sval)
            self.scale_x_spin.blockSignals(False)
            self.scale_x_slider.blockSignals(False)
            self.overlay.set_scales(v, v)
        else:
            self.overlay.set_scales(self.scale_x_spin.value(), v)

    def on_scale_y_slider(self, sval: int):
        v = sval / 100.0
        self.scale_y_spin.blockSignals(True)
        self.scale_y_spin.setValue(v)
        self.scale_y_spin.blockSignals(False)
        if self._lock_aspect:
            self.scale_x_spin.blockSignals(True)
            self.scale_x_slider.blockSignals(True)
            self.scale_x_spin.setValue(v)
            self.scale_x_slider.setValue(sval)
            self.scale_x_spin.blockSignals(False)
            self.scale_x_slider.blockSignals(False)
            self.overlay.set_scales(v, v)
        else:
            self.overlay.set_scales(self.scale_x_spin.value(), v)

    def on_opacity(self, v):
        self.overlay.set_overlay_opacity(v / 100.0)

    def on_top(self, enabled):
        self.overlay.set_always_on_top(enabled)

    def on_grid(self, enabled):
        self.overlay.set_show_grid(enabled)

    def on_grid_alpha(self, a):
        self.overlay.set_grid_alpha(a)

    def on_grid_width(self, w):
        self.overlay.set_grid_width(w)

    def on_holes_enabled(self, enabled):
        self.overlay.set_holes_enabled(enabled)

    def on_hole_percent(self, pct):
        self.overlay.set_hole_percent(pct)

    def on_offsets(self, _):
        self.overlay.set_offsets(self.offset_x.value(), self.offset_y.value())

    def center_overlay(self):
        if not self.overlay.isVisible():
            self.overlay.show()
            self.overlay._apply_click_through()
        scr = QApplication.primaryScreen().availableGeometry()
        ow = self.overlay.frameGeometry()
        x = scr.center().x() - ow.width() // 2
        y = scr.center().y() - ow.height() // 2
        self.overlay.move(x, y)


def main():
    app = QApplication(sys.argv)
    paths = find_pngs("./pix")
    win = ControlWindow(paths)
    win.resize(880, 520)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
