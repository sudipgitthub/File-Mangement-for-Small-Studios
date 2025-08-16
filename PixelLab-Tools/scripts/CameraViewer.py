import hou
from PySide2 import QtWidgets, QtCore, QtGui

# Function to recursively find all camera nodes
def find_all_cameras(node):
    cameras = []

    if node.type().name() == "cam":
        cameras.append(node)

    for child in node.children():
        cameras.extend(find_all_cameras(child))

    return cameras


# Main UI Class
class CameraFinderUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(CameraFinderUI, self).__init__(parent)

        self.setWindowTitle("🎥 Houdini Camera Finder")
        self.setFixedSize(900, 550)

        # Apply modern dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #dddddd;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #3c3f41;
                border: 1px solid #5a5a5a;
                padding: 4px 4px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #4b5052;
            }
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #5a5a5a;
                border-radius: 8px;
                padding: 1px;
            }
            QListWidget::item {
                border-radius: 8px;
                padding: 2px;
            }
            QListWidget::item:selected {
                background-color: #007acc;
                color: white;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Find cameras button
        self.find_button = QtWidgets.QPushButton("🔍 Find All Cameras")
        self.find_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        layout.addWidget(self.find_button)

        # Camera list
        self.camera_list = QtWidgets.QListWidget()
        self.camera_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.camera_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.camera_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.camera_list)

        # Connect button click
        self.find_button.clicked.connect(self.populate_camera_list)

    def populate_camera_list(self):
        self.camera_list.clear()

        root = hou.node("/obj")
        if not root:
            QtWidgets.QMessageBox.warning(self, "Error", "Root /obj node not found.")
            return

        cameras = find_all_cameras(root)

        if not cameras:
            self.camera_list.addItem("No cameras found.")
            return

        for cam in cameras:
            self.camera_list.addItem(cam.path())

    def _show_context_menu(self, pos):
        menu = QtWidgets.QMenu()
        selected_items = self.camera_list.selectedItems()
        if selected_items:
            menu.addAction("📋 Copy Path(s)", self._copy_selected_paths)
        menu.exec_(self.camera_list.viewport().mapToGlobal(pos))

    def _copy_selected_paths(self):
        paths = [item.text() for item in self.camera_list.selectedItems()]
        QtWidgets.QApplication.clipboard().setText("\n".join(paths))


# Show the UI immediately when the script runs
def show_camera_finder():
    try:
        for widget in QtWidgets.QApplication.allWidgets():
            if isinstance(widget, CameraFinderUI):
                widget.close()
    except:
        pass

    dialog = CameraFinderUI(hou.ui.mainQtWindow())
    dialog.show()

# Launch the UI
show_camera_finder()
