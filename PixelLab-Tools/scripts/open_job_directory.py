import hou
import os
import subprocess
import sys

def open_JOB_env_directory():
    JOB_path = hou.getenv("JOB")

    if not JOB_path or not os.path.isdir(JOB_path):
        hou.ui.displayMessage("Invalid or unset $JOB path.")
        return

    # Normalize slashes for Windows
    JOB_path = os.path.normpath(JOB_path)

    try:
        if os.name == "nt":
            subprocess.Popen(f'explorer "{JOB_path}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", JOB_path])
        else:
            subprocess.Popen(["xdg-open", JOB_path])
    except Exception as e:
        hou.ui.displayMessage(f"Failed to open $JOB directory:\n{str(e)}")

open_JOB_env_directory()
