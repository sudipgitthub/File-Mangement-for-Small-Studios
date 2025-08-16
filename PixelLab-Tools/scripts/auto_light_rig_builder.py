from PySide2 import QtWidgets, QtCore
import hou

class LightRigBuilderUI(QtWidgets.QWidget):
    def __init__(self):
        super(LightRigBuilderUI, self).__init__()
        self.setWindowTitle("Auto Light Rig Builder")
        self.setMinimumSize(400, 400)

        self.rig = None  # Store created rig node

        main_layout = QtWidgets.QVBoxLayout(self)

        # Preset selection & create button
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.addItems([
            "3-Point Lighting",
            "Cinematic Lighting",
            "Simple Key Fill",
            "Rembrandt Lighting"
        ])
        main_layout.addWidget(QtWidgets.QLabel("Select Light Preset:"))
        main_layout.addWidget(self.preset_combo)

        self.create_btn = QtWidgets.QPushButton("Create Light Rig")
        main_layout.addWidget(self.create_btn)
        self.create_btn.clicked.connect(self.create_rig)

        # Separator line
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        main_layout.addWidget(line)

        # Scroll area for controls
        self.controls_area = QtWidgets.QScrollArea()
        self.controls_area.setWidgetResizable(True)
        main_layout.addWidget(self.controls_area)

        self.controls_widget = QtWidgets.QWidget()
        self.controls_layout = QtWidgets.QFormLayout(self.controls_widget)
        self.controls_area.setWidget(self.controls_widget)

    def create_rig(self):
        preset = self.preset_combo.currentText()
        try:
            self.build_light_rig(preset)
            hou.ui.displayMessage(f"{preset} rig created successfully!")
            self.populate_controls()
        except Exception as e:
            hou.ui.displayMessage(f"Error creating rig:\n{e}")

    def build_light_rig(self, preset):
        obj = hou.node("/obj")
        if not obj:
            raise RuntimeError("/obj context not found.")

        rig_name = preset.lower().replace(" ", "_") + "_rig"
        existing = hou.node(f"/obj/{rig_name}")
        if existing:
            existing.destroy()
        rig = obj.createNode("subnet", rig_name)

        if preset == "3-Point Lighting":
            self.create_light_with_controls(rig, "key_light", (5, 5, 5), 1.0)
            self.create_light_with_controls(rig, "fill_light", (-5, 2, 5), 0.6)
            self.create_light_with_controls(rig, "back_light", (0, 5, -5), 0.8)
        elif preset == "Cinematic Lighting":
            self.create_light_with_controls(rig, "key_light", (6, 4, 7), 1.2)
            self.create_light_with_controls(rig, "fill_light", (-6, 3, 4), 0.5)
            self.create_light_with_controls(rig, "rim_light", (0, 7, -6), 1.0)
            self.create_light_with_controls(rig, "ambient_light", (0, 8, 0), 0.3, light_type="ambient")
        elif preset == "Simple Key Fill":
            self.create_light_with_controls(rig, "key_light", (4, 4, 4), 1.0)
            self.create_light_with_controls(rig, "fill_light", (-4, 2, 4), 0.5)
        elif preset == "Rembrandt Lighting":
            self.create_light_with_controls(rig, "key_light", (7, 6, 5), 1.0)
            self.create_light_with_controls(rig, "fill_light", (-7, 1, 5), 0.4)
            self.create_light_with_controls(rig, "back_light", (0, 7, -7), 0.6)
        else:
            raise ValueError(f"Unknown preset: {preset}")

        rig.layoutChildren()
        rig.setDisplayFlag(True)
        self.rig = rig

    def create_light_with_controls(self, parent_node, name, position, intensity, light_type="point"):
        light_node = parent_node.createNode("hlight", name)
        light_node.parm("light_type").set(light_type)
        light_node.parmTuple("t").set(position)

        intensity_parm = light_node.parm("intensity")
        if intensity_parm:
            intensity_parm.set(intensity)

        # Create or get subnet parm group
        parm_group = parent_node.parmTemplateGroup()

        folder_name = f"{name}_controls"
        if not any(pt.name() == folder_name for pt in parm_group.entries()):
            folder = hou.FolderParmTemplate(folder_name, f"{name} Controls")

            intensity_parm_template = hou.FloatParmTemplate(
                f"{name}_intensity", "Intensity", 1,
                default_value=(intensity,), min=0.0)
            folder.addParmTemplate(intensity_parm_template)

            color_parm_template = hou.FloatParmTemplate(
                f"{name}_color", "Color", 3,
                default_value=(1.0, 1.0, 1.0), min=0.0, max=1.0)
            folder.addParmTemplate(color_parm_template)

            parm_group.append(folder)
            parent_node.setParmTemplateGroup(parm_group)

        intensity_sub_parm = parent_node.parm(f"{name}_intensity")
        if intensity_sub_parm and intensity_parm:
            intensity_parm.setExpression(f'ch("../{parent_node.name()}/{name}_intensity")')

        color_sub_parm = parent_node.parmTuple(f"{name}_color")
        light_color_parm = light_node.parmTuple("light_color")

        if color_sub_parm and light_color_parm:
            for i in range(3):
                channel_parm = light_color_parm[i]
                if channel_parm:
                    channel_parm.setExpression(f'ch("../{parent_node.name()}/{name}_color{i}")')

    def populate_controls(self):
        # Clear previous controls
        while self.controls_layout.count():
            item = self.controls_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self.rig:
            return

        parm_group = self.rig.parmTemplateGroup()

        # We'll keep track of controls so we can update parms on change
        self.control_widgets = {}

        for folder in parm_group.entries():
            if isinstance(folder, hou.FolderParmTemplate):
                folder_name = folder.name()
                # For each parm in folder
                for parm in folder.parmTemplates():
                    parm_name = parm.name()
                    label = parm.label()
                    if parm.type() == hou.parmTemplateType.Float:
                        if parm.numComponents() == 1:
                            # Single float slider
                            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
                            slider.setMinimum(0)
                            slider.setMaximum(1000)  # scale to 0.0 - 1.0 or more
                            slider.setSingleStep(1)
                            slider.setPageStep(10)
                            slider.setTracking(True)
                            # Get current value from subnet parm
                            subnet_parm = self.rig.parm(parm_name)
                            if subnet_parm:
                                val = subnet_parm.eval()
                                slider.setValue(int(val * 1000))

                            slider.valueChanged.connect(
                                lambda val, p=parm_name: self.on_slider_changed(p, val / 1000.0))
                            self.controls_layout.addRow(label, slider)
                            self.control_widgets[parm_name] = slider

                        elif parm.numComponents() == 3:
                            # Color RGB sliders
                            # Create a horizontal layout with 3 sliders
                            h_layout = QtWidgets.QHBoxLayout()
                            sliders = []
                            for i in range(3):
                                s = QtWidgets.QSlider(QtCore.Qt.Horizontal)
                                s.setMinimum(0)
                                s.setMaximum(1000)
                                s.setSingleStep(1)
                                s.setPageStep(10)
                                s.setTracking(True)

                                # Current value from subnet parm
                                subnet_parm = self.rig.parmTuple(parm_name)
                                if subnet_parm:
                                    val = subnet_parm.eval()[i]
                                    s.setValue(int(val * 1000))

                                def make_callback(p=parm_name, idx=i):
                                    return lambda val: self.on_color_slider_changed(p, idx, val / 1000.0)

                                s.valueChanged.connect(make_callback())
                                h_layout.addWidget(s)
                                sliders.append(s)
                            self.controls_layout.addRow(label, h_layout)
                            self.control_widgets[parm_name] = sliders

    def on_slider_changed(self, parm_name, value):
        if not self.rig:
            return
        parm = self.rig.parm(parm_name)
        if parm:
            parm.set(value)

    def on_color_slider_changed(self, parm_name, index, value):
        if not self.rig:
            return
        parm_tuple = self.rig.parmTuple(parm_name)
        if parm_tuple:
            vals = list(parm_tuple.eval())
            vals[index] = value
            parm_tuple.set(vals)


def show_ui():
    global _light_rig_ui
    try:
        _light_rig_ui.close()
        _light_rig_ui.deleteLater()
    except:
        pass
    _light_rig_ui = LightRigBuilderUI()
    _light_rig_ui.show()


try:
    show_ui()
except Exception as e:
    import hou
    hou.ui.displayMessage(f"Error launching Light Rig UI:\n{e}")
