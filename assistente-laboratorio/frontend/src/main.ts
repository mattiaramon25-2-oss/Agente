import { mount } from 'svelte';
import App from './App.svelte';

const app = mount(App, { target: document.getElementById('app')! });

// Il service worker serve solo a rendere la chat installabile: in sviluppo non si registra.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch((errore) => {
    console.warn('Service worker non registrato:', errore);
  });
}

export default app;
