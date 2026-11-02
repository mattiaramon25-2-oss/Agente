"""Interfaccia da terminale: ciclo di chat, uscita e stampa."""

from typing import Callable

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from assistente.fuso import RisultatoFuso
from assistente.grafo import esegui_turno
from assistente.strumenti import NOME_OROLOGIO

PAROLA_USCITA = "esci"
NESSUNA_RISPOSTA = "(nessuna risposta dal modello)"


def _righe_orologio(nuovi: list[BaseMessage]) -> list[str]:
    """Una riga per ogni chiamata all'orologio eseguita davvero in questo turno."""
    richieste = {
        chiamata["id"]: chiamata
        for messaggio in nuovi
        if isinstance(messaggio, AIMessage)
        for chiamata in messaggio.tool_calls
    }
    righe = []
    for messaggio in nuovi:
        if isinstance(messaggio, ToolMessage) and messaggio.status != "error":
            chiamata = richieste.get(messaggio.tool_call_id)
            if chiamata and chiamata["name"] == NOME_OROLOGIO:
                righe.append(f"[orologio: {chiamata['args'].get('fuso', '?')}]")
    return righe


def esegui_sessione(
    grafo,
    fuso: RisultatoFuso,
    leggi: Callable[[str], str] = input,
    scrivi: Callable[[str], None] = print,
) -> None:
    scrivi("Assistente del laboratorio")
    scrivi(f"Fuso orario: {fuso.fuso} ({fuso.origine})")
    if fuso.avviso:
        scrivi(fuso.avviso)
    scrivi(f"Scrivi «{PAROLA_USCITA}» o premi Ctrl+C per uscire.")

    cronologia: list[BaseMessage] = []
    while True:
        try:
            # Il BOM può arrivare da una pipe di PowerShell e .strip() non lo toglie.
            testo = leggi("Tu: ").replace("﻿", "").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not testo:
            continue
        if testo.lower() == PAROLA_USCITA:
            break

        try:
            nuova = esegui_turno(grafo, cronologia, fuso.fuso, testo)
        except KeyboardInterrupt:
            break
        except Exception as eccezione:
            # La cronologia resta quella di prima: il messaggio fallito non viene conservato.
            scrivi(f"Errore: {eccezione}")
            continue

        for riga in _righe_orologio(nuova[len(cronologia):]):
            scrivi(riga)
        cronologia = nuova
        risposta = nuova[-1].text.strip() if isinstance(nuova[-1], AIMessage) else ""
        scrivi(f"Assistente: {risposta or NESSUNA_RISPOSTA}")

    scrivi("Arrivederci.")
