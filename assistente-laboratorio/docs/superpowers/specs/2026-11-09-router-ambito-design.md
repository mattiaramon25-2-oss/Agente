# Lezione 6, step 1 — Router: conversazione o fuori ambito

Data: 2026-11-09 · Branch: `dev-router` (da `dev-lezione_6`)

## Obiettivo

Le domande fuori ambito ricevono una risposta di rifiuto senza raggiungere l'agente (il nodo `modello`).

## Requisiti (slide 4)

1. L'ambito è descritto in configurazione, non nel codice: `risorse/ambito.json`, versionato.
2. Un nodo `router`, prima dell'agente, usa lo stesso modello di LM Studio con un prompt di sistema suo e un output strutturato: `categoria` (`conversazione` o `fuori_ambito`) e `motivo`.
3. Arco condizionale: `conversazione` → `modello`; `fuori_ambito` → `rifiuto` → `END`.
4. Il router non valuta gli strumenti: il modello non ha strumenti collegati; quali usare lo decide l'agente come oggi.

## Grafo

```
START -> router -> (instrada_dopo_router) -> modello -> (instrada_dopo_modello) -> strumenti -> modello
                                                                                -> limite    -> END
                                                                                -> END
                                          -> rifiuto -> END
```

I nodi esistenti (`modello`, `strumenti`, `limite`) mantengono nomi e comportamento. Se `crea_grafo` riceve un router nullo il grafo resta quello della lezione 5 (usato dai test esistenti).

## `risorse/ambito.json`

```json
{
  "in_ambito": ["..."],
  "fuori_ambito": ["..."],
  "rifiuto": "Mi dispiace, questa richiesta è fuori dal mio ambito. ..."
}
```

- In ambito: data e ora, conversioni di unità, calcoli, scadenze, catalogo dei corsi ITS, note personali, meteo; temi del corso (deep learning, LLM, chatbot, agenti, Python); conversazione normale (saluti, ringraziamenti, domande su che cosa sa fare l'assistente).
- Fuori ambito: tutto il resto, per esempio poesie e testi creativi, cultura generale, sport, ricette, consigli medici, legali o finanziari.
- Il file si legge all'avvio (`assistente/ambito.py`); se manca o è malformato l'avvio fallisce con un messaggio chiaro (`ErroreAvvio`).

## Router

- Prompt di sistema costruito dal file (elenchi in ambito / fuori ambito) più la regola: i messaggi brevi che continuano un discorso («e a Roma?», «sì, eliminala», «la 2») contano come conversazione.
- Vede la nuova domanda e gli ultimi messaggi testuali della cronologia (al massimo 6, solo utente e assistente, senza messaggi di strumento).
- Modello: `ChatOpenAI` con la stessa configurazione, senza strumenti, `with_structured_output(DecisioneRouter, method="json_schema")`.
- Se l'output non è valido (eccezione di parsing, risposta HTTP di errore, valore inatteso) la domanda passa all'agente e il log registra `esito=errore`: un router difettoso non blocca l'utente.
- Gli errori di collegamento con LM Studio (`openai.APIConnectionError`, compreso il timeout) si propagano come oggi: il terminale stampa `Errore: ...` e la cronologia non cambia.

## Rifiuto

Nodo `rifiuto`: aggiunge un `AIMessage` con il testo fisso del file. Il motivo del router va solo nel log. Domanda e rifiuto restano nella cronologia.

## Log (`logs/assistente.log`)

- `nodo=router categoria=<...> motivo=<...> esito=ok|errore [errore=<...>]`
- `nodo=modello` quando parte il nodo dell'agente (a ogni giro): la sua assenza dopo un rifiuto si vede.
- `nodo=rifiuto`.

## Test

- Automatici con router finto: percorso in ambito (router → modello, log con categoria e motivo e `nodo=modello`), percorso fuori ambito (rifiuto, nessuna chiamata al modello, nessuna riga `nodo=modello`), cronologia, router difettoso → agente, errore di collegamento propagato, messaggi visti dal router, prompt costruito dal file, caricamento dell'ambito.
- Prova reale (`--lmstudio`): «che ore sono a Tokyo?» (conversazione, orologio chiamato) e «scrivimi una poesia sul mare» (rifiuto, nessun `nodo=modello` nel log).

## Fuori da questo step

Revisore, riassunto della cronologia, resource e prompt MCP, interfaccia web.
