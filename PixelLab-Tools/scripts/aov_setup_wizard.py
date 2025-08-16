from PySide2 import QtWidgets, QtCore
import hou

class AOVSetupUI(QtWidgets.QWidget):
    MANTRA_PRESET_AOVS = [
        "P", "N", "Z", "diffuse", "diffuse_direct", "diffuse_indirect", "specular", "specular_direct",
        "specular_indirect", "reflection", "refraction", "emission", "shadow", "ambient_occlusion",
        "velocity", "uv", "subsurface", "opacity", "backlight", "transmission", "volume",
        "cryptomatte", "luminance", "world_position", "world_normal", "diffuse_albedo", "specular_albedo",
        "metallic", "roughness", "occlusion", "emission_indirect", "motion_blur",
    ]

    REDSHIFT_PRESET_AOVS = [
        "RGBA", "diffuseLighting", "reflection", "refraction", "sss", "emission", "shadow",
        "specularLighting", "ambientOcclusion", "motionVectors", "Z", "UV", "normal",
        "cryptomatte", "velocity",
    ]

    ARNOLD_PRESET_AOVS = [
        "RGBA", "diffuse_direct", "diffuse_indirect", "specular_direct", "specular_indirect",
        "sss", "emission", "shadow", "ambient_occlusion", "motionvector", "Z", "UV", "normal",
        "cryptomatte",
    ]

    KARMA_PRESET_AOVS = [
        "color", "depth", "normal", "P", "velocity", "direct_diffuse", "indirect_diffuse",
        "direct_specular", "indirect_specular", "sss", "emission", "occlusion", "cryptomatte",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Renderer AOV Setup Wizard")
        self.setMinimumSize(650, 520)

        layout = QtWidgets.QVBoxLayout(self)

        # Renderer selector
        layout.addWidget(QtWidgets.QLabel("Select Renderer:"))
        self.renderer_combo = QtWidgets.QComboBox()
        self.renderer_combo.addItems(["Mantra", "Redshift", "Arnold", "Karma"])
        layout.addWidget(self.renderer_combo)

        # Select Render Node Combo
        layout.addWidget(QtWidgets.QLabel("Select Render Node:"))
        self.render_node_combo = QtWidgets.QComboBox()
        layout.addWidget(self.render_node_combo)

        self.refresh_btn = QtWidgets.QPushButton("Refresh Render Nodes")
        layout.addWidget(self.refresh_btn)

        # Preset AOVs checklist
        layout.addWidget(QtWidgets.QLabel("Select Preset AOVs to Add:"))
        self.preset_list = QtWidgets.QListWidget()
        self.preset_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        layout.addWidget(self.preset_list)

        self.add_preset_btn = QtWidgets.QPushButton("Add Selected Preset AOVs")
        layout.addWidget(self.add_preset_btn)

        # Current AOV list widget
        layout.addWidget(QtWidgets.QLabel("Current Extra Image Planes:"))
        self.aov_list = QtWidgets.QListWidget()
        layout.addWidget(self.aov_list)

        # Remove selected button
        self.remove_aov_btn = QtWidgets.QPushButton("Remove Selected AOV")
        layout.addWidget(self.remove_aov_btn)

        # Log / status output
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        # Signals
        self.refresh_btn.clicked.connect(self.refresh_render_nodes)
        self.render_node_combo.currentIndexChanged.connect(self.refresh_aov_list)
        self.add_preset_btn.clicked.connect(self.add_selected_presets)
        self.remove_aov_btn.clicked.connect(self.remove_selected_aov)
        self.renderer_combo.currentIndexChanged.connect(self.update_preset_list)

        self.aov_names = []
        self.changes_made = False

        self.update_preset_list()
        self.refresh_render_nodes()

    def log(self, msg):
        self.log_text.append(msg)
        print(msg)

    def update_preset_list(self):
        self.preset_list.clear()
        renderer = self.renderer_combo.currentText()
        presets = []
        if renderer == "Mantra":
            presets = self.MANTRA_PRESET_AOVS
        elif renderer == "Redshift":
            presets = self.REDSHIFT_PRESET_AOVS
        elif renderer == "Arnold":
            presets = self.ARNOLD_PRESET_AOVS
        elif renderer == "Karma":
            presets = self.KARMA_PRESET_AOVS
        else:
            self.log(f"Renderer {renderer} not supported yet.")
            return

        for aov in presets:
            item = QtWidgets.QListWidgetItem(aov)
            item.setCheckState(QtCore.Qt.Unchecked)
            self.preset_list.addItem(item)

    def refresh_render_nodes(self):
        self.render_node_combo.clear()
        renderer = self.renderer_combo.currentText()
        nodes = []
        if renderer == "Mantra":
            nodes = [n for n in hou.node("/out").children() if n.type().name() == "ifd"]
        elif renderer == "Redshift":
            nodes = [n for n in hou.node("/out").children() if n.type().name() == "Redshift_ROP"]
        elif renderer == "Arnold":
            nodes = [n for n in hou.node("/out").children() if n.type().name() == "arnold"]
        elif renderer == "Karma":
            # Karma ROP node type is usually 'karma' or 'karma::rop'
            nodes = [n for n in hou.node("/out").children() if n.type().name().lower().startswith("karma")]
        else:
            self.log(f"Renderer {renderer} node scanning not implemented.")
            return

        for node in nodes:
            self.render_node_combo.addItem(node.name(), node)
        self.refresh_aov_list()

    def refresh_aov_list(self):
        self.aov_list.clear()
        self.aov_names.clear()
        idx = self.render_node_combo.currentIndex()
        if idx == -1:
            return
        node = self.render_node_combo.currentData()
        if not node:
            return

        renderer = self.renderer_combo.currentText()
        if renderer == "Mantra":
            num_aux_parm = node.parm("vm_numaux")
            if not num_aux_parm:
                self.log("Selected Mantra node does not have Mantra extra image planes parameters.")
                return
            count = num_aux_parm.eval()
            for i in range(1, count + 1):
                var_parm = node.parm(f"vm_variable_plane{i}")
                if var_parm:
                    name = var_parm.eval()
                    if name:
                        self.aov_names.append(name)
                        self.aov_list.addItem(name)
        elif renderer == "Redshift":
            aov_parm = node.parm("aov_list") or node.parm("aovs")
            if aov_parm:
                aov_val = aov_parm.eval()
                self.aov_names = [aov_val] if aov_val else []
                for aov in self.aov_names:
                    self.aov_list.addItem(aov)
            else:
                self.log("Redshift AOV parameter not found.")
        elif renderer == "Arnold":
            self.log("Arnold AOV reading not implemented yet.")
        elif renderer == "Karma":
            # Karma AOV reading based on 'name' parameter
            aov_parm = node.parm("name")
            if aov_parm:
                aov_val = aov_parm.eval()
                self.aov_names = [aov_val] if aov_val else []
                for aov in self.aov_names:
                    self.aov_list.addItem(aov)
            else:
                self.log("Karma AOV parameter 'name' not found.")
        else:
            self.log(f"Renderer {renderer} AOV reading not implemented.")

    def add_selected_presets(self):
        added = 0
        for i in range(self.preset_list.count()):
            item = self.preset_list.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                name = item.text()
                if name not in self.aov_names:
                    self.aov_names.append(name)
                    self.aov_list.addItem(name)
                    added += 1
                item.setCheckState(QtCore.Qt.Unchecked)
        if added > 0:
            self.changes_made = True
            self.log(f"Added {added} preset AOV(s).")
            self.apply_changes()
        else:
            self.log("No new preset AOVs were added (all already present).")

    def remove_selected_aov(self):
        selected = self.aov_list.selectedItems()
        if not selected:
            self.log("Select an AOV to remove.")
            return
        for item in selected:
            name = item.text()
            self.aov_names.remove(name)
            self.aov_list.takeItem(self.aov_list.row(item))
            self.log(f"Removed AOV: {name}")
        self.changes_made = True
        self.apply_changes()

    def apply_changes(self):
        idx = self.render_node_combo.currentIndex()
        if idx == -1:
            self.log("Select a render node first.")
            return
        node = self.render_node_combo.currentData()
        if not node:
            return

        renderer = self.renderer_combo.currentText()
        if renderer == "Mantra":
            num_aux_parm = node.parm("vm_numaux")
            if not num_aux_parm:
                self.log("Selected node does not have Mantra extra image planes parameters.")
                return

            count = len(self.aov_names)
            num_aux_parm.set(count)

            max_planes = 32

            for i, aov_name in enumerate(self.aov_names, 1):
                var_parm = node.parm(f"vm_variable_plane{i}")
                if var_parm:
                    var_parm.set(aov_name)
                else:
                    self.log(f"Parameter vm_variable_plane{i} not found.")

            for i in range(count + 1, max_planes + 1):
                var_parm = node.parm(f"vm_variable_plane{i}")
                if var_parm:
                    var_parm.set("")

            node.cook(force=True)
            self.log(f"Applied {count} AOV(s) to {node.name()}.")

        elif renderer == "Redshift":
            self.log("Redshift AOV applying not implemented yet.")
        elif renderer == "Arnold":
            self.log("Arnold AOV applying not implemented yet.")
        elif renderer == "Karma":
            # Karma AOV applying logic (based on 'name' parm)
            aov_parm = node.parm("name")
            if aov_parm:
                aov_parm.set(self.aov_names)
            self.log(f"Applied Karma AOVs: {', '.join(self.aov_names)}")
        else:
            self.log(f"Renderer {renderer} applying not implemented.")

def show_aov_setup_ui():
    global _aov_setup_ui
    try:
        _aov_setup_ui.close()
        _aov_setup_ui.deleteLater()
    except:
        pass
    _aov_setup_ui = AOVSetupUI()
    _aov_setup_ui.show()

try:
    show_aov_setup_ui()
except Exception as e:
    import hou
    hou.ui.displayMessage(f"Error launching AOV Setup UI:\n{e}")
