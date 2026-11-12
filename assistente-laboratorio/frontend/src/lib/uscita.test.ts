// @vitest-environment jsdom
import { expect, it } from 'vitest';
import { proteggiUscita } from './uscita';

function chiudi(): Event {
  const evento = new Event('beforeunload', { cancelable: true });
  window.dispatchEvent(evento);
  return evento;
}

it('durante un turno chiudere la finestra chiede conferma; dopo, non più', () => {
  expect(chiudi().defaultPrevented).toBe(false);
  const togli = proteggiUscita(window);
  expect(chiudi().defaultPrevented).toBe(true);
  togli();
  expect(chiudi().defaultPrevented).toBe(false);
});
