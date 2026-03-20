"""
AI Service
===========
Handles:
  1. Audio → Text  (OpenAI Whisper)
  2. Transcript → Summary + Action Points  (OpenAI GPT-4o)

Requires: OPENAI_API_KEY environment variable.
"""

import os
import json
from flask import current_app


def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe a meeting audio file using OpenAI Whisper.

    Args:
        audio_path: Absolute path to audio file.

    Returns:
        Transcript string, or empty string on failure.
    """
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    if not api_key:
        current_app.logger.warning("OPENAI_API_KEY not set – transcription skipped.")
        return "[Transcription unavailable – API key not configured]"

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        with open(audio_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en",
            )
        return response.text

    except Exception as e:
        current_app.logger.error(f"Transcription failed: {e}")
        return f"[Transcription error: {e}]"


def summarize_transcript(transcript: str) -> tuple[str, list[str]]:
    """
    Generate a structured meeting summary and action points from transcript.

    Args:
        transcript: Raw meeting transcript text.

    Returns:
        Tuple of (summary_string, action_points_list).
    """
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    if not api_key or not transcript.strip():
        return "Summary unavailable.", []

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        system_prompt = (
            "You are a professional church/organization secretary. "
            "Given a meeting transcript, produce a clean summary and a list of action points. "
            "Respond ONLY with valid JSON in this exact shape:\n"
            '{"summary": "...", "action_points": ["...", "..."]}\n'
            "No extra text or markdown fences."
        )

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Meeting transcript:\n\n{transcript[:8000]}",
                },
            ],
            max_tokens=1000,
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        return data.get("summary", ""), data.get("action_points", [])

    except Exception as e:
        current_app.logger.error(f"Summarization failed: {e}")
        return f"[Summary error: {e}]", []
