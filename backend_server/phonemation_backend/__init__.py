__all__ = ["PhonemationBackend", "BackendConfig", "create_backend_app"]


def __getattr__(name):
    if name in {"PhonemationBackend", "BackendConfig"}:
        from .service import BackendConfig, PhonemationBackend

        return {"PhonemationBackend": PhonemationBackend, "BackendConfig": BackendConfig}[name]
    if name == "create_backend_app":
        from .api import create_backend_app

        return create_backend_app
    raise AttributeError(name)
