import hou
import os
import re
import sys
import subprocess
import toolutils
from PySide2 import QtWidgets, QtCore


# --------- Utilities --------- #

def get_ffmpeg_bin():
    pixellab = os.getenv("PIXELLAB")
    if not pixellab:
        raise hou.Error("PIXELLAB environment variable not set.")
    ffmpeg = os.path.join(pixellab, "ffmpeg", "bin", "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not os.path.exists(ffmpeg):
        raise hou.Error(f"FFmpeg not found:\n{ffmpeg}")
    return ffmpeg


def find_next_version(base_folder):
    if not os.path.exists(base_folder):
        return "V001"
    versions = [v for v in os.listdir(base_folder) if re.match(r"V\d{3}", v)]
    if not versions:
        return "V001"
    versions.sort()
    last = versions[-1]
    next_num = int(last[1:]) + 1
    return f"V{next_num:03}"


# --------- Dialog --------- #

class FlipbookDialog(QtWidgets.QDialog):
    def __init__(self, start="1001", end="1100", version="V001", parent=None):
        super(FlipbookDialog, self).__init__(parent)
        self.setWindowTitle("Viewport Flipbook Settings")
        self.setFixedWidth(300)

        layout = QtWidgets.QFormLayout(self)

        self.start_edit = QtWidgets.QLineEdit(start)
        self.end_edit = QtWidgets.QLineEdit(end)
        self.version_edit = QtWidgets.QLineEdit(version)
        self.open_checkbox = QtWidgets.QCheckBox("Open MP4 After Render")
        self.open_checkbox.setChecked(False)

        layout.addRow("Start Frame:", self.start_edit)
        layout.addRow("End Frame:", self.end_edit)
        layout.addRow("Version:", self.version_edit)
        layout.addRow("", self.open_checkbox)

        btn_layout = QtWidgets.QHBoxLayout()
        self.ok_btn = QtWidgets.QPushButton("Flipbook")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addRow(btn_layout)

        self.ok_btn.clicked.connect(self.validate_and_accept)
        self.cancel_btn.clicked.connect(self.reject)

    def validate_and_accept(self):
        if not (self.start_edit.text().isdigit() and self.end_edit.text().isdigit()):
            QtWidgets.QMessageBox.warning(self, "Invalid Input", "Start and End must be integers.")
            return
        if not self.version_edit.text().strip():
            QtWidgets.QMessageBox.warning(self, "Invalid Input", "Version cannot be empty.")
            return
        self.accept()

    def get_values(self):
        return (
            int(self.start_edit.text()),
            int(self.end_edit.text()),
            self.version_edit.text().strip(),
            self.open_checkbox.isChecked()
        )


# --------- Main --------- #

def main():
    # Prepare context
    hipfile = hou.hipFile.path()
    if not hipfile:
        raise hou.Error("Please save your scene before flipbooking.")
    hip_name = os.path.splitext(os.path.basename(hipfile))[0]
    hip_dir = os.path.dirname(hipfile)
    flipbook_dir = os.path.join(hip_dir, "Flipbooks")
    version_guess = find_next_version(flipbook_dir)

    start, end = hou.playbar.frameRange()
    default_start = str(int(start))
    default_end = str(int(end))

    # Create dialog
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])  # Only needed outside Houdini

    dialog = FlipbookDialog(start=default_start, end=default_end, version=version_guess)
    if not dialog.exec_():
        return  # Cancelled

    start_frame, end_frame, version_str, open_after = dialog.get_values()

    # Scene Viewer & Camera
    viewer = toolutils.sceneViewer()
    viewport = viewer.curViewport()
    camera = viewport.camera()
    if not camera:
        raise hou.Error("Please lock a camera to the viewport.")

    resx = int(camera.parm("resx").eval())
    resy = int(camera.parm("resy").eval())

    # Setup output
    version_folder = os.path.join(flipbook_dir, version_str)
    os.makedirs(version_folder, exist_ok=True)
    image_pattern = os.path.join(version_folder, f"{hip_name}_{version_str}.$F4.exr")

    # Flipbook settings
    settings = viewer.flipbookSettings()
    settings.stash()
    settings.output(image_pattern)
    settings.frameRange((start_frame, end_frame))
    settings.useResolution(True)
    settings.resolution((resx, resy))

    settings.useMotionBlur(False)
    settings.cropOutMaskOverlay(True)

    viewer.flipbook(viewport, settings)

    # MP4 render via ffmpeg
    try:
        ffmpeg = get_ffmpeg_bin()

        mp4_dir = os.path.normpath(os.path.join(flipbook_dir, "mp4"))
        os.makedirs(mp4_dir, exist_ok=True)

        exr_seq = os.path.normpath(os.path.join(version_folder, f"{hip_name}_{version_str}.%04d.exr"))
        mp4_path = os.path.normpath(os.path.join(mp4_dir, f"{hip_name}.{version_str}.mp4"))

        cmd = [
            ffmpeg,
            "-y",
            "-start_number", str(start_frame),
            "-framerate", "24",
            "-i", exr_seq,
            "-c:v", "libx264",
            "-preset", "veryslow",
            "-crf", "0",  # Lossless CRF
            "-pix_fmt", "yuv444p",  # Full chroma (optional, if source supports it)
            mp4_path
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            raise hou.Error("FFmpeg failed:\n" + result.stderr.decode())

        if open_after:
            if sys.platform == "win32":
                os.startfile(mp4_path)
            elif sys.platform == "darwin":
                subprocess.call(["open", mp4_path])
            else:
                subprocess.call(["xdg-open", mp4_path])

    except Exception as e:
        hou.ui.displayMessage(f"Flipbook succeeded, but MP4 creation failed:\n{e}")


main()
