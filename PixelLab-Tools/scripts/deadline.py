import os
import re
import platform
import getpass
import subprocess
from PySide2 import QtWidgets, QtCore
from PySide2.QtCore import QDate, QDateTime
from PySide2.QtWidgets import QLabel


class DeadlineJobLoader(QtCore.QThread):
    job_loaded = QtCore.Signal(dict)
    finished_loading = QtCore.Signal()

    def __init__(self, deadline_cmd, user=None):
        super().__init__()
        self.deadline_cmd = deadline_cmd
        self.user = user

    def run(self):
        try:
            args = [self.deadline_cmd, "GetJobs"]
            if self.user:
                args += ["-UserName", self.user]
            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out = result.stdout.strip()
            current_job = {}
            for line in out.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    current_job[k.strip()] = v.strip()
                elif line.strip() == "":
                    if current_job:
                        self.job_loaded.emit(current_job.copy())
                        current_job.clear()
            if current_job:
                self.job_loaded.emit(current_job)
        except Exception as e:
            print("Loader error:", e)
        self.finished_loading.emit()


class DeadlineGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Deadline Jobs Viewer")
        self.resize(1500, 850)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.create_deadline_page())

    # ========== DEADLINE PAGE ==========
    def create_deadline_page(self):
        from functools import partial

        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)

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
        filter_layout.addWidget(QLabel("User:"))
        filter_layout.addWidget(self.user_filter)

        self.date_start = QtWidgets.QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addDays(-7))
        self.date_end = QtWidgets.QDateEdit()
        self.date_end.setCalendarPopup(True)
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

        refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_deadline_jobs)
        filter_layout.addWidget(refresh_btn)

        left_layout.addLayout(filter_layout)

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

        left_layout.addWidget(self.deadline_table)

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

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        info_label = QLabel("Job Info")
        info_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 6px;")
        right_layout.addWidget(info_label)

        self.job_info_table = QtWidgets.QTableWidget()
        self.job_info_table.setColumnCount(2)
        self.job_info_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.job_info_table.horizontalHeader().setStretchLastSection(True)
        self.job_info_table.verticalHeader().setVisible(False)
        right_layout.addWidget(self.job_info_table)

        main = QtWidgets.QHBoxLayout()
        main.addWidget(left, 3)
        main.addWidget(right, 1)

        page = QtWidgets.QWidget()
        page.setLayout(main)

        self._deadline_timer = QtCore.QTimer()
        self._deadline_timer.timeout.connect(self.load_deadline_jobs)

        return page

    def _toggle_deadline_autorefresh(self, state):
        if state == QtCore.Qt.Checked:
            interval_sec = max(5, int(self.auto_interval.value()))
            self._deadline_timer.start(interval_sec * 1000)
        else:
            self._deadline_timer.stop()

    def load_deadline_jobs(self):
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
        self.loader_thread = DeadlineJobLoader(self.deadline_cmd, user)
        self.loader_thread.job_loaded.connect(self._store_loaded_job_and_add)
        self.loader_thread.finished_loading.connect(self._deadline_loader_finished)
        self.loader_thread.start()

    def _store_loaded_job_and_add(self, job):
        if not hasattr(self, "jobs"):
            self.jobs = []
        jobid = job.get("JobId") or job.get("Id") or job.get("ID") or ""
        job["__parsed_jobid"] = jobid
        qdate = self._parse_job_submit_date(job.get("JobSubmitDateTime", "") or job.get("JobSubmitDate", ""))
        job["__submit_qdate"] = qdate
        self.jobs.append(job)
        self.apply_deadline_filter()

    def _deadline_loader_finished(self):
        self.search_bar.blockSignals(False)
        try:
            self.search_bar.setText(self.saved_filter_text)
        except Exception:
            pass
        self.apply_deadline_filter()

    def _parse_job_submit_date(self, val):
        try:
            if not val:
                return None
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
        output_dirs = job.get("JobOutputDirectories", "")
        output_files = job.get("JobOutputFileNames", "")
        submit_machine = job.get("JobSubmitMachine", "")
        output_dir = output_dirs[0] if isinstance(output_dirs, list) and output_dirs else output_dirs
        output_file = output_files[0] if isinstance(output_files, list) and output_files else output_files
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
            name = (job.get("Name", "") or "").lower()
            user = (job.get("UserName", "") or job.get("User", "") or "").lower()
            jobid = (job.get("__parsed_jobid", "") or "").lower()
            submit_qdate = job.get("__submit_qdate", None)
            date_ok = True
            if submit_qdate and isinstance(submit_qdate, QDate):
                date_ok = (submit_qdate >= date_from) and (submit_qdate <= date_to)
            user_ok = True
            if user_filter_text:
                user_ok = user_filter_text in user
            text_ok = filter_text in name or filter_text in user or filter_text in jobid if filter_text else True
            if date_ok and user_ok and text_ok:
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
        job_id = None
        for col in range(self.deadline_table.columnCount()):
            item = self.deadline_table.item(index.row(), col)
            if item and item.data(QtCore.Qt.UserRole):
                job_id = item.data(QtCore.Qt.UserRole)
                break
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
        job_id = None
        for col in range(self.deadline_table.columnCount()):
            item = self.deadline_table.item(row, col)
            if item and item.data(QtCore.Qt.UserRole):
                job_id = item.data(QtCore.Qt.UserRole)
                break
        if job_id:
            QtCore.QTimer.singleShot(10, lambda jid=job_id: self.fetch_and_show_job_info(jid))

    def fetch_and_show_job_info(self, job_id):
        try:
            if not hasattr(self, "deadline_cmd") or not self.deadline_cmd:
                deadline_bin_dir = os.getenv("DEADLINE_PATH", r"C:\Program Files\Thinkbox\Deadline10\bin")
                self.deadline_cmd = os.path.join(deadline_bin_dir, "deadlinecommand")
                if platform.system() == "Windows" and os.path.isfile(self.deadline_cmd + ".exe"):
                    self.deadline_cmd += ".exe"
            result = subprocess.run([self.deadline_cmd, "GetJob", job_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out = result.stdout.strip() or result.stderr.strip()
            parsed = {}
            for line in out.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    parsed[k.strip()] = v.strip()
            self.job_info_table.setRowCount(0)
            for i, (k, v) in enumerate(sorted(parsed.items())):
                self.job_info_table.insertRow(i)
                self.job_info_table.setItem(i, 0, QtWidgets.QTableWidgetItem(k))
                self.job_info_table.setItem(i, 1, QtWidgets.QTableWidgetItem(v))
        except Exception as e:
            print("fetch job info error:", e)

    def suspend_selected_jobs(self):
        for job_id in self.get_selected_job_ids():
            self.run_deadline_command("SuspendJob", job_id)
        QtCore.QTimer.singleShot(200, self.load_deadline_jobs)

    def resume_selected_jobs(self):
        for job_id in self.get_selected_job_ids():
            self.run_deadline_command("ResumeJob", job_id)
        QtCore.QTimer.singleShot(200, self.load_deadline_jobs)

    def delete_selected_jobs(self):
        for job_id in self.get_selected_job_ids():
            self.run_deadline_command("DeleteJob", job_id)
        QtCore.QTimer.singleShot(200, self.load_deadline_jobs)

    def run_deadline_command(self, command, job_id):
        try:
            result = subprocess.run([self.deadline_cmd, command, job_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                print(f"{command} failed for job {job_id}: {result.stderr.strip()}")
            else:
                print(f"{command} succeeded for job {job_id}")
        except Exception as e:
            print(f"Error running {command} for job {job_id}: {e}")


app = QtWidgets.QApplication([])
render_viewer = DeadlineGUI()
render_viewer.show()
app.exec_()

