from PySide2 import QtWidgets, QtCore
import hou
import os
import datetime

class GlobalAssetRelinkerUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Global Asset Relinker")
        self.setMinimumSize(600, 600)

        layout = QtWidgets.QVBoxLayout(self)

        form_layout = QtWidgets.QFormLayout()

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Text to find in asset paths")
        form_layout.addRow("Search String:", self.search_edit)

        self.replace_edit = QtWidgets.QLineEdit()
        self.replace_edit.setPlaceholderText("Replacement text")
        form_layout.addRow("Replace With:", self.replace_edit)

        self.node_type_edit = QtWidgets.QLineEdit()
        self.node_type_edit.setPlaceholderText("e.g. geo, cop2net, vopnet (comma separated)")
        form_layout.addRow("Filter Node Types (optional):", self.node_type_edit)

        self.parm_name_edit = QtWidgets.QLineEdit()
        self.parm_name_edit.setPlaceholderText("e.g. file, texture, cache")
        form_layout.addRow("Filter Parm Name Contains (optional):", self.parm_name_edit)

        self.check_missing_files = QtWidgets.QCheckBox("Warn about missing files after replace")
        layout.addWidget(self.check_missing_files)

        layout.addLayout(form_layout)

        self.preview_btn = QtWidgets.QPushButton("Preview Changes")
        layout.addWidget(self.preview_btn)

        self.apply_btn = QtWidgets.QPushButton("Apply Changes")
        self.apply_btn.setEnabled(False)
        layout.addWidget(self.apply_btn)

        self.backup_btn = QtWidgets.QPushButton("Save Backup Log")
        self.backup_btn.setEnabled(False)
        layout.addWidget(self.backup_btn)

        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        self.preview_btn.clicked.connect(self.preview_changes)
        self.apply_btn.clicked.connect(self.apply_changes)
        self.backup_btn.clicked.connect(self.save_backup_log)

        self.changes = []  # (parm, old_path, new_path)
        self.backup_log = []

    def log(self, msg):
        self.log_text.append(msg)
        print(msg)

    def node_type_matches(self, node, types):
        if not types:
            return True
        nodetypes = [t.strip().lower() for t in types.split(",")]
        return node.type().nameComponents()[-1].lower() in nodetypes

    def parm_name_matches(self, parm, filter_str):
        if not filter_str:
            return True
        return filter_str.lower() in parm.name().lower()

    def find_file_parms(self):
        file_parms = []
        for node in hou.node("/").allSubChildren():
            if not self.node_type_matches(node, self.node_type_edit.text()):
                continue
            for parm in node.parms():
                if parm.parmTemplate().type() == hou.parmTemplateType.File or parm.parmTemplate().type() == hou.parmTemplateType.String:
                    val = parm.eval()
                    if val and isinstance(val, str):
                        if os.path.isabs(val) or "/" in val or "\\" in val:
                            if self.parm_name_matches(parm, self.parm_name_edit.text()):
                                file_parms.append((parm, val))
        return file_parms

    def preview_changes(self):
        search_str = self.search_edit.text()
        replace_str = self.replace_edit.text()
        self.log_text.clear()
        self.changes = []
        self.backup_log = []

        if not search_str:
            self.log("Please enter a Search String to find.")
            self.apply_btn.setEnabled(False)
            self.backup_btn.setEnabled(False)
            return

        file_parms = self.find_file_parms()
        if not file_parms:
            self.log("No file path parameters found matching filters.")
            self.apply_btn.setEnabled(False)
            self.backup_btn.setEnabled(False)
            return

        for parm, val in file_parms:
            if search_str in val:
                new_val = val.replace(search_str, replace_str)
                self.changes.append((parm, val, new_val))

        if not self.changes:
            self.log("No matches found for the search string with given filters.")
            self.apply_btn.setEnabled(False)
            self.backup_btn.setEnabled(False)
            return

        self.log(f"Previewing {len(self.changes)} changes:\n")
        for parm, old, new in self.changes:
            missing_note = ""
            if self.check_missing_files.isChecked():
                # Check if file exists after replacement
                path_to_check = new
                if os.path.isdir(path_to_check) or os.path.isfile(path_to_check):
                    missing_note = ""
                else:
                    missing_note = " [MISSING FILE]"
            self.log(f"{parm.node().path()}/{parm.name()}:\n  {old}\n  -> {new}{missing_note}\n")

        self.apply_btn.setEnabled(True)
        self.backup_btn.setEnabled(False)

    def apply_changes(self):
        if not self.changes:
            self.log("No changes to apply.")
            return

        self.log("Applying changes...\n")
        count = 0
        self.backup_log.clear()
        for parm, old, new in self.changes:
            try:
                parm.set(new)
                count += 1
                self.backup_log.append((parm.node().path(), parm.name(), old, new))
            except Exception as e:
                self.log(f"Failed to set {parm.node().path()}/{parm.name()}: {e}")

        self.log(f"\nApplied {count} changes.")
        self.apply_btn.setEnabled(False)
        self.backup_btn.setEnabled(True)

    def save_backup_log(self):
        if not self.backup_log:
            self.log("No backup log to save.")
            return

        import datetime
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = hou.ui.selectFile(
            title="Save Backup Log",
            pattern="*.txt",
            default_value=f"asset_relink_backup_{now_str}.txt",
            chooser_mode=hou.fileChooserMode.Save,
            collapse_sequences=False,
        )

        if not filename:
            self.log("Backup save cancelled.")
            return

        try:
            with open(filename, "w") as f:
                f.write("Asset Relinker Backup Log\n")
                f.write(f"Date: {datetime.datetime.now()}\n\n")
                for node_path, parm_name, old, new in self.backup_log:
                    f.write(f"{node_path}/{parm_name}\n  FROM: {old}\n  TO:   {new}\n\n")
            self.log(f"Backup log saved to:\n{filename}")
        except Exception as e:
            self.log(f"Failed to save backup log: {e}")

def show_global_asset_relinker():
    global _global_asset_relinker_ui
    try:
        _global_asset_relinker_ui.close()
        _global_asset_relinker_ui.deleteLater()
    except:
        pass
    _global_asset_relinker_ui = GlobalAssetRelinkerUI()
    _global_asset_relinker_ui.show()

try:
    show_global_asset_relinker()
except Exception as e:
    import hou
    hou.ui.displayMessage(f"Error launching Global Asset Relinker UI:\n{e}")
