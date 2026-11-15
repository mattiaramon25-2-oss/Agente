"""Lega i processi avviati alla vita di questo programma: se muore, Windows chiude anche loro.

Chi chiude la finestra con la X non passa da «esci»: il programma viene ucciso e non può spegnere
con ordine l'agente e il back-end. Un Job Object con «chiudi tutto alla chiusura» risolve: questo
processo ci entra, i processi che avvia lo ereditano, e quando l'ultima maniglia del Job si chiude
(cioè quando questo processo finisce, in qualunque modo) Windows termina tutti quelli rimasti.
Dopo un «esci» non resta nessuno da terminare: i servizi sono già stati spenti con ordine.
"""

import ctypes
import sys
from ctypes import wintypes

LIMITE_CHIUDI_TUTTO_ALLA_CHIUSURA = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
INFORMAZIONI_ESTESE = 9  # JobObjectExtendedLimitInformation


class _Contatori(ctypes.Structure):  # IO_COUNTERS
    _fields_ = [(nome, ctypes.c_ulonglong) for nome in ("letture", "scritture", "altre", "letti", "scritti", "altri")]


class _LimitiDiBase(ctypes.Structure):  # JOBOBJECT_BASIC_LIMIT_INFORMATION
    _fields_ = [
        ("tempo_per_processo", ctypes.c_longlong),
        ("tempo_per_job", ctypes.c_longlong),
        ("limiti", wintypes.DWORD),
        ("memoria_minima", ctypes.c_size_t),
        ("memoria_massima", ctypes.c_size_t),
        ("processi_attivi", wintypes.DWORD),
        ("affinita", ctypes.c_size_t),
        ("priorita", wintypes.DWORD),
        ("pianificazione", wintypes.DWORD),
    ]


class _LimitiEstesi(ctypes.Structure):  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    _fields_ = [
        ("di_base", _LimitiDiBase),
        ("contatori", _Contatori),
        ("memoria_per_processo", ctypes.c_size_t),
        ("memoria_per_job", ctypes.c_size_t),
        ("picco_per_processo", ctypes.c_size_t),
        ("picco_per_job", ctypes.c_size_t),
    ]


def lega_i_figli() -> object | None:
    """Mette questo processo in un Job Object che termina tutti i suoi processi quando si chiude.

    Restituisce la maniglia del Job, da non chiudere (resta aperta finché il processo vive), oppure
    None se non siamo su Windows o se Windows rifiuta: in quel caso tutto funziona come prima,
    solo senza questa garanzia.
    """
    if sys.platform != "win32":
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    limiti = _LimitiEstesi()
    limiti.di_base.limiti = LIMITE_CHIUDI_TUTTO_ALLA_CHIUSURA
    riuscito = kernel32.SetInformationJobObject(
        job, INFORMAZIONI_ESTESE, ctypes.byref(limiti), ctypes.sizeof(limiti)
    ) and kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess())
    if not riuscito:
        kernel32.CloseHandle(job)
        return None
    return job
