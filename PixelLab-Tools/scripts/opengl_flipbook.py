import hou
import os
import re
import subprocess
import sys
from PySide2 import QtWidgets, QtCore

def get_ffmpeg_bin():
    pixellab = os.getenv("PIXELLAB")
    if not pixellab:
        raise hou.Error("Environment variable PIXELLAB is not set.")
    ffmpeg = os.path.join(pixellab, "ffmpeg", "bin", "ffmpeg.exe")
    if not os.path.exists(ffmpeg):
        raise hou.Error(f"ffmpeg.exe not found at:\n{ffmpeg}")
    return ffmpeg

def find_next_version(base_folder):
    if not os.path.exists(base_folder):
        return "V001"
    versions = [entry for entry in os.listdir(base_folder)
                if os.path.isdir(os.path.join(base_folder, entry)) and re.match(r"V\d{3}", entry)]
    if not versions:
        return "V001"
    versions.sort()
    last_version = versions[-1]
    next_version_number = int(last_version[1:]) + 1
    return f"V{next_version_number:03}"

class FlipbookDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, start="1001", end="1100", version="V001"):
        super().__init__(parent)
        self.setWindowTitle("Flipbook Parameters")
        self.setFixedWidth(300)

        form_layout = QtWidgets.QFormLayout(self)

        self.start_edit = QtWidgets.QLineEdit(start)
        self.end_edit = QtWidgets.QLineEdit(end)
        self.version_edit = QtWidgets.QLineEdit(version)
        self.open_checkbox = QtWidgets.QCheckBox("Open MP4 after render")
        self.open_checkbox.setChecked(False)  # Default to OFF

        form_layout.addRow("Start Frame:", self.start_edit)
        form_layout.addRow("End Frame:", self.end_edit)
        form_layout.addRow("Version:", self.version_edit)
        form_layout.addRow("", self.open_checkbox)

        button_layout = QtWidgets.QHBoxLayout()
        self.flipbook_button = QtWidgets.QPushButton("Flipbook")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        button_layout.addWidget(self.flipbook_button)
        button_layout.addWidget(self.cancel_button)

        form_layout.addRow(button_layout)

        self.flipbook_button.clicked.connect(self.validate_and_accept)
        self.cancel_button.clicked.connect(self.reject)

    def validate_and_accept(self):
        if not self.start_edit.text().isdigit() or not self.end_edit.text().isdigit():
            QtWidgets.QMessageBox.warning(self, "Invalid Input", "Start and End frames must be integers.")
            return
        if not self.version_edit.text().strip():
            QtWidgets.QMessageBox.warning(self, "Invalid Input", "Version cannot be empty.")
            return
        self.accept()

    def get_values(self):
        return (
            self.start_edit.text(),
            self.end_edit.text(),
            self.version_edit.text().strip(),
            self.open_checkbox.isChecked()
        )

def open_sequence_in_mplay(first_frame_path, total_frames):
    match = re.match(r"(.*?)(\d+)\.exr$", os.path.basename(first_frame_path))
    if not match:
        hou.ui.displayMessage("Invalid EXR filename format.")
        return

    prefix, frame_str = match.groups()
    start_frame = int(frame_str)
    end_frame = start_frame + total_frames - 1
    padding = len(frame_str)

    sequence_pattern = f"{prefix}$F{padding}.exr"
    directory = os.path.dirname(first_frame_path)
    full_pattern = os.path.join(directory, sequence_pattern)

    mplay_path = os.path.join(hou.getenv("HFS"), "bin", "mplay")

    try:
        # Pass start, end, and step ('1') as separate arguments after '-f'
        subprocess.Popen([mplay_path, "-f", str(start_frame), str(end_frame), "1", full_pattern])
    except Exception as e:
        hou.ui.displayMessage(f"Could not launch MPlay:\n{str(e)}")


def main():
    ffmpeg_bin = get_ffmpeg_bin()

    hipfile = hou.hipFile.path()
    hip = os.path.dirname(hipfile)
    hip_name = os.path.splitext(os.path.basename(hipfile))[0]

    base = os.path.join(hip, "Flipbooks")
    version_guess = find_next_version(base)

    start, end = hou.playbar.frameRange()
    default_start = str(int(start))
    default_end = str(int(end))

    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])

    dialog = FlipbookDialog(start=default_start, end=default_end, version=version_guess)
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return  # silently exit if user cancels

    start_f_str, end_f_str, user_version, open_after = dialog.get_values()
    start_f = int(start_f_str)
    end_f = int(end_f_str)

    exr_folder = os.path.join(base, user_version)
    os.makedirs(exr_folder, exist_ok=True)

    viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if not viewer:
        raise hou.Error("No Scene Viewer found.")
    viewport = viewer.curViewport()
    camera = viewport.camera()
    if not camera:
        raise hou.Error("Lock a camera to the viewport before running the script.")

    resx = int(camera.parm("resx").eval())
    resy = int(camera.parm("resy").eval())

    # Create temporary OpenGL ROP
    rop = hou.node("/out").createNode("opengl", node_name="temp_flipbook")
    exr_pattern = os.path.join(exr_folder, f"{hip_name}_{user_version}.$F4.exr")
    rop.setParms({
        "camera": camera.path(),
        "trange": 1,
        "f1": start_f,
        "f2": end_f,
        "f3": 1,
        "res1": resx,
        "res2": resy,
        "tres": True,
        "picture": exr_pattern,
        "alights": "",
        "aamode": 6,  # High quality AA
        "usehdr": 2   # HDR setting
    })

    if camera.parm("vm_background"):
        bg_image = camera.parm("vm_background").unexpandedString()
        if bg_image:
            rop.parm("bgimage").set(bg_image)
    if rop.parm("soho_initsim"):
        rop.parm("soho_initsim").set(True)

    rop.parm("execute").pressButton()
    rop.destroy()

    mp4_dir = os.path.join(base, "mp4")
    os.makedirs(mp4_dir, exist_ok=True)
    mp4_path = os.path.join(mp4_dir, f"{hip_name}.{user_version}.mp4")
    exr_input_pattern = os.path.join(exr_folder, f"{hip_name}_{user_version}.%04d.exr")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-start_number", str(start_f),
        "-framerate", "24",
        "-i", exr_input_pattern,
        "-c:v", "libx264",
        "-preset", "veryslow",
        "-crf", "0",
        "-pix_fmt", "yuv444p",
        mp4_path
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise hou.Error("FFmpeg conversion failed:\n" + result.stderr.decode())

    if open_after:
        try:
            if os.name == "nt":
                os.startfile(mp4_path.replace("/", "\\"))
            elif sys.platform == "darwin":
                subprocess.call(["open", mp4_path])
            else:
                subprocess.call(["xdg-open", mp4_path])
        except Exception as e:
            hou.ui.displayMessage(f"Rendered but could not open MP4:\n{str(e)}")

    # Open in MPlay by default
    first_frame_path = os.path.join(exr_folder, f"{hip_name}_{user_version}.{start_f:04d}.exr")
    open_sequence_in_mplay(first_frame_path, end_f - start_f + 1)

main()
