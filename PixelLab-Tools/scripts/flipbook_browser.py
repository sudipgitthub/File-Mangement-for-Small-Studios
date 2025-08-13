import os
import glob
import subprocess
import numpy as np
import OpenImageIO as oiio
from PySide2 import QtWidgets, QtGui, QtCore
import hou

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

class EXRFlipbookBrowser(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("FlipbookImageSequenceBrowser")
        self.setWindowTitle("EXR Flipbook Browser")
        self.setMinimumSize(750, 450)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setViewMode(QtWidgets.QListView.IconMode)
        self.list_widget.setIconSize(QtCore.QSize(160, 90))
        self.list_widget.setGridSize(QtCore.QSize(180, 130))
        self.list_widget.setResizeMode(QtWidgets.QListView.Adjust)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.list_widget.itemDoubleClicked.connect(self.open_in_mplay)

        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.start_thumbnail_loading)

        self.mp4_btn = QtWidgets.QPushButton("Open MP4 Folder")
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
            self.item_lookup[folder_path].setIcon(QtGui.QIcon(thumb))
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
