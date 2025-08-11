from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtWidgets import QInputDialog
import hou

camera_selector_window = None


class CameraSelectorUI(QtWidgets.QWidget):
    """
    UI tool for selecting Alembic cameras, render, matte, and geolight nodes in Houdini,
    and generating a corresponding LOP network under /stage.
    """

    def __init__(self, parent=None):
        super(CameraSelectorUI, self).__init__(parent)
        self.setWindowTitle("Alembic Camera, Render, Matte & GeoLight Node Selector")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.resize(650, 550)

        # Layouts
        self.layout = QtWidgets.QVBoxLayout(self)
        button_layout = QtWidgets.QHBoxLayout()
        bottom_button_layout = QtWidgets.QHBoxLayout()

        # Buttons for node selection
        self.select_camera_button = QtWidgets.QPushButton("Camera")
        self.select_camera_button.setObjectName("SelectCamera")
        self.select_camera_button.clicked.connect(self.on_select_camera)
        button_layout.addWidget(self.select_camera_button)

        self.get_render_nodes_button = QtWidgets.QPushButton("Render")
        self.get_render_nodes_button.setObjectName("RenderNode")
        self.get_render_nodes_button.clicked.connect(self.on_get_render_nodes)
        button_layout.addWidget(self.get_render_nodes_button)

        self.get_matte_nodes_button = QtWidgets.QPushButton("Matte")
        self.get_matte_nodes_button.setObjectName("MatteNode")
        self.get_matte_nodes_button.clicked.connect(self.on_get_matte_nodes)
        button_layout.addWidget(self.get_matte_nodes_button)

        self.get_geolight_nodes_button = QtWidgets.QPushButton("GeoLight")
        self.get_geolight_nodes_button.setObjectName("GeoLightNode")
        self.get_geolight_nodes_button.clicked.connect(self.on_get_geolight_nodes)
        button_layout.addWidget(self.get_geolight_nodes_button)

        # Node list display
        self.node_list = QtWidgets.QListWidget()
        self.layout.addLayout(button_layout)
        self.layout.addWidget(self.node_list)

        # Bottom buttons
        self.generate_lop_button = QtWidgets.QPushButton("Generate LOP")
        self.generate_lop_button.setObjectName("GenerateLOP")
        self.generate_lop_button.clicked.connect(self.on_generate_lop)
        bottom_button_layout.addWidget(self.generate_lop_button)

        self.reset_button = QtWidgets.QPushButton("Reset")
        self.reset_button.setObjectName("Reset")
        self.reset_button.clicked.connect(self.on_reset)
        bottom_button_layout.addWidget(self.reset_button)

        self.layout.addLayout(bottom_button_layout)

        # Status label
        self.status_label = QtWidgets.QLabel("")
        self.layout.addWidget(self.status_label)

        # StyleSheet for colors and layout
        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #e0e0e0;
                border-radius: 4px;
                font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
            }
            QPushButton {
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 110px;
                font-weight: 500;
                transition: background-color 0.3s ease, box-shadow 0.3s ease;
            }
            QPushButton#SelectCamera {
                background-color: #2196F3;
                color: #fff;
                box-shadow: 0 2px 6px rgba(33, 150, 243, 0.5);
            }
            QPushButton#SelectCamera:hover {
                background-color: #1976D2;
                box-shadow: 0 4px 12px rgba(25, 118, 210, 0.7);
            }
            QPushButton#RenderNode {
                background-color: #4CAF50;
                color: #fff;
                box-shadow: 0 2px 6px rgba(76, 175, 80, 0.5);
            }
            QPushButton#RenderNode:hover {
                background-color: #388E3C;
                box-shadow: 0 4px 12px rgba(56, 142, 60, 0.7);
            }
            QPushButton#MatteNode {
                background-color: #9E9E9E;
                color: #fff;
                box-shadow: 0 2px 6px rgba(158, 158, 158, 0.5);
            }
            QPushButton#MatteNode:hover {
                background-color: #757575;
                box-shadow: 0 4px 12px rgba(117, 117, 117, 0.7);
            }
            QPushButton#GeoLightNode {
                background-color: #FF7043;
                color: #fff;
                box-shadow: 0 2px 6px rgba(255, 112, 67, 0.5);
            }
            QPushButton#GeoLightNode:hover {
                background-color: #F4511E;
                box-shadow: 0 4px 12px rgba(244, 81, 30, 0.7);
            }
            QPushButton#GenerateLOP {
                background-color: #FFFFFF;
                color: #000000;
                min-width: 150px;
                font-weight: 600;
                box-shadow: 0 2px 8px rgba(255, 255, 255, 0.9);
                transition: background-color 0.3s ease, box-shadow 0.3s ease;
            }
            QPushButton#GenerateLOP:hover {
                background-color: #F0F0F0;
                box-shadow: 0 4px 16px rgba(240, 240, 240, 1);
            }
            QPushButton#Reset {
                background-color: #E53935;
                color: #fff;
                box-shadow: 0 2px 6px rgba(229, 57, 53, 0.5);
                transition: background-color 0.3s ease, box-shadow 0.3s ease;
            }
            QPushButton#Reset:hover {
                background-color: #B71C1C;
                box-shadow: 0 4px 12px rgba(183, 28, 28, 0.7);
            }
            QListWidget {
                background-color: #1E1E1E;
                border: 1px solid #444444;
                padding: 6px;
                border-radius: 4px;
                selection-background-color: #424242;
                selection-color: #FFFFFF;
            }
            QListWidget::item:selected {
                background-color: #424242;
                color: #FFFFFF;
            }
            QLabel {
                color: #CCCCCC;
            }
        """)

        # Stored node paths by category
        self.camera_nodes = []
        self.render_nodes = []
        self.matte_nodes = []
        self.geolight_nodes = []

        self.generated_count = 0

    def update_display(self):
        """Update the QListWidget with current selected nodes grouped by category."""
        self.node_list.clear()

        def add_header(text):
            item = QtWidgets.QListWidgetItem(text)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsSelectable)
            self.node_list.addItem(item)

        add_header("Camera Node(s):")
        for cam in self.camera_nodes or ["(none)"]:
            item = QtWidgets.QListWidgetItem(cam)
            item.setForeground(QtGui.QColor("#a3d9ff"))
            self.node_list.addItem(item)

        add_header("Render Node(s):")
        for ren in self.render_nodes or ["(none)"]:
            item = QtWidgets.QListWidgetItem(ren)
            item.setForeground(QtGui.QColor("#90ee90"))
            self.node_list.addItem(item)

        add_header("Matte Node(s):")
        for matte in self.matte_nodes or ["(none)"]:
            item = QtWidgets.QListWidgetItem(matte)
            item.setForeground(QtGui.QColor("#d3d3d3"))
            self.node_list.addItem(item)

        add_header("GeoLight Node(s):")
        for light in self.geolight_nodes or ["(none)"]:
            item = QtWidgets.QListWidgetItem(light)
            item.setForeground(QtGui.QColor("#ffbb99"))
            self.node_list.addItem(item)

    def on_select_camera(self):
        """Recursively find and store all camera nodes under the first selected node."""
        selected_nodes = hou.selectedNodes()
        if not selected_nodes:
            self.status_label.setText("❌ No node selected.")
            return
        root = selected_nodes[0]
        cameras = []

        def recursive_search(node):
            if node.type().name() == "cam":
                cameras.append(node.path())
            for child in node.children():
                recursive_search(child)

        recursive_search(root)
        self.camera_nodes = cameras
        self.status_label.setText(f"✅ Found {len(cameras)} camera node(s) under {root.path()}")
        self.update_display()

    def on_get_render_nodes(self):
        """Store currently selected nodes as Render nodes."""
        selected_nodes = hou.selectedNodes()
        if not selected_nodes:
            self.status_label.setText("❌ No node selected.")
            return
        self.render_nodes = [node.path() for node in selected_nodes]
        self.status_label.setText(f"✅ Stored {len(self.render_nodes)} render node(s)")
        self.update_display()

    def on_get_matte_nodes(self):
        """Store currently selected nodes as Matte nodes."""
        selected_nodes = hou.selectedNodes()
        if not selected_nodes:
            self.status_label.setText("❌ No node selected.")
            return
        self.matte_nodes = [node.path() for node in selected_nodes]
        self.status_label.setText(f"✅ Stored {len(self.matte_nodes)} matte node(s)")
        self.update_display()

    def on_get_geolight_nodes(self):
        """Store currently selected nodes as GeoLight nodes."""
        selected_nodes = hou.selectedNodes()
        if not selected_nodes:
            self.status_label.setText("❌ No node selected.")
            return
        self.geolight_nodes = [node.path() for node in selected_nodes]
        self.status_label.setText(f"✅ Stored {len(self.geolight_nodes)} GeoLight node(s)")
        self.update_display()

    def on_reset(self):
        """Clear all stored node paths and reset UI."""
        self.camera_nodes.clear()
        self.render_nodes.clear()
        self.matte_nodes.clear()
        self.geolight_nodes.clear()
        self.node_list.clear()
        self.status_label.setText("🔄 Reset completed.")

    def on_generate_lop(self):
        """
        Create LOP network nodes under /stage based on stored node paths.
        Asks user for Karma Render Settings node name.
        """
        def get_unique_name(stage, base_name):
            count = 1
            name = base_name
            while stage.node(name):
                name = f"{base_name}_{count}"
                count += 1
            return name

        if not (self.camera_nodes or self.render_nodes or self.matte_nodes or self.geolight_nodes):
            self.status_label.setText("❌ No nodes stored to generate LOPs.")
            return

        stage = hou.node("/stage")
        if stage is None:
            self.status_label.setText("❌ /stage context not found.")
            return

        created_nodes = []
        scene_import = None

        # Create SceneImport node for cameras
        if self.camera_nodes:
            node_name = get_unique_name(stage, "SceneImportCamera")
            scene_import = stage.createNode("sceneimport", node_name)
            scene_import.parm("objects").set(" ".join(self.camera_nodes))
            scene_import.setColor(hou.Color((0.4, 0.7, 1.0)))
            created_nodes.append(scene_import)

        # Create SOP Import nodes for render nodes
        render_sop_nodes = []
        for path in self.render_nodes:
            base_name = path.split("/")[-1]
            node_name = get_unique_name(stage, base_name)
            sop_node = stage.createNode("sopimport", node_name)
            sop_node.parm("soppath").set(path)
            sop_node.parm("copycontents").set(2)
            sop_node.setColor(hou.Color((0.5, 1.0, 0.5)))
            render_sop_nodes.append(sop_node)
            created_nodes.append(sop_node)

        # Create SOP Import + RenderGeometrySettings for matte nodes
        matte_geom_settings_nodes = []
        for path in self.matte_nodes:
            base_name = path.split("/")[-1]
            sop_name = get_unique_name(stage, f"{base_name}_Matte")
            geom_name = get_unique_name(stage, f"{base_name}_GeoSettings")

            sop_node = stage.createNode("sopimport", sop_name)
            sop_node.parm("soppath").set(path)
            sop_node.parm("copycontents").set(2)
            sop_node.setColor(hou.Color((0.8, 0.8, 0.8)))

            geom_settings = stage.createNode("rendergeometrysettings", geom_name)
            geom_settings.setInput(0, sop_node)
            geom_settings.setColor(hou.Color((0.8, 0.8, 0.8)))

            primpattern_parm = geom_settings.parm("primpattern")
            if primpattern_parm:
                primpattern_parm.set("%type:Boundable")

            ctrl = geom_settings.parm("xn__primvarskarmaobjectholdoutmode_control_02bfg")
            mode = geom_settings.parm("xn__primvarskarmaobjectholdoutmode_zpbfg")
            if ctrl:
                ctrl.set("set")
            if mode:
                labels = mode.menuLabels()
                items = mode.menuItems()
                if "Matte" in labels:
                    mode.set(items[labels.index("Matte")])

            created_nodes.extend([sop_node, geom_settings])
            matte_geom_settings_nodes.append(geom_settings)

        # Create SOP Import + RenderGeometrySettings for geolight nodes
        geolight_geom_settings_nodes = []
        for path in self.geolight_nodes:
            base_name = path.split("/")[-1]
            sop_name = get_unique_name(stage, f"{base_name}_GeoLight")
            geom_name = get_unique_name(stage, f"{base_name}_GeoLightSettings")

            sop_node = stage.createNode("sopimport", sop_name)
            sop_node.parm("soppath").set(path)
            sop_node.parm("copycontents").set(2)
            sop_node.setColor(hou.Color((1.0, 0.6, 0.4)))

            geom_settings = stage.createNode("rendergeometrysettings", geom_name)
            geom_settings.setInput(0, sop_node)
            geom_settings.setColor(hou.Color((1.0, 0.6, 0.4)))

            primpattern_parm = geom_settings.parm("primpattern")
            if primpattern_parm:
                primpattern_parm.set("%type:Boundable")

            treat_ctrl = geom_settings.parm("xn__primvarskarmaobjecttreat_as_lightsource_control_oicfg")
            treat_toggle = geom_settings.parm("xn__primvarskarmaobjecttreat_as_lightsource_n4bfg")
            if treat_ctrl and treat_toggle:
                treat_ctrl.set("set")
                treat_toggle.set(1)

            geolight_geom_settings_nodes.append(geom_settings)
            created_nodes.extend([sop_node, geom_settings])

        # Merge Matte nodes
        matte_merge = None
        if matte_geom_settings_nodes:
            merge_name = get_unique_name(stage, "MatteMerge")
            matte_merge = stage.createNode("merge", merge_name)
            for i, node in enumerate(matte_geom_settings_nodes):
                matte_merge.setInput(i, node)
            matte_merge.setColor(hou.Color((0.6, 0.6, 0.6)))
            created_nodes.append(matte_merge)

        # Merge GeoLight nodes
        geolight_merge = None
        if geolight_geom_settings_nodes:
            merge_name = get_unique_name(stage, "GeoLightMerge")
            geolight_merge = stage.createNode("merge", merge_name)
            for i, node in enumerate(geolight_geom_settings_nodes):
                geolight_merge.setInput(i, node)
            geolight_merge.setColor(hou.Color((1.0, 0.6, 0.4)))
            created_nodes.append(geolight_merge)

        # Final Merge All node
        merge_name = get_unique_name(stage, "MergeAll")
        merge_node = stage.createNode("merge", merge_name)
        idx = 0
        if scene_import:
            merge_node.setInput(idx, scene_import)
            idx += 1
        for node in render_sop_nodes:
            merge_node.setInput(idx, node)
            idx += 1
        if matte_merge:
            merge_node.setInput(idx, matte_merge)
            idx += 1
        if geolight_merge:
            merge_node.setInput(idx, geolight_merge)
            idx += 1

        merge_node.setColor(hou.Color((1.0, 1.0, 1.0)))
        created_nodes.append(merge_node)

        # Ask user for Karma Render Settings node name
        custom_name, ok = QInputDialog.getText(
            self,
            "Karma Node Name",
            "Enter name for Karma Render Settings node:",
            QtWidgets.QLineEdit.Normal,
            "KarmaRenderSettings"
        )
        if not ok or not custom_name.strip():
            self.status_label.setText("❌ Node creation cancelled. No Karma node name provided.")
            return
        karma_name = custom_name.strip()

        karma_node = stage.createNode("karmarenderproperties", karma_name)
        karma_node.setInput(0, merge_node)
        karma_node.setPosition(merge_node.position() + hou.Vector2(0, -1.5))
        karma_node.setColor(hou.Color((1.0, 1.0, 1.0)))
        created_nodes.append(karma_node)

        usdrender_name = get_unique_name(stage, "usdrender_rop1")
        usdrender_node = stage.createNode("usdrender_rop", usdrender_name)
        usdrender_node.setInput(0, karma_node)
        usdrender_node.setPosition(karma_node.position() + hou.Vector2(0, -1.5))
        usdrender_node.setColor(hou.Color((1.0, 1.0, 1.0)))
        created_nodes.append(usdrender_node)

        stage.layoutChildren()
        usdrender_node.setSelected(True)
        self.status_label.setText(f"✅ Generated LOP network with {len(created_nodes)} nodes in /stage.")


def show_camera_selector():
    """Show the CameraSelectorUI window."""
    global camera_selector_window
    if camera_selector_window is None:
        camera_selector_window = CameraSelectorUI()
    camera_selector_window.show()
    camera_selector_window.raise_()
    camera_selector_window.activateWindow()


show_camera_selector()
