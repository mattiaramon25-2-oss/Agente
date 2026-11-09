from datetime import datetime, timezone

from langchain_core.messages import AIMessage

from assistente.fuso import RisultatoFuso
from assistente.grafo import crea_grafo
from assistente.terminale import esegui_sessione
from tests.finti import ModelloFinto, chiamata, chiamata_orologio, orologio_finto, strumento_finto

ISTANTE = datetime(2026, 11, 2, 14, 4, 5, tzinfo=timezone.utc)
FUSO = RisultatoFuso("Europe/Rome", "computer locale", None)


ORIGINI = {"ora_corrente": "mcp"}


def sessione(righe, risposte=(), fuso=FUSO, strumenti=None, origini=ORIGINI, parametri=None):
    """Esegue una sessione con ingresso e uscita simulati; restituisce (righe stampate, modello)."""
    modello = ModelloFinto(list(risposte))
    grafo = crea_grafo(modello, strumenti if strumenti is not None else [orologio_finto(ISTANTE)])
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

    esegui_sessione(grafo, fuso, leggi=leggi, scrivi=stampate.append, origini=origini, parametri=parametri)
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
    orologio = stampate.index("[ora_corrente · mcp: Asia/Tokyo]")
    risposta = stampate.index("Assistente: Sono le 23:04.")
    assert orologio < risposta


def test_limite_mostra_solo_le_chiamate_eseguite():
    chiamate = [chiamata_orologio("Europe/Rome", f"c{i}") for i in range(1, 5)]
    stampate, _ = sessione(["che ore sono?", "esci"], chiamate)
    assert stampate.count("[ora_corrente · mcp: Europe/Rome]") == 3


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


def test_riga_con_variante():
    stampate, _ = sessione(
        ["2,5 km in metri?", "esci"],
        [chiamata("converti_unita", {"valore": 2.5, "da": "km", "a": "m"}), AIMessage("2500 m")],
        strumenti=[strumento_finto('{"risultato": 2500}')],
        origini={"converti_unita": "mcp"},
    )
    assert stampate.index("[converti_unita · mcp: 2.5, km, m]") < stampate.index("Assistente: 2500 m")


def test_strumento_fallito_non_stampa():
    stampate, _ = sessione(
        ["ora su Marte?", "esci"],
        [chiamata_orologio("Mars/Olympus"), AIMessage("Fuso sconosciuto.")],
    )
    assert not any(riga.startswith("[") for riga in stampate)


def test_benvenuto_con_strumenti():
    stampate, _ = sessione(["esci"], origini={"ora_corrente": "mcp", "calcola": "locale"})
    assert "Strumenti: ora_corrente (mcp), calcola (locale)" in stampate
    indice_fuso = next(i for i, r in enumerate(stampate) if r.startswith("Fuso orario:"))
    assert stampate[indice_fuso + 1].startswith("Strumenti: ")


def test_benvenuto_senza_strumenti():
    stampate, _ = sessione(["esci"], origini={})
    assert not any(r.startswith("Strumenti:") for r in stampate)


def test_argomenti_nell_ordine_dello_schema():
    # Il modello può mandare gli argomenti in qualsiasi ordine: la riga segue l'ordine dello strumento.
    stampate, _ = sessione(
        ["2,5 km in metri?", "esci"],
        [chiamata("converti_unita", {"a": "m", "da": "km", "valore": 2.5}), AIMessage("2500 m")],
        strumenti=[strumento_finto('{"risultato": 2500}')],
        origini={"converti_unita": "mcp"},
        parametri={"converti_unita": ["valore", "da", "a"]},
    )
    assert "[converti_unita · mcp: 2.5, km, m]" in stampate



def sessione_streaming(righe, risposte=(), router=None, ambito=None, strumenti=None):
    """Sessione con `scrivi_pezzo`: righe e pezzi finiscono in un unico testo, nell'ordine di stampa."""
    modello = ModelloFinto(list(risposte))
    grafo = crea_grafo(modello, strumenti if strumenti is not None else [orologio_finto(ISTANTE)], router, ambito)
    da_leggere = list(righe)
    uscita = []

    def leggi(prompt):
        riga = da_leggere.pop(0)
        if isinstance(riga, BaseException):
            raise riga
        return riga

    esegui_sessione(
        grafo, FUSO, leggi=leggi, scrivi=lambda r: uscita.append(r + "\n"), origini=ORIGINI,
        scrivi_pezzo=uscita.append,
    )
    return "".join(uscita), modello


def test_streaming_risposta_a_pezzi():
    testo, _ = sessione_streaming(["ciao", "esci"], [AIMessage("Ciao!")])
    assert "Assistente: Ciao!\nArrivederci.\n" in testo


def test_streaming_riga_dello_strumento_prima_del_testo():
    testo, _ = sessione_streaming(
        ["che ore sono a Tokyo?", "esci"], [chiamata_orologio("Asia/Tokyo"), AIMessage("Sono le 23:04.")]
    )
    assert "[ora_corrente · mcp: Asia/Tokyo]\nAssistente: Sono le 23:04.\n" in testo


def test_streaming_rifiuto_stampato_intero():
    from assistente.ambito import Ambito
    from assistente.router import DecisioneRouter
    from tests.finti import RouterFinto

    ambito = Ambito(("ora",), ("poesie",), "Prova un altro provider.")
    router = RouterFinto([DecisioneRouter(categoria="fuori_ambito", motivo="poesia")])
    testo, modello = sessione_streaming(["poesia", "esci"], router=router, ambito=ambito)
    assert "Assistente: Prova un altro provider.\n" in testo
    assert modello.chiamate == []


def test_streaming_risposta_vuota_e_limite():
    testo, _ = sessione_streaming(["ciao", "esci"], [AIMessage("")])
    assert "Assistente: (nessuna risposta dal modello)\n" in testo
    chiamate = [chiamata_orologio("Europe/Rome", f"c{i}") for i in range(1, 5)]
    testo, _ = sessione_streaming(["che ore sono?", "esci"], chiamate)
    assert testo.count("[ora_corrente · mcp: Europe/Rome]\n") == 3
    assert "Assistente: Non sono riuscito" in testo


def test_streaming_errore_e_cronologia():
    testo, modello = sessione_streaming(["a", "b", "esci"], [RuntimeError("server giù"), AIMessage("ok")])
    assert "Errore: server giù\n" in testo and "Assistente: ok\n" in testo
    assert "a" not in [m.content for m in modello.chiamate[1]]
