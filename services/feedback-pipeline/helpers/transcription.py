import logging

import httpx

from config import WHISPER_MODEL

logger = logging.getLogger(__name__)


def transcribe_video(groq_client, video_url: str) -> str:
    """Transcribe video via Groq Whisper. Tries URL first, falls back to file download."""
    try:
        result = groq_client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            url=video_url,
            language="en",
        )
        return result.text
    except Exception as url_err:
        logger.info("URL transcription failed, trying file download: %s", url_err)
        response = httpx.get(video_url)
        result = groq_client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=("video.mp4", response.content, "video/mp4"),
            language="en",
        )
        return result.text
