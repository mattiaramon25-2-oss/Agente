import urllib.error

import pytest

from assistente.configurazione import Configurazione
from assistente.modello import ErroreServer, crea_modello, verifica_server
from assistente.strumenti import crea_strumento_orologio

URL = "http://localhost:1234/v1"
ELENCO = {"data": [{"id": "google/gemma-4-e2b"}, {"id": "qwen/qwen3.5-9b"}]}


class LettoreFinto:
    def __init__(self, risposta):
        self.risposta = risposta
        self.url_letti = []

    def __call__(self, url, timeout):
        self.url_letti.append(url)
        if isinstance(self.risposta, BaseException):
            raise self.risposta
        return self.risposta


def test_modello_presente():
    leggi = LettoreFinto(ELENCO)
    verifica_server(URL, "google/gemma-4-e2b", leggi_json=leggi)
    assert leggi.url_letti == ["http://localhost:1234/v1/models"]


def test_barra_finale_nell_indirizzo():
    leggi = LettoreFinto(ELENCO)
    verifica_server(URL + "/", "google/gemma-4-e2b", leggi_json=leggi)
    assert leggi.url_letti == ["http://localhost:1234/v1/models"]


def test_modello_assente():
    with pytest.raises(ErroreServer) as errore:
        verifica_server(URL, "inventato", leggi_json=LettoreFinto({"data": [{"id": "qwen/qwen3.5-9b"}]}))
    assert "inventato" in str(errore.value)
    assert "qwen/qwen3.5-9b" in str(errore.value)


@pytest.mark.parametrize(
    "eccezione",
    [urllib.error.URLError("connessione rifiutata"), TimeoutError("scaduto"), OSError("rete")],
)
def test_server_irraggiungibile(eccezione):
    with pytest.raises(ErroreServer) as errore:
        verifica_server(URL, "google/gemma-4-e2b", leggi_json=LettoreFinto(eccezione))
    assert "http://localhost:1234/v1/models" in str(errore.value)
    assert "LM Studio" in str(errore.value)


@pytest.mark.parametrize("risposta", [{}, {"data": "x"}, [], {"data": [{"nome": "x"}]}])
def test_risposta_malformata(risposta):
    with pytest.raises(ErroreServer):
        verifica_server(URL, "google/gemma-4-e2b", leggi_json=LettoreFinto(risposta))


def test_risposta_non_json():
    with pytest.raises(ErroreServer):
        verifica_server(URL, "google/gemma-4-e2b", leggi_json=LettoreFinto(ValueError("non è JSON")))


def test_crea_modello():
    config = Configurazione(URL, "google/gemma-4-e2b")
    modello = crea_modello(config, [crea_strumento_orologio()])
    assert hasattr(modello, "invoke")
    assert modello.bound.model_name == "google/gemma-4-e2b"
    assert modello.bound.openai_api_base == URL
    nomi = [s["function"]["name"] for s in modello.kwargs["tools"]]
    assert nomi == ["ora_corrente"]


@pytest.mark.parametrize("indirizzo", ["http://localhost:1234v1", "http//localhost:1234/v1", "localhost:1234/v1"])
def test_indirizzo_non_valido(indirizzo):
    leggi = LettoreFinto(ELENCO)
    with pytest.raises(ErroreServer) as errore:
        verifica_server(indirizzo, "google/gemma-4-e2b", leggi_json=leggi)
    assert "LMSTUDIO_BASE_URL" in str(errore.value)
    assert leggi.url_letti == []


def test_errore_del_protocollo_http():
    import http.client

    with pytest.raises(ErroreServer) as errore:
        verifica_server(URL, "google/gemma-4-e2b", leggi_json=LettoreFinto(http.client.InvalidURL("x")))
    assert "LM Studio" in str(errore.value)
