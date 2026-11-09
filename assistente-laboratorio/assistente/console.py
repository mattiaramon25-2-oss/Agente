"""Codifica di ingresso e uscita quando non sono un terminale interattivo (pipe o file).

Su Windows Python legge e scrive le pipe in cp1252: il BOM UTF-8 che PowerShell antepone non
viene riconosciuto («esci» non chiude la sessione), gli accenti si guastano (anche nelle note
salvate) e un'emoji nella risposta fa crollare la sessione. Qui ingresso e uscita rediretti
passano a UTF-8; un terminale interattivo resta com'è.
"""

import sys
from typing import TextIO


def configura_flussi(ingresso: TextIO | None = None, uscita: TextIO | None = None) -> None:
    ingresso = ingresso if ingresso is not None else sys.stdin
    uscita = uscita if uscita is not None else sys.stdout
    if ingresso is not None and not ingresso.isatty() and hasattr(ingresso, "reconfigure"):
        ingresso.reconfigure(encoding="utf-8-sig", errors="replace")  # utf-8-sig toglie il BOM iniziale
    if uscita is not None and not uscita.isatty() and hasattr(uscita, "reconfigure"):
        uscita.reconfigure(encoding="utf-8", errors="replace")
