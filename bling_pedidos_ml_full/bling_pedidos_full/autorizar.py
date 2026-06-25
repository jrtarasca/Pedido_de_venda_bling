"""
autorizar.py  —  RODE ISTO UMA VEZ (ou quando o refresh token expirar).

Passo a passo:
1) Preencha o arquivo .env com BLING_CLIENT_ID, BLING_CLIENT_SECRET e
   BLING_REDIRECT_URI (a mesma URL cadastrada no app dentro do Bling).
2) Rode:  python autorizar.py
3) Abra o link que aparecer, faça login no Bling e clique em autorizar.
4) O navegador vai redirecionar para a sua URL com  ?code=XXXX  no final.
   Copie SÓ o valor do code e cole aqui no terminal.
5) Pronto: o tokens.json é criado e o robô já funciona sozinho.
"""

import os
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
from bling_client import BlingClient

load_dotenv()

client = BlingClient(
    client_id=os.environ["BLING_CLIENT_ID"],
    client_secret=os.environ["BLING_CLIENT_SECRET"],
    redirect_uri=os.environ["BLING_REDIRECT_URI"],
)

print("\n1) Abra este link no navegador e autorize o aplicativo:\n")
print(client.montar_url_autorizacao())
print(
    "\n2) Depois de autorizar, o navegador vai para sua redirect_uri com '?code=...'."
    "\n   Cole abaixo a URL inteira OU apenas o code.\n"
)

entrada = input("code (ou URL completa): ").strip()

# aceita tanto o code puro quanto a URL inteira colada
if "code=" in entrada:
    code = parse_qs(urlparse(entrada).query).get("code", [entrada])[0]
else:
    code = entrada

client.trocar_code_por_token(code)
print("\n✓ tokens.json criado com sucesso. Já pode rodar: python criar_pedidos.py\n")
