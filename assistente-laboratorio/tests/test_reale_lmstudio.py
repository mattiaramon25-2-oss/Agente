"""Prova reale: il modello di LM Studio chiede davvero lo strumento orologio.

Si attiva solo con: python -m pytest --lmstudio -m lmstudio -v -s
"""

import json
import re
from datetime import datetime, timedelta

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from assistente.grafo import esegui_turno
from tests.reale import ambiente_reale, posizione_log, righe_del_log

pytestmark = pytest.mark.lmstudio

NOME_OROLOGIO = "ora_corrente"  # pubblicato dal server MCP

# (domanda, fuso atteso nella chiamata — None vuol dire "il fuso dell'utente", la domanda chiede l'ora?)
CASI = [
    ("Che ore sono?", None, True),
    ("Che giorno è oggi?", None, False),
    ("Che ore sono a Tokyo?", "Asia/Tokyo", True),
    ("Che ora è adesso a New York?", "America/New_York", True),
    ("Dimmi l'ora attuale a Londra.", "Europe/London", True),
]


@pytest.fixture(scope="module")
def ambiente():
    with ambiente_reale() as (grafo, fuso_utente, strumenti):
        yield grafo, fuso_utente, strumenti


def forme_dell_ora(istante: datetime) -> set[str]:
    """Modi accettabili di scrivere l'ora: 09:04, 9:04, 09.04, 9.04 (anche per il minuto dopo)."""
    forme = set()
    for t in (istante, istante + timedelta(minutes=1)):
        for ore in (f"{t.hour:02d}", str(t.hour)):
            for separatore in (":", "."):
                forme.add(f"{ore}{separatore}{t.minute:02d}")
    return forme


@pytest.mark.parametrize("domanda, fuso_atteso, chiede_ora", CASI, ids=[c[0] for c in CASI])
def test_il_modello_usa_l_orologio(ambiente, domanda, fuso_atteso, chiede_ora):
    grafo, fuso_utente, _ = ambiente
    atteso = fuso_atteso or fuso_utente
    inizio_log = posizione_log()

    cronologia = esegui_turno(grafo, [], fuso_utente, domanda)  # sessione nuova a ogni caso

    chiamate = [c for m in cronologia if isinstance(m, AIMessage) for c in m.tool_calls]
    risultati = [
        json.loads(m.content)
        for m in cronologia
        if isinstance(m, ToolMessage) and m.name == NOME_OROLOGIO
    ]
    risposta = cronologia[-1]
    print(f"\n  domanda:   {domanda}")
    print(f"  chiamate:  {[(c['name'], c['args']) for c in chiamate]}")
    print(f"  risultati: {risultati}")
    print(f"  risposta:  {risposta.text if isinstance(risposta, AIMessage) else risposta!r}")

    assert chiamate, "il modello non ha chiesto lo strumento"
    assert chiamate[0]["name"] == NOME_OROLOGIO
    assert chiamate[0]["args"].get("fuso") == atteso
    validi = [r for r in risultati if "errore" not in r]
    assert validi, "nessun risultato valido dello strumento"
    assert isinstance(risposta, AIMessage) and risposta.text.strip()
    istante = datetime.fromisoformat(validi[-1]["data_ora"])
    if chiede_ora:
        assert any(forma in risposta.text for forma in forme_dell_ora(istante)), (
            f"l'ora della risposta non corrisponde a {istante:%H:%M}"
        )
    else:  # «Che giorno è oggi?»: il giorno della settimana o il giorno del mese restituiti dallo strumento
        giorno_settimana = validi[-1]["giorno_settimana"]
        giorno_del_mese = re.search(rf"(?<!\d){istante.day}(?!\d)", risposta.text)
        assert giorno_settimana in risposta.text.casefold() or giorno_del_mese, (
            f"la risposta non contiene né «{giorno_settimana}» né il giorno {istante.day}"
        )
    assert f"origine=mcp tool={NOME_OROLOGIO}" in righe_del_log(inizio_log)


def test_errore_controllato_orologio(ambiente):
    """Slide 23: invocazione diretta, senza modello, con un fuso che non esiste."""
    _, _, strumenti = ambiente
    orologio = next(s for s in strumenti if s.name == NOME_OROLOGIO)
    errore = json.loads(orologio.invoke({"fuso": "Mars/Olympus"}))
    print(f"\n  errore controllato: {errore}")
    assert errore["tipo"] == "strumento" and "Fuso orario sconosciuto" in errore["errore"] and "data_ora" not in errore
