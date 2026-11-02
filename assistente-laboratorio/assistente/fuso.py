"""Rilevamento del fuso orario dell'utente, una volta sola all'avvio."""

from dataclasses import dataclass
from typing import Callable, Mapping

from tzlocal import get_localzone_name
from tzlocal.windows_tz import win_tz

from assistente.strumenti import è_fuso_valido

AVVISO_RIPIEGO = (
    "ATTENZIONE: fuso orario non rilevato, uso UTC. "
    "Con Docker avvia con avvia.ps1, oppure imposta FUSO_ORARIO nel file .env (per esempio Europe/Rome)."
)


@dataclass(frozen=True)
class RisultatoFuso:
    fuso: str
    origine: str  # "host Windows", "computer locale", "FUSO_ORARIO" oppure "ripiego"
    avviso: str | None = None


def _fuso_locale_sicuro(fuso_locale: Callable[[], str | None]) -> str | None:
    try:
        return fuso_locale()
    except Exception:
        return None


def rileva_fuso(
    env: Mapping[str, str],
    fuso_locale: Callable[[], str | None] = get_localzone_name,
) -> RisultatoFuso:
    # 1. Fuso di Windows passato da avvia.ps1, convertito in nome IANA.
    nome_windows = (env.get("FUSO_HOST_WINDOWS") or "").strip()
    candidato = win_tz.get(nome_windows)
    if candidato and è_fuso_valido(candidato):
        return RisultatoFuso(candidato, "host Windows")

    # 2. Fuso del computer, solo fuori da Docker (nel container sarebbe quello del container).
    if (env.get("ASSISTENTE_IN_DOCKER") or "").strip() != "1":
        candidato = _fuso_locale_sicuro(fuso_locale)
        if candidato and è_fuso_valido(candidato):
            return RisultatoFuso(candidato, "computer locale")

    # 3. Riserva manuale.
    candidato = (env.get("FUSO_ORARIO") or "").strip()
    if è_fuso_valido(candidato):
        return RisultatoFuso(candidato, "FUSO_ORARIO")

    # 4. Ultima risorsa, con avviso visibile.
    return RisultatoFuso("UTC", "ripiego", AVVISO_RIPIEGO)
