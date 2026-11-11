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


def test_nome_del_logger_separato(tmp_path):
    percorso = tmp_path / "b.log"
    backend = logging.getLogger("servizio_backend")
    assistente = logging.getLogger("assistente")
    prima_b, prima_a = list(backend.handlers), list(assistente.handlers)
    try:
        configura_registro(percorso, nome="servizio_backend")
        logging.getLogger("servizio_backend.chat").info("riga backend")
        logging.getLogger("assistente.strumenti").info("riga assistente")
        for h in backend.handlers:
            h.flush()
        testo = percorso.read_text(encoding="utf-8")
        assert "riga backend" in testo
        assert "riga assistente" not in testo
        assert assistente.handlers == prima_a
    finally:
        for h in backend.handlers[len(prima_b):]:
            h.close()
            backend.removeHandler(h)
        backend.propagate = True
