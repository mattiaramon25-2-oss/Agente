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
});
