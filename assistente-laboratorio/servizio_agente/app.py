"""Applicazione FastAPI: l'agente della CLI raggiungibile via HTTP (lezione 6, step 6).

Il servizio è senza stato: la cronologia la conserva chi chiama e la rimanda a ogni turno,
come fa il terminale. Gli errori sono sempre {"errore": "..."} in italiano.
"""

import logging
import queue
import threading
import time
from typing import Mapping, Sequence

import openai
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, messages_from_dict, messages_to_dict
from pydantic import BaseModel, Field

from assistente.grafo import esegui_turno, esegui_turno_in_streaming
from assistente.http import RispostaJson, messaggio_validazione
from assistente.registro import formatta
from assistente.sse import formatta_sse
from assistente.terminale import NESSUNA_RISPOSTA, chiamate_riuscite

TITOLO = "Servizio dell'agente"
ENDPOINT_CHAT = "/chat"
ENDPOINT_STREAM = "/chat/stream"
MESSAGGIO_OCCUPATO = "L'agente sta già rispondendo a un'altra richiesta."

registro = logging.getLogger("assistente.servizio")


class RichiestaChat(BaseModel):
    messaggio: str = Field(description="il testo dell'utente")
    cronologia: list[dict] = Field(default_factory=list, description="la cronologia restituita dal turno precedente")
    istruzioni: str = Field(default="", max_length=4000, description="istruzioni del progetto, solo nel messaggio di sistema")


def _log_errore(stato: int, messaggio: str, inizio: float, endpoint: str) -> None:
    registro.info(
        formatta({"richiesta endpoint": endpoint, "esito": "errore", "stato": stato, "messaggio": messaggio,
                  "durata": round(time.monotonic() - inizio, 2)})
    )


def _errore(stato: int, messaggio: str, inizio: float, endpoint: str = ENDPOINT_CHAT) -> JSONResponse:
    _log_errore(stato, messaggio, inizio, endpoint)
    return RispostaJson(status_code=stato, content={"errore": messaggio})


def _errore_turno(eccezione: Exception) -> tuple[int, str]:
    """Lo stato HTTP e il messaggio per un'eccezione sollevata durante il turno."""
    if isinstance(eccezione, openai.APIConnectionError):
        return 503, f"LM Studio non raggiungibile: {eccezione}"
    return 500, f"Errore durante il turno: {eccezione}"


def _leggi(richiesta: RichiestaChat, inizio: float, endpoint: str):
    """Valida la richiesta: (testo, cronologia, None) oppure (None, None, risposta 400)."""
    testo = richiesta.messaggio.replace("﻿", "").strip()
    if not testo:
        return None, None, _errore(400, "Richiesta non valida: il messaggio è vuoto.", inizio, endpoint)
    try:
        return testo, messages_from_dict(richiesta.cronologia), None
    except Exception as eccezione:
        return None, None, _errore(400, f"Richiesta non valida: cronologia non leggibile ({eccezione}).", inizio, endpoint)


def crea_app(
    grafo,
    *,
    fuso: str,
    modello: str,
    origini: Mapping[str, str],
    parametri: Mapping[str, Sequence[str]],
) -> FastAPI:
    app = FastAPI(
        title=TITOLO,
        description="L'agente con router e strumenti, lo stesso di python -m assistente.",
        default_response_class=RispostaJson,
    )
    turno_in_corso = threading.Lock()  # un turno alla volta: LM Studio e archivio delle note non si sovrappongono

    def risultato(nuova, cronologia, endpoint: str, inizio: float) -> dict:
        """Il corpo della risposta (e di `fine`) per un turno riuscito; scrive la riga di log."""
        ultimo = nuova[-1]
        risposta = ultimo.text.strip() if isinstance(ultimo, AIMessage) else ""
        strumenti = chiamate_riuscite(nuova[len(cronologia):], origini, parametri)
        corpo = {"risposta": risposta or NESSUNA_RISPOSTA, "strumenti": strumenti, "cronologia": messages_to_dict(nuova)}
        registro.info(
            formatta({"richiesta endpoint": endpoint, "esito": "ok", "strumenti": [s["nome"] for s in strumenti],
                      "durata": round(time.monotonic() - inizio, 2)})
        )
        return corpo

    @app.exception_handler(RequestValidationError)
    async def validazione_in_italiano(richiesta: Request, eccezione: RequestValidationError) -> JSONResponse:
        return _errore(400, messaggio_validazione(eccezione), time.monotonic(), richiesta.url.path)

    @app.get("/salute", summary="Stato del servizio")
    def salute() -> dict:
        return {"stato": "ok", "modello": modello, "fuso": fuso, "strumenti": dict(origini)}

    @app.post(ENDPOINT_CHAT, summary="Un turno di conversazione")
    def chat(richiesta: RichiestaChat):
        inizio = time.monotonic()
        testo, cronologia, rifiuto = _leggi(richiesta, inizio, ENDPOINT_CHAT)
        if rifiuto:
            return rifiuto
        with turno_in_corso:
            try:
                nuova = esegui_turno(grafo, cronologia, fuso, testo, istruzioni=richiesta.istruzioni)
            except Exception as eccezione:
                return _errore(*_errore_turno(eccezione), inizio)
        return risultato(nuova, cronologia, ENDPOINT_CHAT, inizio)

    @app.post(ENDPOINT_STREAM, summary="Un turno di conversazione in streaming (SSE)")
    def chat_stream(richiesta: RichiestaChat):
        inizio = time.monotonic()
        testo, cronologia, rifiuto = _leggi(richiesta, inizio, ENDPOINT_STREAM)
        if rifiuto:
            return rifiuto
        if not turno_in_corso.acquire(blocking=False):
            return _errore(409, MESSAGGIO_OCCUPATO, inizio, ENDPOINT_STREAM)

        coda: queue.Queue = queue.Queue()
        fine_flusso = object()

        def lavora() -> None:
            # Gira in un thread proprio: finisce il turno e rilascia il lock anche se il client si scollega.
            mandate = 0

            def su_messaggi(messaggi) -> None:
                nonlocal mandate
                riuscite = chiamate_riuscite(messaggi[len(cronologia):], origini, parametri)
                for chiamata in riuscite[mandate:]:
                    coda.put(("strumento", chiamata))
                mandate = len(riuscite)

            esito = None
            try:
                try:
                    nuova = esegui_turno_in_streaming(
                        grafo, cronologia, fuso, testo, lambda pezzo: coda.put(("testo", {"pezzo": pezzo})),
                        su_messaggi, istruzioni=richiesta.istruzioni,
                    )
                    esito = ("fine", risultato(nuova, cronologia, ENDPOINT_STREAM, inizio))
                except Exception as eccezione:
                    stato, messaggio = _errore_turno(eccezione)
                    _log_errore(stato, messaggio, inizio, ENDPOINT_STREAM)
                    esito = ("errore", {"errore": messaggio, "stato": stato})
            finally:
                turno_in_corso.release()  # il turno è finito: prima dell'ultimo evento, niente 409 al turno successivo
                if esito:
                    coda.put(esito)
                coda.put(fine_flusso)

        threading.Thread(target=lavora, daemon=True).start()

        def flusso():
            while True:
                voce = coda.get()
                if voce is fine_flusso:
                    return
                yield formatta_sse(*voce)

        return StreamingResponse(
            flusso(), media_type="text/event-stream; charset=utf-8", headers={"Cache-Control": "no-cache"}
        )

    return app
