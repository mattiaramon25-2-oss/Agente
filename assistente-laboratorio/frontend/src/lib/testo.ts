// Piccole funzioni sul testo mostrato dall'interfaccia, senza HTML.

import type { Strumento } from './api';

const proteggi = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Divide il testo attorno alle occorrenze di q, senza badare alle maiuscole.
 *  Le parti di indice dispari sono le occorrenze da evidenziare. */
export function partiEvidenziate(testo: string, q: string): string[] {
  if (!q) return [testo];
  return testo.split(new RegExp(`(${proteggi(q)})`, 'gi'));
}

const comeTesto = (v: unknown) => (typeof v === 'string' ? v : typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v));

/** Come la CLI: «nome · valori», con i valori degli argomenti uniti da «, ». */
export function rigaStrumento(strumento: Strumento): string {
  const valori = Object.values(strumento.argomenti ?? {}).map(comeTesto).join(', ');
  return valori ? `${strumento.nome} · ${valori}` : strumento.nome;
}
