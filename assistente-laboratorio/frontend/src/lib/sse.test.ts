import { describe, expect, it } from 'vitest';
import { LettoreSse } from './sse';

const codifica = (testo: string) => new TextEncoder().encode(testo);

describe('LettoreSse', () => {
  it('un evento completo', () => {
    const lettore = new LettoreSse();
    const eventi = lettore.aggiungi(codifica('event: testo\ndata: {"pezzo":"ciao"}\n\n'));
    expect(eventi).toEqual([{ evento: 'testo', dati: { pezzo: 'ciao' } }]);
  });

  it('evento spezzato tra due pezzi', () => {
    const lettore = new LettoreSse();
    const byte = codifica('event: testo\ndata: {"pezzo":"ciao"}\n\n');
    const meta = 'event: testo\nda'.length;
    expect(lettore.aggiungi(byte.slice(0, meta))).toEqual([]);
    expect(lettore.aggiungi(byte.slice(meta))).toEqual([
      { evento: 'testo', dati: { pezzo: 'ciao' } },
    ]);
  });

  it('carattere multibyte spezzato', () => {
    const lettore = new LettoreSse();
    const byte = codifica('event: testo\ndata: {"pezzo":"è"}\n\n');
    const taglio = byte.indexOf(0xc3) + 1;
    expect(lettore.aggiungi(byte.slice(0, taglio))).toEqual([]);
    expect(lettore.aggiungi(byte.slice(taglio))).toEqual([
      { evento: 'testo', dati: { pezzo: 'è' } },
    ]);
  });

  it('più eventi in un pezzo', () => {
    const lettore = new LettoreSse();
    const eventi = lettore.aggiungi(
      codifica('event: a\ndata: 1\n\nevent: b\ndata: {"x":2}\n\n'),
    );
    expect(eventi).toEqual([
      { evento: 'a', dati: 1 },
      { evento: 'b', dati: { x: 2 } },
    ]);
  });

  it('righe CRLF', () => {
    const lettore = new LettoreSse();
    const eventi = lettore.aggiungi(codifica('event: testo\r\ndata: {"pezzo":"x"}\r\n\r\n'));
    expect(eventi).toEqual([{ evento: 'testo', dati: { pezzo: 'x' } }]);
  });

  it('commenti ignorati', () => {
    const lettore = new LettoreSse();
    const eventi = lettore.aggiungi(codifica(': keep-alive\n\nevent: testo\n: nota\ndata: 3\n\n'));
    expect(eventi).toEqual([{ evento: 'testo', dati: 3 }]);
  });

  it('senza event: l\'evento si chiama message', () => {
    const lettore = new LettoreSse();
    expect(lettore.aggiungi(codifica('data: {"a":1}\n\n'))).toEqual([
      { evento: 'message', dati: { a: 1 } },
    ]);
  });

  it('U+2028 come escape JSON di 6 caratteri resta nella stringa', () => {
    const lettore = new LettoreSse();
    // Nel sorgente '\u2028' è il testo   (backslash, u, 2028), cioè l'escape JSON.
    const eventi = lettore.aggiungi(codifica('event: testo\ndata: {"r":"a\u2028b"}\n\n'));
    expect(eventi).toEqual([{ evento: 'testo', dati: { r: 'a b' } }]);
  });

  it('U+2028 come carattere diretto resta nella stringa', () => {
    const lettore = new LettoreSse();
    const eventi = lettore.aggiungi(codifica('event: testo\ndata: {"r":"a b"}\n\n'));
    expect(eventi).toEqual([{ evento: 'testo', dati: { r: 'a b' } }]);
  });

  it('\r\n diviso tra due pezzi', () => {
    const lettore = new LettoreSse();
    expect(lettore.aggiungi(codifica('event: testo\r\ndata: {"pezzo":"x"}\r'))).toEqual([]);
    expect(lettore.aggiungi(codifica('\n\r\n'))).toEqual([
      { evento: 'testo', dati: { pezzo: 'x' } },
    ]);
  });

  it('fine scarta un evento incompleto', () => {
    const lettore = new LettoreSse();
    expect(lettore.aggiungi(codifica('event: testo\ndata: {"pezzo":"mez'))).toEqual([]);
    lettore.fine();
    expect(lettore.aggiungi(codifica('event: testo\ndata: {"pezzo":"intero"}\n\n'))).toEqual([
      { evento: 'testo', dati: { pezzo: 'intero' } },
    ]);
  });
});
