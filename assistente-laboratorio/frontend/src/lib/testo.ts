// Piccole funzioni sul testo mostrato dall'interfaccia, senza HTML.

import type { Strumento } from './api';

const proteggi = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Divide il testo attorno alle occorrenze di q, senza badare alle maiuscole.
 *  Le parti di indice dispari sono le occorrenze da evidenziare. */
export function partiEvidenziate(testo: string, q: string): string[] {
  if (!q) return [testo];
  return testo.split(new RegExp(`(${proteggi(q)})`, 'gi'));
}

/** L'inizio di un testo su una riga, per citarlo in un avviso: spazi e a capo ridotti
 *  a uno spazio, al massimo `lunghezza` caratteri e «…» se è stato tagliato. */
export function inizioTesto(testo: string, lunghezza = 40): string {
  const caratteri = Array.from(testo.replace(/\s+/g, ' ').trim());
  return caratteri.length <= lunghezza ? caratteri.join('') : `${caratteri.slice(0, lunghezza).join('')}…`;
}

const comeTesto =(v: unknown) => (typeof v === 'string' ? v : typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v));

/** Come la CLI: «nome · valori», con i valori degli argomenti uniti da «, ». */
export function rigaStrumento(strumento: Strumento): string {
  const valori = Object.values(strumento.argomenti ?? {}).map(comeTesto).join(', ');
  return valori ? `${strumento.nome} · ${valori}` : strumento.nome;
}
