# Prima fase: compila la chat (Vite + Svelte).
FROM node:24.21.0-alpine AS costruzione
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Seconda fase: nginx senza privilegi serve i file compilati e inoltra /api al back-end.
FROM nginxinc/nginx-unprivileged:1.30.6-alpine
# L'immagine completa questo modello con le variabili d'ambiente (BACKEND_PORTA) all'avvio.
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=costruzione /app/dist /usr/share/nginx/html
EXPOSE 8080
