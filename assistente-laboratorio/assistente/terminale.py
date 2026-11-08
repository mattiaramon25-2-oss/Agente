"""Interfaccia da terminale: ciclo di chat, uscita e stampa."""

from typing import Callable, Mapping, Sequence

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from assistente.fuso import RisultatoFuso
from assistente.grafo import esegui_turno

PAROLA_USCITA = "esci"
NESSUNA_RISPOSTA = "(nessuna risposta dal modello)"


def _valori(argomenti: Mapping[str, object], ordine: Sequence[str]) -> str:
    """Valori degli argomenti nell'ordine dello schema (il modello può mandarli in qualsiasi ordine)."""
    nomi = [n for n in ordine if n in argomenti] + [n for n in argomenti if n not in ordine]
    return ", ".join(str(argomenti[n]) for n in nomi)


def _righe_strumenti(
    nuovi: list[BaseMessage], origini: Mapping[str, str], parametri: Mapping[str, Sequence[str]]
) -> list[str]:
    """Una riga per ogni chiamata eseguita con successo in questo turno, con la variante usata."""
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
            if chiamata:
                nome = chiamata["name"]
                valori = _valori(chiamata.get("args") or {}, parametri.get(nome, ()))
                righe.append(f"[{nome} · {origini.get(nome, '?')}: {valori}]")
    return righe


def esegui_sessione(
    grafo,
    fuso: RisultatoFuso,
    leggi: Callable[[str], str] = input,
    scrivi: Callable[[str], None] = print,
    origini: Mapping[str, str] | None = None,
    parametri: Mapping[str, Sequence[str]] | None = None,
) -> None:
    origini = dict(origini or {})
    parametri = dict(parametri or {})
    scrivi("Assistente del laboratorio")
    scrivi(f"Fuso orario: {fuso.fuso} ({fuso.origine})")
    if origini:
        scrivi("Strumenti: " + ", ".join(f"{nome} ({origine})" for nome, origine in origini.items()))
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

        for riga in _righe_strumenti(nuova[len(cronologia):], origini, parametri):
            scrivi(riga)
        cronologia = nuova
        risposta = nuova[-1].text.strip() if isinstance(nuova[-1], AIMessage) else ""
        scrivi(f"Assistente: {risposta or NESSUNA_RISPOSTA}")

    scrivi("Arrivederci.")
