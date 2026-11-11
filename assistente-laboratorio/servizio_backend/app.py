"""Applicazione FastAPI del back-end delle chat (lezione 6, step 7).

Progetti, chat, ricerca e il turno in streaming. Gli errori sono sempre {"errore": "..."} in italiano
e il log non contiene mai il testo dei messaggi né le istruzioni.
"""

import logging
import time
from typing import Annotated

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, StringConstraints

from assistente.http import RispostaJson, messaggio_validazione
from servizio_backend.archivio import Archivio, DatabaseNonRaggiungibile, ErroreArchivio, ProgettoInesistente
from servizio_backend.client_agente import AgenteNonDisponibile
from servizio_backend.turni import RegistroTurni, Turno

TITOLO = "Back-end delle chat"
MESSAGGIO_DATABASE = "Il database non risponde: riprova tra poco."
MESSAGGIO_CHAT_OCCUPATA = "C'è già una risposta in corso in questa chat."
MESSAGGIO_CANCELLAZIONE = "C'è un turno in corso in questa chat: aspetta che finisca."

registro = logging.getLogger("servizio_backend")

_MASSIMO_ID = 2**31 - 1  # gli id sono INTEGER nel database
IdPercorso = Annotated[int, Path(ge=1, le=_MASSIMO_ID)]
IdCorpo = Annotated[int, Field(ge=1, le=_MASSIMO_ID)]
Nome = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class NuovoProgetto(BaseModel):
    nome: Nome
    istruzioni: str = Field(default="", max_length=4000)


class ModificaProgetto(BaseModel):
    nome: Nome | None = None
    istruzioni: str | None = Field(default=None, max_length=4000)


class NuovaChat(BaseModel):
    progetto_id: IdCorpo | None = None


class SpostaChat(BaseModel):
    progetto_id: IdCorpo | None  # obbligatorio, ma può essere null: la chat esce dal progetto


class NuovoMessaggio(BaseModel):
    messaggio: str


def _errore(stato: int, messaggio: str) -> JSONResponse:
    return RispostaJson(status_code=stato, content={"errore": messaggio})


def _non_trovato(cosa: str, id: int) -> JSONResponse:
    return _errore(404, f"{cosa} {id} non trovat{'o' if cosa == 'Progetto' else 'a'}.")


def crea_app(archivio: Archivio, agente) -> FastAPI:
    app = FastAPI(
        title=TITOLO,
        description="Progetti, chat e ricerca salvati in PostgreSQL; i turni passano dall'agente.",
        default_response_class=RispostaJson,
    )
    turni = RegistroTurni()

    @app.middleware("http")
    async def riga_di_log(richiesta: Request, chiama_dopo):
        # Una riga per richiesta; solo il percorso, mai la query string (la ricerca contiene testo dell'utente).
        inizio = time.perf_counter()
        stato = 500
        try:
            risposta = await chiama_dopo(richiesta)
            stato = risposta.status_code
            return risposta
        finally:
            registro.info(
                "richiesta metodo=%s endpoint=%s esito=%s stato=%d durata=%.2f",
                richiesta.method, richiesta.url.path, "errore" if stato >= 400 else "ok", stato,
                time.perf_counter() - inizio,
            )

    @app.exception_handler(RequestValidationError)
    async def validazione_in_italiano(richiesta: Request, eccezione: RequestValidationError) -> JSONResponse:
        return _errore(400, messaggio_validazione(eccezione))

    @app.exception_handler(DatabaseNonRaggiungibile)
    async def database_spento(richiesta: Request, eccezione: DatabaseNonRaggiungibile) -> JSONResponse:
        registro.warning("richiesta endpoint=%s esito=errore database non raggiungibile: %s", richiesta.url.path, eccezione)
        return _errore(503, MESSAGGIO_DATABASE)

    @app.exception_handler(ErroreArchivio)
    async def errore_archivio(richiesta: Request, eccezione: ErroreArchivio) -> JSONResponse:
        registro.warning("richiesta endpoint=%s esito=errore archivio %s", richiesta.url.path, type(eccezione).__name__)
        return _errore(500, "Errore dell'archivio delle chat.")

    @app.exception_handler(Exception)
    async def errore_imprevisto(richiesta: Request, eccezione: Exception) -> JSONResponse:
        registro.exception("richiesta endpoint=%s esito=errore imprevisto", richiesta.url.path)
        return _errore(500, f"Errore interno del back-end: {type(eccezione).__name__}.")

    @app.get("/salute", summary="Stato del back-end")
    def salute() -> dict:
        archivio.controlla()
        return {"stato": "ok", "database": "ok", "agente": "ok" if agente.salute() else "non raggiungibile"}

    # Progetti

    @app.get("/progetti", summary="Elenco dei progetti")
    def elenca_progetti() -> list[dict]:
        return archivio.elenca_progetti()

    @app.post("/progetti", status_code=201, summary="Crea un progetto")
    def crea_progetto(corpo: NuovoProgetto) -> dict:
        return archivio.crea_progetto(corpo.nome, corpo.istruzioni)

    @app.get("/progetti/{id}", summary="Un progetto")
    def leggi_progetto(id: IdPercorso):
        progetto = archivio.leggi_progetto(id)
        return progetto if progetto is not None else _non_trovato("Progetto", id)

    @app.patch("/progetti/{id}", summary="Cambia nome o istruzioni di un progetto")
    def aggiorna_progetto(id: IdPercorso, corpo: ModificaProgetto):
        progetto = archivio.aggiorna_progetto(id, corpo.nome, corpo.istruzioni)
        return progetto if progetto is not None else _non_trovato("Progetto", id)

    @app.delete("/progetti/{id}", status_code=204, summary="Cancella un progetto e le sue chat")
    def cancella_progetto(id: IdPercorso):
        # Le chat del progetto si prenotano tutte, così nessun turno può cominciare durante la cancellazione.
        prese: list[int] = []
        try:
            for chat in archivio.elenca_chat(progetto_id=id):
                if not turni.occupa(chat["id"]):
                    return _errore(409, MESSAGGIO_CANCELLAZIONE)
                prese.append(chat["id"])
            if not archivio.cancella_progetto(id):
                return _non_trovato("Progetto", id)
            return Response(status_code=204)
        finally:
            for chat_id in prese:
                turni.libera(chat_id)

    # Chat

    @app.get("/chat", summary="Elenco delle chat, dalla più recente")
    def elenca_chat(progetto: str | None = None):
        # Un progetto che non esiste dà un elenco vuoto, non un 404: il filtro è solo un criterio di ricerca.
        if progetto is None:
            return archivio.elenca_chat()
        if progetto == "nessuno":
            return archivio.elenca_chat(senza_progetto=True)
        if progetto.isascii() and progetto.isdigit() and 1 <= int(progetto) <= _MASSIMO_ID:
            return archivio.elenca_chat(progetto_id=int(progetto))
        return _errore(400, "Richiesta non valida: progetto: usa un numero oppure «nessuno».")

    @app.post("/chat", status_code=201, summary="Crea una chat vuota")
    def crea_chat(corpo: NuovaChat | None = None):
        try:
            return archivio.crea_chat(corpo.progetto_id if corpo else None)
        except ProgettoInesistente:
            return _errore(404, f"Il progetto {corpo.progetto_id} non esiste.")

    @app.get("/chat/{id}", summary="Una chat con i suoi messaggi")
    def leggi_chat(id: IdPercorso):
        chat = archivio.leggi_chat(id)
        return chat if chat is not None else _non_trovato("Chat", id)

    @app.patch("/chat/{id}", summary="Sposta una chat in un progetto o la toglie dal progetto")
    def sposta_chat(id: IdPercorso, corpo: SpostaChat):
        try:
            chat = archivio.sposta_chat(id, corpo.progetto_id)
        except ProgettoInesistente:
            return _errore(404, f"Il progetto {corpo.progetto_id} non esiste.")
        return chat if chat is not None else _non_trovato("Chat", id)

    @app.delete("/chat/{id}", status_code=204, summary="Cancella una chat")
    def cancella_chat(id: IdPercorso):
        if not turni.occupa(id):
            return _errore(409, MESSAGGIO_CANCELLAZIONE)
        try:
            if not archivio.cancella_chat(id):
                return _non_trovato("Chat", id)
            return Response(status_code=204)
        finally:
            turni.libera(id)

    @app.post("/chat/{id}/messaggi", summary="Un turno di conversazione in streaming (SSE)")
    def nuovo_messaggio(id: IdPercorso, corpo: NuovoMessaggio):
        testo = corpo.messaggio.replace("\ufeff", "").strip()
        if not testo:
            return _errore(400, "Richiesta non valida: il messaggio è vuoto.")
        if not turni.occupa(id):
            return _errore(409, MESSAGGIO_CHAT_OCCUPATA)
        try:
            contesto = archivio.contesto_turno(id)
        except BaseException:
            turni.libera(id)
            raise
        if contesto is None:
            turni.libera(id)
            return _non_trovato("Chat", id)
        try:
            cronologia, istruzioni = contesto
            try:
                turno_agente = agente.apri_turno(testo, cronologia, istruzioni)
            except AgenteNonDisponibile as errore:
                turni.libera(id)
                return _errore(503, str(errore))
            turno = Turno(id, testo, turno_agente, archivio, lambda: turni.libera(id))
            try:
                turno.avvia()
            except BaseException:
                turno_agente.chiudi()
                raise
        except BaseException:
            turni.libera(id)  # libera è idempotente: va bene anche se già liberato sopra
            raise
        return StreamingResponse(
            turno.eventi_sse(), media_type="text/event-stream; charset=utf-8", headers={"Cache-Control": "no-cache"}
        )

    @app.get("/ricerca", summary="Cerca nei messaggi")
    def cerca(q: Annotated[str, Query(min_length=2)]) -> list[dict]:
        return archivio.cerca(q)

    return app
