"""Servizio finto per le prove di avvio_chat: risponde `{"stato": "ok"}` a GET /salute, 404 al resto."""

import argparse
import json
import os
import threading
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
    parser.add_argument("--durata", type=float, help="si spegne da solo dopo questi secondi: una prova fallita non lascia orfani")
    opzioni = parser.parse_args()
    if opzioni.durata:
        timer = threading.Timer(opzioni.durata, os._exit, [0])
        timer.daemon = True
        timer.start()
    HTTPServer(("127.0.0.1", opzioni.porta), Gestore).serve_forever()
