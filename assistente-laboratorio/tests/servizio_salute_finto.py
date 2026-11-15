"""Servizio finto per le prove di avvio_chat: risponde `{"stato": "ok"}` a GET /salute, 404 al resto."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Gestore(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/salute":
            self.send_error(404)
            return
        corpo = json.dumps({"stato": "ok"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, formato, *argomenti):
        pass  # nessuna riga nel terminale delle prove


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--porta", type=int, required=True)
    HTTPServer(("127.0.0.1", parser.parse_args().porta), Gestore).serve_forever()
