import logging
import os
import sys
import threading
import time
import requests
from huggingface_hub import get_collection, list_collections, HfApi
from tqdm import TqdmDeprecationWarning
from tqdm.asyncio import tqdm as base_tqdm
from PySide6 import QtCore


class ProgressSignal(QtCore.QObject):
    progress_signal = QtCore.Signal(int)


class CustomTQDM(base_tqdm):
    _last_progress = -1  # Class variable instead of instance variable
    signal = None  # Class variable for signal

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def display(self, msg=None, pos=None):
        try:
            # Get current progress
            n = self.n if hasattr(self, 'n') else 0
            total = self.total if hasattr(self, 'total') else 100
            
            # Calculate percentage
            progress_percent = int((n / total) * 100) if total > 0 else 0
            
            # Only emit if progress has changed
            if progress_percent != CustomTQDM._last_progress:
                CustomTQDM._last_progress = progress_percent
                if CustomTQDM.signal:
                    print(f"Progress: {n}/{total} = {progress_percent}%")  # Debug print
                    CustomTQDM.signal.progress_signal.emit(progress_percent)
                    QtCore.QCoreApplication.processEvents()  # Process events to update GUI
        except Exception as e:
            logging.error(f"Error in CustomTQDM display: {str(e)}")
        return True

    @classmethod
    def set_signal(cls, signal_instance):
        cls.signal = signal_instance
        cls._last_progress = -1


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
        self.api = HfApi()
        for collection in self.collections:
            if collection.title == "emotion_models":
                self.emotion_collection = get_collection(collection.slug, token=self.token)
            elif collection.title == "phoneme_models":
                self.phoneme_collection = get_collection(collection.slug, token=self.token)
            else:
                pass

    def download_file(self, url, local_path, file_size=None):
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()

        # Get content length from headers if file_size not provided
        if file_size is None:
            file_size = int(response.headers.get('content-length', 0))

        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        try:
            with open(local_path, "wb") as f:
                # Create progress bar with known total size
                with CustomTQDM(total=file_size or 100, unit='iB', unit_scale=True, desc=os.path.basename(local_path)) as pbar:
                    for data in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                        size = len(data)  # Use actual chunk size
                        f.write(data)
                        pbar.update(size)
        except Exception as e:
            if os.path.exists(local_path):
                os.remove(local_path)  # Clean up partial file
            raise

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

        try:
            # Get model files info
            model_info = self.api.model_info(model_id, token=self.token)
            if not model_info.siblings:
                raise Exception("No files found in the model repository")

            full_path = f"{download_path}/{model_type}/{model_id.split('/')[-1]}"
            os.makedirs(full_path, exist_ok=True)

            # Download each file
            total_files = len(model_info.siblings)
            for i, file_info in enumerate(model_info.siblings, 1):
                file_url = f"https://huggingface.co/{model_id}/resolve/main/{file_info.rfilename}"
                local_path = os.path.join(full_path, file_info.rfilename)
                
                print(f"Downloading {file_info.rfilename} ({i}/{total_files})...")
                self.download_file(file_url, local_path, getattr(file_info, 'size', None))

        except Exception as e:
            logging.error(f"Error downloading model: {str(e)}")
            raise

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
