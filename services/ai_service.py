"""AI Service - Whisper transcription + GPT-4o summarization"""
import json
from flask import current_app

def transcribe_audio(audio_path: str) -> str:
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    if not api_key:
        return "[Transcription unavailable – API key not configured]"
    try:
        import openai
        import httpx
        client = openai.OpenAI(api_key=api_key, http_client=httpx.Client(timeout=120.0, follow_redirects=True))
        with open(audio_path, "rb") as f:
            response = client.audio.transcriptions.create(model="whisper-1", file=f, language="en")
        return response.text
    except Exception as e:
        current_app.logger.error(f"Transcription failed: {e}")
        return f"[Transcription error: {e}]"

def summarize_transcript(transcript: str) -> tuple:
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    if not api_key or not transcript.strip():
        return "Summary unavailable.", []
    try:
        import openai
        import httpx
        client = openai.OpenAI(api_key=api_key, http_client=httpx.Client(timeout=120.0, follow_redirects=True))
        system = ('You are a professional church/organization secretary. '
                  'Given a meeting transcript produce a clean summary and action points. '
                  'Respond ONLY with valid JSON: {"summary": "...", "action_points": ["...", "..."]}')
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role":"system","content":system},{"role":"user","content":f"Transcript:\n\n{transcript[:8000]}"}],
            max_tokens=1000,
        )
        raw = response.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
        data = json.loads(raw)
        return data.get("summary",""), data.get("action_points",[])
    except Exception as e:
        current_app.logger.error(f"Summarization failed: {e}")
        return f"[Summary error: {e}]", []
