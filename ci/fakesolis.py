"""A stand-in for the Solis app on the Homey: /lucent.json and /beeld/kaart/stroom.png (the example of the handover)."""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

DATA = {"version": 1, "updated": "2026-11-03T22:38:05+01:00", "status": "Normaal", "online": False, "solar_w": 0, "solar_max_w": 2500,
        "house_w": 157, "grid_w": 157, "today_kwh": 1.8, "today_expected_kwh": 3, "month_kwh": 6, "self_use_pct": 48,
        "month_value_eur": 0.41, "price_now_eur": None, "contract": "Vast", "advice": "Geen advies nu", "best_hour_tomorrow": "19:00",
        "prices_today": None, "solar_today": [None] * 9 + [0.15, 0.4, 0.6, 0.5, 0.1] + [None] * 10}
PNG = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "solis", "stroom.png"), "rb").read()


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/lucent.json"):
            body, kind = json.dumps(DATA).encode(), "application/json"
        elif self.path.startswith("/beeld/kaart/stroom.png"):
            body, kind = PNG, "image/png"
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


HTTPServer(("127.0.0.1", 8791), H).serve_forever()
