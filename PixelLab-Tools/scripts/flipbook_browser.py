import os
import glob
import subprocess
import numpy as np
import OpenImageIO as oiio
from PySide2 import QtWidgets, QtGui, QtCore
import hou
import re

# Close any previous instance
for w in QtWidgets.QApplication.allWidgets():
    if w.objectName() == "FlipbookImageSequenceBrowser":
        w.close()

def load_exr_thumbnail(path, size=(160, 90)):
    img = oiio.ImageInput.open(path)
    if not img:
        return None
    spec = img.spec()
    pixels = img.read_image(format=oiio.FLOAT)
    img.close()
    if pixels is None:
        return None

    w, h, c = spec.width, spec.height, spec.nchannels
    pixels = np.clip(pixels, 0.0, 1.0)
    arr = (pixels * 255).astype(np.uint8)

    if c == 3:
        arr = arr.reshape(h, w, 3)
        fmt = QtGui.QImage.Format_RGB888
    elif c >= 4:
        arr = arr.reshape(h, w, c)[:, :, :4]
        fmt = QtGui.QImage.Format_RGBA8888
    else:
        return None

    arr = np.ascontiguousarray(arr)
    qimg = QtGui.QImage(arr.data, w, h, w * arr.shape[2], fmt).copy()
    return QtGui.QPixmap.fromImage(qimg.scaled(*size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

from PySide2.QtGui import QPainter, QColor, QFont

def add_overlay_text(pixmap, resolution, frame_range):
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.TextAntialiasing)

    margin = 6
    rect = pixmap.rect().adjusted(margin, margin, -margin, -margin)
    text = f"{resolution[0]}x{resolution[1]}\n{frame_range[0]}-{frame_range[1]}"

    painter.setPen(QColor("white"))
    painter.setFont(QFont("Segoe UI", 6, QFont.Normal))
    painter.drawText(rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, text)
    painter.end()
    return pixmap

class EXRFlipbookBrowser(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("FlipbookImageSequenceBrowser")
        self.setWindowTitle("EXR Flipbook Browser")
        self.setMinimumSize(900, 550)

        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;  /* Dark grey background */
                color: #FFFFFF;             /* White text */
                font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
                font-size: 12px;             /* Font size 8 pixels */
            }
            QListWidget {
                background-color: #2c2c2c;  /* Slightly lighter dark grey for list */
                border: none;
                border-radius: 6px;
                outline: none;
            }
            QListWidget::item {
                background-color: #3a3a3a;  /* Medium dark grey item bg */
                margin: 6px 10px;
                padding: 6px;
                border-radius: 6px;
                color: #EEE;
            }
            QListWidget::item:selected {
                background-color: #FFFFFF;  /* White selection bg */
                color: #000000;             /* Black text when selected */
            }
            QListWidget::item:hover {
                background-color: #505050;  /* Lighter grey hover bg */
                color: #FFFFFF;
            }
            QPushButton {
                background-color: #bfbfbf;  /* Light gray button bg */
                color: #1e1e1e;             /* Dark text on button */
                padding: 8px 8px;          /* Smaller padding */
                border-radius: 4px;         /* Rounded corners with 4px radius */
                font-weight: 400;
                min-width: 4px;            /* Reduced minimum width */
                transition: background-color 0.2s ease, color 0.2s ease;
            }
            QPushButton:hover {
                background-color: #FFFFFF;  /* White bg on hover */
                color: #000000;             /* Black text on hover */
            }
            QPushButton:pressed {
                background-color: #d9d9d9;  /* Slightly darker gray pressed bg */
                color: #000000;
            }
        """)


        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setViewMode(QtWidgets.QListView.IconMode)
        self.list_widget.setIconSize(QtCore.QSize(160, 90))
        self.list_widget.setGridSize(QtCore.QSize(180, 130))
        self.list_widget.setSpacing(12)
        self.list_widget.setResizeMode(QtWidgets.QListView.Adjust)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.list_widget.itemDoubleClicked.connect(self.open_in_mplay)

        font = QtGui.QFont("Segoe UI", 11)
        self.list_widget.setFont(font)

        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.setFont(font)
        self.refresh_btn.clicked.connect(self.start_thumbnail_loading)

        self.mp4_btn = QtWidgets.QPushButton("Open MP4 Folder")
        self.mp4_btn.setFont(font)
        self.mp4_btn.clicked.connect(self.open_mp4_folder)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.mp4_btn)
        btn_layout.addStretch()

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.list_widget)
        main_layout.addLayout(btn_layout)

        self.folders = []
        self.thumbnail_index = 0
        self.item_lookup = {}

        self.timer = QtCore.QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.load_next_thumbnail)

        QtCore.QTimer.singleShot(100, self.start_thumbnail_loading)

    def hip_root(self):
        return os.path.join(os.path.normpath(os.path.expandvars("$HIP")), "Flipbooks")

    def start_thumbnail_loading(self):
        self.list_widget.clear()
        self.item_lookup.clear()
        self.timer.stop()

        root = self.hip_root()
        if not os.path.isdir(root):
            return

        self.folders = []
        seen_paths = set()

        for name in sorted(os.listdir(root)):
            folder_path = os.path.abspath(os.path.join(root, name))
            if folder_path in seen_paths or not os.path.isdir(folder_path):
                continue

            exrs = sorted(glob.glob(os.path.join(folder_path, "*.exr")))
            if not exrs:
                continue

            seen_paths.add(folder_path)
            self.folders.append((name, folder_path, exrs))

            placeholder = QtGui.QPixmap(160, 90)
            placeholder.fill(QtGui.QColor("gray"))
            item = QtWidgets.QListWidgetItem(QtGui.QIcon(placeholder), name)
            item.setData(QtCore.Qt.UserRole, exrs)
            self.list_widget.addItem(item)
            self.item_lookup[folder_path] = item

        self.thumbnail_index = 0
        self.timer.start()

    def load_next_thumbnail(self):
        if self.thumbnail_index >= len(self.folders):
            self.timer.stop()
            return

        name, folder_path, exrs = self.folders[self.thumbnail_index]
        thumb = load_exr_thumbnail(exrs[0])
        if thumb:
            img = oiio.ImageInput.open(exrs[0])
            spec = img.spec() if img else None
            if img:
                img.close()
            resolution = (spec.width, spec.height) if spec else (0, 0)

            frames = []
            for f in exrs:
                base = os.path.splitext(os.path.basename(f))[0]
                m = re.search(r'(\d+)$', base)
                if m:
                    frames.append(int(m.group(1)))
            if frames:
                frame_range = (min(frames), max(frames))
            else:
                frame_range = (0, 0)

            overlay_pixmap = add_overlay_text(thumb.copy(), resolution, frame_range)
            self.item_lookup[folder_path].setIcon(QtGui.QIcon(overlay_pixmap))

        self.thumbnail_index += 1

    def show_context_menu(self, pos):
        items = self.list_widget.selectedItems()
        if not items:
            return

        folder_path = os.path.dirname(items[0].data(QtCore.Qt.UserRole)[0])

        menu = QtWidgets.QMenu()
        menu.addAction("Open Folder", lambda: self.open_folder(folder_path))
        menu.addAction("Copy Path", lambda: QtWidgets.QApplication.clipboard().setText(folder_path))
        menu.exec_(self.list_widget.viewport().mapToGlobal(pos))

    def open_folder(self, path):
        if os.name == "nt":
            os.startfile(path)
        else:
            subprocess.Popen(["open", path])

    def open_mp4_folder(self):
        path = os.path.join(self.hip_root(), "mp4")
        os.makedirs(path, exist_ok=True)
        self.open_folder(path)

    def open_in_mplay(self, item):
        exr_sequence = item.data(QtCore.Qt.UserRole)
        if not exr_sequence:
            return

        folder = os.path.dirname(exr_sequence[0])
        files = sorted(os.path.basename(f) for f in exr_sequence)

        pattern = re.compile(r"(.*?)(\d+)(\.[^.]+)$")
        matches = [pattern.match(f) for f in files if pattern.match(f)]

        if matches:
            base = matches[0].group(1)
            start = int(matches[0].group(2))
            end = int(matches[-1].group(2))
            ext = matches[0].group(3)
            padding = len(matches[0].group(2))
            sequence = os.path.join(folder, f"{base}$F{padding}{ext}")

            subprocess.Popen(["mplay", "-f", str(start), str(end), "1", sequence])
            return

        subprocess.Popen(["mplay"] + exr_sequence)

def launch_browser():
    global flipbook_browser
    flipbook_browser = EXRFlipbookBrowser()
    flipbook_browser.show()

try:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    launch_browser()
except Exception as e:
    print(f"Error: {e}")
