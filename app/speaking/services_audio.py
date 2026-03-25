import librosa
import soundfile as sf
import numpy as np
import os
import imageio
from core.logger import logger

def preprocess_audio(file_path: str) -> str:
    """
    Load audio, trim silence, normalize, and save as a clean file.
    Returns the path to the cleaned file.
    """
    target_sr = 16000

    try:
        # 1. Try standard Librosa load (uses soundfile/audioread)
        y, sr = librosa.load(file_path, sr=target_sr)
    except Exception as e:
        logger.warning(f"Librosa load failed: {e}. Trying FFmpeg conversion fallback...")
        try:
            # 1b. Fallback: Convert to WAV using imageio_ffmpeg bundled binary
            import imageio_ffmpeg
            import subprocess
            
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            
            # Create a temp filename
            temp_wav = file_path + ".temp.wav"
            
            # Convert: input -> wav, 16k sample rate, mono
            # -y overwrites if exists
            subprocess.run([
                ffmpeg_exe, 
                "-i", file_path, 
                "-ar", str(target_sr), 
                "-ac", "1", 
                temp_wav, 
                "-y"
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Now load the clean WAV
            y, sr = librosa.load(temp_wav, sr=target_sr)
            logger.info("FFmpeg conversion successful.")
            
            # Cleanup temp file
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
            
        except Exception as e2:
            logger.error(f"FFmpeg fallback failed: {e2}", exc_info=True)
            # Try to cleanup if failed
            if 'temp_wav' in locals() and os.path.exists(temp_wav):
                os.remove(temp_wav)
                
            # If all fails, re-raise original or new error
            raise ValueError(f"Could not load audio file. Ensure ffmpeg is installed or format is supported. Error: {e}")

    # 2. Trim silence (top_db=20 is standard for speech)
    y_trimmed, _ = librosa.effects.trim(y, top_db=20)

    # 3. Normalize amplitude
    y_normalized = librosa.util.normalize(y_trimmed)

    # 4. Save to new file
    dir_name = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    clean_name = f"clean_{base_name}"
    # Force .wav extension for compability
    clean_name = os.path.splitext(clean_name)[0] + ".wav"
    clean_path = os.path.join(dir_name, clean_name)

    sf.write(clean_path, y_normalized, sr)

    return clean_path
