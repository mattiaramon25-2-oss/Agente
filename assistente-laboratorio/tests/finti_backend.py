"""Archivio in memoria per i test: rispetta il contratto di `servizio_backend.archivio.Archivio`."""
import copy
import threading
from datetime import datetime, timezone

from servizio_backend.archivio import ChatInesistente, DatabaseNonRaggiungibile, ProgettoInesistente
from servizio_backend.client_agente import AgenteInterrotto, AgenteNonDisponibile
from servizio_backend.testi import TITOLO_PREDEFINITO, estratto, titolo_da

_LIMITE_RICERCA = 50


def _ora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class ArchivioInMemoria:
    def __init__(self):
        self.spento = False
        self._progetti: dict[int, dict] = {}
        self._chat: dict[int, dict] = {}
        self._messaggi: list[dict] = []
        self._prossimo = {"progetto": 1, "chat": 1, "messaggio": 1}

    def _vivo(self):
        if self.spento:
            raise DatabaseNonRaggiungibile("database non raggiungibile")

    def _nuovo_id(self, tipo: str) -> int:
        valore = self._prossimo[tipo]
        self._prossimo[tipo] += 1
        return valore

    def _chat_pubblica(self, chat: dict) -> dict:
        return {
            "id": chat["id"],
            "titolo": chat["titolo"] or TITOLO_PREDEFINITO,
            "progetto_id": chat["progetto_id"],
            "creata": chat["creata"],
            "aggiornata": chat["aggiornata"],
        }

    def prepara(self) -> None:
        self._vivo()

    def controlla(self) -> None:
        self._vivo()

    def elenca_progetti(self) -> list[dict]:
        self._vivo()
        risultato = []
        for p in sorted(self._progetti.values(), key=lambda p: (p["nome"].lower(), p["id"])):
            numero = sum(1 for c in self._chat.values() if c["progetto_id"] == p["id"])
            risultato.append({**p, "numero_chat": numero})
        return risultato

    def crea_progetto(self, nome: str, istruzioni: str) -> dict:
        self._vivo()
        ora = _ora()
        progetto = {"id": self._nuovo_id("progetto"), "nome": nome, "istruzioni": istruzioni, "creato": ora, "aggiornato": ora}
        self._progetti[progetto["id"]] = progetto
        return {**progetto, "numero_chat": 0}

    def leggi_progetto(self, id: int) -> dict | None:
        self._vivo()
        progetto = self._progetti.get(id)
        if progetto is None:
            return None
        numero = sum(1 for c in self._chat.values() if c["progetto_id"] == id)
        return {**progetto, "numero_chat": numero}

    def aggiorna_progetto(self, id: int, nome: str | None, istruzioni: str | None) -> dict | None:
        self._vivo()
        progetto = self._progetti.get(id)
        if progetto is None:
            return None
        if nome is not None:
            progetto["nome"] = nome
        if istruzioni is not None:
            progetto["istruzioni"] = istruzioni
        progetto["aggiornato"] = _ora()
        return self.leggi_progetto(id)

    def cancella_progetto(self, id: int) -> bool:
        self._vivo()
        if id not in self._progetti:
            return False
        for chat_id in [c["id"] for c in self._chat.values() if c["progetto_id"] == id]:
            self.cancella_chat(chat_id)
        del self._progetti[id]
        return True

    def elenca_chat(self, progetto_id: int | None = None, senza_progetto: bool = False) -> list[dict]:
        self._vivo()
        chat = list(self._chat.values())
        if progetto_id is not None:
            chat = [c for c in chat if c["progetto_id"] == progetto_id]
        elif senza_progetto:
            chat = [c for c in chat if c["progetto_id"] is None]
        chat.sort(key=lambda c: (c["aggiornata"], c["id"]), reverse=True)
        return [self._chat_pubblica(c) for c in chat]

    def crea_chat(self, progetto_id: int | None) -> dict:
        self._vivo()
        if progetto_id is not None and progetto_id not in self._progetti:
            raise ProgettoInesistente(f"il progetto {progetto_id} non esiste")
        ora = _ora()
        chat = {
            "id": self._nuovo_id("chat"),
            "progetto_id": progetto_id,
            "titolo": None,
            "cronologia": [],
            "creata": ora,
            "aggiornata": ora,
        }
        self._chat[chat["id"]] = chat
        return {**self._chat_pubblica(chat), "messaggi": []}

    def leggi_chat(self, id: int) -> dict | None:
        self._vivo()
        chat = self._chat.get(id)
        if chat is None:
            return None
        messaggi = [
            {k: copy.deepcopy(m[k]) for k in ("id", "ruolo", "testo", "strumenti", "creato")}
            for m in self._messaggi
            if m["chat_id"] == id
        ]
        return {**self._chat_pubblica(chat), "messaggi": messaggi}

    def contesto_turno(self, chat_id: int) -> tuple[list[dict], str] | None:
        self._vivo()
        chat = self._chat.get(chat_id)
        if chat is None:
            return None
        progetto = self._progetti.get(chat["progetto_id"]) if chat["progetto_id"] is not None else None
        return copy.deepcopy(chat["cronologia"]), progetto["istruzioni"] if progetto else ""

    def sposta_chat(self, id: int, progetto_id: int | None) -> dict | None:
        self._vivo()
        if progetto_id is not None and progetto_id not in self._progetti:
            raise ProgettoInesistente(f"il progetto {progetto_id} non esiste")
        chat = self._chat.get(id)
        if chat is None:
            return None
        chat["progetto_id"] = progetto_id
        return self._chat_pubblica(chat)

    def cancella_chat(self, id: int) -> bool:
        self._vivo()
        if id not in self._chat:
            return False
        del self._chat[id]
        self._messaggi = [m for m in self._messaggi if m["chat_id"] != id]
        return True

    def salva_turno(self, chat_id: int, domanda: str, risposta: str, strumenti: list[dict], cronologia: list[dict]) -> dict:
        self._vivo()
        chat = self._chat.get(chat_id)
        if chat is None:
            raise ChatInesistente(f"la chat {chat_id} non esiste")
        ora = _ora()
        utente = {"id": self._nuovo_id("messaggio"), "chat_id": chat_id, "ruolo": "utente", "testo": domanda, "strumenti": None, "creato": ora}
        assistente = {
            "id": self._nuovo_id("messaggio"),
            "chat_id": chat_id,
            "ruolo": "assistente",
            "testo": risposta,
            "strumenti": copy.deepcopy(strumenti),
            "creato": ora,
        }
        self._messaggi += [utente, assistente]
        chat["cronologia"] = copy.deepcopy(cronologia)
        chat["aggiornata"] = ora
        if chat["titolo"] is None:
            chat["titolo"] = titolo_da(domanda)
        return {"messaggio_utente_id": utente["id"], "messaggio_assistente_id": assistente["id"], "titolo": chat["titolo"]}

    def cerca(self, q: str) -> list[dict]:
        self._vivo()
        trovati = [m for m in self._messaggi if q.lower() in m["testo"].lower()]
        trovati.sort(key=lambda m: m["id"], reverse=True)
        risultato = []
        for m in trovati[:_LIMITE_RICERCA]:
            chat = self._chat[m["chat_id"]]
            risultato.append(
                {
                    "chat_id": chat["id"],
                    "titolo": chat["titolo"] or TITOLO_PREDEFINITO,
                    "progetto_id": chat["progetto_id"],
                    "messaggio_id": m["id"],
                    "ruolo": m["ruolo"],
                    "estratto": estratto(m["testo"], q),
                }
            )
        return risultato


class TurnoFinto:
    """Un turno dell'agente già aperto, con gli eventi preparati."""

    def __init__(self, eventi, interrompi_dopo=None, cancello=None):
        self._eventi = list(eventi)
        self._interrompi_dopo = interrompi_dopo
        self._cancello = cancello
        self.chiuso = False

    def eventi(self):
        for numero, (nome, dati) in enumerate(self._eventi):
            if self._interrompi_dopo is not None and numero >= self._interrompi_dopo:
                raise AgenteInterrotto("Il collegamento con l'agente si è interrotto.")
            if nome == "fine" and self._cancello is not None:
                self._cancello.wait(5)
            yield nome, dati
        if self._interrompi_dopo is not None and len(self._eventi) <= self._interrompi_dopo:
            raise AgenteInterrotto("Il collegamento con l'agente si è interrotto.")

    def chiudi(self) -> None:
        self.chiuso = True


class AgenteFinto:
    """Rispetta il contratto di `servizio_backend.client_agente.ClientAgente`."""

    def __init__(self, eventi, *, non_disponibile: str | None = None, interrompi_dopo: int | None = None,
                 cancello: threading.Event | None = None):
        self._eventi = eventi
        self.non_disponibile = non_disponibile
        self.interrompi_dopo = interrompi_dopo
        self.cancello = cancello
        self.chiamate: list[tuple] = []
        self.turni: list[TurnoFinto] = []

    def salute(self) -> bool:
        return self.non_disponibile is None

    def apri_turno(self, messaggio: str, cronologia: list[dict], istruzioni: str) -> TurnoFinto:
        self.chiamate.append((messaggio, cronologia, istruzioni))
        if self.non_disponibile is not None:
            raise AgenteNonDisponibile(self.non_disponibile)
        turno = TurnoFinto(self._eventi, self.interrompi_dopo, self.cancello)
        self.turni.append(turno)
        return turno
