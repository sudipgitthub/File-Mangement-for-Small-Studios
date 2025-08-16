import os, sys, re, subprocess
from functools import partial
import hou
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QLabel, QMessageBox, QStyle

PIXELLAB_PATH = os.environ.get("PIXELLAB", "")
HIP_ICON_PATH = os.path.join(PIXELLAB_PATH, "icons", "hipicon.png")

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
    
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(2)  # Optional: adjust graphic spacing
        
        labels = ["Project Type", "Project", "Shots", "Sequence", "Shot No", "Task"]
        combos = {}
        
        # Define each label/combo position in the grid
        positions = {
            0: (0, 0),  # Project Type
            1: (0, 1),  # Project
            2: (1, 0),  # Shots
            3: (1, 1),  # Sequence
            4: (2, 0),  # Shot No
            5: (2, 1),  # Task
        }
        
        for idx, label in enumerate(labels):
            row, col = positions[idx]
            grid.addWidget(QLabel(f"{label}:"), row, col * 2)
            cb = QtWidgets.QComboBox()
            cb.setEditable(False)
            cb.currentIndexChanged.connect(partial(self._browser_combo_changed, idx))
            combos[idx] = cb
            grid.addWidget(cb, row, col * 2 + 1)
        
        self.browser_combos = combos
        layout.addLayout(grid)

    
        # --- Path display and buttons ---
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)   # remove padding
        row.setSpacing(2) 
    
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
            
        # --- File list and Recent files side by side ---
        file_layout = QtWidgets.QHBoxLayout()
        
        file_column = QtWidgets.QVBoxLayout()
        file_column.addWidget(QLabel("Files:"))
        self.browser_file_list = QtWidgets.QListWidget()
        self.browser_file_list.setAlternatingRowColors(True)
        self.browser_file_list.itemDoubleClicked.connect(self._browser_file_double_clicked)
        file_column.addWidget(self.browser_file_list)
        
        recent_column = QtWidgets.QVBoxLayout()
        recent_column.addWidget(QLabel("Recent Files:"))
        self.recent_file_list = QtWidgets.QListWidget()
        self.recent_file_list.setAlternatingRowColors(True)
        self.browser_file_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.recent_file_list.itemDoubleClicked.connect(self._recent_file_double_clicked)
        self.browser_file_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.browser_file_list.customContextMenuRequested.connect(self._show_file_context_menu)

        recent_column.addWidget(self.recent_file_list)
        
        file_layout.addLayout(file_column, stretch=1)
        file_layout.addLayout(recent_column, stretch=1)
        
        layout.addLayout(file_layout)

    
        # Populate UI
        self._browser_populate_top()
        self._populate_recent_files()
    
        # Restore last selected path
        saved = self.settings.value("browser/selected_path", "")
        if saved and os.path.isdir(saved):
            QtCore.QTimer.singleShot(100, lambda p=saved: self._browser_restore_from_path(p))
    
        return page
    
    def _show_file_context_menu(self, position):
        selected_items = self.browser_file_list.selectedItems()
        if not selected_items:
            return
    
        menu = QtWidgets.QMenu()
        open_action = menu.addAction("Open")
        import_action = menu.addAction("Import")
        import_camera_action = menu.addAction("Import Camera")
        delete_action = menu.addAction("Delete")
    
        action = menu.exec_(self.browser_file_list.viewport().mapToGlobal(position))
    
        if not action:
            return
    
        current_dir = self.browser_path_display.text().strip()
        files = [os.path.join(current_dir, item.text()) for item in selected_items]
    
        if action == open_action:
            # Only open if exactly one file selected, and it's .hip
            if len(files) == 1:
                self._open_hip_file(files[0])
            else:
                QMessageBox.information(self, "Open File", "Please select exactly one .hip file to open.")
        elif action == import_action:
            self._import_files(files)
        elif action == import_camera_action:
            # For import camera, we expect multiple .abc files, filter only those
            abc_files = [f for f in files if f.lower().endswith(".abc")]
            if abc_files:
                self._import_cameras(abc_files)
            else:
                QMessageBox.information(self, "Import Camera", "No .abc files selected for importing as camera.")

        elif action == delete_action:
            self._delete_files(files)

    def _open_hip_file(self, path):
        if os.path.isfile(path) and path.lower().endswith(".hip"):
            try:
                hou.hipFile.load(path.replace('\\', '/'))
                self._add_to_recent(path)
            except Exception as e:
                print("Error loading hip file:", e)
                hou.ui.displayMessage(f"Error loading file:\n{e}")
        else:
            QMessageBox.warning(self, "Invalid File", "Only .hip files can be opened.")
            
    def _import_files(self, file_list):
        obj = hou.node("/obj")
        for path in file_list:
            if not os.path.isfile(path):
                continue
    
            filename = os.path.basename(path)
            name_no_ext = os.path.splitext(filename)[0]
            ext = os.path.splitext(filename)[1].lower()
            safe_name = self._sanitize_node_name(name_no_ext)
    
            try:
                geo_node = obj.createNode("geo", node_name=safe_name, run_init_scripts=False, force_valid_node_name=True)
    
                if ext == ".abc":
                    alembic_node = geo_node.createNode("alembic", node_name=safe_name)
                    alembic_node.parm("fileName").set(path.replace('\\', '/'))
                else:
                    file_node = geo_node.createNode("file", node_name="file1")
                    file_node.parm("file").set(path.replace('\\', '/'))
    
                geo_node.layoutChildren()
                self._add_to_recent(path)
    
            except Exception as e:
                print(f"Import error for {path}:", e)
                hou.ui.displayMessage(f"Failed to import file:\n{path}\n\n{e}")
    
    def _import_cameras(self, file_list):
        """Import one or more Alembic (.abc) camera files into /obj."""
        for path in file_list:
            if not os.path.isfile(path) or not path.lower().endswith(".abc"):
                QMessageBox.warning(
                    self,
                    "Invalid File",
                    f"Only .abc files can be imported as cameras:\n{path}"
                )
                continue
    
            name_no_ext = os.path.splitext(os.path.basename(path))[0]
            safe_name = self._sanitize_node_name(name_no_ext)
    
            try:
                obj = hou.node("/obj")
                archive_node = obj.createNode(
                    "alembicarchive",
                    node_name=safe_name,
                    run_init_scripts=False,
                    force_valid_node_name=True
                )
                archive_node.parm("fileName").set(path.replace('\\', '/'))
                archive_node.parm("buildHierarchy").pressButton()
                archive_node.layoutChildren()
                self._add_to_recent(path)
    
            except Exception as e:
                print(f"Import camera error for {path}:", e)
                hou.ui.displayMessage(
                    f"Failed to import camera:\n{path}\n\n{e}"
                )
    

    
    def _delete_files(self, file_list):
        confirm = QMessageBox.question(
            self,
            "Delete Files",
            f"Are you sure you want to delete these files?\n" + "\n".join(file_list),
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            for path in file_list:
                try:
                    os.remove(path)
                except Exception as e:
                    QMessageBox.critical(self, "Delete Failed", f"Could not delete file {path}:\n{e}")
            self._browser_populate_files(self.browser_path_display.text().strip())


    def _save_versioned_hip(self):
        shot = self.browser_combos[4].currentText().strip()
        task = self.browser_combos[5].currentText().strip()
        base_path = self.browser_path_display.text().strip()

        if not shot or not task:
            QMessageBox.warning(self, "Missing Info", "Please select both Shot No and Task.")
            return

        if not os.path.isdir(base_path):
            QMessageBox.warning(self, "Invalid Path", "Target directory is invalid.")
            return

        base_name = f"{shot}_{task}"
        existing = [f for f in os.listdir(base_path) if re.match(rf"{re.escape(base_name)}_v\d{{3}}\.hip", f)]

        version = 1
        if existing:
            versions = [int(re.search(r"_v(\d{3})\.hip", f).group(1)) for f in existing]
            version = max(versions) + 1

        filename = f"{base_name}_v{version:03d}.hip"
        full_path = os.path.join(base_path, filename)

        try:
            hou.hipFile.save(full_path.replace('\\', '/'))
            QMessageBox.information(self, "Saved", f"Scene saved as:\n{filename}")
            self._add_to_recent(full_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")
        
        
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
        style = QtWidgets.QApplication.style()  # ✅ fix
    
        self.browser_file_list.clear()
        try:
            if os.path.isdir(path):
                back_item = QtWidgets.QListWidgetItem("⬅️  Back")
                back_item.setData(QtCore.Qt.UserRole, "__back__")
                font = back_item.font()
                font.setBold(True)
                back_item.setFont(font)
                self.browser_file_list.addItem(back_item)
        
                # Add normal entries
                entries = sorted(os.listdir(path))
                for e in entries:
                    full_path = os.path.join(path, e)
                    item = QtWidgets.QListWidgetItem(e)
    
                    if os.path.isdir(full_path):
                        item.setIcon(style.standardIcon(QStyle.SP_DirIcon))
                    elif e.lower().endswith(".hip") and os.path.exists(HIP_ICON_PATH):
                        item.setIcon(QtGui.QIcon(HIP_ICON_PATH))
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
        # Check if it's the special back arrow entry
        if item.data(QtCore.Qt.UserRole) == "__back__":
            self._browser_go_back()
            return
    
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
                geo_node = obj.createNode("geo", node_name=safe_name,
                                          run_init_scripts=False, force_valid_node_name=True)
                alembic_node = geo_node.createNode("alembic", node_name=safe_name)
                alembic_node.parm("fileName").set(full_path.replace('\\', '/'))
                geo_node.layoutChildren()
            else:
                obj = hou.node("/obj")
                geo_node = obj.createNode("geo", node_name=safe_name,
                                          run_init_scripts=False, force_valid_node_name=True)
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

        # --- Dark theme stylesheet ---
        DARK_STYLE = """
        QWidget {
            background-color: #1e1e1e;  /* Dark grey background */
            color: #FFFFFF;             /* White text */
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
            font-size: 12px;             /* Font size 8 pixels */
        }
        QLineEdit, QComboBox, QListWidget {
        background-color: #2c2c2c;  /* Slightly lighter dark grey for list */
        border: none;
        border-radius: 4px;
        outline: none;
        }
        QLineEdit:focus, QComboBox:focus, QListWidget:focus {
            border: 1px solid #00aaff;
        }
        QPushButton {
        background-color: #bfbfbf;  /* Light gray button bg */
        color: #1e1e1e;             /* Dark text on button */
        padding: 1px 1px;          /* Smaller padding */
        border-radius: 4px;         /* Rounded corners with 4px radius */
        font-weight: 400;
        min-width: 40px;            /* Reduced minimum width */
        transition: background-color 0.2s ease, color 0.2s ease;
        }
        QPushButton:hover {
            background-color: #555555;
        }
        QPushButton:pressed {
            background-color: #222222;
        }
        QListWidget::item:selected {
            background-color: #005f87;
            color: #ffffff;
        }
        QScrollBar:vertical {
            background: #2b2b2b;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background: #555555;
            min-height: 20px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical:hover {
            background: #888888;
        }
        """

        # --- Main window setup ---
        win = QtWidgets.QDialog(parent=main_window)
        win.setWindowTitle("Houdini Browser Tool")
        win.setMinimumSize(900, 550)
        win.setStyleSheet(DARK_STYLE)  # Apply dark theme

        stacked_layout = QtWidgets.QStackedLayout()
        container = QtWidgets.QWidget()
        container.setLayout(stacked_layout)
        win.setLayout(QtWidgets.QVBoxLayout())
        win.layout().addWidget(container)

        # Main browser page
        main_page = tool.create_browser_page()
        stacked_layout.addWidget(main_page)

        # --- Floating Save Button ---
        save_btn = QtWidgets.QPushButton("💾 ")
        save_btn.setParent(container)
        save_btn.setToolTip("Save Hip File")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #bfbfbf;  /* Light gray button bg */
                color: #1e1e1e; 
                font-weight: bold;
                border-radius: 20px;
                padding: 0px;
                border: 0px solid rgba(255, 255, 255, 0);
            }
            QPushButton:hover {
                background-color: rgba(76, 175, 80, 0.9);
            }
        """)
        save_btn.resize(40, 40)
        save_btn.clicked.connect(tool._save_versioned_hip)

        def reposition_button():
            parent_size = container.size()
            btn_width, btn_height = save_btn.size().width(), save_btn.size().height()
            save_btn.move(parent_size.width() - btn_width - 20, parent_size.height() - btn_height - 20)

        container.resizeEvent = lambda event: reposition_button()

        # --- Highlight back item in dark theme ---
        def update_back_item():
            for i in range(tool.browser_file_list.count()):
                item = tool.browser_file_list.item(i)
                if item.data(QtCore.Qt.UserRole) == "__back__":
                    item.setBackground(QtGui.QColor("#444444"))
                    item.setForeground(QtGui.QColor("#ffffff"))
        QtCore.QTimer.singleShot(200, update_back_item)

        win.show()
        hou.session.browser_tool_ui = win

    except Exception as e:
        print("Failed to open browser tool:", e)



# Run it
show_browser_tool()
