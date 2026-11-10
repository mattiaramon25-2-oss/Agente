"""Server-Sent Events: formato di scrittura (servizio dell'agente) e di lettura (back-end)."""

import json
from typing import Iterable, Iterator


def formatta_sse(evento: str, dati: dict) -> str:
    """Un evento SSE con i dati in JSON su una riga (gli a capo diventano `\n`)."""
    return f"event: {evento}\ndata: {json.dumps(dati, ensure_ascii=False)}\n\n"


def leggi_sse(righe: Iterable[str]) -> Iterator[tuple[str, dict]]:
    """Legge righe SSE e restituisce una coppia (evento, dati) a ogni riga vuota.

    Le righe possono avere o no l'a capo finale (`str.splitlines()`, `httpx.Response.iter_lines()`).
    Le righe che iniziano con `:` sono commenti e si ignorano. Un evento senza riga `event:`
    ha nome «message». Se il flusso finisce senza la riga vuota finale, l'evento incompleto
    non viene restituito.
    """
    evento, dati = None, []
    for riga in righe:
        riga = riga.rstrip("\r\n")
        if riga == "":
            if dati:
                yield evento or "message", json.loads("\n".join(dati))
            evento, dati = None, []
        elif riga.startswith(":"):
            continue
        elif riga.startswith("event:"):
            evento = riga[6:].strip()
        elif riga.startswith("data:"):
            dati.append(riga[5:].removeprefix(" "))
