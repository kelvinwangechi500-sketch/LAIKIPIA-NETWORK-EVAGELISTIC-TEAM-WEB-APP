"""
OCR Service
============
Uses OpenAI GPT-4 Vision to extract structured member info
(name, residence, year, signature) from a photographed attendance sheet.

Requires: OPENAI_API_KEY environment variable.
Fallback: Returns empty list with a warning if key not set.
"""

import os
import base64
import json
from flask import current_app


def extract_names_from_image(image_path: str) -> list[dict]:
    """
    Send image to OpenAI Vision API and parse returned structured member info.

    Args:
        image_path: Absolute path to the saved image file.

    Returns:
        List of dicts with keys: name, residence, year, signature (if available)
        Example:
        [
            {"name": "John Doe", "residence": "Nairobi", "year": "3", "signature": "✓"},
            {"name": "Jane Smith", "residence": "Mombasa", "year": "2", "signature": "✗"}
        ]
    """
    api_key = current_app.config.get("OPENAI_API_KEY", "")

    if not api_key:
        current_app.logger.warning("OPENAI_API_KEY not set – OCR skipped.")
        return []

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        ext = image_path.rsplit(".", 1)[-1].lower()
        media_type = f"image/{ext}" if ext != "jpg" else "image/jpeg"

        # Prompt the model to extract structured data
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_data}",
                                "detail": "high",
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "You are extracting structured attendance info from a sheet. "
                                "For each present member, return a JSON object with keys: "
                                "\"name\", \"residence\", \"year\", \"signature\" (if visible). "
                                "Return a JSON array of objects ONLY. Example: "
                                "[{\"name\":\"John Doe\",\"residence\":\"Nairobi\",\"year\":\"3\",\"signature\":\"✓\"}]. "
                                "Do NOT include any extra text."
                            ),
                        },
                    ],
                }
            ],
            max_tokens=1200,
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        members = json.loads(raw)

        # Clean up entries
        cleaned = []
        for m in members:
            cleaned.append({
                "name": str(m.get("name", "")).strip(),
                "residence": str(m.get("residence", "")).strip(),
                "year": str(m.get("year", "")).strip(),
                "signature": str(m.get("signature", "")).strip()
            })

        return cleaned

    except Exception as e:
        current_app.logger.error(f"OCR extraction failed: {e}")
        return []