import os, sys, re, subprocess
from functools import partial
import hou
from PySide2 import QtWidgets, QtCore
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QLabel, QMessageBox, QStyle

class BrowserTool(QtWidgets.QWidget):
    MAX_RECENT = 10

    def __init__(self, parent=None):
        super(BrowserTool, self).__init__(parent)
        self.settings = QtCore.QSettings("YourStudio", "HoudiniBrowser")
        self.base_sp_path = self.settings.value("browser/base_path", "")
        self.browser_combos = {}

        recent_files = self.settings.value("browser/recent_files", [])
        if isinstance(recent_files, str):
            self.recent_files = [recent_files]
        elif isinstance(recent_files, list):
            self.recent_files = recent_files
        else:
            self.recent_files = []

    def create_browser_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
    
        # --- Base Path Row ---
        path_layout = QtWidgets.QHBoxLayout()
        self.base_path_edit = QtWidgets.QLineEdit(self.base_sp_path)
        browse_btn = QtWidgets.QPushButton("Browse")
        browse_btn.setAutoDefault(False)
        browse_btn.setDefault(False)
        browse_btn.clicked.connect(self._browser_browse_base_path)
        path_layout.addWidget(QLabel("Base Path:"))
        path_layout.addWidget(self.base_path_edit)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
    
        # --- Dropdowns ---
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(1)
        labels = ["Project Type", "Project", "Shots", "Sequence", "Shot", "Task"]
        for i, lab in enumerate(labels):
            grid.addWidget(QLabel(lab + ":"), i, 0)
            cb = QtWidgets.QComboBox()
            cb.setEditable(False)
            cb.currentIndexChanged.connect(partial(self._browser_combo_changed, i))
            self.browser_combos[i] = cb
            grid.addWidget(cb, i, 1)
        layout.addLayout(grid)
    
        # --- Path display and buttons ---
        row = QtWidgets.QHBoxLayout()
    
        # Editable so user can paste or type a path
        self.browser_path_display = QtWidgets.QLineEdit()
        self.browser_path_display.setPlaceholderText("Type or paste a folder/file path and press Enter")
        self.browser_path_display.returnPressed.connect(self._browser_path_entered)
        row.addWidget(self.browser_path_display)
    
        back_btn = QtWidgets.QPushButton("Back")
        back_btn.setAutoDefault(False)
        back_btn.setDefault(False)
        back_btn.clicked.connect(self._browser_go_back)
        row.addWidget(back_btn)
    
        set_btn = QtWidgets.QPushButton("Set")
        set_btn.setAutoDefault(False)
        set_btn.setDefault(False)
        set_btn.clicked.connect(self._browser_save_selection)
        row.addWidget(set_btn)
    
        open_btn = QtWidgets.QPushButton("Open Folder")
        open_btn.setAutoDefault(False)   # prevent Enter key from triggering this
        open_btn.setDefault(False)
        open_btn.clicked.connect(self._browser_open_selected)
        row.addWidget(open_btn)
    
        layout.addLayout(row)
    
        # --- File list ---
        self.browser_file_list = QtWidgets.QListWidget()
        self.browser_file_list.setAlternatingRowColors(True)
        self.browser_file_list.itemDoubleClicked.connect(self._browser_file_double_clicked)
        layout.addWidget(QLabel("Files:"))
        layout.addWidget(self.browser_file_list)
    
        # --- Recent files list ---
        self.recent_file_list = QtWidgets.QListWidget()
        self.recent_file_list.setAlternatingRowColors(True)
        self.recent_file_list.itemDoubleClicked.connect(self._recent_file_double_clicked)
        layout.addWidget(QLabel("Recent Files:"))
        layout.addWidget(self.recent_file_list)
    
        # Populate UI
        self._browser_populate_top()
        self._populate_recent_files()
    
        # Restore last selected path
        saved = self.settings.value("browser/selected_path", "")
        if saved and os.path.isdir(saved):
            QtCore.QTimer.singleShot(100, lambda p=saved: self._browser_restore_from_path(p))
    
        return page

    def _browser_browse_base_path(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Base Path", self.base_path_edit.text())
        if folder:
            self.base_path_edit.setText(folder)
            self.base_sp_path = folder
            self.settings.setValue("browser/base_path", folder)
            self.settings.sync()
            self._browser_populate_top()

    def _browser_go_back(self):
        current_path = self.browser_path_display.text().strip()
        if not current_path:
            return
        parent_path = os.path.dirname(current_path)
        if os.path.isdir(parent_path):
            self.browser_path_display.setText(parent_path)
            self._browser_populate_files(parent_path)

    def _browser_populate_top(self):
        base = self.base_path_edit.text().strip()
        try:
            if os.path.isdir(base):
                items = sorted([d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))])
                cb = self.browser_combos[0]
                cb.clear()
                cb.addItem("")
                for it in items:
                    cb.addItem(it)
                for i in range(1, 6):
                    self.browser_combos[i].clear()
                self.browser_path_display.setText(base)
        except Exception as e:
            print("Browser top populate error:", e)

    def _browser_combo_changed(self, idx, text=None):
        try:
            base_path = self.base_path_edit.text().strip()
            if not base_path or not os.path.isdir(base_path):
                return

            parts = []
            for i in range(0, idx + 1):
                txt = self.browser_combos[i].currentText().strip()
                if txt:
                    parts.append(txt)
                else:
                    break

            path = os.path.join(base_path, *parts) if parts else base_path
            path = os.path.normpath(path)

            next_idx = idx + 1
            if next_idx < len(self.browser_combos):
                cb = self.browser_combos[next_idx]
                cb.clear()
                if os.path.isdir(path):
                    items = sorted([d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))])
                    cb.addItem("")
                    cb.addItems(items)

            deepest_parts = []
            for i in range(len(self.browser_combos)):
                t = self.browser_combos[i].currentText().strip()
                if t:
                    deepest_parts.append(t)
                else:
                    break

            final_path = os.path.join(base_path, *deepest_parts) if deepest_parts else base_path
            final_path = os.path.normpath(final_path)
            self.browser_path_display.setText(final_path)
            self._browser_populate_files(final_path)

        except Exception as e:
            print("browser combo change error:", e)

    def _browser_populate_files(self, path):
        self.browser_file_list.clear()
        try:
            style = QtWidgets.QApplication.style()
            if os.path.isdir(path):
                entries = sorted(os.listdir(path))
                for e in entries:
                    full_path = os.path.join(path, e)
                    item = QtWidgets.QListWidgetItem(e)
                    if os.path.isdir(full_path):
                        item.setIcon(style.standardIcon(QStyle.SP_DirIcon))
                    else:
                        item.setIcon(style.standardIcon(QStyle.SP_FileIcon))
                    self.browser_file_list.addItem(item)
        except Exception as e:
            print("browser populate files error:", e)

    def _browser_path_entered(self):
        path = self.browser_path_display.text().strip()
        if os.path.isdir(path):
            self._browser_populate_files(path)
        elif os.path.isfile(path):
            fake_item = QtWidgets.QListWidgetItem(os.path.basename(path))
            self.browser_path_display.setText(os.path.dirname(path))
            self._browser_file_double_clicked(fake_item)
        else:
            QMessageBox.warning(self, "Invalid Path", "The entered path does not exist.")

    def _browser_save_selection(self):
        path = self.browser_path_display.text().strip()
        if not path:
            return
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Invalid Path", "Selected path does not exist.")
            return
        self.settings.setValue("browser/selected_path", path)
        self.settings.sync()
        QMessageBox.information(self, "Saved", f"Path saved:\n{path}")

    def _browser_open_selected(self):
        path = self.browser_path_display.text().strip()
        if path and os.path.isdir(path):
            if os.name == 'nt':
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        else:
            QMessageBox.warning(self, "Not Found", "Selected path not found.")

    def _browser_restore_from_path(self, fullpath):
        try:
            fullpath = os.path.normpath(fullpath)
            base = os.path.normpath(self.base_sp_path)
            if not fullpath.startswith(base):
                return
            rel = os.path.relpath(fullpath, base)
            parts = rel.split(os.sep)
            for i, p in enumerate(parts):
                if i > 5:
                    break
                cb = self.browser_combos[i]
                if cb.count() == 0 and i == 0:
                    self._browser_populate_top()
                idx = cb.findText(p)
                if idx >= 0:
                    cb.setCurrentIndex(idx)
            self.browser_path_display.setText(fullpath)
            self._browser_populate_files(fullpath)
        except Exception as e:
            print("browser restore error:", e)

    def _sanitize_node_name(self, name):
        name = re.sub(r'\W', '_', name)
        if not re.match(r'^[A-Za-z_]', name):
            name = '_' + name
        return name

    def _browser_file_double_clicked(self, item):
        current_dir = self.browser_path_display.text().strip()
        filename = item.text()
        full_path = os.path.abspath(os.path.join(current_dir, filename))

        if os.path.isdir(full_path):
            self.browser_path_display.setText(full_path)
            self._browser_populate_files(full_path)
            return

        ext = os.path.splitext(full_path)[1].lower()
        name_no_ext = os.path.splitext(filename)[0]
        safe_name = self._sanitize_node_name(name_no_ext)

        try:
            if ext == ".hip":
                hou.hipFile.load(full_path.replace('\\', '/'))
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

            self._add_to_recent(full_path)

        except Exception as e:
            print(f"Error opening file: {e}")
            try:
                hou.ui.displayMessage(f"Error opening file:\n{e}")
            except:
                pass

    def _add_to_recent(self, filepath):
        filepath = os.path.normpath(filepath)
        if filepath in self.recent_files:
            self.recent_files.remove(filepath)
        self.recent_files.insert(0, filepath)
        if len(self.recent_files) > self.MAX_RECENT:
            self.recent_files = self.recent_files[:self.MAX_RECENT]
        self.settings.setValue("browser/recent_files", self.recent_files)
        self.settings.sync()
        self._populate_recent_files()

    def _populate_recent_files(self):
        self.recent_file_list.clear()
        for f in self.recent_files:
            if os.path.exists(f) and f.lower().endswith(".hip"):
                self.recent_file_list.addItem(f)

    def _recent_file_double_clicked(self, item):
        full_path = item.text()
        if os.path.exists(full_path):
            ext = os.path.splitext(full_path)[1].lower()
            name_no_ext = os.path.splitext(os.path.basename(full_path))[0]
            safe_name = self._sanitize_node_name(name_no_ext)
            try:
                if ext == ".hip":
                    hou.hipFile.load(full_path.replace('\\', '/'))
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

                self.browser_path_display.setText(os.path.dirname(full_path))
                self._browser_populate_files(os.path.dirname(full_path))
                self._add_to_recent(full_path)

            except Exception as e:
                print(f"Error opening recent file: {e}")
                try:
                    hou.ui.displayMessage(f"Error opening file:\n{e}")
                except:
                    pass
        else:
            QMessageBox.warning(self, "File Not Found", "The recent file no longer exists.")
            if full_path in self.recent_files:
                self.recent_files.remove(full_path)
                self.settings.setValue("browser/recent_files", self.recent_files)
                self.settings.sync()
            self._populate_recent_files()

# ==== Show the browser in Houdini ====
def show_browser_tool():
    try:
        if hasattr(hou.session, "browser_tool_ui"):
            old_win = hou.session.browser_tool_ui
            if old_win is not None:
                if old_win.isVisible():
                    old_win.raise_()
                    old_win.activateWindow()
                    return
                else:
                    hou.session.browser_tool_ui = None

        main_window = hou.ui.mainQtWindow()
        tool = BrowserTool()
        win = QtWidgets.QDialog(parent=main_window)
        win.setWindowTitle("Houdini Browser Tool")
        win.setLayout(QtWidgets.QVBoxLayout())
        win.layout().addWidget(tool.create_browser_page())
        win.resize(750, 450)
        win.show()
        hou.session.browser_tool_ui = win
    except Exception as e:
        print("Failed to open browser tool:", e)

# Run it
show_browser_tool()
