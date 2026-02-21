import os
import sys
import base64
import json
import numpy as np
import cv2

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.models.database import get_connection

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), '..', 'templates')
)

router = APIRouter()

# ── Hardcoded credentials (replace with DB auth for production) ────────────────
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


# ─────────────────────────────────────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────────────────────────────────────

def is_logged_in(request: Request) -> bool:
    return request.session.get("officer") == ADMIN_USERNAME


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/officer-login", response_class=HTMLResponse)
async def officer_login_get(request: Request):
    if is_logged_in(request):
        return RedirectResponse("/officer-dashboard", status_code=302)
    return templates.TemplateResponse("officer_login.html", {"request": request, "error": None})


@router.post("/officer-login", response_class=HTMLResponse)
async def officer_login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        request.session["officer"] = username
        return RedirectResponse("/officer-dashboard", status_code=302)

    return templates.TemplateResponse(
        "officer_login.html",
        {"request": request, "error": "Invalid username or password."},
        status_code=401,
    )


@router.get("/officer-logout")
async def officer_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/officer-login", status_code=302)


from app.services.case_service import get_recent_cases, get_case_stats_by_date

@router.get("/officer-dashboard", response_class=HTMLResponse)
async def officer_dashboard(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/officer-login", status_code=302)
    
    cases = get_recent_cases(limit=50)
    stats = get_case_stats_by_date()
    
    # EXHAUSTIVE DEBUG LOGGING
    import os
    from app.models.database import DB_PATH
    from app.config import config
    print(f"\n[DASHBOARD ACCESS] {request.client.host}")
    print(f"  CWD: {os.getcwd()}")
    print(f"  DB_PATH: {DB_PATH}")
    print(f"  DB Size: {os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 'N/A'}")
    print(f"  Upload Folder: {config.UPLOAD_FOLDER}")
    from app.services.case_service import debug_to_file
    debug_to_file(f"Dashboard stats requested. Count={len(cases)}, Stats={stats}")
    
    return templates.TemplateResponse("officer_dashboard.html", {
        "request": request, 
        "cases": cases,
        "stats": stats
    })


# ─────────────────────────────────────────────────────────────────────────────
# DeepFace scan-frame API
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/officer/scan-frame")
async def scan_frame(request: Request):
    if not is_logged_in(request):
        return {"error": "Unauthorised"}

    try:
        body      = await request.json()
        frame_b64 = body.get("frame_b64", "")

        # Decode base64 → OpenCV BGR frame
        img_bytes = base64.b64decode(frame_b64)
        np_arr    = np.frombuffer(img_bytes, np.uint8)
        frame     = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            return {"error": "Could not decode image frame."}

        # Lazy-import DeepFace (TF takes a moment to load)
        from deepface import DeepFace

        # Extract probe embedding
        rep       = DeepFace.represent(
            img_path=frame,
            model_name="ArcFace",
            detector_backend="opencv",
            align=True,
            enforce_detection=True,
        )
        probe_emb = np.array(rep[0]["embedding"])

        # Load all cases with embeddings from DB
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, missing_full_name, image_path, embedding, "
            "       complainant_phone FROM cases WHERE embedding != ''"
        )
        cases = cursor.fetchall()
        conn.close()

        if not cases:
            return {"error": "No registered cases in the database yet."}

        # Compare against every case
        results = []
        THRESHOLD = 0.68
        for case in cases:
            try:
                stored_emb = np.array(json.loads(case["embedding"]))
                # Cosine distance
                dist = float(1.0 - np.dot(probe_emb, stored_emb) /
                             (np.linalg.norm(probe_emb) * np.linalg.norm(stored_emb)))
                results.append({
                    "case_id":  case["id"],
                    "name":     case["missing_full_name"],
                    "distance": round(dist, 4),
                    "matched":  dist <= THRESHOLD,
                    "complainant_phone": case["complainant_phone"],
                })
            except Exception:
                continue

        if not results:
            return {"error": "No valid embeddings found in database."}

        results.sort(key=lambda x: x["distance"])

        # Auto-send WhatsApp alert for first confident match
        top = results[0]
        if top["matched"] and top.get("complainant_phone"):
            try:
                from app.services.whatsapp_service import send_match_alert
                send_match_alert(
                    complainant_phone=top["complainant_phone"],
                    missing_name=top["name"],
                    match_distance=top["distance"],
                    case_id=top["case_id"],
                )
            except Exception:
                pass  # don't fail the scan if WhatsApp errors

        return {"results": results}

    except Exception as e:
        err = str(e)
        if "Face could not be detected" in err or "enforce_detection" in err:
            return {"error": "No face detected — ensure good lighting and face the camera."}
        return {"error": err}

@router.get("/officer/debug-db")
async def debug_db(request: Request):
    if not is_logged_in(request):
        return {"error": "Unauthorised"}
    
    from app.models.database import DB_PATH
    import sqlite3
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM cases")
    total_cases = cursor.fetchone()["count"]
    
    cursor.execute("SELECT missing_date, COUNT(*) as count FROM cases GROUP BY missing_date")
    stats = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT id, image_path FROM cases LIMIT 10")
    images = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "db_path": DB_PATH,
        "db_exists": os.path.exists(DB_PATH),
        "total_cases": total_cases,
        "stats": stats,
        "images": images,
        "upload_folder": config.UPLOAD_FOLDER,
        "upload_folder_exists": os.path.exists(config.UPLOAD_FOLDER)
    }
