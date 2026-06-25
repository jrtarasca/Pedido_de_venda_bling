"""
bling_client.py
Cliente da API v3 do Bling: cuida do OAuth 2.0 (access token + refresh
automático) e expõe os métodos usados pelo robô de pedidos.

Documentação oficial: https://developer.bling.com.br
"""

import os
import json
import time
import base64
import requests

# --- Endpoints oficiais da API v3 ---------------------------------------
AUTH_URL = "https://www.bling.com.br/Api/v3/oauth/authorize"
TOKEN_URL = "https://www.bling.com.br/Api/v3/oauth/token"
API_BASE = "https://api.bling.com.br/Api/v3"

TOKENS_FILE = "tokens.json"          # tokens de acesso (gerado pelo autorizar.py)
CACHE_PRODUTOS = "cache_produtos.json"  # SKU -> id do produto (acelera execuções)

# Limite do Bling: até 3 req/s. Usamos uma folga de segurança.
INTERVALO_REQ = 0.4  # segundos entre requisições


class BlingError(Exception):
    pass


class BlingClient:
    def __init__(self, client_id, client_secret, redirect_uri):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.tokens = self._carregar_tokens()
        self._cache = self._carregar_cache()

    # ------------------------------------------------------------------ #
    # OAuth
    # ------------------------------------------------------------------ #
    def _basic_header(self):
        raw = f"{self.client_id}:{self.client_secret}".encode()
        return "Basic " + base64.b64encode(raw).decode()

    def montar_url_autorizacao(self, state="vincularauto"):
        return (
            f"{AUTH_URL}?response_type=code"
            f"&client_id={self.client_id}"
            f"&state={state}"
            f"&redirect_uri={self.redirect_uri}"
        )

    def trocar_code_por_token(self, code):
        """Fluxo authorization_code -> gera o primeiro par de tokens."""
        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": self._basic_header(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise BlingError(f"Falha ao trocar code: {resp.status_code} - {resp.text}")
        self._salvar_tokens(resp.json())
        return self.tokens

    def _refresh(self):
        rt = self.tokens.get("refresh_token")
        if not rt:
            raise BlingError("Sem refresh_token. Rode 'python autorizar.py' novamente.")
        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": self._basic_header(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={"grant_type": "refresh_token", "refresh_token": rt},
            timeout=30,
        )
        if resp.status_code != 200:
            raise BlingError(
                f"Falha no refresh: {resp.status_code} - {resp.text}\n"
                "Talvez seja preciso autorizar de novo: python autorizar.py"
            )
        self._salvar_tokens(resp.json())

    def _token_valido(self):
        if not self.tokens.get("access_token"):
            return False
        # renova com 60s de folga antes de expirar
        return time.time() < (self.tokens.get("expires_at", 0) - 60)

    def _auth_header(self):
        if not self._token_valido():
            self._refresh()
        return {"Authorization": f"Bearer {self.tokens['access_token']}"}

    # ------------------------------------------------------------------ #
    # Persistência
    # ------------------------------------------------------------------ #
    def _salvar_tokens(self, data):
        self.tokens = {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", self.tokens.get("refresh_token") if hasattr(self, "tokens") else None),
            "expires_at": time.time() + int(data.get("expires_in", 21600)),
        }
        with open(TOKENS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.tokens, f, indent=2)

    @staticmethod
    def _carregar_tokens():
        if os.path.exists(TOKENS_FILE):
            with open(TOKENS_FILE, encoding="utf-8") as f:
                return json.load(f)
        return {}

    @staticmethod
    def _carregar_cache():
        if os.path.exists(CACHE_PRODUTOS):
            with open(CACHE_PRODUTOS, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _salvar_cache(self):
        with open(CACHE_PRODUTOS, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2)

    # ------------------------------------------------------------------ #
    # Requisição genérica (com retry de rate limit)
    # ------------------------------------------------------------------ #
    def _req(self, metodo, caminho, **kwargs):
        url = f"{API_BASE}{caminho}"
        for tentativa in range(4):
            headers = {**self._auth_header(), "Accept": "application/json"}
            if "json" in kwargs:
                headers["Content-Type"] = "application/json"
            resp = requests.request(metodo, url, headers=headers, timeout=30, **kwargs)
            time.sleep(INTERVALO_REQ)
            if resp.status_code == 429:  # rate limit -> espera e repete
                time.sleep(2 * (tentativa + 1))
                continue
            if resp.status_code == 401:  # token expirou no meio -> renova e repete
                self._refresh()
                continue
            return resp
        return resp

    # ------------------------------------------------------------------ #
    # Helpers de negócio
    # ------------------------------------------------------------------ #
    def buscar_contatos(self, pesquisa):
        """Lista contatos por nome/razão social — use para achar o ID do cliente fake."""
        resp = self._req("GET", f"/contatos?pesquisa={pesquisa}&limite=20")
        if resp.status_code != 200:
            raise BlingError(f"Erro ao buscar contatos: {resp.status_code} - {resp.text}")
        return resp.json().get("data", [])

    def resolver_produto_id(self, sku):
        """SKU (código) -> id do produto no Bling, com cache em disco."""
        sku = str(sku).strip()
        if sku in self._cache:
            return self._cache[sku]
        resp = self._req("GET", f"/produtos?codigo={sku}&limite=1")
        if resp.status_code != 200:
            raise BlingError(f"Erro ao buscar produto {sku}: {resp.status_code} - {resp.text}")
        data = resp.json().get("data", [])
        if not data:
            self._cache[sku] = None
            self._salvar_cache()
            return None
        pid = data[0]["id"]
        self._cache[sku] = pid
        self._salvar_cache()
        return pid

    def criar_pedido_venda(self, payload):
        """POST /pedidos/vendas — retorna o objeto Response."""
        return self._req("POST", "/pedidos/vendas", json=payload)

    def listar_depositos(self):
        """GET /depositos — lista os depósitos (id, descricao)."""
        resp = self._req("GET", "/depositos?limite=100")
        if resp.status_code != 200:
            raise BlingError(f"Erro ao listar depósitos: {resp.status_code} - {resp.text}")
        return resp.json().get("data", [])

    def achar_deposito_id(self, nome):
        """Retorna o id do depósito cujo nome bate (case-insensitive)."""
        nome = nome.strip().lower()
        for d in self.listar_depositos():
            if str(d.get("descricao", "")).strip().lower() == nome:
                return d["id"]
        return None

    def saldo_no_deposito(self, id_produto, id_deposito, usar_virtual=True):
        """
        Saldo disponível de um produto NUM depósito específico.
        usar_virtual=True -> saldoVirtual (já desconta reservas existentes).
        usar_virtual=False -> saldoFisico.
        """
        resp = self._req("GET", f"/estoques/saldos?idsProdutos[]={id_produto}")
        if resp.status_code != 200:
            raise BlingError(f"Erro ao consultar saldo de {id_produto}: {resp.status_code} - {resp.text}")
        data = resp.json().get("data", [])
        if not data:
            return 0.0
        depositos = data[0].get("depositos", []) or []
        chave = "saldoVirtual" if usar_virtual else "saldoFisico"
        for d in depositos:
            did = d.get("id", d.get("idDeposito"))
            if did == id_deposito:
                return float(d.get(chave, 0) or 0)
        return 0.0  # produto não tem saldo nesse depósito
