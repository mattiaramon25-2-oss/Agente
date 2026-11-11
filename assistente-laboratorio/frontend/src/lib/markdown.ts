import { Marked } from 'marked';
import createDOMPurify from 'dompurify';

// Unico punto in cui il testo del modello entra nella pagina:
// Markdown (GFM, a capo come interruzioni) poi ripulito con DOMPurify.
const marcatore = new Marked({ gfm: true, breaks: true });
const purificatore = createDOMPurify(window);

purificatore.addHook('afterSanitizeAttributes', (nodo) => {
  if (nodo.tagName === 'A') {
    nodo.setAttribute('target', '_blank');
    nodo.setAttribute('rel', 'noopener noreferrer');
  }
});

export function rendiMarkdown(testo: string): string {
  const html = marcatore.parse(testo, { async: false });
  return purificatore.sanitize(html);
}
