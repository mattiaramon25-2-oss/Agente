import json

import pytest

from assistente.ambito import PERCORSO_AMBITO, Ambito, carica_ambito
from assistente.errori import ErroreAvvio

RIFIUTO = (
    "Mi dispiace, questa richiesta è fuori dal mio ambito. Posso aiutarti con data e ora, conversioni, "
    "calcoli, scadenze, corsi dell'ITS, note, meteo e domande sui temi del corso."
)


def test_file_versionato_con_il_rifiuto_concordato():
    ambito = carica_ambito()
    assert PERCORSO_AMBITO.name == "ambito.json" and PERCORSO_AMBITO.parent.name == "risorse"
    assert ambito.rifiuto == RIFIUTO
    testo = " ".join(ambito.in_ambito).lower()
    for voce in ("data e ora", "conversioni", "calcoli", "scadenze", "catalogo", "note", "meteo", "python", "saluti"):
        assert voce in testo
    assert any("poesie" in v for v in ambito.fuori_ambito)


def test_file_modificabile_senza_toccare_il_codice(tmp_path):
    file = tmp_path / "ambito.json"
    file.write_text(json.dumps({"in_ambito": ["a"], "fuori_ambito": ["b"], "rifiuto": "no"}), encoding="utf-8")
    assert carica_ambito(file) == Ambito(in_ambito=("a",), fuori_ambito=("b",), rifiuto="no")


@pytest.mark.parametrize(
    "contenuto",
    ["non json", "[]", '{"in_ambito": ["a"], "fuori_ambito": ["b"]}', '{"in_ambito": [], "fuori_ambito": ["b"], "rifiuto": "x"}',
     '{"in_ambito": ["a"], "fuori_ambito": "b", "rifiuto": "x"}', '{"in_ambito": ["a"], "fuori_ambito": ["b"], "rifiuto": " "}'],
)
def test_file_malformato(tmp_path, contenuto):
    file = tmp_path / "ambito.json"
    file.write_text(contenuto, encoding="utf-8")
    with pytest.raises(ErroreAvvio, match="ambito.json"):
        carica_ambito(file)


def test_file_mancante(tmp_path):
    with pytest.raises(ErroreAvvio, match="non trovato"):
        carica_ambito(tmp_path / "ambito.json")
