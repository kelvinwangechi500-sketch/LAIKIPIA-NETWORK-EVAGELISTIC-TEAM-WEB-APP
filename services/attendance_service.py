"""
Attendance Service - fuzzy matching, auto member creation, export
"""
import csv, io, uuid, json
from datetime import datetime

def fuzzy_match_members(ocr_rows: list, members: list) -> tuple:
    """
    Match OCR rows to existing members using exact, case-insensitive, and token matching.
    Returns (matched_list, unmatched_list)
    matched: [{ocr_row, member}]
    unmatched: [ocr_row]
    """
    member_map = {m.full_name.lower().strip(): m for m in members}
    matched, unmatched = [], []

    for row in ocr_rows:
        name = str(row.get("name","")).strip()
        if not name:
            continue
        name_lower = name.lower()
        found = None

        # 1. Exact match
        if name_lower in member_map:
            found = member_map[name_lower]
        else:
            # 2. Token overlap matching
            tokens_in = set(name_lower.split())
            best_score = 0
            best_member = None
            for key, member in member_map.items():
                tokens_db = set(key.split())
                overlap = len(tokens_in & tokens_db)
                total = len(tokens_in | tokens_db)
                score = overlap / total if total else 0
                if score > best_score and score >= 0.5:
                    best_score = score
                    best_member = member
            found = best_member

        if found:
            matched.append({"ocr_row": row, "member": found})
        else:
            unmatched.append(row)

    return matched, unmatched

def generate_placeholder_email() -> str:
    return f"member_{uuid.uuid4().hex[:8]}@net.local"

def export_attendance_csv(records) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Meeting Date","Member Name","Residence","Year","Status","Source","Recorded By","Timestamp"])
    for r in records:
        recorder_name = r.recorder.full_name if r.recorder else "System"
        writer.writerow([
            str(r.meeting_date),
            r.user.full_name,
            getattr(r.user, 'residence', '') or '',
            getattr(r.user, 'year', '') or '',
            r.status,
            r.source,
            recorder_name,
            r.created_at.strftime("%Y-%m-%d %H:%M"),
        ])
    return output.getvalue()
