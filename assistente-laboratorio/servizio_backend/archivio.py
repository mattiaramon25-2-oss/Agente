"""Contratto dell'archivio delle chat (eccezioni e interfaccia) e la sua implementazione PostgreSQL."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Protocol

import psycopg
from psycopg.errors import ForeignKeyViolation
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from servizio_backend.testi import TITOLO_PREDEFINITO, estratto, titolo_da


class ErroreArchivio(Exception):
    """Errore generico dell'archivio."""


class ChatInesistente(ErroreArchivio):
    """La chat richiesta non esiste."""


class ProgettoInesistente(ErroreArchivio):
    """Il progetto richiesto non esiste."""


class DatabaseNonRaggiungibile(ErroreArchivio):
    """Il database non risponde."""


class Archivio(Protocol):
    """Ciò che il back-end chiede a un archivio. Le date sono stringhe ISO 8601 in UTC."""

    def prepara(self) -> None:
        """Crea le tabelle se mancano."""

    def controlla(self) -> None:
        """Solleva `DatabaseNonRaggiungibile` se il database non risponde."""

    def elenca_progetti(self) -> list[dict]:
        """Per nome, senza distinguere maiuscole e minuscole. Chiavi: id, nome, istruzioni, numero_chat, creato, aggiornato."""

    def crea_progetto(self, nome: str, istruzioni: str) -> dict: ...

    def leggi_progetto(self, id: int) -> dict | None: ...

    def aggiorna_progetto(self, id: int, nome: str | None, istruzioni: str | None) -> dict | None:
        """Cambia solo i campi non nulli."""

    def cancella_progetto(self, id: int) -> bool:
        """Cancella anche le chat del progetto e i loro messaggi."""

    def elenca_chat(self, progetto_id: int | None = None, senza_progetto: bool = False) -> list[dict]:
        """Da `aggiornata` decrescente, poi `id` decrescente. Chiavi: id, titolo, progetto_id, creata, aggiornata."""

    def crea_chat(self, progetto_id: int | None) -> dict:
        """Solleva `ProgettoInesistente`."""

    def leggi_chat(self, id: int) -> dict | None:
        """La chat con `messaggi` (id, ruolo, testo, strumenti, creato) in ordine."""

    def contesto_turno(self, chat_id: int) -> tuple[list[dict], str] | None:
        """Cronologia salvata e istruzioni del progetto ("" se non c'è); `None` se la chat non esiste."""

    def sposta_chat(self, id: int, progetto_id: int | None) -> dict | None:
        """Solleva `ProgettoInesistente`; `None` se la chat non esiste."""

    def cancella_chat(self, id: int) -> bool: ...

    def salva_turno(self, chat_id: int, domanda: str, risposta: str, strumenti: list[dict], cronologia: list[dict]) -> dict:
        """Salva domanda, risposta e cronologia insieme. Solleva `ChatInesistente`.

        Restituisce messaggio_utente_id, messaggio_assistente_id, titolo."""

    def cerca(self, q: str) -> list[dict]:
        """Al massimo 50 messaggi (entrambi i ruoli) che contengono `q`, da `messaggio_id` decrescente."""


_SCHEMA = Path(__file__).with_name("schema.sql")
_LIMITE_RICERCA = 50


def _iso(momento: datetime) -> str:
    """Stesso formato dell'archivio in memoria: UTC, ISO 8601, microsecondi."""
    return momento.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _progetto(riga: dict) -> dict:
    return {**riga, "creato": _iso(riga["creato"]), "aggiornato": _iso(riga["aggiornato"])}


def _chat(riga: dict) -> dict:
    return {**riga, "creata": _iso(riga["creata"]), "aggiornata": _iso(riga["aggiornata"])}


_COLONNE_PROGETTO = """p.id, p.nome, p.istruzioni, p.creato, p.aggiornato,
    (SELECT count(*) FROM chat c WHERE c.progetto_id = p.id)::int AS numero_chat"""
_COLONNE_CHAT = "id, COALESCE(titolo, %(predefinito)s) AS titolo, progetto_id, creata, aggiornata"


class ArchivioPostgres:
    """Archivio su PostgreSQL: una connessione per chiamata, commit alla fine del blocco."""

    def __init__(self, dsn: str):
        self._dsn = dsn

    @contextmanager
    def _connessione(self) -> Iterator[psycopg.Connection]:
        try:
            with psycopg.connect(self._dsn, row_factory=dict_row) as connessione:
                yield connessione
        except psycopg.OperationalError as errore:
            motivo = " ".join(str(errore).split())
            raise DatabaseNonRaggiungibile(f"il database PostgreSQL non risponde ({motivo})") from errore

    def prepara(self) -> None:
        with self._connessione() as c:
            c.execute(_SCHEMA.read_text(encoding="utf-8"))

    def controlla(self) -> None:
        with self._connessione() as c:
            c.execute("SELECT 1")

    def elenca_progetti(self) -> list[dict]:
        with self._connessione() as c:
            righe = c.execute(f"SELECT {_COLONNE_PROGETTO} FROM progetti p ORDER BY lower(p.nome), p.id").fetchall()
        return [_progetto(r) for r in righe]

    def crea_progetto(self, nome: str, istruzioni: str) -> dict:
        with self._connessione() as c:
            riga = c.execute(
                f"""WITH p AS (INSERT INTO progetti (nome, istruzioni) VALUES (%s, %s) RETURNING *)
                SELECT {_COLONNE_PROGETTO} FROM p""",
                (nome, istruzioni),
            ).fetchone()
        return _progetto(riga)

    def leggi_progetto(self, id: int) -> dict | None:
        with self._connessione() as c:
            riga = c.execute(f"SELECT {_COLONNE_PROGETTO} FROM progetti p WHERE p.id = %s", (id,)).fetchone()
        return _progetto(riga) if riga else None

    def aggiorna_progetto(self, id: int, nome: str | None, istruzioni: str | None) -> dict | None:
        with self._connessione() as c:
            riga = c.execute(
                f"""WITH p AS (
                    UPDATE progetti SET nome = COALESCE(%s, nome), istruzioni = COALESCE(%s, istruzioni), aggiornato = now()
                    WHERE id = %s RETURNING *)
                SELECT {_COLONNE_PROGETTO} FROM p""",
                (nome, istruzioni, id),
            ).fetchone()
        return _progetto(riga) if riga else None

    def cancella_progetto(self, id: int) -> bool:
        with self._connessione() as c:
            return c.execute("DELETE FROM progetti WHERE id = %s", (id,)).rowcount > 0

    def elenca_chat(self, progetto_id: int | None = None, senza_progetto: bool = False) -> list[dict]:
        condizione, parametri = "", {"predefinito": TITOLO_PREDEFINITO}
        if progetto_id is not None:
            condizione, parametri["progetto"] = "WHERE progetto_id = %(progetto)s", progetto_id
        elif senza_progetto:
            condizione = "WHERE progetto_id IS NULL"
        with self._connessione() as c:
            righe = c.execute(
                f"SELECT {_COLONNE_CHAT} FROM chat {condizione} ORDER BY aggiornata DESC, id DESC", parametri
            ).fetchall()
        return [_chat(r) for r in righe]

    def crea_chat(self, progetto_id: int | None) -> dict:
        try:
            with self._connessione() as c:
                riga = c.execute(
                    f"""WITH n AS (INSERT INTO chat (progetto_id) VALUES (%(progetto)s) RETURNING *)
                    SELECT {_COLONNE_CHAT} FROM n""",
                    {"progetto": progetto_id, "predefinito": TITOLO_PREDEFINITO},
                ).fetchone()
        except ForeignKeyViolation as errore:
            raise ProgettoInesistente(f"il progetto {progetto_id} non esiste") from errore
        return {**_chat(riga), "messaggi": []}

    def leggi_chat(self, id: int) -> dict | None:
        with self._connessione() as c:
            riga = c.execute(
                f"SELECT {_COLONNE_CHAT} FROM chat WHERE id = %(id)s", {"id": id, "predefinito": TITOLO_PREDEFINITO}
            ).fetchone()
            if riga is None:
                return None
            messaggi = c.execute(
                "SELECT id, ruolo, testo, strumenti, creato FROM messaggi WHERE chat_id = %s ORDER BY id", (id,)
            ).fetchall()
        return {**_chat(riga), "messaggi": [{**m, "creato": _iso(m["creato"])} for m in messaggi]}

    def contesto_turno(self, chat_id: int) -> tuple[list[dict], str] | None:
        with self._connessione() as c:
            riga = c.execute(
                """SELECT c.cronologia, COALESCE(p.istruzioni, '') AS istruzioni
                FROM chat c LEFT JOIN progetti p ON p.id = c.progetto_id WHERE c.id = %s""",
                (chat_id,),
            ).fetchone()
        return (riga["cronologia"], riga["istruzioni"]) if riga else None

    def sposta_chat(self, id: int, progetto_id: int | None) -> dict | None:
        with self._connessione() as c:
            if progetto_id is not None and c.execute("SELECT 1 FROM progetti WHERE id = %s", (progetto_id,)).fetchone() is None:
                raise ProgettoInesistente(f"il progetto {progetto_id} non esiste")
            riga = c.execute(
                f"UPDATE chat SET progetto_id = %(progetto)s WHERE id = %(id)s RETURNING {_COLONNE_CHAT}",
                {"progetto": progetto_id, "id": id, "predefinito": TITOLO_PREDEFINITO},
            ).fetchone()
        return _chat(riga) if riga else None

    def cancella_chat(self, id: int) -> bool:
        with self._connessione() as c:
            return c.execute("DELETE FROM chat WHERE id = %s", (id,)).rowcount > 0

    def salva_turno(self, chat_id: int, domanda: str, risposta: str, strumenti: list[dict], cronologia: list[dict]) -> dict:
        inserisci = "INSERT INTO messaggi (chat_id, ruolo, testo, strumenti) VALUES (%s, %s, %s, %s) RETURNING id"
        try:
            # Una sola transazione: se la chat non c'è o qualcosa fallisce, il blocco `with` fa il rollback.
            with self._connessione() as c:
                utente = c.execute(inserisci, (chat_id, "utente", domanda, None)).fetchone()["id"]
                assistente = c.execute(inserisci, (chat_id, "assistente", risposta, Jsonb(strumenti))).fetchone()["id"]
                riga = c.execute(
                    """UPDATE chat SET cronologia = %s, aggiornata = now(), titolo = COALESCE(titolo, %s)
                    WHERE id = %s RETURNING titolo""",
                    (Jsonb(cronologia), titolo_da(domanda), chat_id),
                ).fetchone()
                if riga is None:
                    raise ChatInesistente(f"la chat {chat_id} non esiste")
        except ForeignKeyViolation as errore:
            raise ChatInesistente(f"la chat {chat_id} non esiste") from errore
        return {"messaggio_utente_id": utente, "messaggio_assistente_id": assistente, "titolo": riga["titolo"]}

    def cerca(self, q: str) -> list[dict]:
        barra = chr(92)
        schema = q.replace(barra, barra + barra).replace("%", barra + "%").replace("_", barra + "_")
        with self._connessione() as c:
            righe = c.execute(
                r"""SELECT m.chat_id, COALESCE(c.titolo, %s) AS titolo, c.progetto_id, m.id AS messaggio_id, m.ruolo, m.testo
                FROM messaggi m JOIN chat c ON c.id = m.chat_id
                WHERE m.testo ILIKE %s ESCAPE '\' ORDER BY m.id DESC LIMIT %s""",
                (TITOLO_PREDEFINITO, f"%{schema}%", _LIMITE_RICERCA),
            ).fetchall()
        chiavi = ("chat_id", "titolo", "progetto_id", "messaggio_id", "ruolo")
        return [{**{k: r[k] for k in chiavi}, "estratto": estratto(r["testo"], q)} for r in righe]
