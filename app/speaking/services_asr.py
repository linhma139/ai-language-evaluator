from google.cloud import speech
from google.api_core.client_options import ClientOptions
import os
from core.logger import logger

# Automatically resolve credentials from the GOOGLE_APPLICATION_CREDENTIALS environment variable
# Or hardcode the path if necessary: os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./service-account-key.json"

async def transcribe_audio(gcs_uri: str, encoding_mode: str = 'WEBM_OPUS') -> dict:
    client = speech.SpeechAsyncClient()

    audio = speech.RecognitionAudio(uri=gcs_uri)
    
    # Mapping the encoding string to Google's Enum
    encoding_enum = speech.RecognitionConfig.AudioEncoding.WEBM_OPUS
    sample_rate = 48000
    
    if encoding_mode == 'LINEAR16':
        encoding_enum = speech.RecognitionConfig.AudioEncoding.LINEAR16
        sample_rate = 16000

    config = speech.RecognitionConfig(
        encoding=encoding_enum,
        sample_rate_hertz=sample_rate,
        language_code="en-US",
        model="latest_long",
        use_enhanced=True,
        enable_automatic_punctuation=True,
        enable_word_time_offsets=True,  # ENABLE TIMESTAMP
    )

    logger.info(f"Transcribing audio from GCS: {gcs_uri}")
    
    try:
        operation = await client.recognize(config=config, audio=audio)
        
        # Process results
        transcript_parts = []
        words = []
        
        for result in operation.results:
            if result.alternatives:
                alt = result.alternatives[0]
                transcript_parts.append(alt.transcript)
                
                # Extract words
                for word_info in alt.words:
                    word = word_info.word
                    start_time = word_info.start_time.total_seconds()
                    end_time = word_info.end_time.total_seconds()
                    words.append({
                        "word": word,
                        "start_time": start_time,
                        "end_time": end_time
                    })
        
        full_transcript = "\n".join(transcript_parts).strip()
        logger.info(f"Transcript: {full_transcript}")
        
        return {
            "transcript": full_transcript,
            "words": words
        }
        
    except Exception as e:
        logger.error(f"Google Speech Error: {e}", exc_info=True)
        raise e