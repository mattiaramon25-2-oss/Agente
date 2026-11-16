"""La chiusura della finestra con la X: i container accesi dal launcher vanno fermati anche così.

Non importa avvio_chat.passi (che importa questo modulo): niente import circolari.
"""


def installa_chiusura_console(comando: list[str]) -> None:
    """Segnaposto: non fa ancora nulla.

    Il Task 5 lo riempie: alla chiusura della console avvierà `comando` (per esempio
    `docker compose stop backend agente`) in un processo staccato dalla finestra.
    """
