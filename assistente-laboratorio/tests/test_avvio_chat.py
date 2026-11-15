"""Avvio della chat con un doppio clic: i passi di avvio_chat, senza Docker e senza LM Studio."""

import sys

import pytest

from assistente.configurazione import ErroreConfigurazione
from assistente.errori import ErroreAvvio
from assistente.modello import ErroreServer
from avvio_chat import passi
from avvio_chat.passi import Esito, Impostazioni

ENV = {
    "LMSTUDIO_BASE_URL": "http://localhost:1234/v1",
    "LMSTUDIO_MODEL": "finto",
    "MCP_PORTA": "8765",
    "VARIANTE_CALCOLATRICE": "mcp",
    "VARIANTE_SCADENZE": "mcp",
    "AGENTE_PORTA": "8767",
    "BACKEND_PORTA": "8768",
    "POSTGRES_USER": "utente",
    "POSTGRES_PASSWORD": "segreta",
    "POSTGRES_DB": "dati",
}

DOCKER_INFO = ("docker", "info")
DOCKER_AVVIO = ("docker", "desktop", "start")
COMPOSE = ("docker", "compose")


class EseguiFinto:
    """Risponde ai comandi da un copione: per ogni inizio di comando una lista di esiti (l'ultimo si ripete)."""

    def __init__(self, copione):
        self.copione = {inizio: list(risposte) for inizio, risposte in copione.items()}
        self.comandi: list[list[str]] = []
        self.limiti: list[float] = []

    def __call__(self, comando, limite):
        self.comandi.append(list(comando))
        self.limiti.append(limite)
        for inizio, risposte in self.copione.items():
            if tuple(comando[: len(inizio)]) == inizio:
                risposta = risposte.pop(0) if len(risposte) > 1 else risposte[0]
                if isinstance(risposta, BaseException):
                    raise risposta
                return risposta
        raise AssertionError(f"comando non previsto dal copione: {comando}")

    def chiamati(self, inizio) -> int:
        return sum(1 for comando in self.comandi if tuple(comando[: len(inizio)]) == inizio)


class Tempo:
    """Orologio finto: `pausa` fa avanzare il tempo invece di aspettare."""

    def __init__(self):
        self.adesso = 0.0

    def orologio(self) -> float:
        return self.adesso

    def pausa(self, secondi: float) -> None:
        self.adesso += secondi


class Righe:
    """Raccoglie ciò che il programma scrive nella finestra."""

    def __init__(self):
        self.righe: list[str] = []

    def __call__(self, testo: str) -> None:
        self.righe.append(testo)

    @property
    def testo(self) -> str:
        return "\n".join(self.righe)


def in_sequenza(valori):
    """Una funzione che restituisce i valori uno alla volta; l'ultimo si ripete."""
    coda = list(valori)
    return lambda *argomenti, **opzioni: coda.pop(0) if len(coda) > 1 else coda[0]


def impostazioni(**cambi) -> Impostazioni:
    valori = dict(
        base_url="http://localhost:1234/v1", modello="finto", porta_mcp=8765, porta_agente=8767, porta_backend=8768, porta_frontend=8780
    )
    return Impostazioni(**{**valori, **cambi})


# --- Impostazioni ---


def test_impostazioni_dal_env():
    imp = passi.carica_impostazioni(ENV)
    assert (imp.porta_mcp, imp.porta_agente, imp.porta_backend, imp.porta_frontend) == (8765, 8767, 8768, 8780)
    assert imp.base_url == "http://localhost:1234/v1" and imp.modello == "finto"
    assert imp.url_agente == "http://127.0.0.1:8767"
    assert imp.url_backend == "http://127.0.0.1:8768"
    assert imp.url_chat == "http://127.0.0.1:8780"
    assert passi.carica_impostazioni({**ENV, "FRONTEND_PORTA": "8790"}).url_chat == "http://127.0.0.1:8790"


def test_impostazioni_senza_password_del_database():
    with pytest.raises(ErroreConfigurazione) as errore:
        passi.carica_impostazioni({**ENV, "POSTGRES_PASSWORD": ""})
    assert "POSTGRES_PASSWORD" in str(errore.value)


def test_frontend_porta_non_valida():
    with pytest.raises(ErroreConfigurazione) as errore:
        passi.carica_impostazioni({**ENV, "FRONTEND_PORTA": "ottanta"})
    assert "FRONTEND_PORTA" in str(errore.value)


# --- Docker ---


def test_docker_acceso_non_avvia_niente():
    esegui = EseguiFinto({DOCKER_INFO: [Esito(0, "29.1.0")]})
    righe = Righe()
    passi.assicura_docker(esegui, righe)
    assert esegui.chiamati(DOCKER_AVVIO) == 0
    assert "[1/5] Docker: acceso" in righe.testo


def test_docker_spento_lo_avvia_e_aspetta():
    tempo = Tempo()
    esegui = EseguiFinto({DOCKER_INFO: [Esito(1, "errore"), Esito(1, "errore"), Esito(0, "29.1.0")], DOCKER_AVVIO: [Esito(0, "")]})
    righe = Righe()
    passi.assicura_docker(esegui, righe, pausa=tempo.pausa, orologio=tempo.orologio)
    assert esegui.chiamati(DOCKER_AVVIO) == 1
    assert ["docker", "desktop", "start"] in esegui.comandi
    assert esegui.chiamati(DOCKER_INFO) == 3
    assert "lo accendo" in righe.testo and "[1/5] Docker: acceso" in righe.testo


def test_docker_che_non_parte():
    tempo = Tempo()
    esegui = EseguiFinto({DOCKER_INFO: [Esito(1, "errore")], DOCKER_AVVIO: [Esito(0, "")]})
    with pytest.raises(ErroreAvvio) as errore:
        passi.assicura_docker(esegui, Righe(), pausa=tempo.pausa, orologio=tempo.orologio)
    assert "Docker Desktop non risponde" in str(errore.value) and "180" in str(errore.value)
    assert tempo.adesso >= passi.ATTESA_DOCKER


def test_docker_non_installato():
    esegui = EseguiFinto({DOCKER_INFO: [FileNotFoundError("docker")]})
    with pytest.raises(ErroreAvvio) as errore:
        passi.assicura_docker(esegui, Righe())
    assert "Docker non è installato" in str(errore.value)


# --- LM Studio ---


def test_lmstudio_acceso_non_chiama_lms():
    esegui = EseguiFinto({})
    verificati = []
    righe = Righe()
    passi.assicura_lmstudio(
        impostazioni(), esegui, righe, risponde=lambda url: True, verifica=lambda url, modello: verificati.append((url, modello)), lms=lambda: "lms"
    )
    assert esegui.comandi == []
    assert verificati == [("http://localhost:1234/v1", "finto")]
    assert "[2/5] LM Studio: risponde, modello finto presente" in righe.testo


def test_lmstudio_spento_avvia_il_server():
    tempo = Tempo()
    esegui = EseguiFinto({("lms-finto",): [Esito(0, "")]})
    verificati = []
    righe = Righe()
    passi.assicura_lmstudio(
        impostazioni(),
        esegui,
        righe,
        risponde=in_sequenza([False, False, True]),
        verifica=lambda url, modello: verificati.append(modello),
        lms=lambda: "lms-finto",
        pausa=tempo.pausa,
        orologio=tempo.orologio,
    )
    assert esegui.comandi == [["lms-finto", "server", "start"]]
    assert verificati == ["finto"]
    assert "lo accendo" in righe.testo and "[2/5] LM Studio: risponde" in righe.testo


def test_lmstudio_spento_senza_lms():
    esegui = EseguiFinto({})
    with pytest.raises(ErroreAvvio) as errore:
        passi.assicura_lmstudio(impostazioni(), esegui, Righe(), risponde=lambda url: False, verifica=lambda *a: None, lms=lambda: None)
    assert "apri LM Studio" in str(errore.value) and "http://localhost:1234/v1" in str(errore.value)
    assert esegui.comandi == []


def test_lmstudio_che_non_parte():
    tempo = Tempo()
    esegui = EseguiFinto({("lms-finto",): [Esito(0, "")]})
    with pytest.raises(ErroreAvvio) as errore:
        passi.assicura_lmstudio(
            impostazioni(), esegui, Righe(), risponde=lambda url: False, verifica=lambda *a: None, lms=lambda: "lms-finto",
            pausa=tempo.pausa, orologio=tempo.orologio,
        )
    assert "LM Studio non risponde" in str(errore.value) and "60" in str(errore.value)


def test_modello_mancante_non_tocca_lms():
    esegui = EseguiFinto({})

    def verifica(url, modello):
        raise ErroreServer("Il modello 'finto' non è disponibile su LM Studio.")

    with pytest.raises(ErroreServer) as errore:
        passi.assicura_lmstudio(impostazioni(), esegui, Righe(), risponde=lambda url: True, verifica=verifica, lms=lambda: "lms-finto")
    assert "non è disponibile" in str(errore.value)
    assert esegui.comandi == []


# --- Container ---


def test_container_usa_wait_e_attesa_lunga():
    esegui = EseguiFinto({COMPOSE: [Esito(0, "")]})
    righe = Righe()
    passi.assicura_container(esegui, righe)
    assert esegui.comandi == [["docker", "compose", "up", "-d", "--wait", "database", "frontend"]]
    assert esegui.limiti == [600.0]
    assert "la prima volta" in righe.testo and "[3/5] Database e pagina: accesi" in righe.testo


def test_container_che_falliscono():
    esegui = EseguiFinto({COMPOSE: [Esito(1, "riga inutile\nBind for 127.0.0.1:8780 failed: port is already allocated\n")]})
    with pytest.raises(ErroreAvvio) as errore:
        passi.assicura_container(esegui, Righe())
    assert "docker compose up" in str(errore.value) and "port is already allocated" in str(errore.value)


def test_esegui_comando_vero():
    assert passi.esegui_comando([sys.executable, "-c", "print('ciao')"], 20.0) == Esito(0, "ciao\n")
    lento = passi.esegui_comando([sys.executable, "-c", "import time; time.sleep(5)"], 0.2)
    assert lento.codice == 124 and "0.2 secondi" in lento.uscita
    with pytest.raises(FileNotFoundError):
        passi.esegui_comando(["programma-che-non-esiste-di-sicuro"], 5.0)
