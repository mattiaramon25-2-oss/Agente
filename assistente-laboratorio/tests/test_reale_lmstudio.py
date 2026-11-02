"""Prova reale: il modello di LM Studio chiede davvero lo strumento orologio.

Si attiva solo con: python -m pytest --lmstudio -m lmstudio -v -s
"""

import json
import os
from datetime import datetime, timedelta

import pytest
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, ToolMessage

from assistente.configurazione import carica_configurazione
from assistente.fuso import rileva_fuso
from assistente.grafo import crea_grafo, esegui_turno
from assistente.modello import crea_modello, verifica_server
from assistente.strumenti import NOME_OROLOGIO, crea_strumento_orologio

pytestmark = pytest.mark.lmstudio

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
    load_dotenv(override=False)
    config = carica_configurazione(os.environ)
    verifica_server(config.base_url, config.modello)
    fuso_utente = rileva_fuso(os.environ).fuso
    strumenti = [crea_strumento_orologio()]
    grafo = crea_grafo(crea_modello(config, strumenti), strumenti)
    print(f"\nmodello: {config.modello} · fuso utente: {fuso_utente}")
    return grafo, fuso_utente


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
    grafo, fuso_utente = ambiente
    atteso = fuso_atteso or fuso_utente

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
    if chiede_ora:
        istante = datetime.fromisoformat(validi[-1]["data_ora"])
        assert any(forma in risposta.text for forma in forme_dell_ora(istante)), (
            f"l'ora della risposta non corrisponde a {istante:%H:%M}"
        )
