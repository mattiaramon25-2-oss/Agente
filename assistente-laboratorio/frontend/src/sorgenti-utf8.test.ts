import { expect, it } from 'vitest';

// @types/node non è tra i pacchetti ammessi: il modulo si carica con tipo libero.
const NOME_FS = 'node:fs';
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const fs: any = await import(/* @vite-ignore */ NOME_FS);

function elenca(cartella: URL): URL[] {
  return fs.readdirSync(cartella, { withFileTypes: true }).flatMap(
    (voce: { name: string; isDirectory(): boolean }) => {
      const percorso = new URL(voce.name + (voce.isDirectory() ? '/' : ''), cartella);
      return voce.isDirectory() ? elenca(percorso) : [percorso];
    },
  );
}

it('tutti i sorgenti sono UTF-8 valido', () => {
  const decodificatore = new TextDecoder('utf-8', { fatal: true });
  const file = elenca(new URL('./', import.meta.url)).filter((f) =>
    /\.(ts|svelte|css)$/.test(f.pathname),
  );
  expect(file.length).toBeGreaterThan(0);
  for (const f of file) {
    expect(() => decodificatore.decode(fs.readFileSync(f)), f.pathname).not.toThrow();
  }
});
