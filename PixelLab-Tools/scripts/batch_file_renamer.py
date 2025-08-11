from PySide2 import QtWidgets, QtCore
import hou

class BatchRenameUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Batch Rename Selected Nodes")
        self.setMinimumSize(400, 250)

        layout = QtWidgets.QVBoxLayout(self)

        # Prefix
        self.prefix_edit = QtWidgets.QLineEdit()
        layout.addWidget(QtWidgets.QLabel("Prefix:"))
        layout.addWidget(self.prefix_edit)

        # Suffix
        self.suffix_edit = QtWidgets.QLineEdit()
        layout.addWidget(QtWidgets.QLabel("Suffix:"))
        layout.addWidget(self.suffix_edit)

        # Find and Replace
        find_replace_layout = QtWidgets.QHBoxLayout()
        self.find_edit = QtWidgets.QLineEdit()
        self.find_edit.setPlaceholderText("Find substring")
        self.replace_edit = QtWidgets.QLineEdit()
        self.replace_edit.setPlaceholderText("Replace with")
        find_replace_layout.addWidget(self.find_edit)
        find_replace_layout.addWidget(self.replace_edit)
        layout.addWidget(QtWidgets.QLabel("Find and Replace (optional):"))
        layout.addLayout(find_replace_layout)

        # Sequential rename
        self.seq_checkbox = QtWidgets.QCheckBox("Rename sequentially")
        layout.addWidget(self.seq_checkbox)

        seq_layout = QtWidgets.QHBoxLayout()
        self.seq_start_spin = QtWidgets.QSpinBox()
        self.seq_start_spin.setMinimum(1)
        self.seq_start_spin.setValue(1)
        self.seq_padding_spin = QtWidgets.QSpinBox()
        self.seq_padding_spin.setMinimum(1)
        self.seq_padding_spin.setValue(3)
        seq_layout.addWidget(QtWidgets.QLabel("Start number:"))
        seq_layout.addWidget(self.seq_start_spin)
        seq_layout.addWidget(QtWidgets.QLabel("Zero padding:"))
        seq_layout.addWidget(self.seq_padding_spin)
        layout.addLayout(seq_layout)

        # Run button
        self.run_btn = QtWidgets.QPushButton("Run Batch Rename")
        layout.addWidget(self.run_btn)

        # Output log
        self.output_text = QtWidgets.QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)

        self.run_btn.clicked.connect(self.run_rename)

    def log(self, msg):
        self.output_text.append(msg)
        print(msg)

    def run_rename(self):
        selected_nodes = hou.selectedNodes()
        if not selected_nodes:
            self.log("No nodes selected.")
            return
    
        prefix = self.prefix_edit.text()
        suffix = self.suffix_edit.text()
        find_str = self.find_edit.text()
        replace_str = self.replace_edit.text()
        rename_seq = self.seq_checkbox.isChecked()
        seq_start = self.seq_start_spin.value()
        seq_padding = self.seq_padding_spin.value()
    
        count = 0
        for i, node in enumerate(selected_nodes, start=seq_start):
            old_name = node.name()
            new_name = old_name
    
            if rename_seq:
                new_name = f"{prefix}{str(i).zfill(seq_padding)}{suffix}"
            else:
                if find_str and replace_str is not None and find_str != "":
                    new_name = new_name.replace(find_str, replace_str)
                new_name = f"{prefix}{new_name}{suffix}"
    
            if new_name != old_name:
                try:
                    node.setName(new_name, unique_name=True)
                    count += 1
                    self.log(f"Renamed: {old_name} -> {new_name}")
                except hou.NameConflict:
                    self.log(f"Name conflict, skipping: {new_name}")
                except Exception as e:
                    self.log(f"Error renaming {old_name}: {e}")
    
        self.log(f"\nBatch rename completed: {count} nodes renamed.")


def show_batch_rename_ui():
    global _batch_rename_ui
    try:
        _batch_rename_ui.close()
        _batch_rename_ui.deleteLater()
    except:
        pass
    _batch_rename_ui = BatchRenameUI()
    _batch_rename_ui.show()

try:
    show_batch_rename_ui()
except Exception as e:
    hou.ui.displayMessage(f"Error launching Batch Rename UI:\n{e}")
