import json

import pytest

from logica.catalogo import PERCORSO_CATALOGO, carica_catalogo, cerca, dettaglio
from logica.errori import ErroreStrumento

CORSI = [{"codice": "PY-01", "titolo": "Python di base", "sede": "Udine", "durata_ore": 40},
         {"codice": "PY-02", "titolo": "Python per l'analisi dati", "sede": "Pordenone", "durata_ore": 60},
         {"codice": "DLL-01", "titolo": "Deep Learning e LLM", "sede": "Pordenone", "durata_ore": 120}]


def test_ricerca():
    assert cerca(CORSI, "  python ") == {"query": "  python ", "totale": 2, "risultati": [
        {"codice": "PY-01", "titolo": "Python di base", "sede": "Udine"},
        {"codice": "PY-02", "titolo": "Python per l'analisi dati", "sede": "Pordenone"}]}


def test_ricerca_per_sede_e_codice():
    assert [c["codice"] for c in cerca(CORSI, "PORDENONE")["risultati"]] == ["PY-02", "DLL-01"]
    assert [c["codice"] for c in cerca(CORSI, "dll")["risultati"]] == ["DLL-01"]


def test_taglio_e_totale():
    r = cerca(CORSI, "o", max_results="1")
    assert len(r["risultati"]) == 1 and r["totale"] == 3


def test_max_results_predefinito_e_limiti():
    molti = [{**CORSI[0], "codice": f"X-{i}"} for i in range(25)]
    assert len(cerca(molti, "python")["risultati"]) == 5
    assert len(cerca(molti, "python", 20)["risultati"]) == 20 and len(cerca(molti, "python", 1)["risultati"]) == 1


def test_nessun_risultato():
    assert cerca(CORSI, "astrofisica") == {"query": "astrofisica", "risultati": [], "totale": 0}


@pytest.mark.parametrize("query", ["", "   ", None, 3])
def test_query_non_valida(query):
    with pytest.raises(ErroreStrumento, match="parola non vuota"):
        cerca(CORSI, query)


@pytest.mark.parametrize("n", [0, 21, True, 2.5, "tre"])
def test_max_results_non_valido(n):
    with pytest.raises(ErroreStrumento, match="tra 1 e 20"):
        cerca(CORSI, "python", n)


def test_dettaglio():
    assert dettaglio(CORSI, "DLL-01") == CORSI[2]


@pytest.mark.parametrize("code", ["dll-01", "XX-99", "", None])
def test_codice_inesistente(code):
    with pytest.raises(ErroreStrumento, match="Usa prima search_catalog"):
        dettaglio(CORSI, code)


def test_file_reale():
    corsi = carica_catalogo()
    assert PERCORSO_CATALOGO.name == "catalogo_corsi.json"
    assert 10 <= len(corsi) <= 15 and len({c["codice"] for c in corsi}) == len(corsi)
    assert dettaglio(corsi, "DLL-01")["durata_ore"] == 120 and cerca(corsi, "python")["totale"] >= 2
    assert cerca(corsi, "astrofisica")["totale"] == 0


@pytest.mark.parametrize("contenuto", [
    [{"codice": "A", "titolo": "t", "sede": "s", "durata_ore": 1}, {"codice": "A", "titolo": "u", "sede": "s", "durata_ore": 2}],
    [{"codice": "A", "titolo": "t", "sede": "s"}],
    [{"codice": "A", "titolo": "t", "sede": "s", "durata_ore": "molte"}],
    {"codice": "A"},
    [],
    [{"codice": "A", "titolo": "t", "sede": "s", "durata_ore": 0}],
    [{"codice": "A", "titolo": "t", "sede": "s", "durata_ore": -5}],
    [{"codice": "", "titolo": "t", "sede": "s", "durata_ore": 1}],
    [{"codice": " A-01 ", "titolo": "t", "sede": "s", "durata_ore": 1}],
])
def test_catalogo_malformato(tmp_path, contenuto):
    percorso = tmp_path / "catalogo.json"
    percorso.write_text(json.dumps(contenuto), encoding="utf-8")
    with pytest.raises(ValueError, match="Catalogo non valido") as errore:
        carica_catalogo(percorso)
    assert "catalogo.json" in str(errore.value)


@pytest.mark.parametrize("query, codici", [
    ("Python base", ["PY-01"]), ("Deep Learning LLM", ["DLL-01"]), ("python pordenone", ["PY-02"]),
    ("Python per l’analisi", ["PY-02"]), ("Deep Learning e LLM", ["DLL-01"]),
])
def test_ricerca_con_piu_parole(query, codici):
    """Ogni parola deve comparire in codice, titolo o sede: resta una ricerca esatta, non RAG."""
    assert [c["codice"] for c in cerca(CORSI, query)["risultati"]] == codici


def test_parole_non_tutte_presenti():
    assert cerca(CORSI, "Python astrofisica")["totale"] == 0


def test_max_results_nullo_vale_il_predefinito():
    molti = [{**CORSI[0], "codice": f"X-{i}"} for i in range(25)]
    assert len(cerca(molti, "python", None)["risultati"]) == 5
