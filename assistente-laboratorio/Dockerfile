FROM python:3.14-slim

# ASSISTENTE_IN_DOCKER: il fuso del container (UTC) non è quello dell'utente, quindi non va usato.
ENV ASSISTENTE_IN_DOCKER=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY assistente/ assistente/
COPY logica/ logica/
COPY server_mcp/ server_mcp/

CMD ["python", "-m", "assistente"]
