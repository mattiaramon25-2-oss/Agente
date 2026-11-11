"""Log dell'assistente: un file in logs/, righe `chiave=valore` leggibili."""

import json
import logging
from pathlib import Path
from typing import Mapping

CARTELLA_LOG = Path(__file__).resolve().parent.parent / "logs"
LOG_ASSISTENTE = CARTELLA_LOG / "assistente.log"
LOG_SERVER = CARTELLA_LOG / "server_mcp.log"
LOG_API = CARTELLA_LOG / "servizio_api.log"
LOG_BACKEND = CARTELLA_LOG / "servizio_backend.log"


def formatta(campi: Mapping[str, object]) -> str:
    """Stringhe senza a capo così come sono; gli altri valori come JSON compatto."""
    parti = []
    for chiave, valore in campi.items():
        if isinstance(valore, str):
            testo = valore.replace("\r", " ").replace("\n", " ")
        else:
            testo = json.dumps(valore, ensure_ascii=False, separators=(",", ":"))
        parti.append(f"{chiave}={testo}")
    return " ".join(parti)


def configura_registro(percorso: Path = LOG_ASSISTENTE, nome: str = "assistente") -> None:
    """Scrive i log del logger `nome` (predefinito `assistente`) in `percorso` (in coda, UTF-8); idempotente."""
    logger = logging.getLogger(nome)
    destinazione = str(Path(percorso).resolve())
    for gestore in logger.handlers:
        if isinstance(gestore, logging.FileHandler) and gestore.baseFilename == destinazione:
            return
    Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    gestore = logging.FileHandler(percorso, mode="a", encoding="utf-8")
    gestore.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(gestore)
    logger.setLevel(logging.INFO)
    logger.propagate = False
