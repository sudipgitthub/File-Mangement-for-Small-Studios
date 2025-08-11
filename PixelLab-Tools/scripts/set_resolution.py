from PySide2 import QtWidgets, QtCore
import hou

class ResolutionSetter(QtWidgets.QWidget):
    def __init__(self):
        super(ResolutionSetter, self).__init__()

        self.setWindowTitle("Set Resolution")
        self.setMinimumSize(300, 120)

        layout = QtWidgets.QVBoxLayout(self)

        form_layout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)

        # Load saved or default resolution
        default_width = getattr(hou.session, "saved_res_width", 2048)
        default_height = getattr(hou.session, "saved_res_height", 1080)

        self.width_edit = QtWidgets.QLineEdit(str(default_width))
        self.height_edit = QtWidgets.QLineEdit(str(default_height))
        form_layout.addRow("Width:", self.width_edit)
        form_layout.addRow("Height:", self.height_edit)

        self.save_checkbox = QtWidgets.QCheckBox("Save resolution for later")
        self.save_checkbox.setChecked(True)
        layout.addWidget(self.save_checkbox)

        self.set_button = QtWidgets.QPushButton("Set Resolution")
        layout.addWidget(self.set_button)

        self.set_button.clicked.connect(self.on_set_resolution)

    def on_set_resolution(self):
        try:
            width = int(self.width_edit.text())
            height = int(self.height_edit.text())
        except ValueError:
            hou.ui.displayMessage("Please enter valid integer values for width and height.")
            return

        selected_nodes = hou.selectedNodes()
        if not selected_nodes:
            hou.ui.displayMessage("No node selected.")
            return

        params_to_try = [
            ("resx", "resy"),
            ("width", "height"),
            ("resx_override", "resy_override"),
            ("vm_resolution",),
        ]

        def set_params_on_node(node):
            changed = False
            for names in params_to_try:
                if len(names) == 2:
                    if node.parm(names[0]) and node.parm(names[1]):
                        node.parm(names[0]).set(width)
                        node.parm(names[1]).set(height)
                        changed = True
                elif len(names) == 1:
                    parm = node.parm(names[0])
                    if parm and parm.isVector():
                        parm.set((width, height))
                        changed = True
            return changed

        def recurse_and_set(node):
            total_changed = 0
            if set_params_on_node(node):
                total_changed += 1
            for child in node.children():
                total_changed += recurse_and_set(child)
            return total_changed

        total_nodes_changed = 0
        for node in selected_nodes:
            total_nodes_changed += recurse_and_set(node)

        if self.save_checkbox.isChecked():
            hou.session.saved_res_width = width
            hou.session.saved_res_height = height

        if total_nodes_changed > 0:
            hou.ui.displayMessage(f"Resolution set to {width}x{height} on {total_nodes_changed} node(s).")
        else:
            hou.ui.displayMessage("No nodes with recognized resolution parameters found in selection or children.")

def show_resolution_setter():
    global _resolution_setter_win
    try:
        _resolution_setter_win.close()
        _resolution_setter_win.deleteLater()
    except:
        pass
    _resolution_setter_win = ResolutionSetter()
    _resolution_setter_win.show()

show_resolution_setter()
