import pytest


def pytest_addoption(parser):
    parser.addoption("--lmstudio", action="store_true", help="esegue le prove reali con LM Studio")
    parser.addoption("--docker", action="store_true", help="esegue le prove reali con Docker")


def pytest_collection_modifyitems(config, items):
    for marcatore in ("lmstudio", "docker"):
        if config.getoption(f"--{marcatore}"):
            continue
        salta = pytest.mark.skip(reason=f"prova reale: usare --{marcatore}")
        for item in items:
            if marcatore in item.keywords:
                item.add_marker(salta)


@pytest.fixture
def porta():
    """Una porta libera su 127.0.0.1, scelta dal sistema operativo."""
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def popen_registrati(monkeypatch):
    """Registra ogni processo avviato da assistente.avvio_server, per controllare che venga spento."""
    import subprocess

    from assistente import avvio_server

    creati = []
    originale = subprocess.Popen

    def registra(*argomenti, **opzioni):
        processo = originale(*argomenti, **opzioni)
        creati.append(processo)
        return processo

    monkeypatch.setattr(avvio_server.subprocess, "Popen", registra)
    return creati
