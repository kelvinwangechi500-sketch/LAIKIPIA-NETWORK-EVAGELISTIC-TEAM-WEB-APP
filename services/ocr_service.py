"""
OCR Service - Extracts attendance data from images.
Primary: Groq Vision (free, fast)
Fallback: Tesseract (local, free)
"""
import os, base64, json, re
from flask import current_app


def extract_attendance_from_image(image_path: str) -> list:
    google_key = current_app.config.get("GOOGLE_VISION_API_KEY", "")
    openai_key = current_app.config.get("OPENAI_API_KEY", "")
    groq_key = current_app.config.get("GROQ_API_KEY", "")

    if groq_key:
        current_app.logger.info("Using Groq Vision for OCR")
        result = _extract_with_groq(image_path, groq_key)
        if result:
            return result

    if openai_key:
        current_app.logger.info("Using OpenAI GPT-4o for OCR")
        return _extract_with_openai(image_path, openai_key)

    if google_key:
        current_app.logger.info("Using Google Vision for OCR")
        return _extract_with_google(image_path, google_key)

    current_app.logger.info("Using Tesseract for OCR")
    return _extract_with_tesseract(image_path)


def _extract_with_groq(image_path: str, api_key: str) -> list:
    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        ext = image_path.rsplit(".", 1)[-1].lower()
        media_type = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

        prompt = (
            "This is an official attendance register sheet. "
            "It has columns: S/N, NAME, RESIDENCE, PHONE NO., YEAR, SIGNATURE. "
            "Extract EVERY row that has a name written in it. "
            "For each row return JSON: "
            "{\"number\":1,\"name\":\"Full Name\",\"residence\":\"place\","
            "\"year\":\"II\",\"signature\":true}. "
            "Return ONLY a valid JSON array. No markdown, no explanation."
        )

        models = [
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "llama-3.2-90b-vision-preview",
            "llama-3.2-11b-vision-preview",
        ]

        for model in models:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{image_data}"
                                }
                            },
                            {"type": "text", "text": prompt}
                        ]
                    }],
                    max_tokens=2000,
                    temperature=0.1,
                )

                raw = response.choices[0].message.content.strip()
                raw = raw.replace("```json", "").replace("```", "").strip()

                result = json.loads(raw)
                if not isinstance(result, list):
                    continue

                cleaned = []
                for row in result:
                    name = str(row.get("name", "")).strip()
                    if not name or name.lower() in ("name", "n/a", "-", ""):
                        continue
                    cleaned.append({
                        "number": row.get("number", len(cleaned) + 1),
                        "name": name,
                        "residence": str(row.get("residence", "")).strip(),
                        "year": str(row.get("year", "")).strip(),
                        "signature": bool(row.get("signature", True)),
                    })

                if cleaned:
                    current_app.logger.info(
                        f"Groq extracted {len(cleaned)} rows using {model}"
                    )
                    return cleaned

            except json.JSONDecodeError as e:
                current_app.logger.warning(f"Groq JSON error with {model}: {e}")
                continue
            except Exception as e:
                current_app.logger.warning(f"Groq model {model} failed: {e}")
                continue

        return []

    except ImportError:
        current_app.logger.error("groq package not installed. Run: pip install groq")
        return []
    except Exception as e:
        current_app.logger.error(f"Groq OCR failed: {e}")
        return []


def _extract_with_openai(image_path: str, api_key: str) -> list:
    try:
        import httpx
        import openai

        client = openai.OpenAI(
            api_key=api_key,
            http_client=httpx.Client(timeout=120.0, follow_redirects=True)
        )

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        ext = image_path.rsplit(".", 1)[-1].lower()
        media_type = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_data}",
                            "detail": "high"
                        }
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract ALL rows from this attendance sheet as JSON array. "
                            "Each: {\"number\":1,\"name\":\"Full Name\","
                            "\"residence\":\"place\",\"year\":\"II\",\"signature\":true}. "
                            "Return ONLY JSON array."
                        )
                    }
                ]
            }],
            max_tokens=2000,
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)

        if not isinstance(result, list):
            return []

        return [
            {
                "number": r.get("number", 0),
                "name": str(r.get("name", "")).strip(),
                "residence": str(r.get("residence", "")).strip(),
                "year": str(r.get("year", "")).strip(),
                "signature": True,
            }
            for r in result if str(r.get("name", "")).strip()
        ]

    except Exception as e:
        current_app.logger.error(f"OpenAI OCR failed: {e}")
        return []


def _extract_with_google(image_path: str, api_key: str) -> list:
    try:
        import urllib.request

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        payload = json.dumps({
            "requests": [{
                "image": {"content": image_data},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]
            }]
        }).encode("utf-8")

        req = urllib.request.Request(
            f"https://vision.googleapis.com/v1/images:annotate?key={api_key}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        text = (result.get("responses", [{}])[0]
                .get("fullTextAnnotation", {})
                .get("text", ""))

        return _parse_attendance_text(text) if text else []

    except Exception as e:
        current_app.logger.error(f"Google Vision failed: {e}")
        return []


def _extract_with_tesseract(image_path: str) -> list:
    try:
        import pytesseract
        from PIL import Image, ImageEnhance

        tesseract_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\hp\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
        ]
        for path in tesseract_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break

        img = Image.open(image_path)
        if img.mode != "RGB":
            img = img.convert("RGB")

        width, height = img.size
        if width < 2000:
            scale = 2500 / width
            img = img.resize((int(width * scale), int(height * scale)), Image.LANCZOS)

        img = img.convert("L")
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(3.0)
        img = img.point(lambda x: 0 if x < 140 else 255, "1").convert("L")

        best_rows = []
        for config in [r"--oem 3 --psm 6", r"--oem 3 --psm 4", r"--oem 1 --psm 6"]:
            try:
                text = pytesseract.image_to_string(img, config=config)
                rows = _parse_attendance_text(text)
                if len(rows) > len(best_rows):
                    best_rows = rows
            except Exception:
                continue

        current_app.logger.info(f"Tesseract extracted {len(best_rows)} rows")
        return best_rows

    except Exception as e:
        current_app.logger.error(f"Tesseract failed: {e}")
        return []


def _parse_attendance_text(text: str) -> list:
    rows = []
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    skip_keywords = [
        "s/n", "name", "residence", "phone", "year", "signature",
        "attendance", "register", "official", "date", "venue",
        "theme", "facilitator", "meeting", "network", "unit",
        "semester", "revelation", "laikipia", "evangelistic",
    ]

    for line in lines:
        if any(kw in line.lower() for kw in skip_keywords):
            continue
        if len(line) < 4:
            continue

        number_match = re.match(r"^(\d{1,2})[.\s|]+(.+)", line)
        if number_match:
            row_number = int(number_match.group(1))
            rest = number_match.group(2).strip()
            parts = rest.split()
            name_parts, residence_parts, year_str = [], [], ""
            phone_found = False

            for part in parts:
                if re.match(r"^0\d{8,}", part) or re.match(r"^\d{9,}", part):
                    phone_found = True
                    continue
                if re.match(r"^(I{1,3}V?|IV|VI{0,3})$", part, re.IGNORECASE) and len(part) <= 4:
                    year_str = part.upper()
                    continue
                if len(name_parts) < 3 and not phone_found and not year_str:
                    if re.match(r"^[A-Za-z]+$", part):
                        name_parts.append(part)
                    elif name_parts:
                        residence_parts.append(part)
                elif not phone_found:
                    residence_parts.append(part)

            name = " ".join(name_parts).strip()
            residence = re.sub(r"0\d{9,}", "", " ".join(residence_parts)).strip()

            if name and len(name) > 2:
                rows.append({
                    "number": row_number,
                    "name": name,
                    "residence": residence,
                    "year": year_str,
                    "signature": True,
                })

    if len(rows) < 3:
        rows = _simple_parse(lines)

    return rows


def _simple_parse(lines: list) -> list:
    rows = []
    skip = ["s/n", "name", "residence", "attendance", "register", "network", "laikipia"]
    for line in lines:
        line = line.strip()
        if not line or any(kw in line.lower() for kw in skip):
            continue
        match = re.match(r"^(\d{1,2})[.\s]+([A-Za-z][A-Za-z\s]{3,40})", line)
        if match:
            words = [
                w for w in match.group(2).split()[:3]
                if re.match(r"^[A-Za-z]+$", w) and len(w) > 1
            ]
            name = " ".join(words)
            if len(name) > 3:
                rows.append({
                    "number": int(match.group(1)),
                    "name": name,
                    "residence": "",
                    "year": "",
                    "signature": True,
                })
    return rows


# Backward compatibility
def extract_names_from_image(image_path: str) -> list:
    rows = extract_attendance_from_image(image_path)
    return [r.get("name", "") for r in rows if r.get("name")]