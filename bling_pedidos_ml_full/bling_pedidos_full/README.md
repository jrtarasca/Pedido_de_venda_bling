# Robô de Pedidos de Venda — Conferência ML Full (Bling API v3)

Cria pedidos de venda no Bling a partir da sua planilha de conferência:
agrupa os SKUs em **blocos separados por linha em branco** (cada bloco = 1 pedido),
reserva o estoque no depósito **Estoque Geral** e devolve a planilha preenchida.

- **Coluna B** = número do pedido criado
- **Coluna H** = quantidade efetivamente reservada (o que deu, se faltar estoque)
- Itens com reserva abaixo do planejado ficam **destacados em laranja** + relatório de faltas

---

## Jeito fácil: pela INTERFACE (sem terminal)

### Passo 0 — Instalar (só na primeira vez)
- Tenha o **Python** instalado (python.org; no Windows marque "Add Python to PATH").
- **Windows:** dê dois cliques em **"Instalar (primeira vez).bat"**.
- **Mac/Linux:** abra o terminal na pasta e rode `pip install -r requirements.txt`.

### Abrir o programa
- **Windows:** dois cliques em **"Abrir Interface.bat"**.
- **Mac/Linux:** `python gui.py`

Vai abrir uma janela com 3 abas:

**Aba 1 — Configuração (só na 1ª vez)**
1. Cole o **Client ID** e o **Client Secret** (veja abaixo como criar) e clique em *Salvar credenciais*.
2. Clique em **Autorizar Bling**: abre o navegador, você faz login e autoriza.
   A página vai para um endereço `localhost` que mostra **erro de conexão — é normal**.
   Copie a URL inteira da barra de endereço e cole na janelinha que aparecer.

**Aba 2 — Cliente fake**
- Digite o nome do cliente que você já usa hoje (ex.: "Mercado Livre Full"), clique
  em *Buscar*, selecione na lista e clique em *Usar selecionado*.

**Aba 3 — Rodar**
- Clique em **Escolher planilha...** e selecione o arquivo (de qualquer pasta — não
  precisa "colocar" em lugar nenhum).
- **Data da venda:** vem com a data de hoje (pode editar). A **data prevista** é
  calculada automaticamente (data da venda + prazo, padrão 3 dias) e a **data de
  saída** fica igual à data da venda.
- **Observação interna:** digite o nº do Full do mês (ex.: "ENVIO FULL 03"); vale
  para todos os pedidos daquele envio.
- Deixe marcado **"Apenas simular"** na primeira vez (mostra os blocos sem criar nada).
- Clique em **▶ RODAR**. O progresso aparece na própria tela.
- Ao terminar, a planilha preenchida é salva **na mesma pasta da planilha original**
  (botão *Abrir pasta dos resultados*).

> A barra inferior mostra o status: Credenciais / Autorização / Cliente fake.

---

## Como criar o aplicativo no Bling (gera Client ID e Client Secret)

1. No Bling: **Central de Extensões → Área do Integrador**
   (ou `https://www.bling.com.br/cadastro.aplicativos.php`).
2. **Criar aplicativo**. Nome: "Robô Pedidos Full".
3. **URL de redirecionamento:** `http://localhost:3000/callback`
4. **Escopos:** Pedidos de Venda, Produtos, Contatos, Controle de Estoque / Depósitos.
5. Salve e copie o **Client Id** e o **Client Secret** (ícone de olho revela o secret).

---

## Quando falta estoque
O robô reserva **o que for possível** e sinaliza de 3 formas:
- **Planilha:** células da coluna H abaixo do planejado em **laranja**.
- **Tela:** resumo dos pedidos com itens faltando.
- **`faltas_<data>.csv`:** detalhe por SKU (planejado, reservado, faltou, motivo).

## Pela linha de comando (alternativa)
```bash
python processar_planilha.py --arquivo entrada.xlsx --dry-run   # simula
python processar_planilha.py --arquivo entrada.xlsx             # cria de verdade
```

## Problemas comuns
- **"No module named tkinter"**: no Windows, reinstale o Python marcando "tcl/tk";
  no Linux, `sudo apt install python3-tk`.
- **Erro na autorização**: refaça o passo *Autorizar Bling* (o `code` vale poucos minutos).
- **Depósito não encontrado**: confira o nome exato em *Configuração* (padrão "Estoque Geral").

## Pontos a validar no 1º envio real (rode com 1–2 blocos antes)
1. **Número em B**: vem do `numero` que o Bling devolve ao criar o pedido.
2. **Reserva no Estoque Geral**: automática ao criar; a quantidade é limitada ao saldo desse depósito.
3. **Saldo**: usa o virtual (disponível) por padrão.

## Arquivos
| Arquivo                  | Função                                          |
|--------------------------|-------------------------------------------------|
| `gui.py`                 | **Interface gráfica** (jeito fácil)             |
| `Abrir Interface.bat`    | Atalho Windows para abrir a interface           |
| `processar_planilha.py`  | Motor (também roda por terminal)                |
| `bling_client.py`        | Cliente da API (auth, estoque, pedidos)         |
| `autorizar.py` / `buscar_contato.py` | Versões de terminal (opcionais)     |

> Nunca compartilhe o `.env` nem o `tokens.json` (contêm segredos).
