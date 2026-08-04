import sys
import logging
import threading
import os
import time
from huggingface_hub import get_collection, snapshot_download, list_collections
from tqdm.auto import tqdm as base_tqdm
from tqdm import TqdmDeprecationWarning

# Read-only HuggingFace token. Override via the HF_TOKEN environment variable.
_DEFAULT_HF_TOKEN = "hf_add_a_token_here"


class DownloadProgress:
    """Thread-safe aggregate progress tracker for a single model download.

    HuggingFace ``snapshot_download`` spawns one tqdm bar per file, so we
    aggregate the byte counts of all bars to compute an overall percentage.
    """

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.state = "starting"  # starting | downloading | completed | error
        self.error = None
        self.path = None
        self.started_at = time.time()
        self._bars = {}  # bar_id -> (downloaded, total)
        self._lock = threading.Lock()

    def update_bar(self, bar_id, downloaded, total):
        with self._lock:
            self._bars[bar_id] = (int(downloaded or 0), int(total or 0))
            if self.state == "starting":
                self.state = "downloading"

    def set_completed(self, path):
        with self._lock:
            self.state = "completed"
            self.path = path

    def set_error(self, message):
        with self._lock:
            self.state = "error"
            self.error = message

    def snapshot(self):
        with self._lock:
            downloaded = sum(n for n, _ in self._bars.values())
            total = sum(t for _, t in self._bars.values())
            percent = (downloaded / total * 100.0) if total else 0.0
            return {
                "state": self.state,
                "downloaded_bytes": downloaded,
                "total_bytes": total,
                "percent": round(percent, 2),
                "error": self.error,
                "path": str(self.path) if self.path else None,
                "elapsed": round(time.time() - self.started_at, 2),
            }


def make_progress_tqdm(progress: "DownloadProgress"):
    """Return a tqdm subclass that reports byte progress into ``progress``.

    This subclasses the proven ``CustomTQDM`` (which keeps the bar enabled so
    ``self.n`` advances) and only *adds* reporting hooks. We must NOT disable
    the bar (tqdm short-circuits ``update()`` when disabled, leaving progress
    stuck at 0%) and must NOT override ``refresh()`` (doing so breaks the
    download loop).
    """

    class _ProgressTQDM(CustomTQDM):
        def __init__(self, *args, **kwargs):
            # Must set before super().__init__: tqdm calls display() during init.
            self._bar_id = id(self)
            super().__init__(*args, **kwargs)
            progress.update_bar(self._bar_id, self.n, self.total or 0)

        def update(self, n=1):
            result = super().update(n)
            progress.update_bar(self._bar_id, self.n, self.total or 0)
            return result

        def display(self, msg=None, pos=None):
            progress.update_bar(self._bar_id, self.n, self.total or 0)
            return super().display(msg, pos)

        def close(self):
            progress.update_bar(self._bar_id, self.n, self.total or 0)
            super().close()

    return _ProgressTQDM


class CustomTQDM(base_tqdm):

    def __init__(self, *args, **kwargs):
        name = kwargs.pop("name", None)  # do not pass `name` to `tqdm`
        kwargs["smoothing"] = 1
        self._lock = threading.RLock()  # Add threading lock
        super().__init__(*args, **kwargs)

    def display(self, msg=None, pos=None):
        """
        Use `self.sp` to display `msg` in the specified `pos`.

        Consider overloading this function when inheriting to use e.g.:
        `self.some_frontend(**self.format_dict)` instead of `self.sp`.

        Parameters
        ----------
        msg  : str, optional. What to display (default: `repr(self)`).
        pos  : int, optional. Position to `moveto`
          (default: `abs(self.pos)`).
        """
        if pos is None:
            pos = abs(self.pos)

        nrows = self.nrows or 20
        if pos >= nrows - 1:
            if pos >= nrows:
                return False
            if msg or msg is None:  # override at `nrows - 1`
                msg = " ... (more hidden) ..."

        if not hasattr(self, "sp"):
            raise TqdmDeprecationWarning(
                "Please use `tqdm.gui.tqdm(...)`"
                " instead of `tqdm(..., gui=True)`\n",
                fp_write=getattr(self.fp, 'write', sys.stderr.write))

        if pos:
            self.moveto(pos)
        current_progress = self.format_dict["n"]
        total_items = self.format_dict["total"]
        # self.sp(self.__str__() if msg is None else msg)
        if pos:
            self.moveto(-pos)
        logging.info(f"Downloading Models. (This can take a while.) Current progress: {current_progress}/{total_items}")
        # print(f"Current progress: {current_progress}/{total_items}")
        return True


class ModelHandler:
    __instance = None

    @staticmethod
    def get_instance():
        if ModelHandler.__instance is None:
            ModelHandler()
        return ModelHandler.__instance

    def __init__(self):
        if ModelHandler.__instance is not None:
            raise Exception("ModelHandler: This class is a singleton!")
        else:
            ModelHandler.__instance = self
        self.token = os.environ.get("HF_TOKEN") or _DEFAULT_HF_TOKEN  # read-only access
        self.cached_models = {"phoneme": {}, "emotion": {}}
        self.download_threads = []
        self._refresh_collections()

    def _refresh_collections(self):
        """(Re)fetch the HuggingFace collections using the current token."""
        self.collections = list_collections(owner="steveway", token=self.token)
        for collection in self.collections:
            if collection.title == "emotion_models":
                self.emotion_collection = get_collection(collection.slug, token=self.token)
            elif collection.title == "phoneme_models":
                self.phoneme_collection = get_collection(collection.slug, token=self.token)
            else:
                pass

    def set_token(self, token):
        """Update the HuggingFace token and re-fetch the collections.

        Also clears the in-process model list cache so subsequent calls
        reflect the new access scope.  ``token`` may be an empty string to
        fall back to the default read-only token.
        """
        self.token = token or os.environ.get("HF_TOKEN") or _DEFAULT_HF_TOKEN
        self.cached_models = {"phoneme": {}, "emotion": {}}
        self._refresh_collections()

    def cache_models(self):
        for model in self.emotion_collection.items:
            nice_name = model.item_id.split("/")[-1].split("_onnx")[0]
            self.cached_models["emotion"][nice_name] = model.item_id
        for model in self.phoneme_collection.items:
            nice_name = model.item_id.split("/")[-1].split("_onnx")[0]
            self.cached_models["phoneme"][nice_name] = model.item_id

    def get_model_list(self, model_type="phoneme"):
        if model_type == "phoneme":
            model_list = [model.item_id for model in self.phoneme_collection.items]
        if model_type == "emotion":
            model_list = [model.item_id for model in self.emotion_collection.items]
        return model_list

    def download_model(self, model_id, download_path, tqdm_class=CustomTQDM):
        if not model_id:
            return None
            
        if not model_id.startswith("steveway"):
            old_model_id = model_id.split("/")[-1]
            model_id = f"steveway/{old_model_id}_onnx"

        model_name = model_id.split('/')[-1]
        full_path = os.path.join(download_path, model_name)
        return snapshot_download(model_id, local_dir=full_path, token=self.token, tqdm_class=tqdm_class)

    def download_model_threaded(self, model_id, download_path):
        self.download_threads.append(threading.Thread(target=self.download_model, args=(model_id, download_path)))
        self.download_threads[-1].start()

    def model_is_available_locally(self, model_id, download_path, model_type="phoneme"):
        if not model_id.startswith("steveway"):
            old_model_id = model_id.split("/")[-1]
            model_id = f"steveway/{old_model_id}_onnx"
        # Check in the download path if the model is available
        full_path = f"{download_path}/{model_type}/{model_id.split('/')[-1]}"
        if not os.path.exists(full_path):
            return False
        else:
            return True

    def get_model_path(self, model_id, download_path, model_type="phoneme"):
        if not model_id.startswith("steveway"):
            old_model_id = model_id.split("/")[-1]
            model_id = f"steveway/{old_model_id}_onnx"
        # Check in the download path if the model is available
        full_path = f"{download_path}/{model_type}/{model_id.split('/')[-1]}"
        return full_path


if __name__ == "__main__":
    mh = ModelHandler()
    mh.cache_models()
    print(mh.cached_models)
    mh.download_model("steveway/wav2vec2-xlsr-53-espeak-cv-ft_onnx", "./test_model_download")
