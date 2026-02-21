"""
test_whatsapp.py
----------------
Quick standalone test to verify Twilio WhatsApp integration.

USAGE
-----
  python test_whatsapp.py --to <complainant_phone>

  Example (use YOUR number that's joined the Twilio sandbox):
    python test_whatsapp.py --to 8589958840

  ⚠ IMPORTANT – Twilio WhatsApp Sandbox requirement:
  The recipient number must first send  "join <your-sandbox-keyword>"
  to  +1 (415) 523-8886  on WhatsApp before it can receive sandbox messages.

"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from services.whatsapp_service import send_match_alert

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--to",   required=True,
                        help="Complainant phone number, e.g. 8589958840")
    parser.add_argument("--name", default="Ravi Kumar",
                        help="Missing person name (default: Ravi Kumar)")
    parser.add_argument("--dist", type=float, default=0.28,
                        help="Simulated match distance (default: 0.28)")
    parser.add_argument("--case", type=int, default=1,
                        help="Simulated case ID (default: 1)")
    args = parser.parse_args()

    print(f"\n[TEST] Sending WhatsApp alert to {args.to} …")
    result = send_match_alert(
        complainant_phone=args.to,
        missing_name=args.name,
        match_distance=args.dist,
        case_id=args.case,
    )

    if result["success"]:
        print(f"[TEST] ✔ Message sent!  Twilio SID: {result['sid']}")
    else:
        print(f"[TEST] ✘ Failed: {result['error']}")

if __name__ == "__main__":
    main()
