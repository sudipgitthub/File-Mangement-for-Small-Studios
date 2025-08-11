import hou
import os
from collections import defaultdict

def collect_file_references():
    sop_refs = defaultdict(set)
    lop_refs = defaultdict(set)

    for node in hou.node("/").allSubChildren():
        node_path = node.path()
        node_name = node.name()
        node_type = node.type().name()
        is_lop = node_path.startswith("/stage")

        for parm in node.parms():
            try:
                template = parm.parmTemplate()
                if template.type() != hou.parmTemplateType.String:
                    continue

                string_type = template.stringType()
                parm_name = parm.name().lower()

                is_file = string_type in [hou.stringParmType.FileReference, hou.stringParmType.NodeReference]
                is_likely_texture = any(x in parm_name for x in ['file', 'texture', 'map'])

                if not (is_file or is_likely_texture):
                    continue

                value = parm.eval()
                if value and not value.startswith("op:"):
                    resolved = os.path.normpath(hou.expandString(parm.unexpandedString()))
                    if os.path.isabs(resolved) and (os.path.exists(resolved) or os.path.splitext(resolved)[1]):
                        if is_lop:
                            lop_refs[node_name].add(resolved)
                        else:
                            sop_refs[node_name].add(resolved)

            except:
                continue

        # LOP special handling
        if is_lop and node_type in ["reference", "sublayer", "usdimport"]:
            for key in ["filepath1", "filepath"]:
                parm = node.parm(key)
                if parm:
                    try:
                        value = parm.eval()
                        if value:
                            resolved = os.path.normpath(hou.expandString(parm.unexpandedString()))
                            if os.path.isabs(resolved) and (os.path.exists(resolved) or os.path.splitext(resolved)[1]):
                                lop_refs[node_name].add(resolved)
                    except:
                        continue

    return sop_refs, lop_refs

# Ask user what to show
user_input = hou.ui.displayMessage(
    "What do you want to display?",
    buttons=["Only External Paths", "Show Node → Path Mapping"],
    default_choice=0,
    close_choice=0
)

sop_refs, lop_refs = collect_file_references()

if user_input == 0:
    # Only external paths
    all_paths = set()
    for paths in sop_refs.values():
        all_paths.update(paths)
    for paths in lop_refs.values():
        all_paths.update(paths)

    print("📂 External File Paths:\n")
    for path in sorted(all_paths):
        print(path)

else:
    # Detailed node → paths
    print("🟩 SOP File References:\n")
    for node_name, paths in sop_refs.items():
        print(f"▶ Node: {node_name}")
        for path in sorted(paths):
            print(f"   - {path}")
        print()

    print("🟦 LOP File References:\n")
    for node_name, paths in lop_refs.items():
        print(f"▶ Node: {node_name}")
        for path in sorted(paths):
            print(f"   - {path}")
        print()
