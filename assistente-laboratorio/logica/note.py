"""Note persistenti su SQLite: l'unico strumento con effetti che sopravvivono alla sessione.

Ogni operazione apre e chiude la propria connessione (su Windows il `with` di sqlite3 non
chiude la connessione: va chiusa esplicitamente). Gli ID usano AUTOINCREMENT, quindi l'ID di
una nota eliminata non viene mai riusato: un ID vecchio non può indicare una nota nuova.
L'archivio (file e cartella) si crea solo alla prima operazione.
"""

import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Callable

from logica.errori import ErroreStrumento
from logica.orologio import ora_utc

PERCORSO_NOTE = Path(__file__).resolve().parent.parent / "archivio" / "note.sqlite3"
LUNGHEZZA_MASSIMA = 500
LIMITE_MASSIMO = 50
LIMITE_PREDEFINITO = 10

# Schemi JSON degli argomenti (nomi dalla slide 26), unici per ogni registrazione.
SCHEMA_TEXT = {"type": "string", "description": f"Testo della nota, al massimo {LUNGHEZZA_MASSIMA} caratteri"}
SCHEMA_LIMIT = {
    "type": "integer",
    "minimum": 1,
    "maximum": LIMITE_MASSIMO,
    "default": LIMITE_PREDEFINITO,
    "description": f"Numero massimo di note da elencare, da 1 a {LIMITE_MASSIMO}",
}
SCHEMA_NOTE_ID = {"type": "integer", "description": "ID esatto della nota da eliminare, come restituito da list_notes"}

_CIFRE = re.compile(r"[0-9]+", re.ASCII)
_CREA_TABELLA = (
    "CREATE TABLE IF NOT EXISTS note ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, testo TEXT NOT NULL, creata TEXT NOT NULL)"
)


def _intero(valore: object) -> int | None:
    if isinstance(valore, int) and not isinstance(valore, bool):
        return valore
    if isinstance(valore, float) and valore.is_integer():
        return int(valore)
    if isinstance(valore, str) and _CIFRE.fullmatch(valore):
        return int(valore)
    return None


class ArchivioNote:
    def __init__(self, percorso: Path = PERCORSO_NOTE, adesso: Callable[[], datetime] = ora_utc):
        self.percorso = Path(percorso)
        self.adesso = adesso

    def _esegui(self, operazione: Callable[[sqlite3.Connection], dict]) -> dict:
        """Apre l'archivio, esegue `operazione` in una transazione e chiude sempre la connessione."""
        try:
            self.percorso.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.percorso)) as connessione:
                with connessione:  # transazione: commit o rollback
                    connessione.execute(_CREA_TABELLA)
                    return operazione(connessione)
        except (sqlite3.Error, OSError) as errore:
            raise ErroreStrumento(f"Archivio delle note non accessibile: {errore}.") from None

    def aggiungi(self, text: object) -> dict:
        testo = text.strip() if isinstance(text, str) else ""
        if not testo:
            raise ErroreStrumento("Il testo della nota è vuoto.")
        if len(testo) > LUNGHEZZA_MASSIMA:
            raise ErroreStrumento(f"Il testo della nota supera i {LUNGHEZZA_MASSIMA} caratteri.")
        creata = self.adesso().isoformat(timespec="seconds")

        def operazione(connessione: sqlite3.Connection) -> dict:
            cursore = connessione.execute("INSERT INTO note (testo, creata) VALUES (?, ?)", (testo, creata))
            return {"id": cursore.lastrowid, "testo": testo, "creata": creata, "esito": "nota creata"}

        return self._esegui(operazione)

    def elenca(self, limit: object = LIMITE_PREDEFINITO) -> dict:
        quante = LIMITE_PREDEFINITO if limit is None else _intero(limit)  # null = argomento omesso
        if quante is None or not 1 <= quante <= LIMITE_MASSIMO:
            raise ErroreStrumento(f"limit deve essere un intero tra 1 e {LIMITE_MASSIMO}.")

        def operazione(connessione: sqlite3.Connection) -> dict:
            righe = connessione.execute(
                "SELECT id, testo, creata FROM note ORDER BY id DESC LIMIT ?", (quante,)
            ).fetchall()
            (totale,) = connessione.execute("SELECT COUNT(*) FROM note").fetchone()
            return {"note": [{"id": i, "testo": t, "creata": c} for i, t, c in righe], "totale_archivio": totale}

        return self._esegui(operazione)

    def elimina(self, note_id: object) -> dict:
        numero = _intero(note_id)
        if numero is None or numero < 1:
            raise ErroreStrumento("note_id deve essere un intero positivo.")

        def operazione(connessione: sqlite3.Connection) -> dict:
            riga = connessione.execute("SELECT testo FROM note WHERE id = ?", (numero,)).fetchone()
            if riga is None:
                raise ErroreStrumento(f"Nessuna nota con ID {numero}: niente è stato eliminato.")
            connessione.execute("DELETE FROM note WHERE id = ?", (numero,))
            return {"id": numero, "testo": riga[0], "esito": "nota eliminata"}

        return self._esegui(operazione)
