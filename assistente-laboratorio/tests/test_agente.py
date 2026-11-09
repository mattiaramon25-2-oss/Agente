from assistente.agente import crea_agente
from assistente.ambito import carica_ambito
from assistente.configurazione import Configurazione
from tests.finti import strumento_finto

CONFIG = Configurazione("http://127.0.0.1:9/v1", "google/gemma-4-e2b", 8765)


def test_agente_con_router_e_rifiuto():
    grafo = crea_agente(CONFIG, [strumento_finto("{}", nome="ora_corrente")], carica_ambito())
    assert {"router", "rifiuto", "modello", "strumenti", "limite"} <= set(grafo.get_graph().nodes)
