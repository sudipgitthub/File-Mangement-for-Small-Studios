import hou
import os
import subprocess
import sys

def open_hip_env_directory():
    hip_path = hou.getenv("HIP")

    if not hip_path or not os.path.isdir(hip_path):
        hou.ui.displayMessage("Invalid or unset $HIP path.")
        return

    # Normalize slashes for Windows
    hip_path = os.path.normpath(hip_path)

    try:
        if os.name == "nt":
            subprocess.Popen(f'explorer "{hip_path}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", hip_path])
        else:
            subprocess.Popen(["xdg-open", hip_path])
    except Exception as e:
        hou.ui.displayMessage(f"Failed to open $HIP directory:\n{str(e)}")

open_hip_env_directory()
