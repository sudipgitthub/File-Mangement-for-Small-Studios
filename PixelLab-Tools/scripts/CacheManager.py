import os
import re
import shutil
import hou
from PySide2 import QtWidgets, QtCore

# ---------------------------------------------------
# Cache Browser Widget
# ---------------------------------------------------
class CacheBrowser(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(CacheBrowser, self).__init__(parent)
        self.setWindowTitle("Cache Browser")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)  # Floating window
        self.resize(500, 400)

        # --- Main Layout ---
        main_layout = QtWidgets.QVBoxLayout(self)

        # --- Cache Tree ---
        self.cache_tree = QtWidgets.QTreeWidget()
        self.cache_tree.setHeaderLabels(["Cache Files"])
        self.cache_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.cache_tree.customContextMenuRequested.connect(self.show_cache_context_menu)
        main_layout.addWidget(self.cache_tree)

        # --- Refresh Button ---
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch(1)
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.populate_cache_tree)
        btn_layout.addWidget(refresh_btn)
        main_layout.addLayout(btn_layout)

        # --- Populate Initial Data ---
        self.populate_cache_tree()
        self.center_on_parent()

    # ---------------------------------------------------
    # Center on Houdini main window
    # ---------------------------------------------------
    def center_on_parent(self):
        if self.parent():
            parent_geom = self.parent().geometry()
            x = parent_geom.x() + (parent_geom.width() - self.width()) // 2
            y = parent_geom.y() + (parent_geom.height() - self.height()) // 2
            self.move(x, y)

    # ---------------------------------------------------
    # Populate Tree
    # ---------------------------------------------------
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
                        version_item = QtWidgets.QTreeWidgetItem(
                            [f"{version} - {self.human_readable_size(size)}"]
                        )
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

                # --- Auto expand if more than 1 version ---
                if len(version_items) >= 2:
                    QtCore.QTimer.singleShot(0, lambda item=parent_item: item.setExpanded(True))

        except Exception as e:
            print("populate_cache_tree error:", e)

    # ---------------------------------------------------
    # Context Menu
    # ---------------------------------------------------
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

    # ---------------------------------------------------
    # Actions
    # ---------------------------------------------------
    def open_folder(self, path):
        try:
            import subprocess
            if os.path.exists(path):
                subprocess.Popen(f'explorer "{path}"')
        except Exception as e:
            print(f"Open folder failed: {e}")

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

    # ---------------------------------------------------
    # Utils
    # ---------------------------------------------------
    def get_folder_size(self, path):
        total = 0
        for root, dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except:
                    pass
        return total

    def human_readable_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"


# ---------------------------------------------------
# Show in Houdini
# ---------------------------------------------------
_cache_browser_window = None

def show_cache_browser():
    """Show the cache browser as a floating window in Houdini."""
    global _cache_browser_window
    try:
        if _cache_browser_window is None or not _cache_browser_window.isVisible():
            _cache_browser_window = CacheBrowser(parent=hou.ui.mainQtWindow())
        _cache_browser_window.show()
        _cache_browser_window.raise_()
    except Exception as e:
        print(f"Error showing cache browser: {e}")


# Run
show_cache_browser()
