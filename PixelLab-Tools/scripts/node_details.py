from PySide2 import QtWidgets, QtCore
import hou

class NodeDetailsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(NodeDetailsDialog, self).__init__(parent)
        self.setWindowTitle("Node Details")
        self.resize(600, 700)

        layout = QtWidgets.QVBoxLayout(self)

        selected_nodes = hou.selectedNodes()
        if not selected_nodes:
            layout.addWidget(QtWidgets.QLabel("No nodes selected"))
            return

        node = selected_nodes[0]

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        scroll.setWidget(content)

        content_layout = QtWidgets.QVBoxLayout(content)

        # Node basic info
        basic_info_label = QtWidgets.QLabel("<b>Node Basic Info</b>")
        basic_info_label.setStyleSheet("font-size: 16px; margin-bottom: 8px;")
        content_layout.addWidget(basic_info_label)

        info_text = f"""
        <b>Name:</b> {node.name()}<br>
        <b>Type:</b> {node.type().name()}<br>
        <b>Path:</b> {node.path()}<br>
        """
        content_layout.addWidget(QtWidgets.QLabel(info_text))

        # Parameters grouped by folder path
        folders = {}

        for parm in node.parms():
            pt = parm.parmTemplate()
            folder_path = ""
            if hasattr(pt, "folderPath"):
                folder_path = pt.folderPath() or ""

            if folder_path not in folders:
                folders[folder_path] = []
            folders[folder_path].append(parm)

        folder_keys = sorted(folders.keys(), key=lambda x: (x != "", x))

        for folder_name in folder_keys:
            if folder_name and folder_name != "/":
                display_name = folder_name.lstrip("/")
                folder_label = QtWidgets.QLabel(f"<b>Folder: {display_name}</b>")
                folder_label.setStyleSheet("font-size: 14px; margin-top: 12px; margin-bottom: 6px;")
                content_layout.addWidget(folder_label)

            for parm in folders[folder_name]:
                pt = parm.parmTemplate()
                # Parm details
                label = pt.label() if hasattr(pt, "label") else parm.name()
                ptype = type(pt).__name__
                try:
                    val = parm.eval()
                except Exception:
                    val = "<unable to evaluate>"

                extra_info = ""
                # Show default, min, max if available
                if hasattr(pt, "defaultValue"):
                    default_val = pt.defaultValue()
                    if isinstance(default_val, (list, tuple)):
                        default_val = ", ".join(str(x) for x in default_val)
                    extra_info += f" Default: {default_val}"

                if hasattr(pt, "minValue") and hasattr(pt, "maxValue"):
                    try:
                        minv = pt.minValue()
                        maxv = pt.maxValue()
                        if minv != maxv:
                            extra_info += f" Range: [{minv}, {maxv}]"
                    except Exception:
                        pass

                parm_text = f"<b>{label}</b> ({ptype}): {val}{extra_info}"
                parm_label = QtWidgets.QLabel(parm_text)
                parm_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
                content_layout.addWidget(parm_label)

        # User data keys/values
        user_data = node.userDataDict()
        if user_data:
            user_data_label = QtWidgets.QLabel("<b>User Data</b>")
            user_data_label.setStyleSheet("font-size: 14px; margin-top: 12px; margin-bottom: 6px;")
            content_layout.addWidget(user_data_label)

            for key, val in user_data.items():
                ud_label = QtWidgets.QLabel(f"{key}: {val}")
                ud_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
                content_layout.addWidget(ud_label)

        layout.addWidget(scroll)


dlg = NodeDetailsDialog()
dlg.exec_()
