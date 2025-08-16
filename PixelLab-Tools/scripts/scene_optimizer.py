from PySide2 import QtWidgets, QtCore
import hou

class SceneOptimizerUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Houdini Scene Optimizer")
        self.setMinimumSize(400, 300)

        layout = QtWidgets.QVBoxLayout(self)

        self.delete_unused_nodes_cb = QtWidgets.QCheckBox("Delete Unused Nodes (no outputs, no flags)")
        self.delete_unused_nodes_cb.setChecked(True)

        self.delete_unused_materials_cb = QtWidgets.QCheckBox("Delete Unused Materials (/shop)")
        self.delete_unused_materials_cb.setChecked(True)

        self.clear_geometry_caches_cb = QtWidgets.QCheckBox("Clear Geometry Caches (cachepath parm)")
        self.clear_geometry_caches_cb.setChecked(True)

        self.clean_display_flags_cb = QtWidgets.QCheckBox("Clean Display & Render Flags on Subnet Nodes")
        self.clean_display_flags_cb.setChecked(True)

        self.delete_nulls_cb = QtWidgets.QCheckBox("Delete Null Nodes with No Connections")
        self.delete_nulls_cb.setChecked(False)

        self.freeze_animated_cb = QtWidgets.QCheckBox("Freeze Animated Parameters (disable keyframes)")
        self.freeze_animated_cb.setChecked(False)

        layout.addWidget(self.delete_unused_nodes_cb)
        layout.addWidget(self.delete_unused_materials_cb)
        layout.addWidget(self.clear_geometry_caches_cb)
        layout.addWidget(self.clean_display_flags_cb)
        layout.addWidget(self.delete_nulls_cb)
        layout.addWidget(self.freeze_animated_cb)

        self.run_btn = QtWidgets.QPushButton("Run Optimization")
        layout.addWidget(self.run_btn)

        self.output_text = QtWidgets.QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)

        self.run_btn.clicked.connect(self.run_optimization)

    def log(self, msg):
        self.output_text.append(msg)
        print(msg)

    def node_has_display_or_render_flag(self, node):
        if hasattr(node, "isDisplayFlagSet") and hasattr(node, "isRenderFlagSet"):
            if node.isDisplayFlagSet() or node.isRenderFlagSet():
                return True
        for child in node.children():
            if hasattr(child, "isDisplayFlagSet") and hasattr(child, "isRenderFlagSet"):
                if child.isDisplayFlagSet() or child.isRenderFlagSet():
                    return True
        return False

    def run_optimization(self):
        self.output_text.clear()
        self.log("Starting Houdini Scene Optimization...\n")

        deleted_nodes = []
        deleted_materials = []
        cleared_caches = []
        cleaned_flags = []

        obj = hou.node("/obj")
        if not obj:
            self.log("No /obj context found. Aborting.")
            return

        # 1. Delete unused nodes safely
        if self.delete_unused_nodes_cb.isChecked():
            self.log("Deleting unused nodes...")
            nodes_to_delete = []
            for node in obj.allSubChildren():
                if node.isInsideLockedHDA():
                    continue
                if len(node.outputs()) == 0 and not self.node_has_display_or_render_flag(node):
                    nodes_to_delete.append(node)

            for node in nodes_to_delete:
                try:
                    path = node.path()
                    node.destroy()
                    deleted_nodes.append(path)
                except Exception as e:
                    self.log(f"Failed to delete {node.path()}: {e}")

        # 2. Delete unused materials
        if self.delete_unused_materials_cb.isChecked():
            self.log("Deleting unused materials...")
            shop = hou.node("/shop")
            if shop:
                for mat in shop.children():
                    refs = hou.parmReferences(mat)
                    if not refs:
                        try:
                            path = mat.path()
                            mat.destroy()
                            deleted_materials.append(path)
                        except Exception as e:
                            self.log(f"Failed to delete material {mat.path()}: {e}")
            else:
                self.log("No /shop context found.")

        # 3. Clear geometry caches
        if self.clear_geometry_caches_cb.isChecked():
            self.log("Clearing geometry caches...")
            for geo_node in obj.children():
                if geo_node.type().name() == "geo":
                    cache_parm = geo_node.parm("cachepath")
                    if cache_parm:
                        cache_path = cache_parm.eval()
                        if cache_path:
                            try:
                                cache_parm.deleteAllKeyframes()
                                cache_parm.set("")
                                cleared_caches.append(geo_node.path())
                            except Exception as e:
                                self.log(f"Failed clearing cache on {geo_node.path()}: {e}")

        # 4. Clean display/render flags on subnet nodes
        if self.clean_display_flags_cb.isChecked():
            self.log("Cleaning display/render flags on subnet nodes...")
            for node in obj.allSubChildren():
                if node.isInsideLockedHDA():
                    continue
                if node.type().name() == "subnet":
                    for child in node.children():
                        if hasattr(child, "isDisplayFlagSet") and child.isDisplayFlagSet():
                            child.setDisplayFlag(False)
                            cleaned_flags.append(f"Removed display flag from {child.path()}")
                        if hasattr(child, "isRenderFlagSet") and child.isRenderFlagSet():
                            child.setRenderFlag(False)
                            cleaned_flags.append(f"Removed render flag from {child.path()}")

        # 5. Delete null nodes with no connections safely
        if self.delete_nulls_cb.isChecked():
            self.log("Deleting null nodes with no connections...")
            nulls_to_delete = []
            for node in obj.allSubChildren():
                if node.isInsideLockedHDA():
                    continue
                if node.type().name() == "null":
                    if not node.inputs() and not node.outputs():
                        nulls_to_delete.append(node)

            for node in nulls_to_delete:
                try:
                    path = node.path()
                    node.destroy()
                    deleted_nodes.append(path)
                except Exception as e:
                    self.log(f"Failed to delete null node {node.path()}: {e}")

        # 6. Freeze animated parameters (delete keyframes)
        if self.freeze_animated_cb.isChecked():
            self.log("Freezing animated parameters...")
            for node in obj.allSubChildren():
                if node.isInsideLockedHDA():
                    continue
                for parm in node.parms():
                    if parm.isTimeDependent():
                        try:
                            val = parm.eval()
                            parm.deleteAllKeyframes()
                            parm.set(val)
                        except Exception as e:
                            self.log(f"Failed freezing parm {parm.name()} on {node.path()}: {e}")

        # Summary
        self.log("\nOptimization Complete.\n")
        self.log(f"Deleted Nodes: {len(deleted_nodes)}")
        self.log(f"Deleted Materials: {len(deleted_materials)}")
        self.log(f"Cleared Geometry Caches: {len(cleared_caches)}")
        self.log(f"Cleaned Flags: {len(cleaned_flags)}")

        if deleted_nodes:
            self.log("\nNodes deleted:\n" + "\n".join(deleted_nodes))
        if deleted_materials:
            self.log("\nMaterials deleted:\n" + "\n".join(deleted_materials))
        if cleared_caches:
            self.log("\nGeometry caches cleared on:\n" + "\n".join(cleared_caches))
        if cleaned_flags:
            self.log("\nFlags cleaned:\n" + "\n".join(cleaned_flags))


def show_optimizer():
    global _optimizer_ui
    try:
        _optimizer_ui.close()
        _optimizer_ui.deleteLater()
    except:
        pass
    _optimizer_ui = SceneOptimizerUI()
    _optimizer_ui.show()

try:
    show_optimizer()
except Exception as e:
    hou.ui.displayMessage(f"Error launching Scene Optimizer:\n{e}")
