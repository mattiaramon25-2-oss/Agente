// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { applicaTema, leggiScelta, salvaScelta, temaEffettivo } from './tema';

describe('temaEffettivo', () => {
  it.each([
    ['automatico', false, 'chiaro'],
    ['automatico', true, 'scuro'],
    ['chiaro', false, 'chiaro'],
    ['chiaro', true, 'chiaro'],
    ['scuro', false, 'scuro'],
    ['scuro', true, 'scuro'],
  ] as const)('%s con preferenza scura %s dà %s', (scelta, scuro, atteso) => {
    expect(temaEffettivo(scelta, scuro)).toBe(atteso);
  });
});

describe('scelta del tema', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('scelta salvata e riletta', () => {
    salvaScelta('scuro');
    expect(leggiScelta()).toBe('scuro');
  });

  it('valore sconosciuto dà automatico', () => {
    localStorage.setItem('tema', 'blu');
    expect(leggiScelta()).toBe('automatico');
  });

  it('localStorage che solleva un errore dà automatico', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('negato');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('negato');
    });
    expect(leggiScelta()).toBe('automatico');
    expect(() => salvaScelta('chiaro')).not.toThrow();
  });

  it('localStorage non definito d� automatico', () => {
    vi.stubGlobal('localStorage', undefined);
    try {
      expect(leggiScelta()).toBe('automatico');
      expect(() => salvaScelta('chiaro')).not.toThrow();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('applicaTema imposta data-tema', () => {
    applicaTema('scuro');
    expect(document.documentElement.dataset.tema).toBe('scuro');
  });
});
