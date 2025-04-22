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

    def download_file(self, url, local_path, file_size=None, max_retries=3, timeout=300):
        """
        Download a file from a URL to a local path
        :param url: URL to download from
        :param local_path: Local path to save to
        :param file_size: Expected file size
        :param max_retries: Maximum number of retries
        :param timeout: Timeout in seconds for the download
        :return: True if successful, False otherwise
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        
        for retry in range(max_retries):
            try:
                print(f"Downloading {os.path.basename(local_path)} (attempt {retry + 1}/{max_retries})...")
                
                # Set a timeout for the request
                response = requests.get(url, headers=headers, stream=True, timeout=30)  # 30 seconds timeout for initial connection
                response.raise_for_status()

                # Get content length from headers if file_size not provided
                if file_size is None:
                    file_size = int(response.headers.get('content-length', 0))
                
                print(f"File size: {file_size / (1024*1024):.2f} MB")

                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                # Track download progress and time
                start_time = time.time()
                last_update_time = start_time
                bytes_downloaded = 0
                
                with open(local_path, "wb") as f:
                    # Create progress bar with known total size
                    with CustomTQDM(total=file_size or 100, unit='iB', unit_scale=True, desc=os.path.basename(local_path)) as pbar:
                        for data in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                            # Check if download has timed out
                            if time.time() - start_time > timeout:
                                print(f"Download timed out after {timeout} seconds")
                                raise TimeoutError(f"Download timed out after {timeout} seconds")
                            
                            size = len(data)  # Use actual chunk size
                            f.write(data)
                            pbar.update(size)
                            
                            # Update progress information
                            bytes_downloaded += size
                            current_time = time.time()
                            
                            # Print progress every 5 seconds
                            if current_time - last_update_time > 5:
                                elapsed = current_time - start_time
                                speed = bytes_downloaded / elapsed if elapsed > 0 else 0
                                percent = (bytes_downloaded / file_size * 100) if file_size > 0 else 0
                                print(f"Progress: {bytes_downloaded / (1024*1024):.2f} MB / {file_size / (1024*1024):.2f} MB "
                                      f"({percent:.1f}%) - {speed / (1024*1024):.2f} MB/s")
                                last_update_time = current_time
                
                # Verify file was downloaded correctly
                if os.path.getsize(local_path) == 0:
                    print(f"Downloaded file is empty: {local_path}")
                    logging.error(f"Downloaded file is empty: {local_path}")
                    os.remove(local_path)
                    if retry < max_retries - 1:
                        print(f"Retrying download (attempt {retry + 2}/{max_retries})...")
                        continue
                    return False
                
                # Verify file size if known
                if file_size > 0 and os.path.getsize(local_path) < file_size * 0.9:  # Allow for some tolerance
                    print(f"Downloaded file is incomplete: {local_path} ({os.path.getsize(local_path)} bytes vs expected {file_size} bytes)")
                    logging.error(f"Downloaded file is incomplete: {local_path} ({os.path.getsize(local_path)} bytes vs expected {file_size} bytes)")
                    os.remove(local_path)
                    if retry < max_retries - 1:
                        print(f"Retrying download (attempt {retry + 2}/{max_retries})...")
                        continue
                    return False
                
                # For ONNX files, verify they can be loaded
                if local_path.endswith('.onnx'):
                    print(f"Verifying ONNX file: {local_path}")
                    if not self.verify_onnx_file(local_path):
                        print(f"Downloaded ONNX file is invalid: {local_path}")
                        logging.error(f"Downloaded ONNX file is invalid: {local_path}")
                        os.remove(local_path)
                        if retry < max_retries - 1:
                            print(f"Retrying download (attempt {retry + 2}/{max_retries})...")
                            continue
                        return False
                
                print(f"Successfully downloaded {os.path.basename(local_path)}")
                return True
            except TimeoutError as e:
                print(f"Download timed out: {str(e)}")
                logging.error(f"Download timed out: {str(e)}")
                if os.path.exists(local_path):
                    os.remove(local_path)  # Clean up partial file
                
                if retry < max_retries - 1:
                    print(f"Retrying download (attempt {retry + 2}/{max_retries})...")
                else:
                    return False
            except Exception as e:
                print(f"Error downloading file {url} to {local_path}: {str(e)}")
                logging.error(f"Error downloading file {url} to {local_path}: {str(e)}")
                if os.path.exists(local_path):
                    os.remove(local_path)  # Clean up partial file
                
                if retry < max_retries - 1:
                    print(f"Retrying download (attempt {retry + 2}/{max_retries})...")
                else:
                    return False
        
        return False

    def verify_onnx_file(self, file_path):
        """
        Verify that an ONNX file is valid
        :param file_path: Path to the ONNX file
        :return: True if valid, False otherwise
        """
        try:
            # Try to load the ONNX file using onnx package if available
            try:
                import onnx
                onnx_model = onnx.load(file_path)
                onnx.checker.check_model(onnx_model)
                return True
            except ImportError:
                # If onnx package is not available, try using onnxruntime
                import onnxruntime as ort
                # Just try to create a session, don't run inference
                session_options = ort.SessionOptions()
                _ = ort.InferenceSession(file_path, sess_options=session_options, providers=['CPUExecutionProvider'])
                return True
        except Exception as e:
            logging.error(f"ONNX file verification failed: {str(e)}")
            return False

    def download_model(self, model_id, download_path, force_redownload=False, skip_large_files=False, max_file_size_mb=100):
        """
        Download a model from Hugging Face
        :param model_id: ID of the model to download
        :param download_path: Path to download to
        :param force_redownload: Force redownload even if model exists
        :param skip_large_files: Skip files larger than max_file_size_mb
        :param max_file_size_mb: Maximum file size in MB to download if skip_large_files is True
        :return: True if successful, False otherwise
        """
        if not model_id:
            return False
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
        
        if not model_type:
            logging.error(f"Model {model_id} not found in any collection")
            return False

        try:
            # Get model files info
            print(f"Getting model info for {model_id}...")
            model_info = self.api.model_info(model_id, token=self.token)
            if not model_info.siblings:
                print("No files found in the model repository")
                raise Exception("No files found in the model repository")

            full_path = f"{download_path}/{model_type}/{model_id.split('/')[-1]}"
            os.makedirs(full_path, exist_ok=True)

            # Check if model already exists and is valid
            if not force_redownload and self.verify_model(full_path):
                print(f"Model {model_id} already exists and is valid")
                logging.info(f"Model {model_id} already exists and is valid")
                return True

            # Download each file
            total_files = len(model_info.siblings)
            success_count = 0
            skipped_count = 0
            
            print(f"Found {total_files} files to download for model {model_id}")
            
            for i, file_info in enumerate(model_info.siblings, 1):
                file_url = f"https://huggingface.co/{model_id}/resolve/main/{file_info.rfilename}"
                local_path = os.path.join(full_path, file_info.rfilename)
                
                # Get file size safely, handling None values
                file_size = getattr(file_info, 'size', None)
                file_size_mb = 0
                if file_size is not None:
                    file_size_mb = file_size / (1024 * 1024)
                
                # Skip if file exists and force_redownload is False
                if not force_redownload and os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                    if not local_path.endswith('.onnx') or self.verify_onnx_file(local_path):
                        print(f"File {file_info.rfilename} already exists and is valid, skipping")
                        logging.info(f"File {file_info.rfilename} already exists and is valid, skipping")
                        success_count += 1
                        continue
                
                # Skip large files if requested
                if skip_large_files and file_size is not None and file_size_mb > max_file_size_mb:
                    print(f"Skipping large file {file_info.rfilename} ({file_size_mb:.2f} MB > {max_file_size_mb} MB)")
                    logging.info(f"Skipping large file {file_info.rfilename} ({file_size_mb:.2f} MB > {max_file_size_mb} MB)")
                    skipped_count += 1
                    continue
                
                # For ONNX files, always skip if they're too large
                if local_path.endswith('.onnx') and skip_large_files:
                    print(f"Skipping ONNX model file {file_info.rfilename} as it's likely too large")
                    logging.info(f"Skipping ONNX model file {file_info.rfilename} as it's likely too large")
                    skipped_count += 1
                    continue
                
                print(f"Downloading {file_info.rfilename} ({i}/{total_files}) - {file_size_mb:.2f} MB")
                if self.download_file(file_url, local_path, file_size):
                    success_count += 1
                else:
                    print(f"Failed to download {file_info.rfilename}")
                    logging.error(f"Failed to download {file_info.rfilename}")
            
            # Check if all files were downloaded successfully
            if success_count + skipped_count == total_files:
                if skipped_count > 0:
                    print(f"Model {model_id} downloaded partially: {success_count} files downloaded, {skipped_count} files skipped")
                    logging.info(f"Model {model_id} downloaded partially: {success_count} files downloaded, {skipped_count} files skipped")
                    return True  # Consider it a success if we skipped some files intentionally
                else:
                    print(f"Model {model_id} downloaded successfully to {full_path}")
                    logging.info(f"Model {model_id} downloaded successfully to {full_path}")
                    return True
            else:
                print(f"Only {success_count}/{total_files} files were downloaded successfully ({skipped_count} skipped)")
                logging.error(f"Only {success_count}/{total_files} files were downloaded successfully ({skipped_count} skipped)")
                return False

        except Exception as e:
            print(f"Error downloading model: {str(e)}")
            logging.error(f"Error downloading model: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False

    def verify_model(self, model_path):
        """
        Verify that a model is valid
        :param model_path: Path to the model directory
        :return: True if valid, False otherwise
        """
        try:
            # Check if directory exists
            if not os.path.exists(model_path) or not os.path.isdir(model_path):
                return False
            
            # Check if settings.yaml exists
            settings_file = os.path.join(model_path, "settings.yaml")
            if not os.path.exists(settings_file):
                # Try to find any YAML file
                yaml_files = [f for f in os.listdir(model_path) if f.endswith('.yaml')]
                if not yaml_files:
                    return False
                settings_file = os.path.join(model_path, yaml_files[0])
            
            # Check if ONNX file exists and is valid
            onnx_files = [f for f in os.listdir(model_path) if f.endswith('.onnx')]
            if not onnx_files:
                return False
            
            onnx_file = os.path.join(model_path, onnx_files[0])
            if not self.verify_onnx_file(onnx_file):
                return False
            
            return True
        except Exception as e:
            logging.error(f"Error verifying model: {str(e)}")
            return False

    def repair_model(self, model_id, download_path):
        """
        Repair a model by redownloading it
        :param model_id: ID of the model to repair
        :param download_path: Path to download to
        :return: True if successful, False otherwise
        """
        logging.info(f"Repairing model {model_id}...")
        return self.download_model(model_id, download_path, force_redownload=True)

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
