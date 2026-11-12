import { expect, it } from 'vitest';

it('importare il modulo in ambiente node non solleva errori', async () => {
  const modulo = await import('./markdown');
  expect(typeof modulo.rendiMarkdown).toBe('function');
});
