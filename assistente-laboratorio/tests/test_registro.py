import logging

from assistente.registro import configura_registro, formatta


def test_formatta():
    assert (
        formatta({"tool": "x", "argomenti": {"valore": 2.5, "da": "°C"}, "risultato": "a\nb"})
        == 'tool=x argomenti={"valore":2.5,"da":"°C"} risultato=a b'
    )


def test_crea_la_cartella(tmp_path):
    percorso = tmp_path / "nuova" / "assistente.log"
    logger = logging.getLogger("assistente")
    prima = list(logger.handlers)
    try:
        configura_registro(percorso)
        configura_registro(percorso)  # idempotente
        logging.getLogger("assistente.strumenti").info("riga °C")
        for h in logger.handlers:
            h.flush()
        assert percorso.read_text(encoding="utf-8").count("riga °C") == 1
    finally:
        for h in logger.handlers[len(prima):]:
            h.close()
            logger.removeHandler(h)
        logger.propagate = True
