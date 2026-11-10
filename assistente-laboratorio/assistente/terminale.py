"""Interfaccia da terminale: ciclo di chat, uscita e stampa."""

from typing import Callable, Mapping, Sequence

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from assistente.fuso import RisultatoFuso
from assistente.grafo import esegui_turno, esegui_turno_in_streaming

PAROLA_USCITA = "esci"
NESSUNA_RISPOSTA = "(nessuna risposta dal modello)"


def _ordinati(argomenti: Mapping[str, object], ordine: Sequence[str]) -> dict[str, object]:
    """Argomenti nell'ordine dello schema (il modello può mandarli in qualsiasi ordine)."""
    nomi = [n for n in ordine if n in argomenti] + [n for n in argomenti if n not in ordine]
    return {n: argomenti[n] for n in nomi}


def chiamate_riuscite(
    nuovi: list[BaseMessage], origini: Mapping[str, str], parametri: Mapping[str, Sequence[str]]
) -> list[dict]:
    """Le chiamate eseguite con successo in questo turno: nome, variante usata e argomenti ordinati.

    Le usano il terminale (righe `[nome · origine: valori]`) e il servizio HTTP (campo `strumenti`).
    """
    richieste = {
        chiamata["id"]: chiamata
        for messaggio in nuovi
        if isinstance(messaggio, AIMessage)
        for chiamata in messaggio.tool_calls
    }
    riuscite = []
    for messaggio in nuovi:
        if isinstance(messaggio, ToolMessage) and messaggio.status != "error":
            chiamata = richieste.get(messaggio.tool_call_id)
            if chiamata:
                nome = chiamata["name"]
                argomenti = _ordinati(chiamata.get("args") or {}, parametri.get(nome, ()))
                riuscite.append({"nome": nome, "origine": origini.get(nome, "?"), "argomenti": argomenti})
    return riuscite


def _righe_strumenti(
    nuovi: list[BaseMessage], origini: Mapping[str, str], parametri: Mapping[str, Sequence[str]]
) -> list[str]:
    """Una riga per ogni chiamata eseguita con successo in questo turno, con la variante usata."""
    return [
        f"[{c['nome']} · {c['origine']}: {', '.join(str(v) for v in c['argomenti'].values())}]"
        for c in chiamate_riuscite(nuovi, origini, parametri)
    ]


class _StampaInStreaming:
    """Stampa i pezzi della risposta dopo «Assistente: » e le righe degli strumenti appena eseguiti."""

    def __init__(self, cronologia, scrivi, scrivi_pezzo, origini, parametri):
        self.inizio = len(cronologia)
        self.scrivi, self.scrivi_pezzo = scrivi, scrivi_pezzo
        self.origini, self.parametri = origini, parametri
        self.righe_stampate = 0
        self.a_meta_riga = False  # c'è una riga «Assistente: …» ancora aperta
        self.ha_scritto = False  # almeno un pezzo stampato in questo turno

    def chiudi_riga(self) -> None:
        if self.a_meta_riga:
            self.scrivi_pezzo("\n")
            self.a_meta_riga = False

    def testo(self, pezzo: str) -> None:
        if not self.a_meta_riga:
            self.scrivi_pezzo("Assistente: ")
            self.a_meta_riga = True
        self.scrivi_pezzo(pezzo)
        self.ha_scritto = True

    def messaggi(self, messaggi) -> None:
        righe = _righe_strumenti(messaggi[self.inizio:], self.origini, self.parametri)
        nuove = righe[self.righe_stampate:]
        if nuove:
            self.chiudi_riga()
            for riga in nuove:
                self.scrivi(riga)
            self.righe_stampate = len(righe)


def esegui_sessione(
    grafo,
    fuso: RisultatoFuso,
    leggi: Callable[[str], str] = input,
    scrivi: Callable[[str], None] = print,
    origini: Mapping[str, str] | None = None,
    parametri: Mapping[str, Sequence[str]] | None = None,
    scrivi_pezzo: Callable[[str], None] | None = None,
) -> None:
    """Con `scrivi_pezzo` la risposta del modello compare a pezzi man mano che arriva."""
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

        stampa = _StampaInStreaming(cronologia, scrivi, scrivi_pezzo, origini, parametri) if scrivi_pezzo else None
        try:
            if stampa:
                nuova = esegui_turno_in_streaming(grafo, cronologia, fuso.fuso, testo, stampa.testo, stampa.messaggi)
            else:
                nuova = esegui_turno(grafo, cronologia, fuso.fuso, testo)
        except KeyboardInterrupt:
            if stampa:
                stampa.chiudi_riga()
            break
        except Exception as eccezione:
            # La cronologia resta quella di prima: il messaggio fallito non viene conservato.
            if stampa:
                stampa.chiudi_riga()
            scrivi(f"Errore: {eccezione}")
            continue

        if stampa:
            stampa.messaggi(nuova)
            ultimo_in_streaming = stampa.ha_scritto and stampa.a_meta_riga
            stampa.chiudi_riga()
        else:
            for riga in _righe_strumenti(nuova[len(cronologia):], origini, parametri):
                scrivi(riga)
            ultimo_in_streaming = False
        cronologia = nuova
        if not ultimo_in_streaming:  # rifiuto, limite, risposta vuota o niente streaming: riga intera
            risposta = nuova[-1].text.strip() if isinstance(nuova[-1], AIMessage) else ""
            scrivi(f"Assistente: {risposta or NESSUNA_RISPOSTA}")

    scrivi("Arrivederci.")
