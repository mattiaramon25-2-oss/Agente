"""La chiusura della finestra con la X: i container accesi dal launcher vanno fermati anche così.

Non importa avvio_chat.passi (che importa questo modulo): niente import circolari.
"""

import subprocess
import sys
from pathlib import Path

CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent

# Gli eventi che Windows manda alla console: la X, la disconnessione dell'utente, l'arresto del sistema.
CTRL_CLOSE_EVENT = 2
CTRL_LOGOFF_EVENT = 5
CTRL_SHUTDOWN_EVENT = 6
EVENTI_DI_CHIUSURA = (CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT)

# Il gestore registrato. Il riferimento resta qui: senza, il garbage collector lo toglie
# e Windows chiamerebbe una funzione che non c'è più.
_gestore = None


def installa_chiusura_console(comando: list[str]) -> None:
    """Alla chiusura della console avvia `comando` in un processo staccato dalla finestra.

    `comando` è lo spegnimento, per esempio `docker compose stop backend agente`. Windows concede pochi
    secondi a chi riceve l'evento di chiusura: il gestore non aspetta la fine del comando, lo avvia
    soltanto, fuori dalla console che si chiude e in un gruppo suo, così finisce anche dopo che la
    finestra è sparita.
    Agli altri eventi risponde di no: Ctrl+C resta un KeyboardInterrupt. Chi esce in modo normale non
    passa di qui. Fuori da Windows non fa nulla.
    """
    global _gestore
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    comando = list(comando)

    def alla_chiusura(evento: int) -> bool:
        # Gira in un thread creato da Windows: il minimo indispensabile.
        if evento not in EVENTI_DI_CHIUSURA:
            return False
        try:
            # CREATE_NO_WINDOW e non DETACHED_PROCESS: il comando riceve una console sua, senza finestra, e
            # la passa ai figli. Senza nessuna console, il figlio di `docker` (il plugin `compose`) se ne
            # farebbe aprire una nuova, e dopo la X comparirebbe un'altra finestra.
            subprocess.Popen(
                comando,
                cwd=CARTELLA_PROGETTO,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        except Exception:
            # Un'eccezione non deve uscire da una callback di ctypes: la finestra si sta chiudendo
            # e non c'è più nessuno a cui dirlo.
            pass
        return True

    rimuovi_chiusura_console()
    gestore = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)(alla_chiusura)
    if _registra(gestore, True):
        _gestore = gestore


def rimuovi_chiusura_console() -> None:
    """Toglie il gestore installato, se c'è."""
    global _gestore
    if _gestore is not None:
        _registra(_gestore, False)
        _gestore = None


def _registra(gestore, aggiungi: bool) -> bool:
    """Aggiunge il gestore agli eventi della console, o lo toglie."""
    import ctypes

    return bool(ctypes.windll.kernel32.SetConsoleCtrlHandler(gestore, aggiungi))
