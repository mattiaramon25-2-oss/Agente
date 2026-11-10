"""Streaming del turno: i pezzi di testo arrivano solo dal nodo `modello`."""

from datetime import datetime, timezone

from langchain_core.messages import AIMessage, ToolMessage

from assistente.ambito import Ambito
from assistente.grafo import MAX_GIRI_STRUMENTO, crea_grafo, esegui_turno, esegui_turno_in_streaming
from assistente.router import DecisioneRouter
from tests.finti import ModelloFinto, RouterFinto, chiamata_orologio, orologio_finto

FUSO = "Europe/Rome"
AMBITO = Ambito(in_ambito=("data e ora",), fuori_ambito=("poesie",), rifiuto="Fuori ambito.")
OROLOGIO = orologio_finto(datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc))


def grafo_con(risposte, decisioni=None):
    router = RouterFinto(decisioni) if decisioni is not None else None
    return crea_grafo(ModelloFinto(risposte), [OROLOGIO], router, AMBITO if router else None)


def esegui(grafo, testo, cronologia=()):
    pezzi, parziali = [], []
    finale = esegui_turno_in_streaming(grafo, list(cronologia), FUSO, testo, pezzi.append, parziali.append)
    return finale, pezzi, parziali


def test_risposta_diretta_in_un_pezzo():
    finale, pezzi, _ = esegui(grafo_con([AIMessage("Ciao!")]), "ciao")
    assert pezzi == ["Ciao!"]
    assert [m.content for m in finale] == ["ciao", "Ciao!"]


def test_cronologia_uguale_a_quella_senza_streaming():
    risposte = [chiamata_orologio("Asia/Tokyo"), AIMessage("Sono le 19:00.")]
    senza = esegui_turno(grafo_con(list(risposte)), [], FUSO, "che ore sono a Tokyo?")
    con, pezzi, parziali = esegui(grafo_con(list(risposte)), "che ore sono a Tokyo?")
    assert [type(m) for m in con] == [type(m) for m in senza]
    assert [m.content for m in con] == [m.content for m in senza]
    assert pezzi == ["Sono le 19:00."]  # la richiesta di strumento non ha testo
    # la cronologia parziale con il ToolMessage arriva prima della risposta finale
    assert any(isinstance(p[-1], ToolMessage) for p in parziali)


def test_router_e_rifiuto_non_vanno_in_streaming():
    finale, pezzi, _ = esegui(grafo_con([], [DecisioneRouter(categoria="fuori_ambito", motivo="poesia")]), "poesia")
    assert pezzi == []
    assert finale[-1].content == "Fuori ambito."


def test_in_ambito_con_router():
    decisioni = [DecisioneRouter(categoria="conversazione", motivo="saluto")]
    _, pezzi, _ = esegui(grafo_con([AIMessage("Ciao!")], decisioni), "ciao")
    assert pezzi == ["Ciao!"]


def test_limite_non_va_in_streaming():
    risposte = [chiamata_orologio(FUSO, f"c{i}") for i in range(MAX_GIRI_STRUMENTO + 1)]
    finale, pezzi, _ = esegui(grafo_con(risposte), "che ore sono?")
    assert pezzi == []
    assert isinstance(finale[-1], AIMessage) and "troppe chiamate" in finale[-1].content


def test_la_cronologia_passata_non_cambia():
    cronologia = [AIMessage("vecchio")]
    copia = list(cronologia)
    esegui(grafo_con([AIMessage("Ciao!")]), "ciao", cronologia)
    assert cronologia == copia


def test_streaming_passa_le_istruzioni_al_modello():
    modello = ModelloFinto([AIMessage("ok")])
    grafo = crea_grafo(modello, [OROLOGIO])
    esegui_turno_in_streaming(grafo, [], FUSO, "ciao", lambda pezzo: None, istruzioni="Sii breve.")
    assert modello.chiamate[0][0].content.endswith("Sii breve.")
