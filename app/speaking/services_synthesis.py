def synthesize_data(transcript_data: dict, acoustic_data: dict) -> dict:
    """
    Combine transcript stats and acoustic stats into a summary dict.
    Calculate Fluency (Words per minute).
    """
    transcript = transcript_data.get("transcript", "")
    words = transcript_data.get("words", [])
    
    word_count = len(words)
    total_duration = acoustic_data.get("total_duration", 0.0)
    
    # Fluency (WPM)
    # Avoid div by zero
    if total_duration > 0:
        wpm = (word_count / total_duration) * 60
    else:
        wpm = 0.0
        
    acoustic_data["wpm"] = round(wpm, 1)
    acoustic_data["word_count"] = word_count
    
    # Create a text summary for the LLM
    summary_text = (
        f"Speaking Statistics:\n"
        f"- Words per Minute (WPM): {wpm:.1f}\n"
        f"- Pauses (>0.5s): {acoustic_data['pause_count']} (Total: {acoustic_data['total_pause_duration']:.2f}s)\n"
        f"- Pitch Stability (Standard Deviation): {acoustic_data['pitch_std']:.2f} Hz (Lower is more monotone, higher is more expressive/unstable)\n"
        f"- Intensity: {acoustic_data['intensity_mean']:.2f} dB\n"
    )
    
    return {
        "summary_text": summary_text,
        "metrics": acoustic_data,
        "transcript": transcript
    }
