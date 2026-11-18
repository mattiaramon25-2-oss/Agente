"""Il modello della configurazione di nginx: solo il testo, nessun container."""
import re

from tests.compose_prova import CARTELLA

MODELLO = (CARTELLA / "frontend" / "nginx" / "default.conf.template").read_text(encoding="utf-8")


def test_niente_host_docker_internal_scritto():
    assert "host.docker.internal" not in MODELLO


def test_backend_risolto_a_ogni_richiesta():
    assert "resolver 127.0.0.11" in MODELLO
    assert "${BACKEND_INDIRIZZO}:${BACKEND_PORTA}" in MODELLO
    assert "proxy_pass $" in MODELLO, "con una variabile nginx risolve il nome a ogni richiesta"


def test_prefisso_api_tolto():
    assert re.search(r"rewrite\s+\^/api/\(\.\*\)\$\s+/\$1\s+break;", MODELLO), "manca la rewrite che toglie /api/"
