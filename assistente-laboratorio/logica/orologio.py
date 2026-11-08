"""Logica pura dell'orologio: data e ora attuali in un fuso IANA esplicito."""

from datetime import datetime, timezone
from functools import cache
from zoneinfo import ZoneInfo, available_timezones

from logica.errori import ErroreStrumento

GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")


@cache
def _fusi_disponibili() -> frozenset[str]:
    return frozenset(available_timezones())


def è_fuso_valido(nome: object) -> bool:
    """Vero solo per i nomi IANA esatti (maiuscole comprese) noti a zoneinfo."""
    return isinstance(nome, str) and nome in _fusi_disponibili()


def ora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _scarto(istante: datetime) -> str:
    minuti = int(istante.utcoffset().total_seconds() // 60)
    segno = "+" if minuti >= 0 else "-"
    ore, minuti = divmod(abs(minuti), 60)
    return f"{segno}{ore:02d}:{minuti:02d}"


def ora_corrente(fuso: object, adesso: datetime) -> dict:
    """Data e ora di `adesso` nel fuso indicato; solleva ErroreStrumento se il fuso non esiste."""
    if not è_fuso_valido(fuso):
        raise ErroreStrumento(f"Fuso orario sconosciuto: '{fuso}'. Usa un nome IANA, per esempio 'Europe/Rome'.")
    istante = adesso.astimezone(ZoneInfo(fuso))
    return {
        "fuso": fuso,
        "data_ora": istante.isoformat(timespec="seconds"),
        "scarto_utc": _scarto(istante),
        "giorno_settimana": GIORNI[istante.weekday()],
    }
