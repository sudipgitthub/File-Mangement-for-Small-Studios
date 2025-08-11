import os
import sys
import getpass
import re
import hou
import shutil
import platform
import subprocess
from collections import defaultdict
from functools import partial
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtWidgets import QLabel, QMessageBox
from PySide2.QtCore import QSettings, QDate, QDateTime

# Optional OpenImageIO and numpy for EXR thumbnail loading
try:
    import OpenImageIO as oiio
    import numpy as np
    HAS_OIIO = True
except Exception:
    HAS_OIIO = False


class DeadlineJobLoader(QtCore.QThread):
    job_loaded = QtCore.Signal(dict)
    finished_loading = QtCore.Signal()

    def __init__(self, deadline_cmd, user):
        super().__init__()
        self.deadline_cmd = deadline_cmd
        self.user = user

    def run(self):
        try:
            # If deadline command missing extension on Windows, try .exe
            if platform.system() == "Windows" and not self.deadline_cmd.lower().endswith(".exe"):
                if os.path.isfile(self.deadline_cmd + ".exe"):
                    self.deadline_cmd = self.deadline_cmd + ".exe"

            if not os.path.isfile(self.deadline_cmd):
                # Still continue; the subprocess will likely error but we catch it
                pass

            result = subprocess.run(
                [self.deadline_cmd, "GetJobsFilter", f"Username={self.user}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            output = result.stdout.strip().splitlines()

            job = {}
            for line in output:
                line = line.strip()
                if line == "":
                    if job:
                        self.job_loaded.emit(job)
                        job = {}
                else:
                    if "=" in line:
                        key, value = line.split("=", 1)
                        job[key.strip()] = value.strip()
            if job:
                self.job_loaded.emit(job)
        except Exception as e:
            print("Error loading Deadline jobs:", e)
        finally:
            self.finished_loading.emit()

def get_default_base_path():
    return r"\\spdata\PROJECTS_TEMP"
    
class HoudiniManager(QtWidgets.QMainWindow):
    def __init__(self):
        super(HoudiniManager, self).__init__()
        self.setWindowTitle("Houdini Manager")
        self.setMinimumSize(1000, 600)
        self.settings = QSettings("MyStudio", "HoudiniManager")
        # Load stored base path or fallback to default
        self.base_sp_path = self.settings.value("browser/base_path", get_default_base_path())
        self.setup_ui()
        QtCore.QTimer.singleShot(100, self.load_pages)

    # ================= UI SETUP =================
    def setup_ui(self):
        self.setStyleSheet("""
            * { border-radius: 6px; font-family: 'Segoe UI', 'Arial', sans-serif; }
            QWidget { background-color: #2e2e2e; color: #f0f0f0; font-size: 12px; }
            QPushButton {
                background-color: #2e2e2e;
                padding: 8px 12px;
                text-align: left;
                font-weight: 500;
                color: #dddddd;
            }
            QPushButton:hover { background-color: #444; color: white; }
            QListWidget, QTreeWidget { background-color: #383838; padding: 6px; }
            QLabel { padding: 2px; }
            QScrollArea { background-color: transparent; }
            QFrame#Sidebar { background-color: #1f1f1f; }
        """)

        self.sidebar = QtWidgets.QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(110)
        self.sidebar_layout = QtWidgets.QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(10, 10, 10, 10)
        self.sidebar_layout.setSpacing(8)


        # User info
        username = getpass.getuser()
        user_widget = QtWidgets.QWidget()
        user_layout = QtWidgets.QHBoxLayout(user_widget)
        user_layout.setContentsMargins(4, 4, 4, 4)
        user_layout.setSpacing(0)
        
        # Use an icon character like folder or user symbol as text in QLabel
        icon_label = QLabel("👤 ")  # You can replace 👤 with other icons like 📁 or 🔑 if you want
        icon_label.setStyleSheet("font-size: 16px;")
        
        user_layout.addWidget(icon_label)
        user_layout.addWidget(QLabel(username))
        self.sidebar_layout.addWidget(user_widget)


        # Sidebar buttons
        self.menu_names = ["Home", "Browser", "Flipbook", "Deadline", "Render", "QUIT"]
        for name in self.menu_names:
            btn = QtWidgets.QPushButton(name)
            btn.setFixedHeight(36)
            btn.clicked.connect(partial(self.switch_page, name))
            self.sidebar_layout.addWidget(btn)

        self.sidebar_layout.addStretch()
        self.stack = QtWidgets.QStackedWidget()

        main_layout = QtWidgets.QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.stack)

        container = QtWidgets.QWidget()
        container.setLayout(main_layout)

        # Floating Refresh Button with Emoji Icon
        self.refresh_button = QtWidgets.QPushButton("⟳")
        self.refresh_button.setToolTip("Refresh All")
        self.refresh_button.setFixedSize(44, 44)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #383838;
                border-radius: 22px;
                color: white;
                font-weight: bold;
                font-size: 20px;
                border: none;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        self.refresh_button.clicked.connect(self.refresh_everything)
        self.refresh_button.setParent(container)
        self.refresh_button.raise_()
        self.refresh_button.move(self.width() - 60, self.height() - 60)
        self.resizeEvent = self.on_resize

        self.setCentralWidget(container)

    def on_resize(self, event):
        super(HoudiniManager, self).resizeEvent(event)
        if hasattr(self, 'refresh_button'):
            self.refresh_button.move(self.width() - 60, self.height() - 60)

    def switch_page(self, name):
        if name == "QUIT":
            self.close()
        elif name in getattr(self, "pages", {}):
            self.stack.setCurrentWidget(self.pages[name])

    def load_pages(self):
        # Create pages
        self.pages = {
            "Home": self.create_home_page(),
            "Browser": self.create_browser_page(),
            "Flipbook": self.create_flipbook_page(),
            "Deadline": self.create_deadline_page(),
            "Render": self.create_render_page(),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        self.stack.setCurrentWidget(self.pages["Home"])

        QtCore.QTimer.singleShot(150, self.populate_camera_list)
        QtCore.QTimer.singleShot(300, self.populate_grouped_nodes)
        QtCore.QTimer.singleShot(450, self.populate_cache_tree)
        QtCore.QTimer.singleShot(600, self.refresh_exr_thumbnails)

    # ============== HOME MENU ==============
    def create_home_page(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        left_col = QtWidgets.QVBoxLayout()
        left_col.setSpacing(4)

        # Button row
        button_row = QtWidgets.QHBoxLayout()
        hip_btn = QtWidgets.QPushButton("📂 HIP Directory")
        hip_btn.clicked.connect(lambda: self.run_external_script("open_hip_directory.py"))
        refresh_btn = QtWidgets.QPushButton("🔄 Refresh Viewport")
        refresh_btn.clicked.connect(lambda: self.run_external_script("refresh_viewport.py"))
        flipbook_btn = QtWidgets.QPushButton("🖼️ Flipbook")
        flipbook_btn.clicked.connect(lambda: self.run_external_script("viewport_flipbook.py"))
        lop_btn = QtWidgets.QPushButton("🌐 LOP Manager")
        lop_btn.clicked.connect(lambda: self.run_external_script("lop_manager.py"))
        opengl_btn = QtWidgets.QPushButton("📸 OpenGL")
        opengl_btn.clicked.connect(lambda: self.run_external_script("opengl_flipbook.py"))

        for b in (hip_btn, refresh_btn, lop_btn, flipbook_btn, opengl_btn):
            button_row.addWidget(b)

        button_widget = QtWidgets.QWidget()
        button_widget.setLayout(button_row)
        left_col.addWidget(button_widget)

        left_col.addWidget(self.create_labeled_box("\U0001F3A5 Camera Nodes", self.create_camera_list()))
        left_col.addWidget(self.create_labeled_box("\U0001F4E6 Node Group Summary", self.create_node_tree()))

        right_col = QtWidgets.QVBoxLayout()
        right_col.addWidget(self.create_labeled_box("\U0001F4BE Cache Sizes", self.create_cache_tree()))

        layout.addLayout(left_col, 2)
        layout.addLayout(right_col, 1)
        return widget

    def run_external_script(self, script_name):
        try:
            pixellib = hou.getenv("PIXELLAB")
            script_path = os.path.join(pixellib, "scripts", script_name) if pixellib else script_name
            if os.path.isfile(script_path):
                with open(script_path, "r") as f:
                    exec(f.read(), {"__name__": "__main__"})
            else:
                raise FileNotFoundError(f"Script not found: {script_path}")
        except Exception as e:
            QMessageBox.warning(self, "Script Error", str(e))

    def create_camera_list(self):
        self.camera_list = QtWidgets.QListWidget()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.camera_list)
        return scroll

    def create_node_tree(self):
        self.node_tree = QtWidgets.QTreeWidget()
        self.node_tree.setHeaderHidden(True)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.node_tree)
        return scroll

    def create_cache_tree(self):
        self.cache_tree = QtWidgets.QTreeWidget()
        self.cache_tree.setHeaderHidden(True)
        self.cache_tree.setIndentation(12)
        self.cache_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.cache_tree.customContextMenuRequested.connect(self.show_cache_context_menu)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.cache_tree)
        return scroll

    def populate_camera_list(self):
        try:
            self.camera_list.clear()
            for cam in self.get_camera_nodes():
                self.camera_list.addItem(cam)
        except Exception as e:
            print("populate_camera_list error:", e)

    def populate_grouped_nodes(self):
        try:
            self.node_tree.clear()
            grouped = self.get_nodes_grouped_by_parent_type()
            for parent_type, nodes in sorted(grouped.items()):
                parent_item = QtWidgets.QTreeWidgetItem([f"{parent_type} ({len(nodes)})"])
                for node in nodes:
                    parent_item.addChild(QtWidgets.QTreeWidgetItem([node]))
                self.node_tree.addTopLevelItem(parent_item)
                parent_item.setExpanded(False)
        except Exception as e:
            print("populate_grouped_nodes error:", e)

    def populate_cache_tree(self):
        try:
            self.cache_tree.clear()
            hip = hou.getenv("HIP") or ""
            cache_root = os.path.join(hip, "Cache")
            if not os.path.exists(cache_root):
                return

            for folder in sorted(os.listdir(cache_root)):
                full_path = os.path.join(cache_root, folder)
                if not os.path.isdir(full_path):
                    continue

                version_folders = [
                    d for d in os.listdir(full_path)
                    if os.path.isdir(os.path.join(full_path, d)) and re.match(r"v\d+", d)
                ]

                total_size = 0
                version_items = []
                if version_folders:
                    for version in sorted(version_folders):
                        version_path = os.path.join(full_path, version)
                        size = self.get_folder_size(version_path)
                        total_size += size
                        version_item = QtWidgets.QTreeWidgetItem([f"{version} - {self.human_readable_size(size)}"])
                        version_item.setData(0, QtCore.Qt.UserRole, version_path.replace("\\", "/"))
                        version_items.append(version_item)
                else:
                    size = self.get_folder_size(full_path)
                    total_size += size

                parent_label = f"{folder} ({self.human_readable_size(total_size)})"
                parent_item = QtWidgets.QTreeWidgetItem([parent_label])
                parent_item.setData(0, QtCore.Qt.UserRole, full_path.replace("\\", "/"))
                for v in version_items:
                    parent_item.addChild(v)
                self.cache_tree.addTopLevelItem(parent_item)
                if len(version_items) >= 2:
                    parent_item.setExpanded(True)
        except Exception as e:
            print("populate_cache_tree error:", e)

    def show_cache_context_menu(self, pos):
        item = self.cache_tree.itemAt(pos)
        if not item:
            return
        full_path = item.data(0, QtCore.Qt.UserRole)
        if full_path is None:
            return
        full_path = hou.expandString(full_path)
        full_path = os.path.normpath(full_path)
        menu = QtWidgets.QMenu()
        menu.addAction("Open Folder", lambda: self.open_folder(full_path))
        menu.addAction("Copy Path", lambda: QtWidgets.QApplication.clipboard().setText(full_path))
        menu.addAction("Delete Cache", lambda: self.delete_cache_folder(full_path))
        menu.addAction("Override with Blank", lambda: self.override_with_blank(full_path))
        menu.exec_(self.cache_tree.viewport().mapToGlobal(pos))

    def delete_cache_folder(self, path):
        try:
            if os.path.exists(path):
                shutil.rmtree(path)
                self.populate_cache_tree()
        except Exception as e:
            print(f"Failed to delete cache folder {path}: {e}")

    def override_with_blank(self, path):
        try:
            if os.path.exists(path):
                for root, dirs, files in os.walk(path):
                    for f in files:
                        open(os.path.join(root, f), 'w').close()
        except Exception as e:
            print(f"Override with blank failed: {e}")

    # ============== FLIPBOOK MENU ==============
    def create_flipbook_page(self):
        self.exr_list = QtWidgets.QListWidget()
        self.exr_list.setViewMode(QtWidgets.QListView.IconMode)
        self.exr_list.setIconSize(QtCore.QSize(160, 90))
        self.exr_list.setGridSize(QtCore.QSize(180, 120))
        self.exr_list.setResizeMode(QtWidgets.QListView.Adjust)
        self.exr_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.exr_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.exr_list.customContextMenuRequested.connect(self.show_flipbook_context)
        self.exr_list.itemDoubleClicked.connect(self.open_in_mplay)

        refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_exr_thumbnails)

        mp4_btn = QtWidgets.QPushButton("🎞️ Open MP4 Folder")
        mp4_btn.clicked.connect(self.open_mp4_folder)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(mp4_btn)
        btn_row.addStretch()

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(btn_row)
        layout.addWidget(self.exr_list)

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        return widget

    def refresh_exr_thumbnails(self):
        self.exr_list.clear()
        self.exr_folders = []
        self.exr_items = {}
        self.exr_index = 0

        flipbook_root = os.path.normpath(hou.expandString("$HIP/Flipbooks"))
        if not os.path.exists(flipbook_root):
            return

        for name in sorted(os.listdir(flipbook_root)):
            folder = os.path.join(flipbook_root, name)
            if not os.path.isdir(folder):
                continue
            exrs = sorted([f for f in os.listdir(folder) if f.lower().endswith(".exr")])
            if not exrs:
                continue

            exr_paths = [os.path.join(folder, f) for f in exrs]
            self.exr_folders.append((name, folder, exr_paths))

            placeholder = QtGui.QPixmap(160, 90)
            placeholder.fill(QtGui.QColor("#2a2a2a"))
            item = QtWidgets.QListWidgetItem(QtGui.QIcon(placeholder), name)
            item.setData(QtCore.Qt.UserRole, exr_paths)
            self.exr_list.addItem(item)
            self.exr_items[folder] = item

        self.thumb_timer = QtCore.QTimer()
        self.thumb_timer.timeout.connect(self.load_next_exr_thumbnail)
        self.thumb_timer.start(60)

    def load_next_exr_thumbnail(self):
        if self.exr_index >= len(self.exr_folders):
            self.thumb_timer.stop()
            return

        name, folder, exr_paths = self.exr_folders[self.exr_index]
        thumb = self.load_exr_thumbnail(exr_paths[0])
        if thumb:
            self.exr_items[folder].setIcon(QtGui.QIcon(thumb))
        self.exr_index += 1

    def load_exr_thumbnail(self, path, size=(160, 90)):
        if not HAS_OIIO:
            return None
        try:
            inp = oiio.ImageInput.open(path)
            if not inp:
                return None
            spec = inp.spec()
            pixels = inp.read_image(format=oiio.FLOAT)
            inp.close()

            if pixels is None:
                return None

            w, h, c = spec.width, spec.height, spec.nchannels
            pixels = (pixels * 255).clip(0, 255).astype(np.uint8)

            if c == 3:
                img = pixels.reshape(h, w, 3)
                fmt = QtGui.QImage.Format_RGB888
            elif c >= 4:
                img = pixels.reshape(h, w, c)[:, :, :4]
                fmt = QtGui.QImage.Format_RGBA8888
            else:
                return None

            qimg = QtGui.QImage(img.data, w, h, w * img.shape[2], fmt)
            return QtGui.QPixmap.fromImage(qimg).scaled(*size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        except Exception as e:
            print(f"Thumbnail load failed for {path}: {e}")
            return None

    def open_in_mplay(self, item):
        exr_sequence = item.data(QtCore.Qt.UserRole)
        if exr_sequence:
            subprocess.Popen(["mplay"] + exr_sequence)

    def open_mp4_folder(self):
        mp4_path = os.path.normpath(os.path.expandvars("$HIP/Flipbooks/mp4"))
        os.makedirs(mp4_path, exist_ok=True)
        try:
            if platform.system() == "Windows":
                os.startfile(mp4_path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", mp4_path])
            else:
                subprocess.run(["xdg-open", mp4_path])
        except Exception as e:
            print(f"Failed to open MP4 folder: {e}")

    def show_flipbook_context(self, pos):
        items = self.exr_list.selectedItems()
        if not items:
            return
        folder = os.path.dirname(items[0].data(QtCore.Qt.UserRole)[0])
        menu = QtWidgets.QMenu()
        menu.addAction("Open Folder", lambda: self.open_folder(folder))
        menu.addAction("Copy Path", lambda: QtWidgets.QApplication.clipboard().setText(folder))
        menu.exec_(self.exr_list.viewport().mapToGlobal(pos))


    # ============== BROWSER PAGE (multi-level dropdown navigator) ==============
    def create_browser_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(8, 0, 80, 8)
        # --- Base Path Row ---
        path_layout = QtWidgets.QHBoxLayout()
        self.base_path_edit = QtWidgets.QLineEdit(self.base_sp_path)
        browse_btn = QtWidgets.QPushButton("Browse")
        browse_btn.clicked.connect(self._browser_browse_base_path)
        path_layout.addWidget(QtWidgets.QLabel("Base Path:"))
        path_layout.addWidget(self.base_path_edit)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)  # Add above dropdowns
        
        # Removed the Browser header QLabel here
        
        # Dropdowns area
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(2)
    
        labels = ["Project Type", "Project", "Shots", "Sequence", "Shot", "Task"]
        self.browser_combos = {}
        for i, lab in enumerate(labels):
            grid.addWidget(QLabel(lab + ":"), i, 0)
            cb = QtWidgets.QComboBox()
            cb.setEditable(False)
            cb.currentIndexChanged.connect(partial(self._browser_combo_changed, i))
            self.browser_combos[i] = cb
            grid.addWidget(cb, i, 1)
    
        layout.addLayout(grid)
    
        # Path display + Set button + Open Folder + Back button
        row = QtWidgets.QHBoxLayout()
        self.browser_path_display = QtWidgets.QLineEdit()
        self.browser_path_display.setReadOnly(True)
        self.browser_path_display.setPlaceholderText("Selected path will appear here")
        row.addWidget(self.browser_path_display)
    
        back_btn = QtWidgets.QPushButton("Back")
        back_btn.clicked.connect(self._browser_go_back)
        row.addWidget(back_btn)
    
        set_btn = QtWidgets.QPushButton("Set")
        set_btn.clicked.connect(self._browser_save_selection)
        row.addWidget(set_btn)
    
        open_btn = QtWidgets.QPushButton("Open Folder")
        open_btn.clicked.connect(self._browser_open_selected)
        row.addWidget(open_btn)
    
        layout.addLayout(row)
    
        # File list area
        self.browser_file_list = QtWidgets.QListWidget()
        self.browser_file_list.itemDoubleClicked.connect(self._browser_file_double_clicked)
        layout.addWidget(self.browser_file_list)
    
        # Populate top-level from BASE_SP_PATH
        self._browser_populate_top()
    
        # Restore previous saved path if any
        saved = self.settings.value("browser/selected_path", "")
        if saved and os.path.isdir(saved):
            QtCore.QTimer.singleShot(100, lambda p=saved: self._browser_restore_from_path(p))
    
        return page

    
        # --- File list area ---
        self.browser_file_list = QtWidgets.QListWidget()
        self.browser_file_list.setAlternatingRowColors(True)
        self.browser_file_list.itemDoubleClicked.connect(self._browser_file_double_clicked)
        layout.addWidget(self.browser_file_list)
    
        # Populate top-level from base path
        self._browser_populate_top()
    
        # Restore previous saved path if any
        saved = self.settings.value("browser/selected_path", "")
        if saved and os.path.isdir(saved):
            QtCore.QTimer.singleShot(100, lambda p=saved: self._browser_restore_from_path(p))
    
        return page

    
    def _browser_browse_base_path(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Base Path", self.base_path_edit.text())
        if folder:
            self.base_path_edit.setText(folder)
            self.base_sp_path = folder
            self.settings.setValue("browser/base_path", folder)  # Save per user
            self._browser_populate_top()  # Refresh dropdowns
        
    def _browser_go_back(self):
        """Navigate one folder level up."""
        current_path = self.browser_path_display.text().strip()
        if not current_path:
            return
        parent_path = os.path.dirname(current_path)
        if os.path.isdir(parent_path):
            self.browser_path_display.setText(parent_path)
            self._browser_populate_files(parent_path)

    def _browser_populate_top(self):
        # Fill Project Type combo with top-level directories under selected base path
        base = self.base_path_edit.text().strip()
        try:
            if os.path.isdir(base):
                items = sorted([d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))])
                cb = self.browser_combos[0]
                cb.clear()
                cb.addItem("")  # empty default
                for it in items:
                    cb.addItem(it)
                # clear downstream combos
                for i in range(1, 6):
                    self.browser_combos[i].clear()
                self.browser_path_display.setText(base)
        except Exception as e:
            print("Browser top populate error:", e)

    def _browser_combo_changed(self, idx, text=None):
        """Triggered when a dropdown changes selection."""
        try:
            # Use the base path from the text field
            base_path = self.base_path_edit.text().strip()
            if not base_path or not os.path.isdir(base_path):
                print("Invalid base path:", base_path)
                return
    
            # Build path up to current combo
            parts = []
            for i in range(0, idx + 1):
                txt = self.browser_combos[i].currentText().strip()
                if txt:
                    parts.append(txt)
                else:
                    break
    
            path = os.path.join(base_path, *parts) if parts else base_path
            path = os.path.normpath(path)
    
            # Populate the next combo if there is one
            next_idx = idx + 1
            if next_idx < len(self.browser_combos):
                cb = self.browser_combos[next_idx]
                cb.clear()
                if os.path.isdir(path):
                    items = sorted(
                        [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
                    )
                    cb.addItem("")  # Blank option
                    cb.addItems(items)
    
            # Determine the deepest non-empty selection
            deepest_parts = []
            for i in range(len(self.browser_combos)):
                t = self.browser_combos[i].currentText().strip()
                if t:
                    deepest_parts.append(t)
                else:
                    break
    
            final_path = os.path.join(base_path, *deepest_parts) if deepest_parts else base_path
            final_path = os.path.normpath(final_path)
    
            # Update path display and file list
            self.browser_path_display.setText(final_path)
            self._browser_populate_files(final_path)
    
        except Exception as e:
            print("browser combo change error:", e)

    def _browser_populate_files(self, path):
        self.browser_file_list.clear()
        try:
            if os.path.isdir(path):
                # show files and directories under path
                entries = sorted(os.listdir(path))
                for e in entries:
                    self.browser_file_list.addItem(e)
        except Exception as e:
            print("browser populate files error:", e)

    def _browser_save_selection(self):
        path = self.browser_path_display.text().strip()
        if not path:
            return
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Invalid Path", "Selected path does not exist.")
            return
        self.settings.setValue("browser/selected_path", path)
        QMessageBox.information(self, "Saved", f"Path saved:\n{path}")

    def _browser_open_selected(self):
        path = self.browser_path_display.text().strip()
        if path and os.path.isdir(path):
            self.open_folder(path)
        else:
            QMessageBox.warning(self, "Not Found", "Selected path not found.")

    def _browser_restore_from_path(self, fullpath):
        try:
            fullpath = os.path.normpath(fullpath)
            base = os.path.normpath(self.base_sp_path)  # <== lowercase here
            if not fullpath.startswith(base):
                return
            rel = os.path.relpath(fullpath, base)
            parts = rel.split(os.sep)
            for i, p in enumerate(parts):
                if i > 5:
                    break
                cb = self.browser_combos[i]
                # ensure combo has values
                if cb.count() == 0:
                    # trigger upstream selection to populate
                    if i == 0:
                        self._browser_populate_top()
                idx = cb.findText(p)
                if idx >= 0:
                    cb.setCurrentIndex(idx)
            # ensure final files list updated
            self.browser_path_display.setText(fullpath)
            self._browser_populate_files(fullpath)
        except Exception as e:
            print("browser restore error:", e)

    def _sanitize_node_name(self, name):
        import re
        name = re.sub(r'\W', '_', name)
        if not re.match(r'^[A-Za-z_]', name):
            name = '_' + name
        return name
    
    def _browser_file_double_clicked(self, item):
        current_dir = self.browser_path_display.text().strip()
        filename = item.text()
    
        full_path = os.path.join(current_dir, filename)
        full_path = os.path.abspath(os.path.normpath(full_path))
    
        if os.path.isdir(full_path):
            self.browser_path_display.setText(full_path)
            self._browser_populate_files(full_path)
            return
    
        ext = os.path.splitext(full_path)[1].lower()
        name_no_ext = os.path.splitext(filename)[0]
        safe_name = self._sanitize_node_name(name_no_ext)
    
        try:
            if ext == ".hip":
                full_path_unix = full_path.replace('\\', '/')
                hou.hipFile.load(full_path_unix)
    
            elif ext == ".abc":
                obj = hou.node("/obj")
                geo_node = obj.createNode("geo", node_name=safe_name, run_init_scripts=False, force_valid_node_name=True)
                alembic_node = geo_node.createNode("alembic", node_name=safe_name)
                alembic_node.parm("fileName").set(full_path.replace('\\', '/'))
                geo_node.layoutChildren()
    
            else:
                obj = hou.node("/obj")
                geo_node = obj.createNode("geo", node_name=safe_name, run_init_scripts=False, force_valid_node_name=True)
                file_node = geo_node.createNode("file", node_name="file1")
                file_node.parm("file").set(full_path.replace('\\', '/'))
                geo_node.layoutChildren()
    
        except Exception as e:
            print(f"Error opening file: {e}")
            hou.ui.displayMessage(f"Error opening file:\n{e}")


    # ============== COMMON UTILITIES ==============
    def open_folder(self, path):
        try:
            if "$HIP" in path or "${HIP}" in path:
                path = hou.expandString(path)
            path = os.path.normpath(path)
            if os.path.exists(path):
                if platform.system() == "Windows":
                    os.startfile(path)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
            else:
                QMessageBox.warning(self, "Folder Not Found", f"The folder '{path}' does not exist.")
        except Exception as e:
            QMessageBox.warning(self, "Open Folder Error", str(e))

    def create_labeled_box(self, title, widget):
        label = QtWidgets.QLabel(title)
        label.setStyleSheet("font-weight: bold; font-size: 13px; padding: 4px;")
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.addWidget(label)
        layout.addWidget(widget)
        box = QtWidgets.QWidget()
        box.setLayout(layout)
        box.setStyleSheet("background-color: #3a3a3a;")
        return box

    def create_blank_page(self, title):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        label = QtWidgets.QLabel(f"{title} Page")
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")
        layout.addWidget(label)
        return page

    def get_camera_nodes(self):
        cameras = []

        def recurse(node):
            try:
                tname = node.type().name().lower()
                # guess camera types contain 'cam'
                if "cam" in tname:
                    cameras.append(node.path())
                for child in node.children():
                    recurse(child)
            except Exception:
                pass

        root = hou.node("/")
        if root:
            recurse(root)
        return cameras

    def get_nodes_grouped_by_parent_type(self):
        grouped = defaultdict(list)

        def recurse(node):
            try:
                parent = node.parent()
                if parent:
                    grouped[parent.type().name()].append(node.path())
                for child in node.children():
                    recurse(child)
            except Exception:
                pass

        root = hou.node("/")
        if root:
            recurse(root)
        return dict(grouped)

    def get_folder_size(self, path):
        total = 0
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.isfile(fp):
                    total += os.path.getsize(fp)
        return total

    def human_readable_size(self, size, decimal_places=1):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.{decimal_places}f} {unit}"
            size /= 1024
        return f"{size:.{decimal_places}f} PB"


   # ========== RENDER PAGE ==========
    def create_render_page(self):
        self.render_table = QtWidgets.QTableWidget()
        self.render_table.setColumnCount(7)
        self.render_table.setHorizontalHeaderLabels([
            "Render Layer", "Frame Range", "Frame Count", "Resolution",
            "Version", "Date & Time", "User"
        ])
        self.render_table.horizontalHeader().setStretchLastSection(True)
        self.render_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.render_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.render_table.verticalHeader().setVisible(False)
        self.render_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.render_table.customContextMenuRequested.connect(self.show_render_context_menu)
        self.render_table.cellDoubleClicked.connect(self.handle_render_double_click)
        QtCore.QTimer.singleShot(300, self.populate_render_table)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.render_table)
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        return widget

    def populate_render_table(self):
        try:
            self.render_table.setRowCount(0)
            hip_dir = hou.getenv("HIP") or ""
            render_dir = os.path.join(hip_dir, "render")
            if not os.path.exists(render_dir):
                return
            version_folders = sorted([f for f in os.listdir(render_dir) if f.lower().startswith('v') and os.path.isdir(os.path.join(render_dir, f))])
            row = 0
            for i, version in enumerate(version_folders):
                version_path = os.path.join(render_dir, version)
                layer_folders = sorted(os.listdir(version_path))
                text_color = QtGui.QColor("#FFFFFF") if i % 2 == 0 else QtGui.QColor("#FFDAB3")
                for layer in layer_folders:
                    layer_path = os.path.join(version_path, layer)
                    if not os.path.isdir(layer_path):
                        continue
                    exr_files = [f for f in os.listdir(layer_path) if os.path.splitext(f)[1].lower() in (".exr", ".jpg", ".jpeg", ".png", ".dpx", ".tif", ".tiff")]
                    if not exr_files:
                        continue
                    exr_files.sort()
                    pattern = re.compile(r"^(.*?)(\d+)\.[^.]+$")
                    matches = [pattern.match(f) for f in exr_files]
                    frame_range = ""
                    if matches and all(matches):
                        start = int(matches[0].group(2))
                        end = int(matches[-1].group(2))
                        frame_range = f"{start}-{end}"
                    else:
                        frame_range = f"1-{len(exr_files)}"
                    resolution = "Unknown"
                    try:
                        if HAS_OIIO:
                            img = oiio.ImageInput.open(os.path.join(layer_path, exr_files[0]))
                            if img:
                                spec = img.spec()
                                resolution = f"{spec.width}x{spec.height}"
                                img.close()
                    except Exception:
                        resolution = "Unknown"
                    modified_time = os.path.getmtime(layer_path)
                    datetime_str = QDateTime.fromSecsSinceEpoch(int(modified_time)).toString("yyyy-MM-dd hh:mm")
                    user = getpass.getuser()
                    frame_count = str(len(exr_files))
                    row_data = [layer, frame_range, frame_count, resolution, version, datetime_str, user]
                    self.render_table.insertRow(row)
                    for col, data in enumerate(row_data):
                        item = QtWidgets.QTableWidgetItem(data)
                        item.setForeground(text_color)
                        item.setData(QtCore.Qt.UserRole, layer_path)
                        if col == 0:
                            item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                        else:
                            item.setTextAlignment(QtCore.Qt.AlignCenter)
                        self.render_table.setItem(row, col, item)
                    row += 1
            min_widths = [140, 140, 90, 140, 90, 140, 140]
            for col, width in enumerate(min_widths):
                self.render_table.setColumnWidth(col, width)
                self.render_table.horizontalHeader().setMinimumSectionSize(50)
        except Exception as e:
            print("populate_render_table error:", e)

    def show_render_context_menu(self, pos):
        index = self.render_table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        item = self.render_table.item(row, 0)
        if not item:
            return
        folder_path = item.data(QtCore.Qt.UserRole)
        if not folder_path or not os.path.exists(folder_path):
            return
        menu = QtWidgets.QMenu()
        menu.addAction("📂 Open Folder", lambda: self.open_folder(folder_path))
        menu.addAction("📋 Copy Path", lambda: QtWidgets.QApplication.clipboard().setText(folder_path))
        menu.addAction("🗑️ Delete", lambda: self.delete_render_folder(row, folder_path))
        menu.exec_(self.render_table.viewport().mapToGlobal(pos))
    def handle_render_double_click(self, row, column):
        import re
    
        layer_item = self.render_table.item(row, 0)
        version_item = self.render_table.item(row, 4)
        if not layer_item or not version_item:
            return
    
        folder = os.path.normpath(os.path.join(
            os.environ.get("HIP", ""), "render", version_item.text(), layer_item.text()))
    
        if not os.path.exists(folder):
            QMessageBox.warning(self, "Not Found", f"Folder not found:\n{folder}")
            return
    
        try:
            # Supported image sequence extensions
            extensions = [".exr", ".jpg", ".jpeg", ".png", ".dpx", ".tif", ".tiff"]
            files = sorted(f for f in os.listdir(folder)
                           if os.path.splitext(f)[1].lower() in extensions)
    
            pattern = re.compile(r"(.*?)(\d+)\.(exr|jpg|jpeg|png|dpx|tif|tiff)$", re.IGNORECASE)
            matches = [pattern.match(f) for f in files if pattern.match(f)]
    
            if matches:
                base, start = matches[0].group(1), int(matches[0].group(2))
                end = int(matches[-1].group(2))
                ext = matches[0].group(3).lower()
                padding = len(matches[0].group(2))
                sequence = os.path.join(folder, f"{base}$F{padding}.{ext}")
                subprocess.Popen(["mplay", "-f", str(start), str(end), "1", sequence])
                return
    
            # If image sequences not found, fallback to mp4
            mp4s = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".mp4")]
            if mp4s:
                if os.name == 'nt':
                    os.startfile(mp4s[0])
                elif sys.platform == 'darwin':
                    subprocess.Popen(["open", mp4s[0]])
                else:
                    subprocess.Popen(["xdg-open", mp4s[0]])
                return
    
            # Final fallback: open the folder
            self.open_folder(folder)
    
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def delete_render_folder(self, row, path):
        confirm = QtWidgets.QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete:\n{path}", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if confirm == QtWidgets.QMessageBox.Yes:
            try:
                shutil.rmtree(path)
                self.render_table.removeRow(row)
            except Exception as e:
                QMessageBox.warning(self, "Delete Failed", str(e))


    # ========== DEADLINE PAGE (with auto-refresh, date range filter, job-info side panel) ==========
    def create_deadline_page(self):
        # Left side: filters + table
        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)

        filter_layout = QtWidgets.QHBoxLayout()
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search jobs (name/user/id)...")
        self.search_bar.textChanged.connect(self.apply_deadline_filter)
        filter_layout.addWidget(self.search_bar)

        # User filter
        self.user_filter = QtWidgets.QComboBox()
        self.user_filter.setEditable(True)
        self.user_filter.setMinimumWidth(140)
        self.user_filter.addItem(getpass.getuser())
        self.user_filter.setCurrentText(getpass.getuser())
        filter_layout.addWidget(QLabel("User:"))
        filter_layout.addWidget(self.user_filter)

        # Date range
        self.date_start = QtWidgets.QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addDays(-7))
        self.date_end = QtWidgets.QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        self.date_start.dateChanged.connect(self.apply_deadline_filter)
        self.date_end.dateChanged.connect(self.apply_deadline_filter)
        filter_layout.addWidget(QLabel("From:"))
        filter_layout.addWidget(self.date_start)
        filter_layout.addWidget(QLabel("To:"))
        filter_layout.addWidget(self.date_end)

        # Auto-refresh
        self.auto_refresh_chk = QtWidgets.QCheckBox("Auto-refresh")
        self.auto_refresh_chk.setToolTip("Automatically refresh deadline jobs every interval")
        self.auto_refresh_chk.stateChanged.connect(self._toggle_deadline_autorefresh)
        filter_layout.addWidget(self.auto_refresh_chk)

        # refresh interval spinbox
        self.auto_interval = QtWidgets.QSpinBox()
        self.auto_interval.setMinimum(5)
        self.auto_interval.setMaximum(3600)
        self.auto_interval.setValue(20)
        self.auto_interval.setSuffix(" s")
        self.auto_interval.setToolTip("Auto-refresh interval (seconds)")
        filter_layout.addWidget(self.auto_interval)

        refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_deadline_jobs)
        filter_layout.addWidget(refresh_btn)

        left_layout.addLayout(filter_layout)

        # Deadline table
        self.deadline_table = QtWidgets.QTableWidget()
        self.deadline_table.setColumnCount(14)
        self.deadline_table.setHorizontalHeaderLabels([
            "Job Name", "User", "Progress", "Status", "Frames", "Pool",
            "Priority", "Submitted", "Started", "Completed",
            "Output Directory", "Output File", "Submitted From", "Job ID"
        ])
        self.deadline_table.setSortingEnabled(True)
        self.deadline_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.deadline_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.deadline_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.deadline_table.customContextMenuRequested.connect(self.show_deadline_context_menu)
        self.deadline_table.itemSelectionChanged.connect(self._deadline_row_selected)

        left_layout.addWidget(self.deadline_table)

        # action buttons row
        actions_row = QtWidgets.QHBoxLayout()
        self.suspend_btn = QtWidgets.QPushButton("🛑 Suspend")
        self.resume_btn = QtWidgets.QPushButton("▶️ Resume")
        self.delete_btn = QtWidgets.QPushButton("❌ Delete")
        self.suspend_btn.clicked.connect(self.suspend_selected_jobs)
        self.resume_btn.clicked.connect(self.resume_selected_jobs)
        self.delete_btn.clicked.connect(self.delete_selected_jobs)
        actions_row.addWidget(self.suspend_btn)
        actions_row.addWidget(self.resume_btn)
        actions_row.addWidget(self.delete_btn)
        actions_row.addStretch()
        left_layout.addLayout(actions_row)

        # Right side: job info panel
        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        info_label = QLabel("Job Info")
        info_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 6px;")
        right_layout.addWidget(info_label)

        self.job_info_table = QtWidgets.QTableWidget()
        self.job_info_table.setColumnCount(2)
        self.job_info_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.job_info_table.horizontalHeader().setStretchLastSection(True)
        self.job_info_table.verticalHeader().setVisible(False)
        right_layout.addWidget(self.job_info_table)

        # Layout: left + right
        main = QtWidgets.QHBoxLayout()
        main.addWidget(left, 3)
        main.addWidget(right, 1)

        page = QtWidgets.QWidget()
        page.setLayout(main)

        # autorefresh timer
        self._deadline_timer = QtCore.QTimer()
        self._deadline_timer.timeout.connect(self.load_deadline_jobs)

        return page

    def _toggle_deadline_autorefresh(self, state):
        if state == QtCore.Qt.Checked:
            interval_sec = max(5, int(self.auto_interval.value()))
            self._deadline_timer.start(interval_sec * 1000)
        else:
            self._deadline_timer.stop()

    def load_deadline_jobs(self):
        # preserve filter text
        self.saved_filter_text = self.search_bar.text()
        self.search_bar.blockSignals(True)
        self.search_bar.clear()
        # clear table & jobs
        self.deadline_table.setRowCount(0)
        self.jobs = []
        # prepare deadline command
        deadline_bin_dir = os.getenv("DEADLINE_PATH", r"C:\Program Files\Thinkbox\Deadline10\bin")
        self.deadline_cmd = os.path.join(deadline_bin_dir, "deadlinecommand")
        if platform.system() == "Windows" and not self.deadline_cmd.lower().endswith(".exe"):
            if os.path.isfile(self.deadline_cmd + ".exe"):
                self.deadline_cmd += ".exe"
        user = self.user_filter.currentText().strip() or getpass.getuser()
        # start loader thread
        self.loader_thread = DeadlineJobLoader(self.deadline_cmd, user)
        self.loader_thread.job_loaded.connect(self._store_loaded_job_and_add)
        self.loader_thread.finished_loading.connect(self._deadline_loader_finished)
        self.loader_thread.start()

    def _store_loaded_job_and_add(self, job):
        # store job
        if not hasattr(self, "jobs"):
            self.jobs = []
        # normalize a few keys
        jobid = job.get("JobId") or job.get("Id") or job.get("ID") or ""
        job["__parsed_jobid"] = jobid
        # parse submit time into QDate for filtering convenience
        qdate = self._parse_job_submit_date(job.get("JobSubmitDateTime", "") or job.get("JobSubmitDate", ""))
        job["__submit_qdate"] = qdate
        self.jobs.append(job)
        # add immediately (we'll filter later)
        # but only add if it matches current filters
        # (apply_deadline_filter will rebuild entire table incrementally)
        # simply re-apply filter
        self.apply_deadline_filter()

    def _deadline_loader_finished(self):
        self.search_bar.blockSignals(False)
        try:
            self.search_bar.setText(self.saved_filter_text)
        except Exception:
            pass
        self.apply_deadline_filter()

    def _parse_job_submit_date(self, val):
        # Try a few formats: epoch seconds (digits), common ISO, or human readable
        try:
            if not val:
                return None
            if str(val).isdigit():
                dt = QDateTime.fromSecsSinceEpoch(int(val))
                return dt.date()
            # Try ISO formats
            for fmt in ("yyyy-MM-dd hh:mm:ss", "yyyy-MM-ddThh:mm:ss", "yyyy-MM-dd hh:mm", "yyyy-MM-dd"):
                dt = QDateTime.fromString(val, fmt)
                if dt.isValid():
                    return dt.date()
            # try fallback parsing numeric inside string
            m = re.search(r"(\d{4}-\d{2}-\d{2})", val)
            if m:
                dt = QDateTime.fromString(m.group(1), "yyyy-MM-dd")
                if dt.isValid():
                    return dt.date()
        except Exception:
            pass
        return None

    def add_deadline_job_row(self, job):
        row = self.deadline_table.rowCount()
        self.deadline_table.insertRow(row)
        name = job.get("Name", "Unknown")
        user = job.get("UserName", "") or job.get("User", "")
        status = job.get("Status", "")
        pool = job.get("Pool", "")
        priority = str(job.get("Priority", ""))
        job_id = job.get("__parsed_jobid", "UNKNOWN")
        # frames parsing
        raw_frames = job.get("Frames", "")
        frame_numbers = set()
        if isinstance(raw_frames, str):
            parts = re.split(r"[,\s]+", raw_frames.strip())
            for p in parts:
                if "-" in p:
                    try:
                        a, b = p.split("-", 1)
                        a_i, b_i = int(a), int(b)
                        frame_numbers.update(range(a_i, b_i + 1))
                    except Exception:
                        pass
                elif p.isdigit():
                    frame_numbers.add(int(p))
        frame_list = sorted(frame_numbers)
        frame_range = f"{frame_list[0]}-{frame_list[-1]}" if frame_list else ""
        # times
        submit_time = job.get("JobSubmitDateTime", "")
        started_time = job.get("JobStartedDateTime", "")
        completed_time = job.get("JobCompletedDateTime", "")
        # outputs
        output_dirs = job.get("JobOutputDirectories", "")
        output_files = job.get("JobOutputFileNames", "")
        submit_machine = job.get("JobSubmitMachine", "")
        output_dir = output_dirs[0] if isinstance(output_dirs, list) and output_dirs else (output_dirs or "")
        output_file = output_files[0] if isinstance(output_files, list) and output_files else (output_files or "")
        # progress
        try:
            completed = int(job.get("JobCompletedTasks", 0))
            total = int(job.get("JobTaskCount", 1))
            progress = int((completed / total) * 100) if total > 0 else 0
        except Exception:
            progress = 0
        columns = [
            name, user, None, status, frame_range, pool,
            priority, submit_time, started_time, completed_time,
            output_dir, output_file, submit_machine, job_id
        ]
        for i, value in enumerate(columns):
            if i == 2:
                progress_bar = QtWidgets.QProgressBar()
                progress_bar.setValue(progress)
                progress_bar.setAlignment(QtCore.Qt.AlignCenter)
                progress_bar.setFormat(f"{progress}%")
                progress_bar.setFixedHeight(16)
                self.deadline_table.setCellWidget(row, i, progress_bar)
            else:
                item = QtWidgets.QTableWidgetItem(value or "")
                if i == 0:
                    item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                else:
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setData(QtCore.Qt.UserRole, job_id)
                self.deadline_table.setItem(row, i, item)

    def apply_deadline_filter(self):
        # Rebuild table from self.jobs applying search, user, and date filters
        filter_text = self.search_bar.text().lower().strip()
        user_filter_text = (self.user_filter.currentText() or "").lower().strip()
        date_from = self.date_start.date()
        date_to = self.date_end.date()
        self.deadline_table.setRowCount(0)
        for job in getattr(self, "jobs", []):
            name = (job.get("Name", "") or "").lower()
            user = (job.get("UserName", "") or job.get("User", "") or "").lower()
            jobid = (job.get("__parsed_jobid", "") or "").lower()
            # date filtering: if job has __submit_qdate, filter by range; else accept
            submit_qdate = job.get("__submit_qdate", None)
            date_ok = True
            if submit_qdate and isinstance(submit_qdate, QDate):
                date_ok = (submit_qdate >= date_from) and (submit_qdate <= date_to)
            # user filter if set
            user_ok = True
            if user_filter_text:
                user_ok = user_filter_text in user
            # text filter
            text_ok = False
            if not filter_text:
                text_ok = True
            else:
                if filter_text in name or filter_text in user or filter_text in jobid:
                    text_ok = True
            if date_ok and user_ok and text_ok:
                self.add_deadline_job_row(job)

    def get_selected_job_ids(self):
        selected = self.deadline_table.selectionModel().selectedRows()
        job_ids = set()
        for row in selected:
            for col in range(self.deadline_table.columnCount()):
                item = self.deadline_table.item(row.row(), col)
                if item and item.data(QtCore.Qt.UserRole):
                    job_ids.add(item.data(QtCore.Qt.UserRole))
                    break
        return list(job_ids)

    def show_deadline_context_menu(self, pos):
        index = self.deadline_table.indexAt(pos)
        if not index.isValid():
            return
        self.deadline_table.selectRow(index.row())
        job_id = None
        for col in range(self.deadline_table.columnCount()):
            item = self.deadline_table.item(index.row(), col)
            if item and item.data(QtCore.Qt.UserRole):
                job_id = item.data(QtCore.Qt.UserRole)
                break
        if not job_id:
            return
        menu = QtWidgets.QMenu()
        menu.addAction("🛑 Suspend", self.suspend_selected_jobs)
        menu.addAction("▶️ Resume", self.resume_selected_jobs)
        menu.addAction("❌ Delete", self.delete_selected_jobs)
        menu.addSeparator()
        menu.addAction("🛈 View Job Info", lambda jid=job_id: self.fetch_and_show_job_info(jid))
        menu.exec_(self.deadline_table.viewport().mapToGlobal(pos))

    def _deadline_row_selected(self):
        # when user selects a row, auto-load job info for convenience
        sels = self.deadline_table.selectionModel().selectedRows()
        if not sels:
            return
        row = sels[0].row()
        job_id = None
        for col in range(self.deadline_table.columnCount()):
            item = self.deadline_table.item(row, col)
            if item and item.data(QtCore.Qt.UserRole):
                job_id = item.data(QtCore.Qt.UserRole)
                break
        if job_id:
            # fetch job info asynchronously to avoid blocking UI
            QtCore.QTimer.singleShot(10, lambda jid=job_id: self.fetch_and_show_job_info(jid))

    def fetch_and_show_job_info(self, job_id):
        try:
            if not hasattr(self, "deadline_cmd") or not self.deadline_cmd:
                deadline_bin_dir = os.getenv("DEADLINE_PATH", r"C:\Program Files\Thinkbox\Deadline10\bin")
                self.deadline_cmd = os.path.join(deadline_bin_dir, "deadlinecommand")
                if platform.system() == "Windows" and os.path.isfile(self.deadline_cmd + ".exe"):
                    self.deadline_cmd += ".exe"
            result = subprocess.run([self.deadline_cmd, "GetJob", job_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out = result.stdout.strip()
            if not out:
                out = result.stderr.strip()
            parsed = {}
            for line in out.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    parsed[k.strip()] = v.strip()
            # show in job_info_table
            self.job_info_table.setRowCount(0)
            for i, (k, v) in enumerate(sorted(parsed.items())):
                self.job_info_table.insertRow(i)
                k_item = QtWidgets.QTableWidgetItem(k)
                k_item.setFlags(k_item.flags() ^ QtCore.Qt.ItemIsEditable)
                v_item = QtWidgets.QTableWidgetItem(v)
                v_item.setFlags(v_item.flags() ^ QtCore.Qt.ItemIsEditable)
                self.job_info_table.setItem(i, 0, k_item)
                self.job_info_table.setItem(i, 1, v_item)
        except Exception as e:
            print("fetch job info error:", e)

    def suspend_selected_jobs(self):
        for job_id in self.get_selected_job_ids():
            self.run_deadline_command("SuspendJob", job_id)
        QtCore.QTimer.singleShot(200, self.load_deadline_jobs)

    def resume_selected_jobs(self):
        for job_id in self.get_selected_job_ids():
            self.run_deadline_command("ResumeJob", job_id)
        QtCore.QTimer.singleShot(200, self.load_deadline_jobs)

    def delete_selected_jobs(self):
        for job_id in self.get_selected_job_ids():
            self.run_deadline_command("DeleteJob", job_id)
        QtCore.QTimer.singleShot(200, self.load_deadline_jobs)

    def run_deadline_command(self, command, job_id):
        try:
            result = subprocess.run([self.deadline_cmd, command, job_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                print(f"{command} failed for job {job_id}: {result.stderr.strip()}")
            else:
                print(f"{command} succeeded for job {job_id}")
        except Exception as e:
            print(f"Error running {command} for job {job_id}: {e}")

    # ========== REFRESH ==========
    def refresh_everything(self):
        self.populate_camera_list()
        self.populate_grouped_nodes()
        self.populate_cache_tree()
        self.refresh_exr_thumbnails()
        try:
            self.load_deadline_jobs()
        except Exception:
            pass

# ========== LAUNCH ==========
try:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    win = HoudiniManager()
    win.show()
except Exception as e:
    print("Error launching Houdini Manager:", e)


