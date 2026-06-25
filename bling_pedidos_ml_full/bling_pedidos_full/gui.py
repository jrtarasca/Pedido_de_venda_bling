"""
gui.py  —  Interface gráfica do Robô de Pedidos ML Full.

Rode com:  python gui.py    (ou dê dois cliques no "Abrir Interface.bat" no Windows)

Aqui você: salva as credenciais, autoriza o Bling, escolhe o cliente fake,
seleciona a planilha (de qualquer pasta) e acompanha o progresso na tela.
Nada de terminal nem porta.
"""

import os
import sys
import queue
import threading
import webbrowser
import subprocess
import datetime as dt
from urllib.parse import urlparse, parse_qs

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog

from dotenv import load_dotenv
from bling_client import BlingClient, BlingError
import processar_planilha as proc

PASTA = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(PASTA, ".env")
REDIRECT_PADRAO = "http://localhost:3000/callback"


# ----------------- utilidades de .env -----------------
def ler_env():
    load_dotenv(ENV_PATH, override=True)
    return dict(os.environ)


def gravar_env(updates: dict):
    """Atualiza/insere chaves no arquivo .env preservando o resto."""
    linhas, vistos = [], set()
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as f:
            linhas = f.read().splitlines()
    for i, ln in enumerate(linhas):
        if "=" in ln and not ln.strip().startswith("#"):
            chave = ln.split("=", 1)[0].strip()
            if chave in updates:
                linhas[i] = f"{chave}={updates[chave]}"
                vistos.add(chave)
    for chave, val in updates.items():
        if chave not in vistos:
            linhas.append(f"{chave}={val}")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    load_dotenv(ENV_PATH, override=True)


def abrir_pasta(caminho):
    pasta = caminho if os.path.isdir(caminho) else os.path.dirname(caminho)
    try:
        if sys.platform.startswith("win"):
            os.startfile(pasta)
        elif sys.platform == "darwin":
            subprocess.run(["open", pasta])
        else:
            subprocess.run(["xdg-open", pasta])
    except Exception:
        pass


# ----------------- janela principal -----------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Robô de Pedidos — ML Full (Bling)")
        self.geometry("760x680")
        self.minsize(700, 620)
        self.arquivo = None
        self.fila = queue.Queue()
        ler_env()
        self._montar()
        self._atualizar_status()
        self.after(100, self._consumir_fila)

    def _montar(self):
        pad = {"padx": 8, "pady": 4}
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        # ---- Aba 1: Configuração ----
        cfg = ttk.Frame(nb); nb.add(cfg, text="1. Configuração (1ª vez)")

        ttk.Label(cfg, text="Client ID:").grid(row=0, column=0, sticky="e", **pad)
        self.e_cid = ttk.Entry(cfg, width=55); self.e_cid.grid(row=0, column=1, **pad)
        ttk.Label(cfg, text="Client Secret:").grid(row=1, column=0, sticky="e", **pad)
        self.e_csec = ttk.Entry(cfg, width=55, show="•"); self.e_csec.grid(row=1, column=1, **pad)
        ttk.Label(cfg, text="Depósito:").grid(row=2, column=0, sticky="e", **pad)
        self.e_dep = ttk.Entry(cfg, width=55); self.e_dep.grid(row=2, column=1, **pad)
        ttk.Label(cfg, text="Prazo entrega (dias):").grid(row=3, column=0, sticky="e", **pad)
        self.e_prazo = ttk.Entry(cfg, width=10); self.e_prazo.grid(row=3, column=1, sticky="w", **pad)

        env = ler_env()
        self.e_cid.insert(0, env.get("BLING_CLIENT_ID", ""))
        self.e_csec.insert(0, env.get("BLING_CLIENT_SECRET", ""))
        self.e_dep.insert(0, env.get("BLING_DEPOSITO", "Estoque Geral"))
        self.e_prazo.insert(0, env.get("BLING_PRAZO_DIAS", "3"))

        ttk.Button(cfg, text="Salvar credenciais", command=self._salvar_cfg)\
            .grid(row=4, column=1, sticky="w", **pad)
        ttk.Separator(cfg, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Label(cfg, text="Depois de salvar, autorize o acesso à sua conta Bling:")\
            .grid(row=6, column=0, columnspan=2, sticky="w", **pad)
        ttk.Button(cfg, text="Autorizar Bling", command=self._autorizar)\
            .grid(row=7, column=1, sticky="w", **pad)

        # ---- Aba 2: Cliente fake ----
        cli = ttk.Frame(nb); nb.add(cli, text="2. Cliente fake")
        ttk.Label(cli, text="Buscar cliente por nome:").grid(row=0, column=0, sticky="e", **pad)
        self.e_busca = ttk.Entry(cli, width=40); self.e_busca.grid(row=0, column=1, sticky="w", **pad)
        self.e_busca.insert(0, "ENVIO FULL")
        ttk.Button(cli, text="Buscar", command=self._buscar_contato).grid(row=0, column=2, **pad)
        self.lst = tk.Listbox(cli, width=70, height=8); self.lst.grid(row=1, column=0, columnspan=3, **pad)
        ttk.Button(cli, text="Usar selecionado", command=self._usar_contato)\
            .grid(row=2, column=1, sticky="w", **pad)
        self.lbl_contato = ttk.Label(cli, text="")
        self.lbl_contato.grid(row=3, column=0, columnspan=3, sticky="w", **pad)
        self._contatos = []

        # ---- Aba 3: Rodar ----
        run = ttk.Frame(nb); nb.add(run, text="3. Rodar")
        ttk.Button(run, text="Escolher planilha...", command=self._escolher)\
            .grid(row=0, column=0, **pad)
        self.lbl_arq = ttk.Label(run, text="Nenhuma planilha selecionada")
        self.lbl_arq.grid(row=0, column=1, columnspan=2, sticky="w", **pad)

        ttk.Label(run, text="Data da venda:").grid(row=1, column=0, sticky="e", **pad)
        self.e_data = ttk.Entry(run, width=14)
        self.e_data.insert(0, dt.date.today().strftime("%d/%m/%Y"))
        self.e_data.grid(row=1, column=1, sticky="w", **pad)
        self.e_data.bind("<KeyRelease>", lambda e: self._mostrar_prevista())
        self.lbl_prev = ttk.Label(run, text="")
        self.lbl_prev.grid(row=1, column=2, sticky="w", **pad)

        ttk.Label(run, text="Observação interna\n(nº do Full do mês):", justify="right")\
            .grid(row=2, column=0, sticky="e", **pad)
        self.e_obs = ttk.Entry(run, width=50)
        self.e_obs.grid(row=2, column=1, columnspan=2, sticky="w", **pad)

        self.var_sim = tk.BooleanVar(value=True)
        ttk.Checkbutton(run, text="Apenas simular (não cria pedidos) — recomendado da 1ª vez",
                        variable=self.var_sim).grid(row=3, column=0, columnspan=3, sticky="w", **pad)
        self.var_semest = tk.BooleanVar(value=False)
        ttk.Checkbutton(run, text="Ignorar estoque (reservar a quantidade planejada cheia)",
                        variable=self.var_semest).grid(row=4, column=0, columnspan=3, sticky="w", **pad)

        self.btn_rodar = ttk.Button(run, text="▶  RODAR", command=self._rodar)
        self.btn_rodar.grid(row=5, column=0, **pad)
        self.btn_pasta = ttk.Button(run, text="Abrir pasta dos resultados",
                                    command=lambda: abrir_pasta(self.arquivo) if self.arquivo else None)
        self.btn_pasta.grid(row=5, column=1, sticky="w", **pad)

        self.log = scrolledtext.ScrolledText(run, width=92, height=17, font=("Consolas", 9))
        self.log.grid(row=6, column=0, columnspan=3, padx=8, pady=6)
        self._mostrar_prevista()

        # barra de status
        self.status = ttk.Label(self, text="", anchor="w", relief="sunken")
        self.status.pack(fill="x", side="bottom")

    # ----------------- ações -----------------
    def _log(self, txt):
        self.log.insert("end", txt + "\n"); self.log.see("end")

    def _salvar_cfg(self):
        cid = self.e_cid.get().strip(); csec = self.e_csec.get().strip()
        dep = self.e_dep.get().strip() or "Estoque Geral"
        if not cid or not csec:
            messagebox.showwarning("Faltam dados", "Preencha Client ID e Client Secret.")
            return
        gravar_env({"BLING_CLIENT_ID": cid, "BLING_CLIENT_SECRET": csec,
                    "BLING_REDIRECT_URI": REDIRECT_PADRAO, "BLING_DEPOSITO": dep,
                    "BLING_PRAZO_DIAS": (self.e_prazo.get().strip() or "3")})
        self._atualizar_status()
        if hasattr(self, "lbl_prev"):
            self._mostrar_prevista()
        messagebox.showinfo("Pronto", "Credenciais salvas. Agora clique em 'Autorizar Bling'.")

    def _cliente(self):
        env = ler_env()
        return BlingClient(env["BLING_CLIENT_ID"], env["BLING_CLIENT_SECRET"],
                           env.get("BLING_REDIRECT_URI", REDIRECT_PADRAO))

    def _autorizar(self):
        env = ler_env()
        if not env.get("BLING_CLIENT_ID"):
            messagebox.showwarning("Falta configurar", "Salve as credenciais primeiro.")
            return
        client = self._cliente()
        url = client.montar_url_autorizacao()
        webbrowser.open(url)
        messagebox.showinfo("Autorização",
            "Abri o navegador. Faça login e clique em autorizar.\n\n"
            "A página vai redirecionar para um endereço 'localhost' que mostra erro "
            "de conexão — isso é normal. Copie a URL inteira da barra de endereço "
            "e cole na próxima janela.")
        cole = simpledialog.askstring("Cole a URL (ou o código)",
            "Cole aqui a URL que ficou no navegador (ou só o code):")
        if not cole:
            return
        code = parse_qs(urlparse(cole).query).get("code", [cole])[0] if "code=" in cole else cole.strip()
        try:
            client.trocar_code_por_token(code)
            self._atualizar_status()
            messagebox.showinfo("Pronto", "Autorizado com sucesso! O acesso renova sozinho daqui pra frente.")
        except (BlingError, Exception) as e:
            messagebox.showerror("Erro na autorização", str(e))

    def _buscar_contato(self):
        try:
            self._contatos = self._cliente().buscar_contatos(self.e_busca.get().strip())
        except Exception as e:
            messagebox.showerror("Erro", str(e)); return
        self.lst.delete(0, "end")
        for c in self._contatos:
            self.lst.insert("end", f"{c.get('id')}  —  {c.get('nome')}")
        if not self._contatos:
            self.lst.insert("end", "(nenhum contato encontrado)")

    def _usar_contato(self):
        sel = self.lst.curselection()
        if not sel or not self._contatos:
            return
        c = self._contatos[sel[0]]
        gravar_env({"BLING_CONTATO_ID": str(c.get("id"))})
        self._atualizar_status()
        messagebox.showinfo("Pronto", f"Cliente definido: {c.get('nome')} (id {c.get('id')})")

    def _escolher(self):
        f = filedialog.askopenfilename(title="Selecione a planilha",
                                       filetypes=[("Planilhas Excel", "*.xlsx *.xlsm"), ("Todos", "*.*")])
        if f:
            self.arquivo = f
            self.lbl_arq.config(text=os.path.basename(f))

    def _ler_data(self):
        """Lê a data da venda do campo (dd/mm/aaaa); usa hoje se inválida."""
        try:
            return dt.datetime.strptime(self.e_data.get().strip(), "%d/%m/%Y").date()
        except ValueError:
            return dt.date.today()

    def _mostrar_prevista(self):
        env = ler_env()
        prazo = int(env.get("BLING_PRAZO_DIAS", "3") or 3)
        prev = self._ler_data() + dt.timedelta(days=prazo)
        self.lbl_prev.config(text=f"→ prevista: {prev:%d/%m/%Y}  (+{prazo} dias)")

    def _rodar(self):
        if not self.arquivo:
            messagebox.showwarning("Falta a planilha", "Escolha a planilha primeiro.")
            return
        if not self.var_sim.get():
            if not messagebox.askyesno("Confirmar",
                "Isso vai CRIAR pedidos de venda no Bling de verdade.\nDeseja continuar?"):
                return
        self.btn_rodar.config(state="disabled")
        self.log.delete("1.0", "end")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            r = proc.processar(self.arquivo, dry_run=self.var_sim.get(),
                               sem_estoque=self.var_semest.get(),
                               data_venda=self._ler_data(),
                               obs_interna=self.e_obs.get().strip(),
                               emit=lambda t: self.fila.put(("log", t)))
            self.fila.put(("fim", r))
        except Exception as e:
            self.fila.put(("erro", str(e)))

    def _consumir_fila(self):
        try:
            while True:
                tipo, dado = self.fila.get_nowait()
                if tipo == "log":
                    self._log(dado)
                elif tipo == "erro":
                    self._log(f"\n[ERRO] {dado}")
                    messagebox.showerror("Erro", dado)
                    self.btn_rodar.config(state="normal")
                elif tipo == "fim":
                    self.btn_rodar.config(state="normal")
                    if not dado.get("dry_run"):
                        msg = f"{dado['pedidos_ok']}/{dado['blocos']} pedidos criados."
                        if dado.get("pedidos_com_falta"):
                            msg += f"\n{dado['pedidos_com_falta']} pedido(s) com itens faltando (ver coluna laranja)."
                        msg += f"\n\nPlanilha salva em:\n{dado['saida']}"
                        messagebox.showinfo("Concluído", msg)
        except queue.Empty:
            pass
        self.after(150, self._consumir_fila)

    def _atualizar_status(self):
        env = ler_env()
        cred = "OK" if env.get("BLING_CLIENT_ID") and env.get("BLING_CLIENT_SECRET") else "faltando"
        token = "OK" if os.path.exists(os.path.join(PASTA, "tokens.json")) else "não autorizado"
        contato = env.get("BLING_CONTATO_ID") or "não definido"
        self.status.config(text=f"  Credenciais: {cred}    |    Autorização: {token}    |    Cliente fake: {contato}")
        if hasattr(self, "lbl_contato"):
            self.lbl_contato.config(text=f"Cliente fake atual: {contato}")


if __name__ == "__main__":
    App().mainloop()
