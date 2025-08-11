import hou
import os
import subprocess
import sys

def open_HOME_env_directory():
    HOME_path = hou.getenv("HOME")

    if not HOME_path or not os.path.isdir(HOME_path):
        hou.ui.displayMessage("Invalid or unset $HOME path.")
        return

    # Normalize slashes for Windows
    HOME_path = os.path.normpath(HOME_path)

    try:
        if os.name == "nt":
            subprocess.Popen(f'explorer "{HOME_path}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", HOME_path])
        else:
            subprocess.Popen(["xdg-open", HOME_path])
    except Exception as e:
        hou.ui.displayMessage(f"Failed to open $HOME directory:\n{str(e)}")

open_HOME_env_directory()
