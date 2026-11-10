"""Contratto dell'archivio delle chat: eccezioni e interfaccia."""
from typing import Protocol


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
