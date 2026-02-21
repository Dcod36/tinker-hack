"""
Re-generate embeddings for ALL cases using the SAME detector chain as the live
scan pipeline (retinaface → ssd → opencv → enforce_detection=False).

IMPORTANT: Run this script whenever you change the detector order so that
           stored embeddings stay consistent with the scan code.

Run: python reembed_cases.py
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.models.database import get_connection
from app.config import config

print("Loading DeepFace (first run may download models, ~1 min)...")
from deepface import DeepFace
print("DeepFace loaded.\n")

# ── MUST match the order in officer.py scan_frame AND case_service.save_case ──
# opencv = fast and consistent with live scan
DETECTORS = ["opencv", "ssd", "retinaface"]


def get_embedding_with_fallback(image_path):
    """Try detectors in the same priority as the live scan; last resort: enforce_detection=False."""
    for backend in DETECTORS:
        try:
            results = DeepFace.represent(
                img_path=image_path,
                model_name="ArcFace",
                detector_backend=backend,
                align=True,
                enforce_detection=True,
            )
            print(f"    ✅ Succeeded with detector: {backend}")
            return results[0]["embedding"]
        except Exception as e:
            print(f"    ⚠️  {backend} failed: {e}")

    # Final fallback – no detection enforcement (whole-image embedding)
    try:
        results = DeepFace.represent(
            img_path=image_path,
            model_name="ArcFace",
            detector_backend="opencv",
            align=True,
            enforce_detection=False,
        )
        print("    ✅ Succeeded with enforce_detection=False (fallback).")
        return results[0]["embedding"]
    except Exception as e:
        raise RuntimeError(f"All detectors failed: {e}")


conn = get_connection()
cursor = conn.cursor()

# Re-embed ALL cases so inconsistent old embeddings are fixed
cursor.execute("SELECT id, missing_full_name, image_path FROM cases")
cases = cursor.fetchall()

if not cases:
    print("No cases found in database.")
    conn.close()
    sys.exit(0)

print(f"Found {len(cases)} case(s) to re-embed.\n")

success = 0
failed  = 0

for case in cases:
    image_path = os.path.join(config.UPLOAD_FOLDER, case["image_path"])
    print(f"Case {case['id']}: {case['missing_full_name']}  ({case['image_path']})")

    if not os.path.exists(image_path):
        print(f"    ❌ Image file not found at: {image_path}\n")
        failed += 1
        continue

    try:
        embedding      = get_embedding_with_fallback(image_path)
        embedding_json = json.dumps(embedding)

        update_cursor = conn.cursor()
        update_cursor.execute(
            "UPDATE cases SET embedding = ? WHERE id = ?",
            (embedding_json, case["id"])
        )
        conn.commit()
        print(f"    💾 Saved embedding ({len(embedding)} dims).\n")
        success += 1
    except Exception as e:
        print(f"    ❌ All detectors failed: {e}\n")
        failed += 1

conn.close()
print(f"Done. ✅ {success} succeeded  ❌ {failed} failed.")
