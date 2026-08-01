"""Small Tkinter UI for the Phonemation backend server."""

import sys

# Windows GUI apps have no console; uvicorn/asyncio logging crashes
# if stdout/stderr are None. Redirect them to devnull.
if sys.stdout is None:
    import os

    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    import os

    sys.stderr = open(os.devnull, "w")

import tkinter as tk
from tkinter import ttk, scrolledtext
import logging
import os
from pathlib import Path
import threading
import time

import uvicorn

from .api import create_backend_app
from .environment import format_environment_summary, get_environment_info
from .service import BackendConfig, PhonemationBackend


class TextHandler(logging.Handler):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record):
        msg = self.format(record) + "\n"
        try:
            self.widget.after(0, lambda: self._append(msg))
        except Exception:
            pass

    def _append(self, msg):
        self.widget.configure(state="normal")
        self.widget.insert("end", msg)
        self.widget.see("end")
        self.widget.configure(state="disabled")


class BackendUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Phonemation Backend")
        self.root.geometry("620x560")
        self.root.minsize(520, 420)
        self._set_icon()

        self.backend: PhonemationBackend | None = None
        self.app = None
        self.server: uvicorn.Server | None = None
        self.server_thread: threading.Thread | None = None
        self._closing = False

        self._build_ui()
        self._setup_logging()
        self._poll_status()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        # Top status frame
        status_frame = ttk.LabelFrame(self.root, text="Status", padding=10)
        status_frame.pack(fill="x", padx=10, pady=5)

        self.status_var = tk.StringVar(value="Stopped")
        ttk.Label(status_frame, textvariable=self.status_var, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.url_var = tk.StringVar(value="URL: —")
        ttk.Label(status_frame, textvariable=self.url_var).pack(anchor="w", pady=(4, 0))

        self.phoneme_var = tk.StringVar(value="Phoneme model: —")
        ttk.Label(status_frame, textvariable=self.phoneme_var).pack(anchor="w")

        self.emotion_var = tk.StringVar(value="Emotion model: —")
        ttk.Label(status_frame, textvariable=self.emotion_var).pack(anchor="w")

        self.init_var = tk.StringVar(value="Initialized: —")
        ttk.Label(status_frame, textvariable=self.init_var).pack(anchor="w")

        self.runtime_var = tk.StringVar(value="Runtime: —")
        ttk.Label(status_frame, textvariable=self.runtime_var).pack(anchor="w")

        self.providers_var = tk.StringVar(value="Providers: —")
        ttk.Label(status_frame, textvariable=self.providers_var, wraplength=570).pack(anchor="w")

        self.resources_var = tk.StringVar(value="Resources: —")
        ttk.Label(status_frame, textvariable=self.resources_var).pack(anchor="w")

        self._update_environment(get_environment_info())

        # Controls frame
        ctrl_frame = ttk.Frame(self.root, padding=10)
        ctrl_frame.pack(fill="x", padx=10, pady=2)

        ttk.Label(ctrl_frame, text="Port:").pack(side="left")
        self.port_var = tk.StringVar(value=os.environ.get("PHONEMATION_PORT", "8007"))
        ttk.Entry(ctrl_frame, textvariable=self.port_var, width=8).pack(side="left", padx=5)

        self.start_btn = ttk.Button(ctrl_frame, text="Start", command=self.on_start)
        self.start_btn.pack(side="left", padx=5)

        self.stop_btn = ttk.Button(ctrl_frame, text="Stop", command=self.on_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=5)

        self.unload_btn = ttk.Button(ctrl_frame, text="Unload models", command=self.on_unload, state="disabled")
        self.unload_btn.pack(side="left", padx=5)

        # Log frame
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=5)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True)

    def _set_icon(self):
        icon = self._resolve_icon_path()
        if icon:
            try:
                self.root.iconbitmap(str(icon))
            except Exception:
                pass

    def _resolve_icon_path(self):
        try:
            p = Path(__compiled__.containing_dir) / "phonemation.ico"
            if p.exists():
                return p
        except NameError:
            pass
        # Development / fallback relative to this module
        base = Path(__file__).resolve().parent
        for rel in ("../phonemation.ico", "../../phonemation.ico"):
            p = (base / rel).resolve()
            if p.exists():
                return p
        return None

    def _setup_logging(self):
        handler = TextHandler(self.log_text)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        logging.info("Environment: %s", format_environment_summary(get_environment_info()))

    @staticmethod
    def _format_bytes(value):
        if value is None:
            return "unknown"
        return f"{value / (1024 ** 3):.1f} GiB"

    def _update_environment(self, environment):
        build = environment.get("build", {})
        ort_info = environment.get("onnxruntime", {})
        resources = environment.get("resources", {})
        runtime = build.get("runtime", "unknown")
        providers = ort_info.get("active_providers") or ort_info.get("configured_providers") or ort_info.get("available_providers", [])
        self.runtime_var.set(f"Runtime: {runtime} | ONNX Runtime {ort_info.get('version', 'unknown')} | {ort_info.get('device', 'unknown')}")
        self.providers_var.set(f"Providers: {', '.join(providers) if providers else 'none'}")
        total = self._format_bytes(resources.get("system_memory_total_bytes"))
        available = self._format_bytes(resources.get("system_memory_available_bytes"))
        process = self._format_bytes(resources.get("process_working_set_bytes"))
        self.resources_var.set(f"Resources: {resources.get('logical_cpu_count', 'unknown')} CPUs | RAM {available} free / {total} | Process {process}")

    def on_start(self):
        self.start_btn.configure(state="disabled")
        self._start_backend()

    def _start_backend(self):
        try:
            port = int(self.port_var.get())
        except ValueError:
            logging.error("Invalid port number")
            self.start_btn.configure(state="normal")
            return

        phoneme_model = os.environ.get("PHONEMATION_PHONEME_MODEL") or None
        emotion_model = os.environ.get("PHONEMATION_EMOTION_MODEL") or None
        host_api = os.environ.get("PHONEMATION_HOST_API") or None
        input_device = os.environ.get("PHONEMATION_INPUT_DEVICE") or None
        output_device = os.environ.get("PHONEMATION_OUTPUT_DEVICE") or None
        enable_output = os.environ.get("PHONEMATION_ENABLE_OUTPUT", "") == "1"
        vad_system = os.environ.get("PHONEMATION_VAD_SYSTEM", "volume")
        volume_threshold = float(os.environ.get("PHONEMATION_VOLUME_THRESHOLD", "0.05"))

        if phoneme_model and emotion_model:
            logging.info("Models configured from environment: phoneme=%s emotion=%s", phoneme_model, emotion_model)
        else:
            logging.info("No models pre-configured; waiting for frontend to load them via API")

        try:
            self.backend = PhonemationBackend(
                BackendConfig(
                    phoneme_model_path=phoneme_model,
                    emotion_model_path=emotion_model,
                    host_api=host_api,
                    input_device=input_device,
                    output_device=output_device,
                    enable_output=enable_output,
                    vad_system=vad_system,
                    volume_level_threshold=volume_threshold,
                    audio_source="remote",
                )
            )
            self.backend.start()
        except Exception as exc:
            logging.error("Failed to start backend: %s", exc)
            self.start_btn.configure(state="normal")
            return

        self.app = create_backend_app(self.backend)
        config = uvicorn.Config(self.app, host="127.0.0.1", port=port, log_level="info", access_log=False)
        self.server = uvicorn.Server(config)
        # Expose the server so the /shutdown endpoint can terminate the process.
        self.app.state.server = self.server

        def run_server():
            try:
                self.server.run()
            except Exception as exc:
                logging.error("Server error: %s", exc)

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        self.status_var.set("Running")
        self.url_var.set(f"URL: http://127.0.0.1:{port}")
        self.stop_btn.configure(state="normal")
        self.unload_btn.configure(state="normal")
        logging.info("Backend server started on port %d", port)

    def on_stop(self):
        self.stop_btn.configure(state="disabled")
        if self.server:
            try:
                self.server.should_exit = True
            except Exception:
                pass
        if self.backend:
            try:
                self.backend.stop()
            except Exception:
                pass
        self.backend = None
        self.app = None
        self.server = None
        self.server_thread = None
        self.status_var.set("Stopped")
        self.url_var.set("URL: —")
        self.phoneme_var.set("Phoneme model: —")
        self.emotion_var.set("Emotion model: —")
        self.init_var.set("Initialized: —")
        self.start_btn.configure(state="normal")
        self.unload_btn.configure(state="disabled")
        logging.info("Backend server stopped")

    def on_close(self):
        self._closing = True
        self.on_stop()
        self.root.destroy()

    def on_unload(self):
        if not self.app:
            return
        try:
            current = self.app.state.backend
            if current:
                current.stop()
            self.app.state.backend = PhonemationBackend(
                BackendConfig(audio_source="remote")
            )
            logging.info("Models unloaded")
        except Exception as exc:
            logging.error("Failed to unload models: %s", exc)

    def _poll_status(self):
        if not self._closing and self.app:
            # A remote /shutdown sets should_exit; close the window to exit fully.
            if self.server is not None and getattr(self.server, "should_exit", False):
                logging.info("Remote shutdown detected; closing UI.")
                self.on_close()
                return
            try:
                backend = self.app.state.backend
                if not backend:
                    self.root.after(200, self._poll_status)
                    return
                status = backend.get_status()
                running = status.get("running", False)
                self.status_var.set("Running" if running else "Stopped")
                init = status.get("initialized", False)
                self.init_var.set(f"Initialized: {'Yes' if init else 'No'}")
                self._update_environment(status.get("environment") or get_environment_info())

                if backend.recognizer:
                    pm = Path(backend.recognizer.phoneme_model_path).name
                    em = Path(backend.recognizer.emotion_model_path).name
                    self.phoneme_var.set(f"Phoneme model: {pm}")
                    self.emotion_var.set(f"Emotion model: {em}")
                elif backend.config.phoneme_model_path:
                    pm = Path(backend.config.phoneme_model_path).name
                    em = Path(backend.config.emotion_model_path).name
                    self.phoneme_var.set(f"Phoneme model (not loaded): {pm}")
                    self.emotion_var.set(f"Emotion model (not loaded): {em}")
                else:
                    self.phoneme_var.set("Phoneme model: —")
                    self.emotion_var.set("Emotion model: —")
            except Exception:
                pass
        self.root.after(200, self._poll_status)


def run_ui():
    root = tk.Tk()
    app = BackendUI(root)
    root.mainloop()
