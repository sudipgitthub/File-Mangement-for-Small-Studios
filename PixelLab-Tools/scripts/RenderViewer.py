import hou
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtCore import QDateTime
import os
import re
import shutil
import getpass
import subprocess
import sys

try:
    import OpenImageIO as oiio
    HAS_OIIO = True
except ImportError:
    HAS_OIIO = False


def get_folder_owner(path):
    try:
        if os.name == 'nt':
            try:
                import win32security
                sd = win32security.GetFileSecurity(path, win32security.OWNER_SECURITY_INFORMATION)
                owner_sid = sd.GetSecurityDescriptorOwner()
                name, domain, _ = win32security.LookupAccountSid(None, owner_sid)
                return f"{domain}\\{name}"
            except ImportError:
                return getpass.getuser()
            except Exception as e:
                print(f"Error getting Windows owner for {path}: {e}")
                return "Unknown"
        else:
            import pwd
            stat_info = os.stat(path)
            return pwd.getpwuid(stat_info.st_uid).pw_name
    except Exception as e:
        print(f"Error getting owner for {path}: {e}")
        return "Unknown"


class RenderBrowser(QtWidgets.QDialog):
    def __init__(self, parent=None):
        parent = parent or hou.ui.mainQtWindow()
        super(RenderBrowser, self).__init__(parent)
        self.setWindowTitle("Render Browser")
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #dddddd;
                font-family: "Segoe UI", "Arial", sans-serif;
                font-size: 8pt;
            }
            
            QHeaderView::section {
                background-color: #3c3c3c;
                color: #dddddd;
                padding: 4px;
                border: 1px solid #444;
            }
        
            QTableWidget {
                background-color: #2b2b2b;
                gridline-color: #555555;
                alternate-background-color: #3a3a3a;
            }
        
            QTableWidget::item:selected {
                background-color: #505F79;
                color: white;
            }
        
            QMenu {
                background-color: #2b2b2b;
                color: #dddddd;
                border: 1px solid #444444;
            }
        
            QMenu::item:selected {
                background-color: #505F79;
            }
        
            QScrollBar:vertical {
                background: #2b2b2b;
                width: 12px;
                margin: 0px;
            }
        
            QScrollBar::handle:vertical {
                background: #555;
                min-height: 20px;
                border-radius: 4px;
            }
        
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: none;
                height: 0;
            }
        
            QLabel {
                color: #dddddd;
            }
        
            QMessageBox {
                background-color: #2b2b2b;
            }
        """)
        self.resize(900, 550)

        layout = QtWidgets.QVBoxLayout(self)

        self.render_table = QtWidgets.QTableWidget()
        self.render_table.setColumnCount(8)
        self.render_table.setHorizontalHeaderLabels([
            "Preview", "Render Layer", "Frame Range", "Frame No", "Resolution",
            "Version", "Date & Time", "User"
        ])
        self.render_table.horizontalHeader().setStretchLastSection(True)
        self.render_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.render_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.render_table.verticalHeader().setVisible(False)
        self.render_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.render_table.customContextMenuRequested.connect(self.show_render_context_menu)
        self.render_table.cellDoubleClicked.connect(self.handle_render_double_click)

        layout.addWidget(self.render_table)

        QtCore.QTimer.singleShot(300, self.populate_render_table)

    def generate_thumbnail(self, image_path, size=(160, 90)):
        label = QtWidgets.QLabel()
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setStyleSheet("padding: 2px; background-color: #222222; color: gray;")

        if not os.path.isfile(image_path):
            label.setText("File not found")
            return label

        ext = os.path.splitext(image_path)[1].lower()
        display_path = image_path

        if ext == ".exr" and HAS_OIIO:
            try:
                import tempfile
                buf = oiio.ImageBuf(image_path)
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                display_path = tmp.name
                buf.write(display_path)
            except Exception:
                label.setText("EXR read error")
                return label

        reader = QtGui.QImageReader(display_path)
        reader.setAutoTransform(True)
        image = reader.read()

        if image.isNull():
            label.setText("Unsupported Format")
        else:
            pixmap = QtGui.QPixmap.fromImage(image)
            scaled_pixmap = pixmap.scaled(size[0], size[1], QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            label.setPixmap(scaled_pixmap)

        if ext == ".exr" and HAS_OIIO:
            try:
                os.remove(display_path)
            except:
                pass

        return label

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
                    user = get_folder_owner(layer_path)
                    frame_count = str(len(exr_files))
                    self.render_table.insertRow(row)

                    thumb_path = os.path.join(layer_path, exr_files[len(exr_files) // 2])
                    thumb_label = self.generate_thumbnail(thumb_path)
                    self.render_table.setCellWidget(row, 0, thumb_label)

                    row_data = [layer, frame_range, frame_count, resolution, version, datetime_str, user]
                    for col, data in enumerate(row_data):
                        item = QtWidgets.QTableWidgetItem(data)
                        item.setForeground(text_color)
                        item.setData(QtCore.Qt.UserRole, layer_path)
                        item.setTextAlignment(QtCore.Qt.AlignCenter)
                        if col == 0:
                            item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                        self.render_table.setItem(row, col + 1, item)
                    row += 1

            min_widths = [60, 140, 140, 80, 140, 70, 140, 140]
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
        item = self.render_table.item(row, 1)
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
        layer_item = self.render_table.item(row, 1)
        version_item = self.render_table.item(row, 5)
        if not layer_item or not version_item:
            return

        folder = os.path.normpath(os.path.join(
            os.environ.get("HIP", ""), "render", version_item.text(), layer_item.text()))

        if not os.path.exists(folder):
            QtWidgets.QMessageBox.warning(self, "Not Found", f"Folder not found:\n{folder}")
            return

        try:
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

            mp4s = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".mp4")]
            if mp4s:
                if os.name == 'nt':
                    os.startfile(mp4s[0])
                elif sys.platform == 'darwin':
                    subprocess.Popen(["open", mp4s[0]])
                else:
                    subprocess.Popen(["xdg-open", mp4s[0]])
                return

            self.open_folder(folder)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def delete_render_folder(self, row, path):
        confirm = QtWidgets.QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete:\n{path}",
                                                 QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if confirm == QtWidgets.QMessageBox.Yes:
            try:
                shutil.rmtree(path)
                self.render_table.removeRow(row)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Delete Failed", str(e))

    def open_folder(self, folder):
        if os.name == 'nt':
            os.startfile(folder)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', folder])
        else:
            subprocess.Popen(['xdg-open', folder])

    def closeEvent(self, event):
        try:
            if hasattr(hou.session, "render_browser_window"):
                hou.session.render_browser_window = None
        except Exception:
            pass
        super().closeEvent(event)
    


# 🚫 Prevent duplicate window
if hasattr(hou.session, "render_browser_window") and hou.session.render_browser_window is not None:
    if hou.session.render_browser_window.isVisible():
        hou.session.render_browser_window.raise_()
        hou.session.render_browser_window.activateWindow()
    else:
        hou.session.render_browser_window.show()
else:
    hou.session.render_browser_window = RenderBrowser()
    hou.session.render_browser_window.show()
