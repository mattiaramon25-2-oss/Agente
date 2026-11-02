from datetime import datetime, timezone

from langchain_core.messages import AIMessage

from assistente.fuso import RisultatoFuso
from assistente.grafo import crea_grafo
from assistente.strumenti import crea_strumento_orologio
from assistente.terminale import esegui_sessione
from tests.finti import ModelloFinto, chiamata_orologio

ISTANTE = datetime(2026, 11, 2, 14, 4, 5, tzinfo=timezone.utc)
FUSO = RisultatoFuso("Europe/Rome", "computer locale", None)


def sessione(righe, risposte=(), fuso=FUSO):
    """Esegue una sessione con ingresso e uscita simulati; restituisce (righe stampate, modello)."""
    modello = ModelloFinto(list(risposte))
    grafo = crea_grafo(modello, [crea_strumento_orologio(lambda: ISTANTE)])
    da_leggere = list(righe)
    stampate = []

    def leggi(prompt):
        assert prompt == "Tu: "
        if not da_leggere:
            raise AssertionError("ingresso esaurito")
        riga = da_leggere.pop(0)
        if isinstance(riga, BaseException):
            raise riga
        return riga

    esegui_sessione(grafo, fuso, leggi=leggi, scrivi=stampate.append)
    return stampate, modello


def test_esci():
    stampate, modello = sessione(["  ESCI "])
    assert modello.chiamate == []
    assert "Arrivederci." in stampate


def test_esci_con_bom_da_pipe_powershell():
    # PowerShell può anteporre il BOM UTF-8 al testo inviato con una pipe.
    stampate, modello = sessione(["﻿esci"])
    assert modello.chiamate == []
    assert "Arrivederci." in stampate


def test_riga_vuota_ignorata():
    _, modello = sessione(["", "   ", "esci"])
    assert modello.chiamate == []


def test_eof():
    stampate, _ = sessione([EOFError()])
    assert stampate[-1] == "Arrivederci."


def test_ctrl_c_in_lettura():
    stampate, _ = sessione([KeyboardInterrupt()])
    assert stampate[-1] == "Arrivederci."


def test_ctrl_c_durante_la_risposta():
    stampate, modello = sessione(["ciao"], [KeyboardInterrupt()])
    assert len(modello.chiamate) == 1
    assert stampate[-1] == "Arrivederci."


def test_benvenuto():
    stampate, _ = sessione(["esci"], fuso=RisultatoFuso("UTC", "ripiego", "AVVISO X"))
    benvenuto = "\n".join(stampate[:-1])
    assert "UTC" in benvenuto and "(ripiego)" in benvenuto
    assert "AVVISO X" in benvenuto
    assert "esci" in benvenuto


def test_benvenuto_mostra_origine():
    stampate, _ = sessione(["esci"], fuso=RisultatoFuso("Europe/Berlin", "host Windows", None))
    assert any("Fuso orario: Europe/Berlin (host Windows)" in riga for riga in stampate)


def test_conversazione_con_orologio():
    stampate, _ = sessione(
        ["che ore sono a Tokyo?", "esci"],
        [chiamata_orologio("Asia/Tokyo"), AIMessage("Sono le 23:04.")],
    )
    orologio = stampate.index("[orologio: Asia/Tokyo]")
    risposta = stampate.index("Assistente: Sono le 23:04.")
    assert orologio < risposta


def test_limite_mostra_solo_le_chiamate_eseguite():
    chiamate = [chiamata_orologio("Europe/Rome", f"c{i}") for i in range(1, 5)]
    stampate, _ = sessione(["che ore sono?", "esci"], chiamate)
    assert stampate.count("[orologio: Europe/Rome]") == 3


def test_risposta_vuota():
    stampate, _ = sessione(["ciao", "esci"], [AIMessage("")])
    assert "Assistente: (nessuna risposta dal modello)" in stampate


def test_errore_del_modello():
    stampate, modello = sessione(["a", "b", "esci"], [RuntimeError("server giù"), AIMessage("ok")])
    errore = stampate.index("Errore: server giù")
    assert stampate.index("Assistente: ok") > errore
    contenuti = [m.content for m in modello.chiamate[1]]
    assert "a" not in contenuti
    assert "b" in contenuti


def test_cronologia_tra_turni():
    _, modello = sessione(["uno", "due", "esci"], [AIMessage("primo"), AIMessage("secondo")])
    contenuti = [m.content for m in modello.chiamate[1][1:]]
    assert contenuti == ["uno", "primo", "due"]
