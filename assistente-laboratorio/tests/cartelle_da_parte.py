"""Sposta da parte cartelle dell'utente (logs/, archivio/) durante una prova e le ripristina sempre.

Regole, per non perdere né nascondere dati:
- la preparazione è dentro il blocco protetto: se fallisce a metà, le rinomine già fatte si annullano;
- una riserva già presente (avanzo di una prova interrotta) blocca tutto, senza toccare nulla;
- le cartelle create durante la prova si eliminano sempre (l'originale è al sicuro o non esisteva),
  rinominandole prima, così un file bloccato non impedisce il ripristino;
- ogni riserva si ripristina per conto suo; gli errori di ripristino si riportano tutti alla fine.
"""

import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence

SUFFISSO_RISERVA = ".riserva-prova-docker"


def _elimina_creata(cartella: Path) -> None:
    if not cartella.exists():
        return
    da_eliminare = cartella.with_name(f"{cartella.name}.da-eliminare-{uuid.uuid4().hex[:8]}")
    try:
        cartella.rename(da_eliminare)
    except OSError:
        da_eliminare = cartella  # non si può rinominare: si prova comunque a eliminarla
    shutil.rmtree(da_eliminare, ignore_errors=True)


@contextmanager
def cartelle_da_parte(base: Path, nomi: Sequence[str]) -> Iterator[None]:
    spostate: dict[Path, Path] = {}
    # Si elimina solo ciò che è stato creato durante la prova: una cartella il cui originale è stato
    # spostato, o che all'inizio non esisteva. Mai un originale non ancora spostato.
    assenti_all_inizio = {nome for nome in nomi if not (base / nome).exists()}
    try:
        for nome in nomi:
            riserva = base / f"{nome}{SUFFISSO_RISERVA}"
            if riserva.exists():
                raise RuntimeError(
                    f"{riserva} esiste già (avanzo di una prova interrotta): ripristinala a mano come "
                    f"'{nome}' prima di rilanciare la prova."
                )
        for nome in nomi:
            cartella = base / nome
            if cartella.exists():
                riserva = base / f"{nome}{SUFFISSO_RISERVA}"
                cartella.rename(riserva)
                spostate[cartella] = riserva
        yield
    finally:
        for nome in nomi:
            if nome in assenti_all_inizio or (base / nome) in spostate:
                _elimina_creata(base / nome)
        errori = []
        for cartella, riserva in spostate.items():
            try:
                _elimina_creata(cartella)  # se qualcosa l'ha ricreata nel frattempo
                riserva.rename(cartella)
            except OSError as errore:
                errori.append(f"{riserva} → {cartella}: {errore}")
        if errori:
            raise RuntimeError("Ripristino incompleto, rinomina a mano: " + "; ".join(errori))
