import parselmouth
from parselmouth.praat import call
import librosa
import numpy as np

def analyze_audio(file_path: str) -> dict:
    """
    Extract acoustic metrics: Pitch, Intensity, and Pauses.
    """
    # 1. Parselmouth Analysis (Pitch & Intensity)
    sound = parselmouth.Sound(file_path)
    
    # Pitch
    pitch = sound.to_pitch()
    pitch_values = pitch.selected_array['frequency']
    # Filter out 0 (unvoiced)
    pitch_values = pitch_values[pitch_values > 0]
    
    if len(pitch_values) > 0:
        pitch_mean = np.mean(pitch_values)
        pitch_std = np.std(pitch_values)
    else:
        pitch_mean = 0.0
        pitch_std = 0.0

    # Intensity
    intensity = sound.to_intensity()
    intensity_values = intensity.values.T
    intensity_mean = np.mean(intensity_values)

    # 2. Librosa Analysis (Pauses)
    # Reload with librosa to detect silence (or reuse if we passed the valid array, but file path is safer)
    y, sr = librosa.load(file_path, sr=16000)
    top_db = 25  # Threshold for silence
    
    # Split into non-silent intervals
    non_silent_intervals = librosa.effects.split(y, top_db=top_db)
    
    # Calculate pauses
    # Pauses are the gaps between non_silent_intervals
    pause_count = 0
    total_pause_duration = 0.0
    
    if len(non_silent_intervals) > 0:
        # Check gaps between intervals
        for i in range(len(non_silent_intervals) - 1):
            end_current = non_silent_intervals[i][1]
            start_next = non_silent_intervals[i+1][0]
            
            gap_samples = start_next - end_current
            gap_duration = gap_samples / sr
            
            if gap_duration > 0.5:  # Pause > 0.5s
                pause_count += 1
                total_pause_duration += gap_duration

    duration = librosa.get_duration(y=y, sr=sr)

    return {
        "pitch_mean": float(pitch_mean),
        "pitch_std": float(pitch_std),
        "intensity_mean": float(intensity_mean),
        "pause_count": int(pause_count),
        "total_pause_duration": float(total_pause_duration),
        "total_duration": float(duration)
    }
