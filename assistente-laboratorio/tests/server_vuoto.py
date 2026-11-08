"""Server MCP senza strumenti, per provare l'errore «catalogo vuoto»."""

import argparse

from fastmcp import FastMCP

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--porta", type=int, required=True)
    porta = parser.parse_args().porta
    FastMCP("vuoto").run(
        transport="http", host="127.0.0.1", port=porta, path="/mcp", show_banner=False,
        stateless_http=True, json_response=True, log_level="warning",
    )
