"""
test_deepface.py  –  DeepFace webcam matching test
===================================================
Recognition runs in a BACKGROUND THREAD so the webcam window never freezes.

USAGE
-----
  python test_deepface.py --images sample_faces/

  Optional flags:
    --threshold  float  cosine-distance cutoff        (default 0.55)
    --interval   float  seconds between checks        (default 3)
    --camera     int    webcam index                  (default 0)

  Press Q in the webcam window to quit.
"""

import argparse
import os
import sys
import time
import threading
import cv2
import numpy as np

# ── make app/ importable from the project root ──────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from services.face_recognition_service import (
    get_embedding,
    cosine_distance,
    MATCH_THRESHOLD,
)
from services.whatsapp_service import send_match_alert
from deepface import DeepFace

# Fast detector for live webcam frames (ssd is ~10x faster than retinaface)
LIVE_DETECTOR = "ssd"


# ─────────────────────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────────────────────

def load_registered_faces(folder: str) -> list:
    """
    Compute ArcFace embeddings for every image in `folder`.
    Uses retinaface (accurate) since this runs once at startup.
    Returns list of { name, image_path, embedding }.
    """
    VALID_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    registered = []

    if not os.path.isdir(folder):
        print(f"[ERROR] Folder not found: {folder}")
        sys.exit(1)

    files = [f for f in os.listdir(folder)
             if os.path.splitext(f)[1].lower() in VALID_EXT]

    if not files:
        print(f"[ERROR] No images found in {folder}")
        sys.exit(1)

    print(f"\n[INFO] Registering {len(files)} image(s) from '{folder}' …")
    for fname in files:
        path = os.path.join(folder, fname)
        name = os.path.splitext(fname)[0].replace("_", " ").title()
        try:
            emb = get_embedding(path)            # uses retinaface + align=True
            registered.append({"name": name, "image_path": path, "embedding": emb})
            print(f"  ✔  {name}  (embedding dim={len(emb)})")
        except Exception as e:
            print(f"  ✘  {name}  SKIPPED → {e}")

    print(f"[INFO] {len(registered)} face(s) registered.\n")
    return registered


# ─────────────────────────────────────────────────────────────────────────────
# Recognition worker (runs in a background thread)
# ─────────────────────────────────────────────────────────────────────────────

class RecognitionWorker(threading.Thread):
    """
    Continuously grabs the latest frame snapshot, runs ArcFace recognition,
    and stores the results.  The main thread just reads `self.last_results`.
    """

    def __init__(self, registered: list, threshold: float, interval: float,
                 complainant_phone: str = None):
        super().__init__(daemon=True)
        self.registered        = registered
        self.threshold         = threshold
        self.interval          = interval
        self.complainant_phone = complainant_phone   # send WhatsApp here on match
        self._alerted_cases    = set()               # avoid duplicate alerts

        self._frame_lock   = threading.Lock()
        self._current_frame = None          # latest frame from main thread

        self.last_results  = []             # read by main thread for overlay
        self.status_msg    = "Warming up …"
        self.running       = True

    # called by main thread every loop iteration
    def update_frame(self, frame):
        with self._frame_lock:
            self._current_frame = frame.copy()

    def _get_frame(self):
        with self._frame_lock:
            if self._current_frame is None:
                return None
            return self._current_frame.copy()

    def _compare(self, probe_emb):
        results = []
        for reg in self.registered:
            dist = cosine_distance(probe_emb, reg["embedding"])
            results.append({
                "name":    reg["name"],
                "distance": round(dist, 4),
                "matched":  dist <= self.threshold,
            })
        results.sort(key=lambda x: x["distance"])
        return results

    def run(self):
        while self.running:
            frame = self._get_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            # ── Upscale 1.5x so SSD can detect faces at normal/far distances ──
            h, w = frame.shape[:2]
            upscaled = cv2.resize(frame, (int(w * 1.5), int(h * 1.5)),
                                  interpolation=cv2.INTER_LINEAR)

            ts = time.strftime("%H:%M:%S")
            print(f"\n[{ts}] Recognising …")
            try:
                rep = DeepFace.represent(
                    img_path=upscaled,
                    model_name="ArcFace",
                    detector_backend=LIVE_DETECTOR,
                    align=True,
                    enforce_detection=True,
                )
                probe_emb = rep[0]["embedding"]
                results   = self._compare(probe_emb)
                self.last_results = results

                matches = [r for r in results if r["matched"]]
                best    = results[0]

                if matches:
                    m = matches[0]
                    self.status_msg = f"✔ MATCH: {m['name']}  (d={m['distance']})"
                    print(f"  🔴  MATCH → {m['name']}  distance={m['distance']}")

                    # ── Send WhatsApp alert (once per unique name) ────────────
                    if (self.complainant_phone
                            and m['name'] not in self._alerted_cases):
                        self._alerted_cases.add(m['name'])
                        threading.Thread(
                            target=send_match_alert,
                            kwargs=dict(
                                complainant_phone=self.complainant_phone,
                                missing_name=m['name'],
                                match_distance=m['distance'],
                            ),
                            daemon=True,
                        ).start()
                        print(f"  📲  WhatsApp alert sent to {self.complainant_phone}")
                else:
                    # Always show closest as a possible match with confidence %
                    conf = max(0, round((1 - best['distance']) * 100, 1))
                    self.status_msg = (
                        f"Possible match: {best['name']}  "
                        f"(d={best['distance']}, {conf}% similarity)"
                    )
                    print(f"  🟡  Possible match → {best['name']}  "
                          f"d={best['distance']}  ({conf}% similarity)")

                for r in results:
                    tag = "✔ MATCH  " if r["matched"] else "? Possible"
                    print(f"     {tag}  {r['name']:30s}  d={r['distance']}")

            except Exception as e:
                self.last_results = []
                self.status_msg   = "No face detected – move closer or improve lighting"
                print(f"  ⚠  {e}")

            time.sleep(self.interval)

    def stop(self):
        self.running = False


# ─────────────────────────────────────────────────────────────────────────────
# Overlay drawing
# ─────────────────────────────────────────────────────────────────────────────

def draw_overlay(frame, worker: RecognitionWorker):
    h, w = frame.shape[:2]
    y = 30

    # ── Status bar background ────────────────────────────────────────────────
    cv2.rectangle(frame, (0, 0), (w, 36), (30, 30, 30), -1)

    # Colour the status bar: green=match, yellow=possible, grey=no face
    msg = worker.status_msg
    if msg.startswith("✔ MATCH"):
        bar_color = (0, 200, 60)
    elif msg.startswith("Possible"):
        bar_color = (0, 180, 230)
    else:
        bar_color = (100, 100, 100)

    cv2.putText(frame, msg, (8, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, bar_color, 2)
    y = 55

    # ── Per-person result rows ───────────────────────────────────────────────
    for i, r in enumerate(worker.last_results[:5]):
        conf = max(0, round((1 - r['distance']) * 100, 1))
        if r['matched']:
            color = (0, 255, 80)
            tag   = "MATCH"
        elif i == 0 and worker.last_results:
            color = (0, 210, 255)
            tag   = "Possible"
        else:
            color = (160, 160, 160)
            tag   = "unlikely"
        label = f"{tag}  {r['name']}  {conf}% similar  (d={r['distance']})"
        cv2.putText(frame, label, (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 2)
        y += 24


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="DeepFace webcam matching test")
    parser.add_argument("--images",      required=True)
    parser.add_argument("--threshold",   type=float, default=MATCH_THRESHOLD)
    parser.add_argument("--interval",    type=float, default=3.0)
    parser.add_argument("--camera",      type=int,   default=0)
    parser.add_argument("--complainant", default=None,
                        help="Phone number to WhatsApp when a match is found, e.g. 8589958840")
    args = parser.parse_args()

    # 1. Register reference faces (one-time, uses retinaface)
    registered = load_registered_faces(args.images)
    if not registered:
        print("[ERROR] No usable faces. Exiting.")
        sys.exit(1)

    # 2. Open webcam
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera {args.camera}")
        sys.exit(1)

    print("[INFO] Webcam opened.  Press Q to quit.\n")

    # 3. Start background recognition thread
    worker = RecognitionWorker(
        registered, args.threshold, args.interval,
        complainant_phone=args.complainant,
    )
    if args.complainant:
        print(f"[INFO] WhatsApp alerts will be sent to {args.complainant} on match.\n")
    worker.start()

    # 4. Main loop — always responsive, recognition results updated async
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

        worker.update_frame(frame)          # share latest frame with thread
        draw_overlay(frame, worker)         # draw last known results on live feed
        cv2.imshow("DeepFace Missing-Person Test  (Q to quit)", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    worker.stop()
    cap.release()
    cv2.destroyAllWindows()
    print("\n[INFO] Done.")


if __name__ == "__main__":
    main()
