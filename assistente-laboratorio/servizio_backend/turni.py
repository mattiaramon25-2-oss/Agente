"""Un turno di chat in un thread: legge gli eventi dell'agente, li inoltra al browser e salva a risposta completa."""

import logging
import queue
import threading
import time
from typing import Callable, Iterator

from assistente.registro import formatta
from assistente.sse import formatta_sse
from servizio_backend.archivio import ErroreArchivio
from servizio_backend.client_agente import AgenteInterrotto

registro = logging.getLogger("servizio_backend")

TURNO_INTERROTTO = "La risposta dell'agente si è interrotta: il turno non è stato salvato."
_CHIUSURA = None


class RegistroTurni:
    """Le chat con un turno in corso: una sola risposta alla volta per chat, sicuro tra thread."""

    def __init__(self):
        self._blocco = threading.Lock()
        self._occupate: set[int] = set()

    def occupa(self, chat_id: int) -> bool:
        with self._blocco:
            if chat_id in self._occupate:
                return False
            self._occupate.add(chat_id)
            return True

    def libera(self, chat_id: int) -> None:
        with self._blocco:
            self._occupate.discard(chat_id)

    def in_corso(self, chat_id: int) -> bool:
        with self._blocco:
            return chat_id in self._occupate


class Turno:
    def __init__(self, chat_id: int, domanda: str, turno_agente, archivio, al_termine: Callable[[], None]):
        self.chat_id = chat_id
        self.esito = "errore"
        self.scollegato = False
        self.strumenti: list[str] = []
        self._domanda = domanda
        self._turno_agente = turno_agente
        self._archivio = archivio
        self._al_termine = al_termine
        self._coda: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._esegui, daemon=True)

    def avvia(self) -> None:
        self._thread.start()

    def attendi(self, limite: float) -> None:
        self._thread.join(limite)

    def eventi_sse(self) -> Iterator[str]:
        """Le righe SSE per il browser; se il browser si scollega il thread continua e salva."""
        try:
            while True:
                voce = self._coda.get()
                if voce is _CHIUSURA:
                    return
                yield formatta_sse(*voce)
        except GeneratorExit:
            self.scollegato = True
            raise

    def _esegui(self) -> None:
        inizio = time.monotonic()
        try:
            self._leggi_eventi()
        except AgenteInterrotto as errore:
            self._coda.put(("errore", {"errore": str(errore)}))
        except ErroreArchivio as errore:
            self._coda.put(("errore", {"errore": f"Il turno non è stato salvato: {errore}"}))
        except Exception as errore:  # il thread non deve morire in silenzio
            self._coda.put(("errore", {"errore": f"Errore imprevisto: {errore or type(errore).__name__}."}))
        finally:
            try:
                self._turno_agente.chiudi()
            finally:
                try:
                    self._al_termine()
                finally:
                    registro.info(
                        formatta({"richiesta endpoint": f"/chat/{self.chat_id}/messaggi", "chat_id": self.chat_id,
                                  "esito": self.esito, "strumenti": self.strumenti, "scollegato": self.scollegato,
                                  "durata": round(time.monotonic() - inizio, 2)})
                    )
                    self._coda.put(_CHIUSURA)

    def _leggi_eventi(self) -> None:
        for nome, dati in self._turno_agente.eventi():
            if nome == "testo":
                self._coda.put(("testo", dati))
            elif nome == "strumento":
                self.strumenti.append(dati["nome"])
                self._coda.put(("strumento", dati))
            elif nome == "errore":
                self._coda.put(("errore", {"errore": dati["errore"]}))
                return
            elif nome == "fine":
                salvato = self._archivio.salva_turno(
                    self.chat_id, self._domanda, dati["risposta"], dati["strumenti"], dati["cronologia"]
                )
                self.esito = "ok"
                self._coda.put(("fine", {"risposta": dati["risposta"], "strumenti": dati["strumenti"], **salvato}))
                return
        self._coda.put(("errore", {"errore": TURNO_INTERROTTO}))
