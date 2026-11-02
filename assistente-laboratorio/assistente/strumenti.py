"""Strumenti che il modello può chiedere di eseguire: per ora solo l'orologio."""

import json
from datetime import datetime, timezone
from functools import cache
from typing import Callable
from zoneinfo import ZoneInfo, available_timezones

from langchain_core.tools import BaseTool, StructuredTool

NOME_OROLOGIO = "ora_corrente"

DESCRIZIONE_OROLOGIO = (
    "Restituisce data e ora attuali nel fuso orario indicato. "
    '`fuso`: nome IANA, per esempio "Europe/Rome" o "Asia/Tokyo".'
)

GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")


@cache
def _fusi_disponibili() -> frozenset[str]:
    return frozenset(available_timezones())


def è_fuso_valido(nome: str) -> bool:
    """Vero solo per i nomi IANA esatti (maiuscole comprese) noti a zoneinfo."""
    return isinstance(nome, str) and nome in _fusi_disponibili()


def _ora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _scarto(istante: datetime) -> str:
    minuti = int(istante.utcoffset().total_seconds() // 60)
    segno = "+" if minuti >= 0 else "-"
    ore, minuti = divmod(abs(minuti), 60)
    return f"{segno}{ore:02d}:{minuti:02d}"


def crea_strumento_orologio(adesso: Callable[[], datetime] = _ora_utc) -> BaseTool:
    """Crea lo strumento `ora_corrente`; `adesso` fornisce l'istante (iniettabile nei test)."""

    def ora_corrente(fuso: str) -> str:
        if not è_fuso_valido(fuso):
            errore = f"Fuso orario sconosciuto: '{fuso}'. Usa un nome IANA, per esempio 'Europe/Rome'."
            return json.dumps({"errore": errore}, ensure_ascii=False)
        istante = adesso().astimezone(ZoneInfo(fuso))
        risultato = {
            "fuso": fuso,
            "data_ora": istante.isoformat(timespec="seconds"),
            "scarto_utc": _scarto(istante),
            "giorno_settimana": GIORNI[istante.weekday()],
        }
        return json.dumps(risultato, ensure_ascii=False)

    return StructuredTool.from_function(
        func=ora_corrente, name=NOME_OROLOGIO, description=DESCRIZIONE_OROLOGIO
    )
