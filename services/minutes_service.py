import json
import os
import uuid

from werkzeug.utils import secure_filename


ALLOWED_MINUTES_DOCUMENTS = {
    "pdf", "doc", "docx", "odt", "rtf", "txt", "md", "csv",
    "xls", "xlsx", "ppt", "pptx",
    "jpg", "jpeg", "png", "webp",
}


def save_minutes_document(upload, upload_folder):
    """Save an allowlisted minutes document with a generated server filename."""
    original_name = secure_filename(upload.filename or "")
    if not original_name or "." not in original_name:
        raise ValueError("Choose a supported document file.")

    extension = original_name.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_MINUTES_DOCUMENTS:
        raise ValueError("Supported files: PDF, Word, text, spreadsheet, presentation, or image files.")

    stored_name = f"minutes_{uuid.uuid4().hex}.{extension}"
    os.makedirs(upload_folder, exist_ok=True)
    upload.save(os.path.join(upload_folder, stored_name))
    return stored_name, original_name, upload.mimetype or "application/octet-stream"


def action_points_json(raw):
    """Normalize textarea lines or a JSON list for storage."""
    raw = (raw or "").strip()
    if not raw:
        return "[]"
    try:
        points = json.loads(raw)
        if isinstance(points, list):
            return json.dumps([str(point).strip() for point in points if str(point).strip()])
    except (TypeError, ValueError):
        pass
    return json.dumps([line.strip() for line in raw.splitlines() if line.strip()])