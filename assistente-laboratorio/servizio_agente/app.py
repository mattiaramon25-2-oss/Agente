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
from assistente.registro import formatta
from assistente.sse import formatta_sse
from assistente.terminale import NESSUNA_RISPOSTA, chiamate_riuscite

TITOLO = "Servizio dell'agente"
ENDPOINT_CHAT = "/chat"
ENDPOINT_STREAM = "/chat/stream"
MESSAGGIO_OCCUPATO = "L'agente sta già rispondendo a un'altra richiesta."

registro = logging.getLogger("assistente.servizio")


class RispostaJson(JSONResponse):
    """JSON con il charset dichiarato: Invoke-RestMethod di PowerShell 5.1 altrimenti legge in Latin-1."""

    media_type = "application/json; charset=utf-8"


class RichiestaChat(BaseModel):
    messaggio: str = Field(description="il testo dell'utente")
    cronologia: list[dict] = Field(default_factory=list, description="la cronologia restituita dal turno precedente")
    istruzioni: str = Field(default="", max_length=4000, description="istruzioni del progetto, solo nel messaggio di sistema")


def _errore(stato: int, messaggio: str, inizio: float, endpoint: str = ENDPOINT_CHAT) -> JSONResponse:
    registro.info(
        formatta({"richiesta endpoint": endpoint, "esito": "errore", "stato": stato, "messaggio": messaggio,
                  "durata": round(time.monotonic() - inizio, 2)})
    )
    return RispostaJson(status_code=stato, content={"errore": messaggio})


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

    @app.exception_handler(RequestValidationError)
    async def validazione_in_italiano(richiesta: Request, eccezione: RequestValidationError) -> JSONResponse:
        dettagli = []
        for errore in eccezione.errors():
            nome = ".".join(str(parte) for parte in errore.get("loc", ("?",))[1:]) or "corpo"
            dettagli.append(f"{nome}: mancante" if errore.get("type") == "missing" else f"{nome}: valore non valido")
        return _errore(400, "Richiesta non valida: " + "; ".join(dettagli), time.monotonic())

    @app.get("/salute", summary="Stato del servizio")
    def salute() -> dict:
        return {"stato": "ok", "modello": modello, "fuso": fuso, "strumenti": dict(origini)}

    @app.post(ENDPOINT_CHAT, summary="Un turno di conversazione")
    def chat(richiesta: RichiestaChat):
        inizio = time.monotonic()
        testo = richiesta.messaggio.replace("﻿", "").strip()
        if not testo:
            return _errore(400, "Richiesta non valida: il messaggio è vuoto.", inizio)
        try:
            cronologia = messages_from_dict(richiesta.cronologia)
        except Exception as eccezione:
            return _errore(400, f"Richiesta non valida: cronologia non leggibile ({eccezione}).", inizio)

        with turno_in_corso:
            try:
                nuova = esegui_turno(grafo, cronologia, fuso, testo, istruzioni=richiesta.istruzioni)
            except openai.APIConnectionError as eccezione:
                return _errore(503, f"LM Studio non raggiungibile: {eccezione}", inizio)
            except Exception as eccezione:
                return _errore(500, f"Errore durante il turno: {eccezione}", inizio)

        ultimo = nuova[-1]
        risposta = ultimo.text.strip() if isinstance(ultimo, AIMessage) else ""
        strumenti = chiamate_riuscite(nuova[len(cronologia):], origini, parametri)
        registro.info(
            formatta({"richiesta endpoint": ENDPOINT_CHAT, "esito": "ok", "strumenti": [s["nome"] for s in strumenti],
                      "durata": round(time.monotonic() - inizio, 2)})
        )
        return {
            "risposta": risposta or NESSUNA_RISPOSTA,
            "strumenti": strumenti,
            "cronologia": messages_to_dict(nuova),
        }

    @app.post(ENDPOINT_STREAM, summary="Un turno di conversazione in streaming (SSE)")
    def chat_stream(richiesta: RichiestaChat):
        inizio = time.monotonic()
        testo = richiesta.messaggio.replace("﻿", "").strip()
        if not testo:
            return _errore(400, "Richiesta non valida: il messaggio è vuoto.", inizio, ENDPOINT_STREAM)
        try:
            cronologia = messages_from_dict(richiesta.cronologia)
        except Exception as eccezione:
            return _errore(400, f"Richiesta non valida: cronologia non leggibile ({eccezione}).", inizio, ENDPOINT_STREAM)
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

            try:
                try:
                    nuova = esegui_turno_in_streaming(
                        grafo, cronologia, fuso, testo, lambda pezzo: coda.put(("testo", {"pezzo": pezzo})),
                        su_messaggi, istruzioni=richiesta.istruzioni,
                    )
                except openai.APIConnectionError as eccezione:
                    stato, messaggio = 503, f"LM Studio non raggiungibile: {eccezione}"
                except Exception as eccezione:
                    stato, messaggio = 500, f"Errore durante il turno: {eccezione}"
                else:
                    ultimo = nuova[-1]
                    risposta = ultimo.text.strip() if isinstance(ultimo, AIMessage) else ""
                    strumenti = chiamate_riuscite(nuova[len(cronologia):], origini, parametri)
                    registro.info(
                        formatta({"richiesta endpoint": ENDPOINT_STREAM, "esito": "ok",
                                  "strumenti": [s["nome"] for s in strumenti],
                                  "durata": round(time.monotonic() - inizio, 2)})
                    )
                    coda.put(("fine", {"risposta": risposta or NESSUNA_RISPOSTA, "strumenti": strumenti,
                                       "cronologia": messages_to_dict(nuova)}))
                    return
                registro.info(
                    formatta({"richiesta endpoint": ENDPOINT_STREAM, "esito": "errore", "stato": stato,
                              "messaggio": messaggio, "durata": round(time.monotonic() - inizio, 2)})
                )
                coda.put(("errore", {"errore": messaggio, "stato": stato}))
            finally:
                coda.put(fine_flusso)
                turno_in_corso.release()

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
