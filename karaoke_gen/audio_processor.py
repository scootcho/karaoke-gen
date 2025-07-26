import os
import sys
import json
import logging
import glob
import shutil
import tempfile
import time
import fcntl
import errno
import psutil
from datetime import datetime
from pydub import AudioSegment

# Try to import the remote API client if available
try:
    from audio_separator.remote import AudioSeparatorAPIClient
    REMOTE_API_AVAILABLE = True
except ImportError:
    REMOTE_API_AVAILABLE = False
    AudioSeparatorAPIClient = None


# Placeholder class or functions for audio processing
class AudioProcessor:
    def __init__(
        self,
        logger,
        log_level,
        log_formatter,
        model_file_dir,
        lossless_output_format,
        clean_instrumental_model,
        backing_vocals_models,
        other_stems_models,
        ffmpeg_base_command,
    ):
        self.logger = logger
        self.log_level = log_level
        self.log_formatter = log_formatter
        self.model_file_dir = model_file_dir
        self.lossless_output_format = lossless_output_format
        self.clean_instrumental_model = clean_instrumental_model
        self.backing_vocals_models = backing_vocals_models
        self.other_stems_models = other_stems_models
        self.ffmpeg_base_command = ffmpeg_base_command  # Needed for combined instrumentals

    def _file_exists(self, file_path):
        """Check if a file exists and log the result."""
        exists = os.path.isfile(file_path)
        if exists:
            self.logger.info(f"File already exists, skipping creation: {file_path}")
        return exists

    def separate_audio(self, audio_file, model_name, artist_title, track_output_dir, instrumental_path, vocals_path):
        if audio_file is None or not os.path.isfile(audio_file):
            raise Exception("Error: Invalid audio source provided.")

        self.logger.debug(f"audio_file is valid file: {audio_file}")

        self.logger.info(
            f"instantiating Separator with model_file_dir: {self.model_file_dir}, model_filename: {model_name} output_format: {self.lossless_output_format}"
        )

        from audio_separator.separator import Separator

        separator = Separator(
            log_level=self.log_level,
            log_formatter=self.log_formatter,
            model_file_dir=self.model_file_dir,
            output_format=self.lossless_output_format,
        )

        separator.load_model(model_filename=model_name)
        output_files = separator.separate(audio_file)

        self.logger.debug(f"Separator output files: {output_files}")

        model_name_no_extension = os.path.splitext(model_name)[0]

        for file in output_files:
            if "(Vocals)" in file:
                self.logger.info(f"Moving Vocals file {file} to {vocals_path}")
                shutil.move(file, vocals_path)
            elif "(Instrumental)" in file:
                self.logger.info(f"Moving Instrumental file {file} to {instrumental_path}")
                shutil.move(file, instrumental_path)
            elif model_name in file:
                # Example filename 1: "Freddie Jackson - All I'll Ever Ask (feat. Najee) (Local)_(Piano)_htdemucs_6s.flac"
                # Example filename 2: "Freddie Jackson - All I'll Ever Ask (feat. Najee) (Local)_(Guitar)_htdemucs_6s.flac"
                # The stem name in these examples would be "Piano" or "Guitar"
                # Extract stem_name from the filename
                stem_name = file.split(f"_{model_name}")[0].split("_")[-1]
                stem_name = stem_name.strip("()")  # Remove parentheses if present

                other_stem_path = os.path.join(track_output_dir, f"{artist_title} ({stem_name} {model_name}).{self.lossless_output_format}")
                self.logger.info(f"Moving other stem file {file} to {other_stem_path}")
                shutil.move(file, other_stem_path)

            elif model_name_no_extension in file:
                # Example filename 1: "Freddie Jackson - All I'll Ever Ask (feat. Najee) (Local)_(Piano)_htdemucs_6s.flac"
                # Example filename 2: "Freddie Jackson - All I'll Ever Ask (feat. Najee) (Local)_(Guitar)_htdemucs_6s.flac"
                # The stem name in these examples would be "Piano" or "Guitar"
                # Extract stem_name from the filename
                stem_name = file.split(f"_{model_name_no_extension}")[0].split("_")[-1]
                stem_name = stem_name.strip("()")  # Remove parentheses if present

                other_stem_path = os.path.join(track_output_dir, f"{artist_title} ({stem_name} {model_name}).{self.lossless_output_format}")
                self.logger.info(f"Moving other stem file {file} to {other_stem_path}")
                shutil.move(file, other_stem_path)

        self.logger.info(f"Separation complete! Output file(s): {vocals_path} {instrumental_path}")

    def process_audio_separation(self, audio_file, artist_title, track_output_dir):
        # Check if we should use remote API
        remote_api_url = os.environ.get("AUDIO_SEPARATOR_API_URL")
        if remote_api_url:
            if not REMOTE_API_AVAILABLE:
                self.logger.warning("AUDIO_SEPARATOR_API_URL is set but remote API client is not available. "
                                  "Please ensure audio-separator is updated to a version that includes remote API support. "
                                  "Falling back to local processing.")
            else:
                self.logger.info(f"Using remote audio separator API at: {remote_api_url}")
                try:
                    return self._process_audio_separation_remote(audio_file, artist_title, track_output_dir, remote_api_url)
                except Exception as e:
                    error_str = str(e)
                    # Don't fall back for download failures - these indicate API issues that should be fixed
                    if ("no files were downloaded" in error_str or 
                        "failed to produce essential" in error_str):
                        self.logger.error(f"Remote API processing failed with download/file organization issue: {error_str}")
                        self.logger.error("This indicates an audio-separator API issue that should be fixed. Not falling back to local processing.")
                        raise e
                    else:
                        # Fall back for other types of errors (network issues, etc.)
                        self.logger.error(f"Remote API processing failed: {error_str}")
                        self.logger.info("Falling back to local audio separation")
        else:
            self.logger.info("AUDIO_SEPARATOR_API_URL not set, using local audio separation. "
                           "Set this environment variable to use remote GPU processing.")
        
        from audio_separator.separator import Separator

        self.logger.info(f"Starting local audio separation process for {artist_title}")

        # Define lock file path in system temp directory
        lock_file_path = os.path.join(tempfile.gettempdir(), "audio_separator.lock")

        # Try to acquire lock
        while True:
            try:
                # First check if there's a stale lock
                if os.path.exists(lock_file_path):
                    try:
                        with open(lock_file_path, "r") as f:
                            lock_data = json.load(f)
                            pid = lock_data.get("pid")
                            start_time = datetime.fromisoformat(lock_data.get("start_time"))
                            running_track = lock_data.get("track")

                            # Check if process is still running
                            if not psutil.pid_exists(pid):
                                self.logger.warning(f"Found stale lock from dead process {pid}, removing...")
                                os.remove(lock_file_path)
                            else:
                                # Calculate runtime
                                runtime = datetime.now() - start_time
                                runtime_mins = runtime.total_seconds() / 60

                                # Get process command line
                                try:
                                    proc = psutil.Process(pid)
                                    cmdline_args = proc.cmdline()
                                    # Handle potential bytes in cmdline args (cross-platform compatibility)
                                    cmd = " ".join(arg.decode('utf-8', errors='replace') if isinstance(arg, bytes) else arg for arg in cmdline_args)
                                except (psutil.AccessDenied, psutil.NoSuchProcess):
                                    cmd = "<command unavailable>"

                                self.logger.info(
                                    f"Waiting for other audio separation process to complete before starting separation for {artist_title}...\n"
                                    f"Currently running process details:\n"
                                    f"  Track: {running_track}\n"
                                    f"  PID: {pid}\n"
                                    f"  Running time: {runtime_mins:.1f} minutes\n"
                                    f"  Command: {cmd}\n"
                                    f"To force clear the lock and kill the process, run:\n"
                                    f"  kill {pid} && rm {lock_file_path}"
                                )
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        self.logger.warning(f"Found invalid lock file, removing: {e}")
                        os.remove(lock_file_path)

                # Try to acquire lock
                lock_file = open(lock_file_path, "w")
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                # Write metadata to lock file
                lock_data = {
                    "pid": os.getpid(),
                    "start_time": datetime.now().isoformat(),
                    "track": f"{artist_title}",
                }
                json.dump(lock_data, lock_file)
                lock_file.flush()
                break

            except IOError as e:
                if e.errno != errno.EAGAIN:
                    raise
                # Lock is held by another process
                time.sleep(30)  # Wait 30 seconds before trying again
                continue

        try:
            separator = Separator(
                log_level=self.log_level,
                log_formatter=self.log_formatter,
                model_file_dir=self.model_file_dir,
                output_format=self.lossless_output_format,
            )

            stems_dir = self._create_stems_directory(track_output_dir)
            result = {"clean_instrumental": {}, "other_stems": {}, "backing_vocals": {}, "combined_instrumentals": {}}

            if os.environ.get("KARAOKE_GEN_SKIP_AUDIO_SEPARATION"):
                return result

            result["clean_instrumental"] = self._separate_clean_instrumental(
                separator, audio_file, artist_title, track_output_dir, stems_dir
            )
            result["other_stems"] = self._separate_other_stems(separator, audio_file, artist_title, stems_dir)
            result["backing_vocals"] = self._separate_backing_vocals(
                separator, result["clean_instrumental"]["vocals"], artist_title, stems_dir
            )
            result["combined_instrumentals"] = self._generate_combined_instrumentals(
                result["clean_instrumental"]["instrumental"], result["backing_vocals"], artist_title, track_output_dir
            )
            self._normalize_audio_files(result, artist_title, track_output_dir)

            # Create Audacity LOF file
            if result["backing_vocals"]:
                lof_path = os.path.join(stems_dir, f"{artist_title} (Audacity).lof")
                first_model = list(result["backing_vocals"].keys())[0]

                files_to_include = [
                    audio_file,  # Original audio
                    result["clean_instrumental"]["instrumental"],  # Clean instrumental
                    result["backing_vocals"][first_model]["backing_vocals"],  # Backing vocals
                    result["combined_instrumentals"][first_model],  # Combined instrumental+BV
                ]

                # Convert to absolute paths
                files_to_include = [os.path.abspath(f) for f in files_to_include]

                with open(lof_path, "w") as lof:
                    for file_path in files_to_include:
                        lof.write(f'file "{file_path}"\n')

                self.logger.info(f"Created Audacity LOF file: {lof_path}")
                result["audacity_lof"] = lof_path

                # Launch Audacity with multiple tracks
                if sys.platform == "darwin":  # Check if we're on macOS
                    if lof_path and os.path.exists(lof_path):
                        self.logger.info(f"Launching Audacity with LOF file: {lof_path}")
                        os.system(f'open -a Audacity "{lof_path}"')
                    else:
                        self.logger.debug("Audacity LOF file not available or not found")

            self.logger.info("Audio separation, combination, and normalization process completed")
            return result
        finally:
            # Release lock
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            try:
                os.remove(lock_file_path)
            except OSError:
                pass

    def _process_audio_separation_remote(self, audio_file, artist_title, track_output_dir, remote_api_url):
        """Process audio separation using remote API with proper two-stage workflow."""
        self.logger.info(f"Starting remote audio separation process for {artist_title}")
        
        # Initialize the API client
        api_client = AudioSeparatorAPIClient(remote_api_url, self.logger)
        
        stems_dir = self._create_stems_directory(track_output_dir)
        result = {"clean_instrumental": {}, "other_stems": {}, "backing_vocals": {}, "combined_instrumentals": {}}

        if os.environ.get("KARAOKE_GEN_SKIP_AUDIO_SEPARATION"):
            return result

        try:
            # Stage 1: Process original song with clean instrumental model + other stems models
            stage1_models = []
            if self.clean_instrumental_model:
                stage1_models.append(self.clean_instrumental_model)
            stage1_models.extend(self.other_stems_models)
            
            self.logger.info(f"Stage 1: Submitting audio separation job with models: {stage1_models}")
            
            # Submit the first stage job
            stage1_result = api_client.separate_audio_and_wait(
                audio_file,
                models=stage1_models,
                timeout=1800,  # 30 minutes timeout
                poll_interval=15,  # Check every 15 seconds
                download=True,
                output_dir=stems_dir,
                output_format=self.lossless_output_format.lower()
            )
            
            if stage1_result["status"] != "completed":
                raise Exception(f"Stage 1 remote audio separation failed: {stage1_result.get('error', 'Unknown error')}")
            
            self.logger.info(f"Stage 1 completed. Downloaded {len(stage1_result['downloaded_files'])} files")
            
            # Check if we actually got the expected files for Stage 1
            if len(stage1_result["downloaded_files"]) == 0:
                error_msg = ("Stage 1 audio separation completed successfully but no files were downloaded. "
                           "This indicates a filename encoding or API issue in the audio-separator remote service. "
                           f"Expected files for models {stage1_models} but got 0.")
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
            # Organize the stage 1 results
            result = self._organize_stage1_remote_results(
                stage1_result["downloaded_files"], artist_title, track_output_dir, stems_dir
            )
            
            # Validate that we got the essential clean instrumental outputs
            if not result["clean_instrumental"].get("vocals") or not result["clean_instrumental"].get("instrumental"):
                missing = []
                if not result["clean_instrumental"].get("vocals"):
                    missing.append("clean vocals")
                if not result["clean_instrumental"].get("instrumental"):
                    missing.append("clean instrumental")
                error_msg = (f"Stage 1 completed but failed to produce essential clean instrumental outputs: {', '.join(missing)}. "
                           "This may indicate a model naming or file organization issue in the remote API.")
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
            # Stage 2: Process clean vocals with backing vocals models (if we have both)
            if result["clean_instrumental"].get("vocals") and self.backing_vocals_models:
                self.logger.info(f"Stage 2: Processing clean vocals for backing vocals separation...")
                vocals_path = result["clean_instrumental"]["vocals"]
                
                stage2_result = api_client.separate_audio_and_wait(
                    vocals_path,
                    models=self.backing_vocals_models,
                    timeout=900,  # 15 minutes timeout for backing vocals
                    poll_interval=10,
                    download=True,
                    output_dir=stems_dir,
                    output_format=self.lossless_output_format.lower()
                )
                
                if stage2_result["status"] == "completed":
                    self.logger.info(f"Stage 2 completed. Downloaded {len(stage2_result['downloaded_files'])} files")
                    
                    # Check if we actually got the expected files
                    if len(stage2_result["downloaded_files"]) == 0:
                        error_msg = ("Stage 2 backing vocals separation completed successfully but no files were downloaded. "
                                   "This indicates a filename encoding or API issue in the audio-separator remote service. "
                                   "Expected 2 files (lead vocals + backing vocals) but got 0.")
                        self.logger.error(error_msg)
                        raise Exception(error_msg)
                    
                    # Organize the stage 2 results (backing vocals)
                    backing_vocals_result = self._organize_stage2_remote_results(
                        stage2_result["downloaded_files"], artist_title, stems_dir
                    )
                    result["backing_vocals"] = backing_vocals_result
                else:
                    error_msg = f"Stage 2 backing vocals separation failed: {stage2_result.get('error', 'Unknown error')}"
                    self.logger.error(error_msg)
                    raise Exception(error_msg)
            else:
                result["backing_vocals"] = {}
            
            # Generate combined instrumentals
            if result["clean_instrumental"].get("instrumental") and result["backing_vocals"]:
                result["combined_instrumentals"] = self._generate_combined_instrumentals(
                    result["clean_instrumental"]["instrumental"], result["backing_vocals"], artist_title, track_output_dir
                )
            else:
                result["combined_instrumentals"] = {}
            
            # Normalize audio files
            self._normalize_audio_files(result, artist_title, track_output_dir)

            # Create Audacity LOF file
            if result["backing_vocals"]:
                lof_path = os.path.join(stems_dir, f"{artist_title} (Audacity).lof")
                first_model = list(result["backing_vocals"].keys())[0]

                files_to_include = [
                    audio_file,  # Original audio
                    result["clean_instrumental"]["instrumental"],  # Clean instrumental
                    result["backing_vocals"][first_model]["backing_vocals"],  # Backing vocals
                    result["combined_instrumentals"][first_model],  # Combined instrumental+BV
                ]

                # Convert to absolute paths
                files_to_include = [os.path.abspath(f) for f in files_to_include]

                with open(lof_path, "w") as lof:
                    for file_path in files_to_include:
                        lof.write(f'file "{file_path}"\n')

                self.logger.info(f"Created Audacity LOF file: {lof_path}")
                result["audacity_lof"] = lof_path

                # Launch Audacity with multiple tracks
                if sys.platform == "darwin":  # Check if we're on macOS
                    if lof_path and os.path.exists(lof_path):
                        self.logger.info(f"Launching Audacity with LOF file: {lof_path}")
                        os.system(f'open -a Audacity "{lof_path}"')
                    else:
                        self.logger.debug("Audacity LOF file not available or not found")

            self.logger.info("Remote audio separation, combination, and normalization process completed")
            return result
            
        except Exception as e:
            self.logger.error(f"Error during remote audio separation: {str(e)}")
            raise e

    def _organize_stage1_remote_results(self, downloaded_files, artist_title, track_output_dir, stems_dir):
        """Organize stage 1 separation results (clean instrumental + other stems)."""
        result = {"clean_instrumental": {}, "other_stems": {}}
        
        for file_path in downloaded_files:
            filename = os.path.basename(file_path)
            self.logger.debug(f"Stage 1 - Processing downloaded file: {filename}")
            
            # Determine which model and stem type this file represents
            model_name = None
            stem_type = None
            
            # Extract model name and stem type from filename
            # Expected format: "audio_(StemType)_modelname.ext"
            if "_(Vocals)_" in filename:
                stem_type = "Vocals"
                model_name = filename.split("_(Vocals)_")[1].split(".")[0]
            elif "_(Instrumental)_" in filename:
                stem_type = "Instrumental"
                model_name = filename.split("_(Instrumental)_")[1].split(".")[0]
            elif "_(Drums)_" in filename:
                stem_type = "Drums"
                model_name = filename.split("_(Drums)_")[1].split(".")[0]
            elif "_(Bass)_" in filename:
                stem_type = "Bass"
                model_name = filename.split("_(Bass)_")[1].split(".")[0]
            elif "_(Other)_" in filename:
                stem_type = "Other"
                model_name = filename.split("_(Other)_")[1].split(".")[0]
            elif "_(Guitar)_" in filename:
                stem_type = "Guitar"
                model_name = filename.split("_(Guitar)_")[1].split(".")[0]
            elif "_(Piano)_" in filename:
                stem_type = "Piano"
                model_name = filename.split("_(Piano)_")[1].split(".")[0]
            else:
                # Try to extract stem type from parentheses
                import re
                match = re.search(r'_\(([^)]+)\)_([^.]+)', filename)
                if match:
                    stem_type = match.group(1)
                    model_name = match.group(2)
                else:
                    self.logger.warning(f"Could not parse stem type and model from filename: {filename}")
                    continue
            
            # Check if this model name matches the clean instrumental model
            is_clean_instrumental_model = (
                model_name == self.clean_instrumental_model or 
                self.clean_instrumental_model.startswith(model_name) or
                model_name.startswith(self.clean_instrumental_model.split('.')[0])
            )
            
            if is_clean_instrumental_model:
                if stem_type == "Vocals":
                    target_path = os.path.join(stems_dir, f"{artist_title} (Vocals {self.clean_instrumental_model}).{self.lossless_output_format}")
                    shutil.move(file_path, target_path)
                    result["clean_instrumental"]["vocals"] = target_path
                elif stem_type == "Instrumental":
                    target_path = os.path.join(track_output_dir, f"{artist_title} (Instrumental {self.clean_instrumental_model}).{self.lossless_output_format}")
                    shutil.move(file_path, target_path)
                    result["clean_instrumental"]["instrumental"] = target_path
            
            elif any(model_name == os_model or os_model.startswith(model_name) or model_name.startswith(os_model.split('.')[0]) for os_model in self.other_stems_models):
                # Find the matching other stems model
                matching_os_model = None
                for os_model in self.other_stems_models:
                    if model_name == os_model or os_model.startswith(model_name) or model_name.startswith(os_model.split('.')[0]):
                        matching_os_model = os_model
                        break
                
                if matching_os_model:
                    if matching_os_model not in result["other_stems"]:
                        result["other_stems"][matching_os_model] = {}
                    
                    target_path = os.path.join(stems_dir, f"{artist_title} ({stem_type} {matching_os_model}).{self.lossless_output_format}")
                    shutil.move(file_path, target_path)
                    result["other_stems"][matching_os_model][stem_type] = target_path
        
        return result

    def _organize_stage2_remote_results(self, downloaded_files, artist_title, stems_dir):
        """Organize stage 2 separation results (backing vocals)."""
        result = {}
        
        for file_path in downloaded_files:
            filename = os.path.basename(file_path)
            self.logger.debug(f"Stage 2 - Processing downloaded file: {filename}")
            
            # Determine which model and stem type this file represents
            model_name = None
            stem_type = None
            
            # Extract model name and stem type from filename
            if "_(Vocals)_" in filename:
                stem_type = "Vocals"
                model_name = filename.split("_(Vocals)_")[1].split(".")[0]
            elif "_(Instrumental)_" in filename:
                stem_type = "Instrumental"
                model_name = filename.split("_(Instrumental)_")[1].split(".")[0]
            else:
                # Try to extract stem type from parentheses
                import re
                match = re.search(r'_\(([^)]+)\)_([^.]+)', filename)
                if match:
                    stem_type = match.group(1)
                    model_name = match.group(2)
                else:
                    self.logger.warning(f"Could not parse stem type and model from filename: {filename}")
                    continue
            
            # Find the matching backing vocals model
            matching_bv_model = None
            for bv_model in self.backing_vocals_models:
                if model_name == bv_model or bv_model.startswith(model_name) or model_name.startswith(bv_model.split('.')[0]):
                    matching_bv_model = bv_model
                    break
            
            if matching_bv_model:
                if matching_bv_model not in result:
                    result[matching_bv_model] = {}
                
                if stem_type == "Vocals":
                    target_path = os.path.join(stems_dir, f"{artist_title} (Lead Vocals {matching_bv_model}).{self.lossless_output_format}")
                    shutil.move(file_path, target_path)
                    result[matching_bv_model]["lead_vocals"] = target_path
                elif stem_type == "Instrumental":
                    target_path = os.path.join(stems_dir, f"{artist_title} (Backing Vocals {matching_bv_model}).{self.lossless_output_format}")
                    shutil.move(file_path, target_path)
                    result[matching_bv_model]["backing_vocals"] = target_path
        
        return result

    def _create_stems_directory(self, track_output_dir):
        stems_dir = os.path.join(track_output_dir, "stems")
        os.makedirs(stems_dir, exist_ok=True)
        self.logger.info(f"Created stems directory: {stems_dir}")
        return stems_dir

    def _separate_clean_instrumental(self, separator, audio_file, artist_title, track_output_dir, stems_dir):
        self.logger.info(f"Separating using clean instrumental model: {self.clean_instrumental_model}")
        instrumental_path = os.path.join(
            track_output_dir, f"{artist_title} (Instrumental {self.clean_instrumental_model}).{self.lossless_output_format}"
        )
        vocals_path = os.path.join(stems_dir, f"{artist_title} (Vocals {self.clean_instrumental_model}).{self.lossless_output_format}")

        result = {}
        if not self._file_exists(instrumental_path) or not self._file_exists(vocals_path):
            separator.load_model(model_filename=self.clean_instrumental_model)
            clean_output_files = separator.separate(audio_file)

            for file in clean_output_files:
                if "(Vocals)" in file and not self._file_exists(vocals_path):
                    shutil.move(file, vocals_path)
                    result["vocals"] = vocals_path
                elif "(Instrumental)" in file and not self._file_exists(instrumental_path):
                    shutil.move(file, instrumental_path)
                    result["instrumental"] = instrumental_path
        else:
            result["vocals"] = vocals_path
            result["instrumental"] = instrumental_path

        return result

    def _separate_other_stems(self, separator, audio_file, artist_title, stems_dir):
        self.logger.info(f"Separating using other stems models: {self.other_stems_models}")
        result = {}
        for model in self.other_stems_models:
            self.logger.info(f"Processing with model: {model}")
            result[model] = {}

            # Check if any stem files for this model already exist
            existing_stems = glob.glob(os.path.join(stems_dir, f"{artist_title} (*{model}).{self.lossless_output_format}"))

            if existing_stems:
                self.logger.info(f"Found existing stem files for model {model}, skipping separation")
                for stem_file in existing_stems:
                    stem_name = os.path.basename(stem_file).split("(")[1].split(")")[0].strip()
                    result[model][stem_name] = stem_file
            else:
                separator.load_model(model_filename=model)
                other_stems_output = separator.separate(audio_file)

                for file in other_stems_output:
                    file_name = os.path.basename(file)
                    stem_name = file_name[file_name.rfind("_(") + 2 : file_name.rfind(")_")]
                    new_filename = f"{artist_title} ({stem_name} {model}).{self.lossless_output_format}"
                    other_stem_path = os.path.join(stems_dir, new_filename)
                    if not self._file_exists(other_stem_path):
                        shutil.move(file, other_stem_path)
                    result[model][stem_name] = other_stem_path

        return result

    def _separate_backing_vocals(self, separator, vocals_path, artist_title, stems_dir):
        self.logger.info(f"Separating clean vocals using backing vocals models: {self.backing_vocals_models}")
        result = {}
        for model in self.backing_vocals_models:
            self.logger.info(f"Processing with model: {model}")
            result[model] = {}
            lead_vocals_path = os.path.join(stems_dir, f"{artist_title} (Lead Vocals {model}).{self.lossless_output_format}")
            backing_vocals_path = os.path.join(stems_dir, f"{artist_title} (Backing Vocals {model}).{self.lossless_output_format}")

            if not self._file_exists(lead_vocals_path) or not self._file_exists(backing_vocals_path):
                separator.load_model(model_filename=model)
                backing_vocals_output = separator.separate(vocals_path)

                for file in backing_vocals_output:
                    if "(Vocals)" in file and not self._file_exists(lead_vocals_path):
                        shutil.move(file, lead_vocals_path)
                        result[model]["lead_vocals"] = lead_vocals_path
                    elif "(Instrumental)" in file and not self._file_exists(backing_vocals_path):
                        shutil.move(file, backing_vocals_path)
                        result[model]["backing_vocals"] = backing_vocals_path
            else:
                result[model]["lead_vocals"] = lead_vocals_path
                result[model]["backing_vocals"] = backing_vocals_path
        return result

    def _generate_combined_instrumentals(self, instrumental_path, backing_vocals_result, artist_title, track_output_dir):
        self.logger.info("Generating combined instrumental tracks with backing vocals")
        result = {}
        for model, paths in backing_vocals_result.items():
            backing_vocals_path = paths["backing_vocals"]
            combined_path = os.path.join(track_output_dir, f"{artist_title} (Instrumental +BV {model}).{self.lossless_output_format}")

            if not self._file_exists(combined_path):
                ffmpeg_command = (
                    f'{self.ffmpeg_base_command} -i "{instrumental_path}" -i "{backing_vocals_path}" '
                    f'-filter_complex "[0:a][1:a]amix=inputs=2:duration=longest:weights=1 1" '
                    f'-c:a {self.lossless_output_format.lower()} "{combined_path}"'
                )

                self.logger.debug(f"Running command: {ffmpeg_command}")
                os.system(ffmpeg_command)

            result[model] = combined_path
        return result

    def _normalize_audio_files(self, separation_result, artist_title, track_output_dir):
        self.logger.info("Normalizing clean instrumental and combined instrumentals")

        files_to_normalize = [
            ("clean_instrumental", separation_result["clean_instrumental"]["instrumental"]),
        ] + [("combined_instrumentals", path) for path in separation_result["combined_instrumentals"].values()]

        for key, file_path in files_to_normalize:
            if self._file_exists(file_path):
                try:
                    self._normalize_audio(file_path, file_path)  # Normalize in-place

                    # Verify the normalized file
                    if os.path.getsize(file_path) > 0:
                        self.logger.info(f"Successfully normalized: {file_path}")
                    else:
                        raise Exception("Normalized file is empty")

                except Exception as e:
                    self.logger.error(f"Error during normalization of {file_path}: {e}")
                    self.logger.warning(f"Normalization failed for {file_path}. Original file remains unchanged.")
            else:
                self.logger.warning(f"File not found for normalization: {file_path}")

        self.logger.info("Audio normalization process completed")

    def _normalize_audio(self, input_path, output_path, target_level=0.0):
        self.logger.info(f"Normalizing audio file: {input_path}")

        # Load audio file
        audio = AudioSegment.from_file(input_path, format=self.lossless_output_format.lower())

        # Calculate the peak amplitude
        peak_amplitude = float(audio.max_dBFS)

        # Calculate the necessary gain
        gain_db = target_level - peak_amplitude

        # Apply gain
        normalized_audio = audio.apply_gain(gain_db)

        # Ensure the audio is not completely silent
        if normalized_audio.rms == 0:
            self.logger.warning(f"Normalized audio is silent for {input_path}. Using original audio.")
            normalized_audio = audio

        # Export normalized audio, overwriting the original file
        normalized_audio.export(output_path, format=self.lossless_output_format.lower())

        self.logger.info(f"Normalized audio saved, replacing: {output_path}")
        self.logger.debug(f"Original peak: {peak_amplitude} dB, Applied gain: {gain_db} dB")
