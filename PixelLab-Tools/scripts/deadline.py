import os
import re
import platform
import getpass
import subprocess
from PySide2 import QtWidgets, QtCore
from PySide2.QtCore import QDate, QDateTime
from PySide2.QtWidgets import QLabel

# ---------------------------
# Worker threads
# ---------------------------
class DeadlineJobLoader(QtCore.QThread):
    jobs_loaded = QtCore.Signal(list)  # list of job dicts
    error = QtCore.Signal(str)

    def __init__(self, deadline_cmd, user=None, parent=None):
        super().__init__(parent)
        self.deadline_cmd = deadline_cmd
        self.user = user

    def run(self):
        jobs = []
        try:
            args = [self.deadline_cmd, "GetJobs"]
            if self.user:
                args += ["-UserName", self.user]
            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out = result.stdout.strip() or result.stderr.strip()
            current_job = {}
            for line in out.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    current_job[k.strip()] = v.strip()
                elif not line.strip():  # blank line => job boundary
                    if current_job:
                        jobs.append(current_job.copy())
                        current_job.clear()
            if current_job:
                jobs.append(current_job.copy())
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.jobs_loaded.emit(jobs)


class JobInfoLoader(QtCore.QThread):
    info_loaded = QtCore.Signal(dict)
    error = QtCore.Signal(str)

    def __init__(self, deadline_cmd, job_id, parent=None):
        super().__init__(parent)
        self.deadline_cmd = deadline_cmd
        self.job_id = job_id

    def run(self):
        parsed = {}
        try:
            result = subprocess.run([self.deadline_cmd, "GetJob", self.job_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out = result.stdout.strip() or result.stderr.strip()
            for line in out.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    parsed[k.strip()] = v.strip()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.info_loaded.emit(parsed)


class CommandRunner(QtCore.QThread):
    finished_running = QtCore.Signal(str, bool, str)  # command, success, message

    def __init__(self, deadline_cmd, command, job_id, parent=None):
        super().__init__(parent)
        self.deadline_cmd = deadline_cmd
        self.command = command
        self.job_id = job_id

    def run(self):
        try:
            result = subprocess.run([self.deadline_cmd, self.command, self.job_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            success = result.returncode == 0
            msg = (result.stdout.strip() or result.stderr.strip())
            self.finished_running.emit(self.command, success, msg)
        except Exception as e:
            self.finished_running.emit(self.command, False, str(e))

# ---------------------------
# Main GUI
# ---------------------------
class DeadlineGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Deadline Jobs Viewer")
        self.resize(900, 550)
        self.apply_dark_theme()
        self.jobs = []
        self.threads = []  # keep references to threads to avoid GC
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.create_deadline_page())

    def create_deadline_page(self):
        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)

        # Filters
        filter_layout = QtWidgets.QHBoxLayout()
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search jobs (name/user/id)...")
        self.search_bar.textChanged.connect(self.apply_deadline_filter)
        filter_layout.addWidget(self.search_bar)

        self.user_filter = QtWidgets.QComboBox()
        self.user_filter.setEditable(True)
        self.user_filter.setMinimumWidth(140)
        self.user_filter.addItem(getpass.getuser())
        self.user_filter.setCurrentText(getpass.getuser())
        self.user_filter.currentIndexChanged.connect(self.apply_deadline_filter)
        filter_layout.addWidget(QLabel("User:"))
        filter_layout.addWidget(self.user_filter)

        self.date_start = QtWidgets.QDateEdit(calendarPopup=True)
        self.date_end = QtWidgets.QDateEdit(calendarPopup=True)
        self.date_start.setDate(QDate.currentDate().addDays(-7))
        self.date_end.setDate(QDate.currentDate())
        self.date_start.dateChanged.connect(self.apply_deadline_filter)
        self.date_end.dateChanged.connect(self.apply_deadline_filter)
        filter_layout.addWidget(QLabel("From:"))
        filter_layout.addWidget(self.date_start)
        filter_layout.addWidget(QLabel("To:"))
        filter_layout.addWidget(self.date_end)

        self.auto_refresh_chk = QtWidgets.QCheckBox("Auto-refresh")
        self.auto_refresh_chk.setToolTip("Automatically refresh deadline jobs every interval")
        self.auto_refresh_chk.stateChanged.connect(self._toggle_deadline_autorefresh)
        filter_layout.addWidget(self.auto_refresh_chk)

        self.auto_interval = QtWidgets.QSpinBox()
        self.auto_interval.setMinimum(5)
        self.auto_interval.setMaximum(3600)
        self.auto_interval.setValue(20)
        self.auto_interval.setSuffix(" s")
        self.auto_interval.setToolTip("Auto-refresh interval (seconds)")
        filter_layout.addWidget(self.auto_interval)

        self.refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.load_deadline_jobs)
        filter_layout.addWidget(self.refresh_btn)

        left_layout.addLayout(filter_layout)

        # Job table
        self.deadline_table = QtWidgets.QTableWidget()
        self.deadline_table.setColumnCount(14)
        self.deadline_table.setHorizontalHeaderLabels([
            "Job Name", "User", "Progress", "Status", "Frames", "Pool",
            "Priority", "Submitted", "Started", "Completed",
            "Output Directory", "Output File", "Submitted From", "Job ID"
        ])
        self.deadline_table.setSortingEnabled(True)
        self.deadline_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.deadline_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.deadline_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.deadline_table.customContextMenuRequested.connect(self.show_deadline_context_menu)
        self.deadline_table.itemSelectionChanged.connect(self._deadline_row_selected)
        self.deadline_table.itemDoubleClicked.connect(self._deadline_row_selected)
        left_layout.addWidget(self.deadline_table)

        # Action buttons
        actions_row = QtWidgets.QHBoxLayout()
        self.suspend_btn = QtWidgets.QPushButton("🛑 Suspend")
        self.resume_btn = QtWidgets.QPushButton("▶️ Resume")
        self.delete_btn = QtWidgets.QPushButton("❌ Delete")
        self.suspend_btn.clicked.connect(self.suspend_selected_jobs)
        self.resume_btn.clicked.connect(self.resume_selected_jobs)
        self.delete_btn.clicked.connect(self.delete_selected_jobs)
        actions_row.addWidget(self.suspend_btn)
        actions_row.addWidget(self.resume_btn)
        actions_row.addWidget(self.delete_btn)
        actions_row.addStretch()
        left_layout.addLayout(actions_row)

        main = QtWidgets.QHBoxLayout()
        main.addWidget(left)


        page = QtWidgets.QWidget()
        page.setLayout(main)

        self._deadline_timer = QtCore.QTimer(self)
        self._deadline_timer.timeout.connect(self.load_deadline_jobs)

        return page

    def apply_dark_theme(self):
        modern_stylesheet = """
        QWidget {
            background-color: #2b2b2b;
            color: #dddddd;
            font-family: "Segoe UI", "Arial", sans-serif;
            font-size: 8pt;
        }
        QLineEdit, QComboBox, QListWidget {
        background-color: #2c2c2c;  /* Slightly lighter dark grey for list */
        border: none;
        border-radius: 4px;
        outline: none;
        }
        QLineEdit:focus, QComboBox:focus, QListWidget:focus {
            border: 1px solid #00aaff;
        }
        QPushButton {
        background-color: #bfbfbf;  /* Light gray button bg */
        color: #1e1e1e;             /* Dark text on button */
        padding: 2px 2px;          /* Smaller padding */
        border-radius: 4px;         /* Rounded corners with 4px radius */
        font-weight: 400;
        min-width: 80px;            /* Reduced minimum width */
        transition: background-color 0.2s ease, color 0.2s ease;
        }
        QPushButton:hover {
            background-color: #555555;
        }
        QPushButton:pressed {
            background-color: #222222;
        }
        QListWidget::item:selected {
            background-color: #005f87;
            color: #ffffff;
        }
        QScrollBar:vertical {
            background: #2b2b2b;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background: #555555;
            min-height: 20px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical:hover {
            background: #888888;
        }
        """
        self.setStyleSheet(modern_stylesheet)

        
    def _toggle_deadline_autorefresh(self, state):
        if state == QtCore.Qt.Checked:
            interval_sec = max(5, int(self.auto_interval.value()))
            self._deadline_timer.start(interval_sec * 1000)
        else:
            self._deadline_timer.stop()

    # ---------------------------
    # Loading jobs (threaded)
    # ---------------------------
    def load_deadline_jobs(self):
        # Avoid overlapping refreshes
        self._deadline_timer.stop()
        self.saved_filter_text = self.search_bar.text()
        self.search_bar.blockSignals(True)
        self.search_bar.clear()
        self.deadline_table.setRowCount(0)
        self.jobs = []

        deadline_bin_dir = os.getenv("DEADLINE_PATH", r"C:\Program Files\Thinkbox\Deadline10\bin")
        self.deadline_cmd = os.path.join(deadline_bin_dir, "deadlinecommand")
        if platform.system() == "Windows" and not self.deadline_cmd.lower().endswith(".exe"):
            if os.path.isfile(self.deadline_cmd + ".exe"):
                self.deadline_cmd += ".exe"

        user = self.user_filter.currentText().strip() or getpass.getuser()

        # disable refresh while loading
        self.refresh_btn.setEnabled(False)

        loader = DeadlineJobLoader(self.deadline_cmd, user)
        loader.jobs_loaded.connect(self._jobs_from_thread)
        loader.error.connect(self._worker_error)
        loader.finished.connect(lambda: self._thread_cleanup(loader))
        loader.start()
        self.threads.append(loader)

    def _thread_cleanup(self, thread):
        # keep list small, and delete finished refs
        try:
            self.threads = [t for t in self.threads if t.isRunning()]
        except Exception:
            self.threads = []

    def _worker_error(self, msg):
        # show minimal message (main thread)
        print("Worker error:", msg)

    def _jobs_from_thread(self, jobs):
        # Called on main thread via signal
        self.jobs = []
        for job in jobs:
            jobid = job.get("JobId") or job.get("Id") or job.get("ID") or ""
            job["__parsed_jobid"] = jobid
            job["__submit_qdate"] = self._parse_job_submit_date(job.get("JobSubmitDateTime", "") or job.get("JobSubmitDate", ""))
            self.jobs.append(job)

        # restore search text and enable refresh
        self.search_bar.blockSignals(False)
        try:
            self.search_bar.setText(self.saved_filter_text)
        finally:
            self.refresh_btn.setEnabled(True)

        self.apply_deadline_filter()

        # restart auto timer if needed
        if self.auto_refresh_chk.isChecked():
            self._deadline_timer.start(self.auto_interval.value() * 1000)

    def _parse_job_submit_date(self, val):
        if not val:
            return None
        try:
            if str(val).isdigit():
                dt = QDateTime.fromSecsSinceEpoch(int(val))
                return dt.date()
            for fmt in ("yyyy-MM-dd hh:mm:ss", "yyyy-MM-ddThh:mm:ss", "yyyy-MM-dd hh:mm", "yyyy-MM-dd"):
                dt = QDateTime.fromString(val, fmt)
                if dt.isValid():
                    return dt.date()
            m = re.search(r"(\d{4}-\d{2}-\d{2})", val)
            if m:
                dt = QDateTime.fromString(m.group(1), "yyyy-MM-dd")
                if dt.isValid():
                    return dt.date()
        except Exception:
            pass
        return None

    # ---------------------------
    # Table population (main thread only)
    # ---------------------------
    def add_deadline_job_row(self, job):
        row = self.deadline_table.rowCount()
        self.deadline_table.insertRow(row)

        name = job.get("Name", "Unknown")
        user = job.get("UserName", "") or job.get("User", "")
        status = job.get("Status", "")
        pool = job.get("Pool", "")
        priority = str(job.get("Priority", ""))
        job_id = job.get("__parsed_jobid", "UNKNOWN")
        raw_frames = job.get("Frames", "")
        frame_numbers = set()

        if isinstance(raw_frames, str):
            parts = re.split(r"[,\s]+", raw_frames.strip())
            for p in parts:
                if "-" in p:
                    try:
                        a, b = p.split("-", 1)
                        frame_numbers.update(range(int(a), int(b) + 1))
                    except:
                        pass
                elif p.isdigit():
                    frame_numbers.add(int(p))

        frame_list = sorted(frame_numbers)
        frame_range = f"{frame_list[0]}-{frame_list[-1]}" if frame_list else ""

        submit_time = job.get("JobSubmitDateTime", "")
        started_time = job.get("JobStartedDateTime", "")
        completed_time = job.get("JobCompletedDateTime", "")
        output_dir = job.get("JobOutputDirectories", "")
        output_file = job.get("JobOutputFileNames", "")
        output_dir = output_dir[0] if isinstance(output_dir, list) and output_dir else output_dir
        output_file = output_file[0] if isinstance(output_file, list) and output_file else output_file
        submit_machine = job.get("JobSubmitMachine", "")

        try:
            completed = int(job.get("JobCompletedTasks", 0))
            total = int(job.get("JobTaskCount", 1))
            progress = int((completed / total) * 100) if total > 0 else 0
        except:
            progress = 0

        columns = [
            name, user, None, status, frame_range, pool,
            priority, submit_time, started_time, completed_time,
            output_dir, output_file, submit_machine, job_id
        ]

        for i, value in enumerate(columns):
            if i == 2:
                pb = QtWidgets.QProgressBar()
                pb.setValue(progress)
                pb.setAlignment(QtCore.Qt.AlignCenter)
                pb.setFormat(f"{progress}%")
                pb.setFixedHeight(16)
                self.deadline_table.setCellWidget(row, i, pb)
            else:
                item = QtWidgets.QTableWidgetItem(value or "")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setData(QtCore.Qt.UserRole, job_id)
                self.deadline_table.setItem(row, i, item)

    def apply_deadline_filter(self):
        filter_text = self.search_bar.text().lower().strip()
        user_filter_text = (self.user_filter.currentText() or "").lower().strip()
        date_from = self.date_start.date()
        date_to = self.date_end.date()

        self.deadline_table.setRowCount(0)
        for job in getattr(self, "jobs", []):
            name = job.get("Name", "").lower()
            user = (job.get("UserName", "") or job.get("User", "")).lower()
            jobid = (job.get("__parsed_jobid", "") or "").lower()
            submit_qdate = job.get("__submit_qdate", None)
            if not submit_qdate:
                continue
            if not (date_from <= submit_qdate <= date_to):
                continue
            if user_filter_text and user_filter_text not in user:
                continue
            if filter_text and filter_text not in name and filter_text not in user and filter_text not in jobid:
                continue
            self.add_deadline_job_row(job)

    def get_selected_job_ids(self):
        selected = self.deadline_table.selectionModel().selectedRows()
        job_ids = set()
        for row in selected:
            for col in range(self.deadline_table.columnCount()):
                item = self.deadline_table.item(row.row(), col)
                if item and item.data(QtCore.Qt.UserRole):
                    job_ids.add(item.data(QtCore.Qt.UserRole))
                    break
        return list(job_ids)

    def show_deadline_context_menu(self, pos):
        index = self.deadline_table.indexAt(pos)
        if not index.isValid():
            return
        self.deadline_table.selectRow(index.row())
        job_id = self.deadline_table.item(index.row(), 0).data(QtCore.Qt.UserRole)
        if not job_id:
            return
        menu = QtWidgets.QMenu()
        menu.addAction("🛑 Suspend", self.suspend_selected_jobs)
        menu.addAction("▶️ Resume", self.resume_selected_jobs)
        menu.addAction("❌ Delete", self.delete_selected_jobs)
        menu.addSeparator()
        menu.addAction("🛈 View Job Info", lambda jid=job_id: self.fetch_and_show_job_info(jid))
        menu.exec_(self.deadline_table.viewport().mapToGlobal(pos))

    def _deadline_row_selected(self):
        sels = self.deadline_table.selectionModel().selectedRows()
        if not sels:
            return
        row = sels[0].row()
        job_id = self.deadline_table.item(row, 0).data(QtCore.Qt.UserRole)
        if job_id:
            self.fetch_and_show_job_info(job_id)


    # ---------------------------
    # Job info (threaded)
    # ---------------------------
    def fetch_and_show_job_info(self, job_id):
        # ensure self.deadline_cmd exists
        if not hasattr(self, "deadline_cmd") or not self.deadline_cmd:
            deadline_bin_dir = os.getenv("DEADLINE_PATH", r"C:\Program Files\Thinkbox\Deadline10\bin")
            self.deadline_cmd = os.path.join(deadline_bin_dir, "deadlinecommand")
            if platform.system() == "Windows" and os.path.isfile(self.deadline_cmd + ".exe"):
                self.deadline_cmd += ".exe"

        info_loader = JobInfoLoader(self.deadline_cmd, job_id)
        info_loader.info_loaded.connect(self._show_job_info)
        info_loader.error.connect(self._worker_error)
        info_loader.finished.connect(lambda: self._thread_cleanup(info_loader))
        info_loader.start()
        self.threads.append(info_loader)

    def _show_job_info(self, parsed):
        # Create a modal dialog to show job info
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Job Info")
        dialog.resize(600, 400)
        layout = QtWidgets.QVBoxLayout(dialog)
    
        table = QtWidgets.QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Field", "Value"])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
    
        for i, (k, v) in enumerate(sorted(parsed.items())):
            table.insertRow(i)
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(k))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem(v))
    
        layout.addWidget(table)
    
        btn_close = QtWidgets.QPushButton("Close")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)
    
        dialog.exec_()


    # ---------------------------
    # Run commands (threaded)
    # ---------------------------
    def _run_command_on_jobs(self, command, job_ids):
        if not job_ids:
            return
        if not hasattr(self, "deadline_cmd") or not self.deadline_cmd:
            deadline_bin_dir = os.getenv("DEADLINE_PATH", r"C:\Program Files\Thinkbox\Deadline10\bin")
            self.deadline_cmd = os.path.join(deadline_bin_dir, "deadlinecommand")
            if platform.system() == "Windows" and os.path.isfile(self.deadline_cmd + ".exe"):
                self.deadline_cmd += ".exe"

        # optionally disable action buttons to prevent double-clicks
        self.suspend_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

        for jid in job_ids:
            runner = CommandRunner(self.deadline_cmd, command, jid)
            runner.finished_running.connect(self._command_finished)
            runner.finished.connect(lambda: self._thread_cleanup(runner))
            runner.start()
            self.threads.append(runner)

    def suspend_selected_jobs(self):
        self._run_command_on_jobs("SuspendJob", self.get_selected_job_ids())
        # refresh after a short delay
        QtCore.QTimer.singleShot(400, self.load_deadline_jobs)

    def resume_selected_jobs(self):
        self._run_command_on_jobs("ResumeJob", self.get_selected_job_ids())
        QtCore.QTimer.singleShot(400, self.load_deadline_jobs)

    def delete_selected_jobs(self):
        self._run_command_on_jobs("DeleteJob", self.get_selected_job_ids())
        QtCore.QTimer.singleShot(400, self.load_deadline_jobs)

    def _command_finished(self, command, success, message):
        # Called on main thread
        print(f"{command} finished: success={success}, msg={message}")
        # re-enable action buttons (could be more nuanced)
        self.suspend_btn.setEnabled(True)
        self.resume_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        # optionally show small popup for failures
        if not success:
            QtWidgets.QMessageBox.warning(self, f"{command} failed", message or "Unknown error")

# ---------------------------
# Entrypoint
# ---------------------------
def show_deadline_viewer():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewer = DeadlineGUI()
    viewer.show()
    viewer.load_deadline_jobs()
    return viewer


# Always launch when script runs directly
show_deadline_viewer()

