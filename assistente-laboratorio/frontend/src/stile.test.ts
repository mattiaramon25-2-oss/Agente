import { expect, it } from 'vitest';

// @types/node non è tra i pacchetti ammessi: il modulo si carica con tipo libero.
const NOME_FS = 'node:fs';
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const fs: any = await import(/* @vite-ignore */ NOME_FS);

const css: string = fs.readFileSync(new URL('./stile.css', import.meta.url), 'utf-8');

/** Le dichiarazioni (variabili e color-scheme) del primo blocco che segue `selettore`. */
function dichiarazioni(selettore: string): string[] {
  const inizio = css.indexOf(selettore);
  expect(inizio, `manca ${selettore}`).toBeGreaterThanOrEqual(0);
  const apertura = css.indexOf('{', inizio + selettore.length);
  const chiusura = css.indexOf('}', apertura);
  return css
    .slice(apertura + 1, chiusura)
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split(';')
    .map((d) => d.trim())
    .filter(Boolean);
}

it('prima del JavaScript la pagina segue il tema del sistema: il blocco scuro automatico è uguale a quello scelto', () => {
  const scelto = dichiarazioni(":root[data-tema='scuro']");
  expect(scelto).toContain('color-scheme: dark');
  expect(css).toMatch(/@media \(prefers-color-scheme: dark\)\s*\{\s*:root:not\(\[data-tema\]\)\s*\{/);
  expect(dichiarazioni(':root:not([data-tema])')).toEqual(scelto);
});
