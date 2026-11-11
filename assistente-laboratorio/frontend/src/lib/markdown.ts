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

// Niente immagini (canale di esfiltrazione), moduli, stili e contenuti incorporati.
const TAG_VIETATI = [
  'style', 'form', 'input', 'button', 'textarea', 'select',
  'iframe', 'object', 'embed', 'img',
];
const ATTRIBUTI_VIETATI = ['style', 'action', 'formaction'];

export function rendiMarkdown(testo: string): string {
  const html = marcatore.parse(testo, { async: false });
  return ottieniPurificatore().sanitize(html, {
    FORBID_TAGS: TAG_VIETATI,
    FORBID_ATTR: ATTRIBUTI_VIETATI,
  });
}
