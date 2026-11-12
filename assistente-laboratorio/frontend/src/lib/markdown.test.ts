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

  describe('nessun elemento che carica risorse esterne', () => {
    const VIETATI = [
      'src=', 'poster=', 'srcset=', 'href=', 'background=',
      '<video', '<audio', '<source', '<picture', '<svg', '<image', '<feimage', '<img',
    ];
    const vettori: Array<[string, string]> = [
      ['video con poster e src', '<video poster="https://evil/p.png" src="https://evil/v.mp4"></video>'],
      ['audio con src e autoplay', '<audio src="https://evil/a.mp3" autoplay></audio>'],
      ['video con source', '<video><source src="https://evil/v.mp4"></video>'],
      ['picture con source srcset', '<picture><source srcset="https://evil/i.png"></picture>'],
      ['svg con image href', '<svg><image href="https://evil/i.png"></image></svg>'],
      ['svg con image xlink:href', '<svg><image xlink:href="https://evil/i.png"></image></svg>'],
      ['svg con feImage', '<svg><filter><feImage href="https://evil/i.png"></feImage></filter></svg>'],
      ['table e td con background', '<table background="https://evil/t.png"><tr><td background="https://evil/c.png">x</td></tr></table>'],
    ];
    for (const [nome, html] of vettori) {
      it(nome, () => {
        const uscita = rendiMarkdown(html).toLowerCase();
        for (const v of VIETATI) expect(uscita, `${nome}: ${uscita}`).not.toContain(v);
      });
    }

    it('il testo della tabella resta', () => {
      expect(rendiMarkdown('<table><tr><td background="https://evil/c.png">cella</td></tr></table>')).toContain('<td>cella</td>');
    });
  });

  it('tabella Markdown con allineamento', () => {
    const html = rendiMarkdown('| a | b |\n|:-:|--:|\n| 1 | 2 |');
    expect(html).toContain('<table>');
    expect(html).toContain('<th align="center">a</th>');
    expect(html).toContain('<td align="right">2</td>');
  });

  it('elenco numerato da 3 tiene start; niente class sul codice', () => {
    expect(rendiMarkdown('3. tre\n4. quattro')).toContain('<ol start="3">');
    expect(rendiMarkdown('```python\nx = 1\n```')).toContain('<pre><code>x = 1');
  });

  it('link in HTML grezzo e seconda chiamata ricevono target e rel', () => {
    for (let i = 0; i < 2; i++) {
      const html = rendiMarkdown('<a href="https://x">x</a>');
      expect(html).toContain('target="_blank"');
      expect(html).toContain('rel="noopener noreferrer"');
    }
  });
});
