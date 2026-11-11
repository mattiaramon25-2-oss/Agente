export type SceltaTema = 'automatico' | 'chiaro' | 'scuro';

const CHIAVE = 'tema';

export function temaEffettivo(
  scelta: SceltaTema,
  preferisceScuro: boolean,
): 'chiaro' | 'scuro' {
  if (scelta === 'automatico') return preferisceScuro ? 'scuro' : 'chiaro';
  return scelta;
}

export function leggiScelta(): SceltaTema {
  try {
    const valore = localStorage.getItem(CHIAVE);
    if (valore === 'chiaro' || valore === 'scuro' || valore === 'automatico') {
      return valore;
    }
  } catch {
    // localStorage assente o bloccato: si usa il tema automatico.
  }
  return 'automatico';
}

export function salvaScelta(scelta: SceltaTema): void {
  try {
    localStorage.setItem(CHIAVE, scelta);
  } catch {
    // La scelta vale solo per questa sessione.
  }
}

export function applicaTema(tema: 'chiaro' | 'scuro'): void {
  if (typeof document === 'undefined') return;
  document.documentElement.dataset.tema = tema;
}
