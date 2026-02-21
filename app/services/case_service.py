import os
import json
import uuid
import shutil
import threading
import numpy as np
from app.models.database import get_connection
from app.config import config


def _generate_embedding_background(case_id: int, image_path: str):
    """Generate embedding in background and update the case."""
    try:
        from app.services.face_recognition_service import get_embedding
        _embedding = get_embedding(image_path)
        if _embedding:
            embedding_json = json.dumps(_embedding)
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE cases SET embedding = ? WHERE id = ?", (embedding_json, case_id))
            conn.commit()
            conn.close()
            print(f"[CaseService] Embedding generated for case {case_id}")
    except Exception as e:
        print(f"[CaseService] Embedding error for case {case_id}: {e}")


def save_case(data: dict, image_file):
    """
    Saves a missing person case to the database. Saves immediately with empty
    embedding for fast response; generates embedding in background (~15-30s).
    """
    # 1. Save the image file
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    ext = image_file.filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    image_path = os.path.join(config.UPLOAD_FOLDER, filename)

    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image_file.file, buffer)

    # 2. Save to Database immediately (embedding = '' for now)
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO cases (
            missing_full_name, gender, age, missing_state, missing_city, 
            pin_code, missing_date, missing_time, description, image_path, embedding,
            complainant_name, relationship, complainant_phone, address_line1
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("missing_full_name"),
        data.get("gender"),
        data.get("age"),
        data.get("missing_state"),
        data.get("missing_city"),
        data.get("pin_code"),
        data.get("missing_date"),
        data.get("missing_time"),
        data.get("description"),
        filename, # store relative path/filename
        "",       # embedding filled in by background thread
        data.get("complainant_name"),
        data.get("relationship"),
        data.get("complainant_phone"),
        data.get("address_line1")
    ))
    
    case_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # 3. Generate embedding in background (DeepFace takes 15-30s; user gets instant redirect)
    thread = threading.Thread(
        target=_generate_embedding_background,
        args=(case_id, image_path),
        daemon=True,
    )
    thread.start()

    return case_id

def get_recent_cases(limit=10):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cases ORDER BY created_at DESC LIMIT ?", (limit,))
    cases = cursor.fetchall()
    conn.close()
    return cases

def get_case_by_id(case_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    case = cursor.fetchone()
    conn.close()
    return case

def delete_case(case_id):
    """
    Deletes a case from the database. Deletes related comments first to avoid
    foreign key constraint issues.
    """
    print(f"[DEBUG] CaseService.delete_case called for ID: {case_id}")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Delete related comments first (foreign key from comments → cases)
        cursor.execute("DELETE FROM comments WHERE case_id = ?", (case_id,))
        comments_deleted = cursor.rowcount
        # Then delete the case
        cursor.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        rows_affected = cursor.rowcount
        conn.commit()
        print(f"[DEBUG] CaseService.delete_case finished. Comments deleted: {comments_deleted}, Case rows: {rows_affected}")
        return rows_affected
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
