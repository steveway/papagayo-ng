import logging
import os
import sys
import threading

from huggingface_hub import get_collection, snapshot_download, list_collections
from tqdm import TqdmDeprecationWarning
from tqdm.asyncio import tqdm as base_tqdm


class CustomTQDM(base_tqdm):

    def __init__(self, *args, **kwargs):
        name = kwargs.pop("name", None)  # do not pass `name` to `tqdm`
        kwargs["smoothing"] = 1

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
        self.token = "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"  # This token has only Read Access
        self.collections = list_collections(owner="steveway", token=self.token)
        self.cached_models = {"phoneme": {}, "emotion": {}}
        self.download_threads = []
        for collection in self.collections:
            if collection.title == "emotion_models":
                self.emotion_collection = get_collection(collection.slug, token=self.token)
            elif collection.title == "phoneme_models":
                self.phoneme_collection = get_collection(collection.slug, token=self.token)
            else:
                pass

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

    def download_model(self, model_id, download_path):
        if not model_id:
            return
        if not model_id.startswith("steveway"):
            old_model_id = model_id.split("/")[-1]
            model_id = f"steveway/{old_model_id}_onnx"

        model_type = ""
        for item in self.emotion_collection.items:
            if item.item_id == model_id:
                model_type = "emotion"
                break
        for item in self.phoneme_collection.items:
            if item.item_id == model_id:
                model_type = "phoneme"
                break
        full_path = f"{download_path}/{model_type}/{model_id.split('/')[-1]}"
        snapshot_download(model_id, local_dir=full_path, token=self.token, tqdm_class=CustomTQDM)

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
