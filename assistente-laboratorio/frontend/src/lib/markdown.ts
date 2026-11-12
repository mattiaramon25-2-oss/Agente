import { Marked } from 'marked';
import createDOMPurify from 'dompurify';

// Unico punto in cui il testo del modello entra nella pagina:
// Markdown (GFM, a capo come interruzioni) poi ripulito con DOMPurify.
const marcatore = new Marked({ gfm: true, breaks: true });

type Purificatore = ReturnType<typeof createDOMPurify>;
let purificatore: Purificatore | undefined;

// Creato alla prima chiamata: importare il modulo non tocca `window`.
function ottieniPurificatore(): Purificatore {
  if (!purificatore) {
    const nuovo = createDOMPurify(window);
    nuovo.addHook('afterSanitizeAttributes', (nodo) => {
      if (nodo.tagName === 'A') {
        nodo.setAttribute('target', '_blank');
        nodo.setAttribute('rel', 'noopener noreferrer');
      }
    });
    purificatore = nuovo;
  }
  return purificatore;
}

// Elenco di ciò che è ammesso (allowlist): solo i tag che il Markdown produce per testo,
// elenchi, codice, citazioni, link e tabelle. Tutto il resto sparisce: immagini, audio,
// video, <picture>/<source>, SVG e MathML (caricherebbero risorse esterne, un canale di
// esfiltrazione), moduli, stili e contenuti incorporati. Del testo dei tag tolti resta il contenuto.
const TAG_AMMESSI = [
  'p', 'br', 'strong', 'em', 'del', 'code', 'pre', 'blockquote',
  'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr',
  'table', 'thead', 'tbody', 'tr', 'th', 'td', 'span',
];
// href passa anche dal controllo degli URI di DOMPurify (niente javascript:, data: e simili).
const ATTRIBUTI_AMMESSI = ['href', 'title', 'align', 'start'];

export function rendiMarkdown(testo: string): string {
  const html = marcatore.parse(testo, { async: false });
  return ottieniPurificatore().sanitize(html, {
    ALLOWED_TAGS: TAG_AMMESSI,
    ALLOWED_ATTR: ATTRIBUTI_AMMESSI,
  });
}
