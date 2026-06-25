"""
buscar_contato.py  —  Ache o ID do cliente fake que você usa nos pedidos.

Uso:
    python buscar_contato.py "Mercado Livre Full"
    python buscar_contato.py "consumidor"
"""

import os
import sys
from dotenv import load_dotenv
from bling_client import BlingClient

load_dotenv()

if len(sys.argv) < 2:
    sys.exit('Uso: python buscar_contato.py "nome do cliente"')

client = BlingClient(
    client_id=os.environ["BLING_CLIENT_ID"],
    client_secret=os.environ["BLING_CLIENT_SECRET"],
    redirect_uri=os.environ["BLING_REDIRECT_URI"],
)

contatos = client.buscar_contatos(sys.argv[1])
if not contatos:
    print("Nenhum contato encontrado. Tente outro termo.")
else:
    print(f"\n{'ID':>12}  NOME")
    print("-" * 50)
    for c in contatos:
        print(f"{c.get('id'):>12}  {c.get('nome')}")
    print("\nCopie o ID desejado para BLING_CONTATO_ID no arquivo .env\n")
