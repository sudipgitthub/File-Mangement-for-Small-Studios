from PySide2 import QtWidgets, QtCore
import hou

class FrameRangeSetter(QtWidgets.QWidget):
    def __init__(self):
        super(FrameRangeSetter, self).__init__()

        self.setWindowTitle("Set Frame Range")
        self.setMinimumSize(300, 140)

        layout = QtWidgets.QVBoxLayout(self)

        form_layout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)

        # Load saved or default frame range
        default_start = getattr(hou.session, "saved_frame_start", int(hou.playbar.frameRange()[0]))
        default_end = getattr(hou.session, "saved_frame_end", int(hou.playbar.frameRange()[1]))

        self.start_edit = QtWidgets.QLineEdit(str(default_start))
        self.end_edit = QtWidgets.QLineEdit(str(default_end))
        form_layout.addRow("Start Frame:", self.start_edit)
        form_layout.addRow("End Frame:", self.end_edit)

        self.playbar_checkbox = QtWidgets.QCheckBox("Set Houdini Playbar Frame Range")
        self.playbar_checkbox.setChecked(True)
        layout.addWidget(self.playbar_checkbox)

        self.save_checkbox = QtWidgets.QCheckBox("Save frame range for later")
        self.save_checkbox.setChecked(True)
        layout.addWidget(self.save_checkbox)

        self.set_button = QtWidgets.QPushButton("Set Frame Range")
        layout.addWidget(self.set_button)

        self.set_button.clicked.connect(self.on_set_frame_range)

    def on_set_frame_range(self):
        try:
            start = int(self.start_edit.text())
            end = int(self.end_edit.text())
        except ValueError:
            hou.ui.displayMessage("Please enter valid integer values for start and end frames.")
            return

        if start > end:
            hou.ui.displayMessage("Start frame must be less than or equal to End frame.")
            return

        # Set playbar frame range regardless of node selection
        if self.playbar_checkbox.isChecked():
            hou.playbar.setFrameRange(start, end)

        # Set frame range on nodes if any selected
        selected_nodes = hou.selectedNodes()
        total_nodes_changed = 0

        if selected_nodes:
            params_to_try = [
                ("f1", "f2"),
                ("frame_range_start", "frame_range_end"),
                ("frameStart", "frameEnd"),
                ("startframe", "endframe"),
                ("start", "end"),
                ("frame",),  # single param, sometimes frame is a vector or range
            ]

            def set_params_on_node(node):
                changed = False
                for names in params_to_try:
                    if len(names) == 2:
                        pstart = node.parm(names[0])
                        pend = node.parm(names[1])
                        if pstart and pend:
                            pstart.set(start)
                            pend.set(end)
                            changed = True
                    elif len(names) == 1:
                        p = node.parm(names[0])
                        if p:
                            if p.isTuple():
                                if len(p) >= 2:
                                    p.set((start, end))
                                    changed = True
                            else:
                                p.set(start)
                                changed = True
                return changed

            def recurse_and_set(node):
                total_changed = 0
                if set_params_on_node(node):
                    total_changed += 1
                for child in node.children():
                    total_changed += recurse_and_set(child)
                return total_changed

            for node in selected_nodes:
                total_nodes_changed += recurse_and_set(node)

        if self.save_checkbox.isChecked():
            hou.session.saved_frame_start = start
            hou.session.saved_frame_end = end

        msg = f"Frame range set to {start} - {end}."
        if total_nodes_changed > 0:
            msg += f" Set on {total_nodes_changed} node(s)."
        else:
            if selected_nodes:
                msg += " No nodes with recognized frame range parameters found in selection or children."

        hou.ui.displayMessage(msg)

def show_frame_range_setter():
    global _frame_range_setter_win
    try:
        _frame_range_setter_win.close()
        _frame_range_setter_win.deleteLater()
    except:
        pass
    _frame_range_setter_win = FrameRangeSetter()
    _frame_range_setter_win.show()

show_frame_range_setter()
