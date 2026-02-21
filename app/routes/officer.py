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


from app.services.case_service import get_recent_cases

@router.get("/officer-dashboard", response_class=HTMLResponse)
async def officer_dashboard(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/officer-login", status_code=302)

    cases = get_recent_cases(limit=50)
    # Pass query params for delete feedback
    deleted = request.query_params.get("deleted") == "1"
    error = request.query_params.get("error")
    return templates.TemplateResponse(
        "officer_dashboard.html",
        {"request": request, "cases": cases, "deleted": deleted, "delete_error": error}
    )


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

        # ── Preprocessing (now handled by service) ──────────────────
        from app.services.face_recognition_service import embedding_from_frame, cosine_distance
        
        try:
            # Service handles BGR to RGB conversion internally
            probe_emb = embedding_from_frame(frame)
        except Exception as e:
            err = str(e)
            if "Face could not be detected" in err or "enforce_detection" in err:
                return {"error": "No face detected — ensure good lighting and face the camera."}
            return {"error": f"Recognition error: {err}"}

        # Gender filtering skipped for speed (saves ~3-5 sec per scan)
        probe_gender = None

        # Load all cases with embeddings from DB
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, missing_full_name, gender, embedding, complainant_phone FROM cases WHERE embedding != ''"
        )
        cases = cursor.fetchall()
        conn.close()

        if not cases:
            return {"error": "No registered cases in the database yet."}

        # Compare probe against all cases using centralized service logic
        results = []
        from app.services.face_recognition_service import MATCH_THRESHOLD
        
        print(f"[DEBUG] Comparing probe against {len(cases)} cases...")
        
        for case in cases:
            try:
                # ── Gender Filtering ──
                case_gender = (case["gender"] or "").lower()
                gender_match = True
                
                if probe_gender and case_gender:
                    p_gen = probe_gender.lower()
                    is_male_probe = ('man' in p_gen or 'male' in p_gen)
                    is_female_probe = ('woman' in p_gen or 'female' in p_gen)
                    is_male_case = ('male' in case_gender and 'female' not in case_gender)
                    is_female_case = ('female' in case_gender)
                    
                    if (is_male_probe and is_female_case) or (is_female_probe and is_male_case):
                        gender_match = False
                
                stored_emb = np.array(json.loads(case["embedding"]))
                
                # Use centralized distance logic
                dist = cosine_distance(probe_emb, stored_emb)
                
                print(f"[DEBUG] Case: {case['missing_full_name']}, Gender: {case_gender}, Distance: {dist:.4f}, GenderMatch: {gender_match}")
                
                if not gender_match:
                    continue

                matched = dist <= MATCH_THRESHOLD
                results.append({
                    "case_id":  case["id"],
                    "name":     case["missing_full_name"],
                    "distance": round(dist, 4),
                    "matched":  matched,
                    "complainant_phone": case["complainant_phone"],
                    "gender": case["gender"]
                })
            except Exception as e:
                print(f"[DEBUG] Error matching case {case.get('id')}: {e}")
                continue

        if not results:
            return {"results": [], "message": "No database records found."}

        # Filter strictly by distance < 0.6 as requested for display
        filtered_results = [r for r in results if r["distance"] < 0.6]
        
        filtered_results.sort(key=lambda x: x["distance"])

        # Auto-send WhatsApp alerts only after SURITY (e.g. 2 consecutive hits)
        # We use the top match from the filtered list
        if filtered_results:
            top = filtered_results[0]
            if top["matched"]: # Still check against the more conservative MATCH_THRESHOLD for alerts
                case_id = str(top["case_id"])
                
                if not hasattr(router, "_hit_counter"):
                    router._hit_counter = {}

                router._hit_counter[case_id] = router._hit_counter.get(case_id, 0) + 1
                print(f"[DEBUG] Match found for {top['name']}! Surity: {router._hit_counter[case_id]}/2")
                
                if router._hit_counter[case_id] >= 2:
                    try:
                        from app.services.whatsapp_service import send_match_alert
                        import random
                        
                        SCAN_LOCATION = "Main Terminal - Gate 4 (CCTV-08)"
                        RANDOM_OFFICER = f"{random.randint(7000, 9999)}{random.randint(100000, 999999)}"

                        if top.get("complainant_phone"):
                            send_match_alert(
                                complainant_phone=top["complainant_phone"],
                                missing_name=top["name"],
                                match_distance=top["distance"],
                                case_id=top["case_id"],
                                location=SCAN_LOCATION,
                                officer_no=RANDOM_OFFICER
                            )
                        router._hit_counter[case_id] = 0 # Reset
                    except Exception as e:
                        return {"results": filtered_results}

        return {"results": filtered_results}

    except Exception as e:
        err = str(e)
        if "Face could not be detected" in err or "enforce_detection" in err:
            return {"error": "No face detected — ensure good lighting and face the camera."}
        return {"error": err}


@router.post("/officer/delete-case/{case_id}")
async def delete_case_route(request: Request, case_id: int):
    print(f"[DEBUG] Delete route hit for case_id: {case_id}")
    if not is_logged_in(request):
        print("[DEBUG] Delete aborted: User not logged in.")
        return RedirectResponse("/officer-login?expired=1", status_code=302)

    from app.services.case_service import delete_case
    try:
        rows = delete_case(case_id)
        print(f"[DEBUG] Deleted case {case_id}. Rows affected: {rows}")
        if rows > 0:
            return RedirectResponse("/officer-dashboard?deleted=1", status_code=303)
        return RedirectResponse("/officer-dashboard?error=notfound", status_code=303)
    except Exception as e:
        print(f"[ERROR] Failed to delete case {case_id}: {e}")
        return RedirectResponse("/officer-dashboard?error=delete", status_code=303)
