"""Запускает существующие этапы в отдельном процессе и передаёт их журнал окну."""

import os
import queue
import subprocess
import sys
import threading
from uuid import uuid4

from core.run_options import RunOptions
from core.settings_defaults import PROJECT_DIR


class StageRunner:
    def __init__(self):
        self.events = queue.Queue()
        self.process = None
        self.stop_file = None

    def start(self, command, worksheet, html_file=None, options=None, extra_args=()):
        """Запускает одну команду run.py с выбранной вкладкой таблицы."""
        if self.process is not None:
            raise RuntimeError("Другой этап ещё работает.")
        options = options or RunOptions()
        options.validate(command)

        data_dir = PROJECT_DIR / "data"
        data_dir.mkdir(exist_ok=True)
        stop_file = data_dir / f".gui-stop-{uuid4().hex}"

        env = os.environ.copy()
        env["AUTO_HH_WORKSHEET"] = worksheet
        env["AUTO_HH_STOP_FILE"] = str(stop_file)
        env["PYTHONIOENCODING"] = "utf-8"
        args = [sys.executable, "-u", "-X", "utf8", str(PROJECT_DIR / "Scripts" / "run.py"), command]
        if html_file:
            args.append(str(html_file))
        args.extend(options.cli_args())
        args.extend(extra_args)

        # Отдельный процесс оставляет Tkinter отзывчивым во время Google и Chrome.
        process = subprocess.Popen(
            args, cwd=PROJECT_DIR, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        self.process = process
        self.stop_file = stop_file
        threading.Thread(target=self._read_output, args=(process,), daemon=True).start()
        return process.pid

    def _read_output(self, process):
        """Читает консоль без обращения к виджетам из фонового потока."""
        try:
            for line in process.stdout:
                self.events.put(("line", line))
        finally:
            self.events.put(("exit", process.wait()))

    def stop(self):
        """Просит этап завершиться на ближайшей безопасной границе."""
        if self.process is None or self.process.poll() is not None:
            return False
        self.stop_file.touch()
        return True

    def finish(self):
        """Удаляет сигнал после завершения дочернего процесса."""
        if self.stop_file is not None:
            self.stop_file.unlink(missing_ok=True)
        self.process = None
        self.stop_file = None
