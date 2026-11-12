import { expect, it } from 'vitest';

// @types/node non è tra i pacchetti ammessi: il modulo si carica con tipo libero.
const NOME_FS = 'node:fs';
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const fs: any = await import(/* @vite-ignore */ NOME_FS);

const pubblico = new URL('../../public/', import.meta.url);

const manifest = JSON.parse(fs.readFileSync(new URL('manifest.webmanifest', pubblico), 'utf-8'));

// Larghezza e altezza stanno nel chunk IHDR, subito dopo la firma PNG (8 byte) e l'intestazione del chunk (8 byte).
function dimensioniPng(percorso: string): [number, number] {
  const dati: Uint8Array = fs.readFileSync(new URL(percorso, pubblico));
  const vista = new DataView(dati.buffer, dati.byteOffset, dati.byteLength);
  return [vista.getUint32(16), vista.getUint32(20)];
}

it('il manifest descrive l\'app', () => {
  expect(manifest.name).toBe('Assistente del laboratorio');
  expect(manifest.short_name).toBe('Assistente');
  expect(manifest.display).toBe('standalone');
  expect(manifest.start_url).toBe('/');
  expect(manifest.theme_color).toBe('#5fb3a6');
  expect(manifest.background_color).toBe('#f6f8f6');
});

it('le icone PNG 192 e 512 esistono con le dimensioni dichiarate', () => {
  for (const lato of [192, 512]) {
    const icona = manifest.icons.find(
      (i: { sizes: string; type: string }) => i.sizes === `${lato}x${lato}` && i.type === 'image/png',
    );
    expect(icona, `icona ${lato}`).toBeTruthy();
    expect(dimensioniPng(icona.src.replace(/^\//, ''))).toEqual([lato, lato]);
  }
});

it('esiste l\'icona SVG e il service worker', () => {
  expect(fs.existsSync(new URL('icone/icona.svg', pubblico))).toBe(true);
  expect(fs.existsSync(new URL('sw.js', pubblico))).toBe(true);
});
