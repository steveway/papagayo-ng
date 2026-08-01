import ctypes
import json
import os
import platform
import sys
from pathlib import Path

import onnxruntime as ort


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ulong),
        ("memory_load", ctypes.c_ulong),
        ("total_physical", ctypes.c_ulonglong),
        ("available_physical", ctypes.c_ulonglong),
        ("total_page_file", ctypes.c_ulonglong),
        ("available_page_file", ctypes.c_ulonglong),
        ("total_virtual", ctypes.c_ulonglong),
        ("available_virtual", ctypes.c_ulonglong),
        ("available_extended_virtual", ctypes.c_ulonglong),
    ]


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("page_fault_count", ctypes.c_ulong),
        ("peak_working_set_size", ctypes.c_size_t),
        ("working_set_size", ctypes.c_size_t),
        ("quota_peak_paged_pool_usage", ctypes.c_size_t),
        ("quota_paged_pool_usage", ctypes.c_size_t),
        ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
        ("quota_non_paged_pool_usage", ctypes.c_size_t),
        ("pagefile_usage", ctypes.c_size_t),
        ("peak_pagefile_usage", ctypes.c_size_t),
    ]


def _read_build_info():
    candidates = [
        Path(__file__).resolve().with_name("build_info.json"),
        Path(sys.executable).resolve().with_name("build_info.json"),
    ]
    for path in candidates:
        try:
            if path.is_file():
                with path.open("r", encoding="utf-8-sig") as file:
                    return json.load(file)
        except (OSError, ValueError):
            pass
    return {"runtime": os.environ.get("PHONEMATION_AI_RUNTIME", "source"), "version": "development"}


def _memory_info():
    if os.name != "nt":
        return {}
    status = _MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {}
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_process_memory_info.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ProcessMemoryCounters), ctypes.c_ulong]
    get_process_memory_info.restype = ctypes.c_bool
    process = ctypes.windll.kernel32.GetCurrentProcess()
    if not get_process_memory_info(process, ctypes.byref(counters), counters.cb):
        process_working_set = None
    else:
        process_working_set = counters.working_set_size
    return {
        "system_memory_total_bytes": status.total_physical,
        "system_memory_available_bytes": status.available_physical,
        "system_memory_load_percent": status.memory_load,
        "process_working_set_bytes": process_working_set,
    }


def get_environment_info(recognizer=None):
    build = _read_build_info()
    available_providers = ort.get_available_providers()
    configured_providers = []
    active_providers = []
    if recognizer is not None:
        configured_providers = [provider[0] if isinstance(provider, tuple) else provider for provider in recognizer.providers]
        for model in (recognizer.phoneme_model, recognizer.emotion_model):
            if model and hasattr(model, "get_providers"):
                for provider in model.get_providers():
                    if provider not in active_providers:
                        active_providers.append(provider)
    return {
        "build": build,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "frozen": bool(getattr(sys, "frozen", False) or "__compiled__" in globals()),
        },
        "onnxruntime": {
            "version": ort.__version__,
            "device": ort.get_device(),
            "available_providers": available_providers,
            "configured_providers": configured_providers,
            "active_providers": active_providers,
        },
        "resources": {
            "logical_cpu_count": os.cpu_count(),
            **_memory_info(),
        },
    }


def format_environment_summary(info):
    runtime = info["build"].get("runtime", "unknown")
    ort_info = info["onnxruntime"]
    resources = info["resources"]
    providers = ort_info["active_providers"] or ort_info["configured_providers"] or ort_info["available_providers"]
    memory_total = resources.get("system_memory_total_bytes")
    memory_gib = f"{memory_total / (1024 ** 3):.1f} GiB" if memory_total else "unknown"
    return (
        f"runtime={runtime}; ONNX Runtime={ort_info['version']}; device={ort_info['device']}; "
        f"providers={', '.join(providers)}; CPUs={resources.get('logical_cpu_count')}; memory={memory_gib}"
    )
