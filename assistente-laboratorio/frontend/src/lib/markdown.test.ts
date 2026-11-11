// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { rendiMarkdown } from './markdown';

describe('rendiMarkdown', () => {
  it('grassetto ed elenchi', () => {
    const html = rendiMarkdown('**forte**\n\n- uno\n- due');
    expect(html).toContain('<strong>forte</strong>');
    expect(html).toContain('<ul>');
    expect(html).toContain('<li>uno</li>');
  });

  it('codice in blocco', () => {
    const html = rendiMarkdown('```\nprint(1)\n```');
    expect(html).toContain('<pre>');
    expect(html).toContain('<code>');
    expect(html).toContain('print(1)');
  });

  it('toglie script e attributi pericolosi', () => {
    const html = rendiMarkdown(
      '<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[x](javascript:alert(1))',
    );
    expect(html).not.toContain('<script');
    expect(html).not.toContain('onerror');
    expect(html).not.toContain('javascript:');
  });

  it('link esterno con noopener', () => {
    const html = rendiMarkdown('[sito](https://example.com)');
    expect(html).toContain('href="https://example.com"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
  });

  it('nessuna immagine, né in Markdown né in HTML', () => {
    expect(rendiMarkdown('![x](https://evil/?q=1)')).not.toContain('<img');
    expect(rendiMarkdown('<img src="https://evil/?q=1">')).not.toContain('<img');
  });

  it('toglie moduli e controlli', () => {
    const html = rendiMarkdown('<form action="https://evil"><input><button>ok</button></form>');
    for (const tag of ['<form', '<input', '<button']) expect(html).not.toContain(tag);
  });

  it('toglie style e attributi style', () => {
    expect(rendiMarkdown('<style>body{}</style>')).not.toContain('<style');
    expect(rendiMarkdown('<p style="color:red">x</p>')).not.toContain('style=');
  });

  it('toglie iframe', () => {
    expect(rendiMarkdown('<iframe src="https://evil"></iframe>')).not.toContain('<iframe');
  });

  it('blocca href pericolosi', () => {
    for (const md of [
      '[a](vbscript:x)',
      '[a](data:text/html,x)',
      '<a href="&#106;avascript:alert(1)">x</a>',
    ]) {
      const html = rendiMarkdown(md);
      expect(html).not.toMatch(/href="(javascript|vbscript|data):/i);
    }
  });

  it('toglie onload da svg', () => {
    expect(rendiMarkdown('<svg onload=alert(1)>')).not.toContain('onload');
  });

  it('link in HTML grezzo e seconda chiamata ricevono target e rel', () => {
    for (let i = 0; i < 2; i++) {
      const html = rendiMarkdown('<a href="https://x">x</a>');
      expect(html).toContain('target="_blank"');
      expect(html).toContain('rel="noopener noreferrer"');
    }
  });
});
