import { describe, expect, it } from 'vitest';
import { partiEvidenziate, rigaStrumento } from './testo';

describe('partiEvidenziate', () => {
  it('le parti di indice dispari sono le occorrenze, senza badare alle maiuscole', () => {
    expect(partiEvidenziate('Il Risultato è 14, il risultato giusto', 'risultato')).toEqual([
      'Il ',
      'Risultato',
      ' è 14, il ',
      'risultato',
      ' giusto',
    ]);
  });

  it("un'occorrenza in testa lascia una parte vuota all'inizio", () => {
    const parti = partiEvidenziate('14 è il risultato', '14');
    expect(parti).toEqual(['', '14', ' è il risultato']);
  });

  it('i metacaratteri delle espressioni regolari valgono come testo', () => {
    expect(partiEvidenziate('Quanto fa (3+4)*2? E 3+4?', '(3+4)*2?')).toEqual([
      'Quanto fa ',
      '(3+4)*2?',
      ' E 3+4?',
    ]);
    expect(partiEvidenziate('a.b axb', 'a.b')).toEqual(['', 'a.b', ' axb']);
    expect(partiEvidenziate('c:\\dati [x]', '\\dati [x]')).toEqual(['c:', '\\dati [x]', '']);
  });

  it('con la ricerca vuota il testo resta intero', () => {
    expect(partiEvidenziate('Il risultato è 14', '')).toEqual(['Il risultato è 14']);
  });

  it('senza occorrenze il testo resta intero', () => {
    expect(partiEvidenziate('Il risultato è 14', 'meteo')).toEqual(['Il risultato è 14']);
  });
});

describe('rigaStrumento', () => {
  it('nome · valori uniti da virgola, come la CLI', () => {
    expect(rigaStrumento({ nome: 'calcola', origine: 'mcp', argomenti: { espressione: '(3+4)*2' } })).toBe(
      'calcola · (3+4)*2',
    );
    expect(
      rigaStrumento({ nome: 'converti', origine: 'mcp', argomenti: { valore: '10', da: 'km', a: 'mi' } }),
    ).toBe('converti · 10, km, mi');
  });

  it('i valori che non sono stringhe diventano testo', () => {
    expect(
      rigaStrumento({
        nome: 'prova',
        origine: 'mcp',
        argomenti: { n: 3, b: true, x: null, lista: [1, 'a'], oggetto: { k: 'v' } },
      }),
    ).toBe('prova · 3, true, null, [1,"a"], {"k":"v"}');
  });

  it('senza argomenti resta solo il nome', () => {
    expect(rigaStrumento({ nome: 'ora_corrente', origine: 'mcp', argomenti: {} })).toBe('ora_corrente');
  });
});
