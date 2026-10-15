
import tkinter as tk
from tkinter import ttk, messagebox
import pyodbc
import hashlib
import secrets
import hmac
from decimal import Decimal, InvalidOperation
from datetime import datetime


# =========================================================
# CONFIGURACAO DO SQL SERVER
# =========================================================

SERVIDOR = r"DESKTOP-VO24U09\SQLEXPRESS"
BANCO = "SistemaPedidos"
DRIVER = "ODBC Driver 17 for SQL Server"


def conectar_banco():
    return pyodbc.connect(
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={SERVIDOR};"
        f"DATABASE={BANCO};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )


# =========================================================
# SENHAS: HASH COM SAL ALEATORIO
# =========================================================

def gerar_hash_senha(senha):
    sal = secrets.token_bytes(16)
    resultado = hashlib.pbkdf2_hmac(
        "sha256",
        senha.encode("utf-8"),
        sal,
        600000
    )
    return sal.hex() + "$" + resultado.hex()


def verificar_senha(senha, senha_armazenada):
    try:
        sal_hex, hash_hex = senha_armazenada.split("$", 1)
        sal = bytes.fromhex(sal_hex)
        hash_original = bytes.fromhex(hash_hex)

        resultado = hashlib.pbkdf2_hmac(
            "sha256",
            senha.encode("utf-8"),
            sal,
            600000
        )

        return hmac.compare_digest(resultado, hash_original)
    except (ValueError, TypeError):
        return False


# =========================================================
# VARIAVEIS DO SISTEMA
# =========================================================

usuario_logado = None
cliente_selecionado = None
produtos = []
itens_pedido = []
janela = None
tela_login = None


# =========================================================
# FUNCOES AUXILIARES
# =========================================================

def dinheiro(valor):
    valor = Decimal(str(valor))
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def consultar_quantidade_usuarios():
    conexao = conectar_banco()
    try:
        cursor = conexao.cursor()
        cursor.execute("SELECT COUNT(*) FROM Usuarios")
        return cursor.fetchone()[0]
    finally:
        conexao.close()


def salvar_usuario(nome, login, senha, perfil):
    conexao = conectar_banco()
    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO Usuarios (Nome, Login, SenhaHash, Perfil, Ativo)
            VALUES (?, ?, ?, ?, 1)
            """,
            nome,
            login,
            gerar_hash_senha(senha),
            perfil
        )
        conexao.commit()
    finally:
        conexao.close()


def obter_produtos():
    conexao = conectar_banco()
    try:
        cursor = conexao.cursor()
        cursor.execute("""
            SELECT Id, Nome, Preco, Categoria
            FROM Produtos
            WHERE Ativo = 1
            ORDER BY Nome
        """)
        return [
            {
                "id": linha.Id,
                "nome": linha.Nome,
                "preco": Decimal(str(linha.Preco)),
                "categoria": linha.Categoria or ""
            }
            for linha in cursor.fetchall()
        ]
    finally:
        conexao.close()


# =========================================================
# LOGIN E PRIMEIRO ADMINISTRADOR
# =========================================================

def abrir_login():
    global tela_login

    tela_login = tk.Toplevel(janela)
    tela_login.title("Acesso ao sistema")
    tela_login.geometry("400x370")
    tela_login.resizable(False, False)
    tela_login.protocol("WM_DELETE_WINDOW", janela.destroy)

    try:
        primeiro_acesso = consultar_quantidade_usuarios() == 0
    except Exception as erro:
        messagebox.showerror(
            "Erro de conexão",
            "Não consegui acessar o banco de dados.\n\n"
            "Confira o nome do servidor, o banco e as tabelas.\n\n"
            f"Detalhes: {erro}",
            parent=tela_login
        )
        tela_login.destroy()
        janela.destroy()
        return

    if primeiro_acesso:
        mostrar_formulario_primeiro_admin()
    else:
        mostrar_formulario_login()


def limpar_tela_login():
    for widget in tela_login.winfo_children():
        widget.destroy()


def mostrar_formulario_primeiro_admin():
    limpar_tela_login()

    ttk.Label(
        tela_login,
        text="CRIAR PRIMEIRO ADMINISTRADOR",
        font=("Arial", 14, "bold")
    ).pack(pady=(25, 8))

    ttk.Label(
        tela_login,
        text="Crie a conta que administrará o sistema."
    ).pack(pady=(0, 15))

    campos = {}

    for rotulo, chave, ocultar in [
        ("Nome completo", "nome", False),
        ("Login", "login", False),
        ("Senha", "senha", True),
        ("Confirmar senha", "confirmar", True)
    ]:
        ttk.Label(tela_login, text=rotulo).pack(anchor="w", padx=45)
        campo = ttk.Entry(
            tela_login,
            width=36,
            show="*" if ocultar else ""
        )
        campo.pack(padx=45, pady=(2, 8))
        campos[chave] = campo

    def criar_admin():
        nome = campos["nome"].get().strip()
        login = campos["login"].get().strip()
        senha = campos["senha"].get()
        confirmar = campos["confirmar"].get()

        if not nome or not login or not senha:
            messagebox.showwarning(
                "Atenção",
                "Preencha todos os campos.",
                parent=tela_login
            )
            return

        if len(senha) < 8:
            messagebox.showwarning(
                "Senha fraca",
                "Use uma senha com pelo menos 8 caracteres.",
                parent=tela_login
            )
            return

        if senha != confirmar:
            messagebox.showwarning(
                "Atenção",
                "As senhas não são iguais.",
                parent=tela_login
            )
            return

        try:
            # Confere novamente para evitar criar outro primeiro administrador.
            if consultar_quantidade_usuarios() != 0:
                messagebox.showerror(
                    "Atenção",
                    "Já existe um usuário. Faça login.",
                    parent=tela_login
                )
                mostrar_formulario_login()
                return

            salvar_usuario(nome, login, senha, "Administrador")

            messagebox.showinfo(
                "Sucesso",
                "Administrador criado! Agora faça login.",
                parent=tela_login
            )
            mostrar_formulario_login()

        except pyodbc.IntegrityError:
            messagebox.showerror(
                "Erro",
                "Esse login já está sendo utilizado.",
                parent=tela_login
            )
        except Exception as erro:
            messagebox.showerror(
                "Erro",
                f"Não foi possível criar o administrador.\n{erro}",
                parent=tela_login
            )

    ttk.Button(
        tela_login,
        text="Criar administrador",
        command=criar_admin
    ).pack(pady=10)


def mostrar_formulario_login():
    limpar_tela_login()

    ttk.Label(
        tela_login,
        text="SISTEMA DE PEDIDOS",
        font=("Arial", 17, "bold")
    ).pack(pady=(40, 25))

    ttk.Label(tela_login, text="Login").pack()
    campo_login = ttk.Entry(tela_login, width=32)
    campo_login.pack(pady=(3, 12))

    ttk.Label(tela_login, text="Senha").pack()
    campo_senha = ttk.Entry(tela_login, width=32, show="*")
    campo_senha.pack(pady=(3, 18))

    def entrar(event=None):
        global usuario_logado

        login = campo_login.get().strip()
        senha = campo_senha.get()

        if not login or not senha:
            messagebox.showwarning(
                "Atenção",
                "Informe o login e a senha.",
                parent=tela_login
            )
            return

        try:
            conexao = conectar_banco()
            try:
                cursor = conexao.cursor()
                cursor.execute("""
                    SELECT Id, Nome, Login, SenhaHash, Perfil
                    FROM Usuarios
                    WHERE Login = ? AND Ativo = 1
                """, login)
                registro = cursor.fetchone()
            finally:
                conexao.close()

            if not registro or not verificar_senha(
                senha, registro.SenhaHash
            ):
                messagebox.showerror(
                    "Acesso negado",
                    "Login ou senha incorretos.",
                    parent=tela_login
                )
                return

            usuario_logado = {
                "id": registro.Id,
                "nome": registro.Nome,
                "login": registro.Login,
                "perfil": registro.Perfil
            }

            tela_login.destroy()
            janela.deiconify()
            montar_sistema()

        except Exception as erro:
            messagebox.showerror(
                "Erro",
                f"Não foi possível realizar o login.\n\n{erro}",
                parent=tela_login
            )

    ttk.Button(
        tela_login,
        text="Entrar",
        command=entrar
    ).pack()

    campo_senha.bind("<Return>", entrar)
    campo_login.focus_set()


# =========================================================
# JANELA PRINCIPAL
# =========================================================

def montar_sistema():
    for widget in janela.winfo_children():
        widget.destroy()

    janela.title("Sistema de Pedidos")
    janela.geometry("1100x760")
    janela.minsize(900, 650)

    topo = ttk.Frame(janela, padding=10)
    topo.pack(fill="x")

    ttk.Label(
        topo,
        text="SISTEMA DE PEDIDOS",
        font=("Arial", 18, "bold")
    ).pack(side="left")

    ttk.Label(
        topo,
        text=(
            f"Usuário: {usuario_logado['nome']} "
            f"({usuario_logado['perfil']})"
        )
    ).pack(side="right")

    menu = ttk.Frame(janela, padding=(10, 0, 10, 10))
    menu.pack(fill="x")

    ttk.Button(
        menu,
        text="Histórico de pedidos",
        command=abrir_historico
    ).pack(side="left", padx=(0, 8))

    if usuario_logado["perfil"] == "Administrador":
        ttk.Button(
            menu,
            text="Gerenciar usuários",
            command=abrir_usuarios
        ).pack(side="left")

    ttk.Button(
        menu,
        text="Sair",
        command=sair_sistema
    ).pack(side="right")

    # ---------------- CLIENTE ----------------

    quadro_cliente = ttk.LabelFrame(
        janela,
        text="Cliente",
        padding=10
    )
    quadro_cliente.pack(fill="x", padx=10, pady=5)

    ttk.Label(
        quadro_cliente,
        text="Telefone:"
    ).grid(row=0, column=0, sticky="w")

    global campo_telefone, label_cliente

    campo_telefone = ttk.Entry(quadro_cliente, width=25)
    campo_telefone.grid(row=0, column=1, padx=5)

    ttk.Button(
        quadro_cliente,
        text="Buscar cliente",
        command=buscar_cliente
    ).grid(row=0, column=2, padx=5)

    ttk.Button(
        quadro_cliente,
        text="Cadastrar cliente",
        command=abrir_cadastro_cliente
    ).grid(row=0, column=3, padx=5)

    label_cliente = ttk.Label(
        quadro_cliente,
        text="Nenhum cliente selecionado"
    )
    label_cliente.grid(
        row=1, column=0, columnspan=4,
        sticky="w", pady=(8, 0)
    )

    # ---------------- PRODUTOS ----------------

    quadro_produto = ttk.LabelFrame(
        janela,
        text="Adicionar produtos",
        padding=10
    )
    quadro_produto.pack(fill="x", padx=10, pady=5)

    ttk.Label(
        quadro_produto,
        text="Produto:"
    ).grid(row=0, column=0, sticky="w")

    global combo_produto, campo_quantidade

    combo_produto = ttk.Combobox(
        quadro_produto,
        width=45,
        state="readonly"
    )
    combo_produto.grid(row=0, column=1, padx=5)

    ttk.Label(
        quadro_produto,
        text="Quantidade:"
    ).grid(row=0, column=2)

    campo_quantidade = ttk.Entry(
        quadro_produto,
        width=7
    )
    campo_quantidade.insert(0, "1")
    campo_quantidade.grid(row=0, column=3, padx=5)

    ttk.Button(
        quadro_produto,
        text="Adicionar",
        command=adicionar_item
    ).grid(row=0, column=4, padx=5)

    try:
        carregar_produtos()
    except Exception as erro:
        messagebox.showerror(
            "Erro",
            f"Não foi possível carregar os produtos.\n{erro}",
            parent=janela
        )

    # ---------------- ITENS DO PEDIDO ----------------

    quadro_itens = ttk.LabelFrame(
        janela,
        text="Itens do pedido",
        padding=10
    )
    quadro_itens.pack(
        fill="both", expand=True,
        padx=10, pady=5
    )

    colunas = ("produto", "quantidade", "preco", "subtotal")
    global tabela_itens

    tabela_itens = ttk.Treeview(
        quadro_itens,
        columns=colunas,
        show="headings",
        height=10
    )

    tabela_itens.heading("produto", text="Produto")
    tabela_itens.heading("quantidade", text="Quantidade")
    tabela_itens.heading("preco", text="Preço unitário")
    tabela_itens.heading("subtotal", text="Subtotal")

    tabela_itens.column("produto", width=400)
    tabela_itens.column("quantidade", width=110, anchor="center")
    tabela_itens.column("preco", width=150, anchor="e")
    tabela_itens.column("subtotal", width=150, anchor="e")

    tabela_itens.pack(fill="both", expand=True)

    linha_acoes = ttk.Frame(quadro_itens)
    linha_acoes.pack(fill="x", pady=8)

    ttk.Button(
        linha_acoes,
        text="Remover item selecionado",
        command=remover_item
    ).pack(side="left")

    global label_total

    label_total = ttk.Label(
        linha_acoes,
        text="TOTAL: R$ 0,00",
        font=("Arial", 15, "bold")
    )
    label_total.pack(side="right")

    # ---------------- PAGAMENTO E ORIGEM ----------------

    quadro_final = ttk.LabelFrame(
        janela,
        text="Finalizar pedido",
        padding=10
    )
    quadro_final.pack(fill="x", padx=10, pady=5)

    global combo_origem, combo_pagamento

    ttk.Label(quadro_final, text="Origem:").grid(
        row=0, column=0, sticky="w"
    )
    combo_origem = ttk.Combobox(
        quadro_final,
        values=["Telefone", "WhatsApp", "Sistema próprio", "iFood"],
        state="readonly",
        width=20
    )
    combo_origem.set("WhatsApp")
    combo_origem.grid(row=0, column=1, padx=5)

    ttk.Label(quadro_final, text="Pagamento:").grid(
        row=0, column=2, sticky="w", padx=(15, 0)
    )
    combo_pagamento = ttk.Combobox(
        quadro_final,
        values=[
            "Pix", "Dinheiro", "Cartão de crédito",
            "Cartão de débito", "A definir"
        ],
        state="readonly",
        width=22
    )
    combo_pagamento.set("A definir")
    combo_pagamento.grid(row=0, column=3, padx=5)

    ttk.Button(
        quadro_final,
        text="Salvar pedido",
        command=salvar_pedido
    ).grid(row=0, column=4, padx=15)


def sair_sistema():
    global usuario_logado, cliente_selecionado, itens_pedido

    if not messagebox.askyesno(
        "Sair",
        "Deseja sair do sistema?",
        parent=janela
    ):
        return

    usuario_logado = None
    cliente_selecionado = None
    itens_pedido.clear()

    janela.withdraw()
    abrir_login()


# =========================================================
# CLIENTES
# =========================================================

def buscar_cliente():
    global cliente_selecionado

    telefone = campo_telefone.get().strip()
    if not telefone:
        messagebox.showwarning(
            "Atenção",
            "Digite o telefone do cliente.",
            parent=janela
        )
        return

    # Ignora espaços e pontuação para facilitar a busca.
    numero = "".join(c for c in telefone if c.isdigit())

    conexao = conectar_banco()
    try:
        cursor = conexao.cursor()
        cursor.execute("""
            SELECT TOP 1 Id, Nome, Telefone
            FROM Clientes
            WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                Telefone, '(', ''), ')', ''), '-', ''), ' ', ''), '+', '')
                LIKE ?
            ORDER BY Id DESC
        """, "%" + numero)

        registro = cursor.fetchone()
    finally:
        conexao.close()

    if not registro:
        cliente_selecionado = None
        label_cliente.config(text="Cliente não encontrado.")
        messagebox.showinfo(
            "Cliente",
            "Não encontrei esse cliente. Você pode cadastrá-lo.",
            parent=janela
        )
        return

    cliente_selecionado = {
        "id": registro.Id,
        "nome": registro.Nome,
        "telefone": registro.Telefone
    }

    label_cliente.config(
        text=f"Selecionado: {registro.Nome} | {registro.Telefone}"
    )


def abrir_cadastro_cliente():
    cadastro = tk.Toplevel(janela)
    cadastro.title("Cadastrar cliente")
    cadastro.geometry("430x410")
    cadastro.transient(janela)
    cadastro.grab_set()

    campos = {}

    definicoes = [
        ("Nome:", "nome"),
        ("Telefone:", "telefone"),
        ("WhatsApp:", "whatsapp"),
        ("Endereço:", "endereco"),
        ("Observação:", "observacao")
    ]

    for linha, (rotulo, chave) in enumerate(definicoes):
        ttk.Label(cadastro, text=rotulo).grid(
            row=linha, column=0, padx=10, pady=8, sticky="w"
        )
        campo = ttk.Entry(cadastro, width=38)
        campo.grid(row=linha, column=1, padx=10, pady=8)
        campos[chave] = campo

    def salvar_cliente():
        global cliente_selecionado

        nome = campos["nome"].get().strip()
        telefone = campos["telefone"].get().strip()

        if not nome or not telefone:
            messagebox.showwarning(
                "Atenção",
                "Nome e telefone são obrigatórios.",
                parent=cadastro
            )
            return

        conexao = conectar_banco()
        try:
            cursor = conexao.cursor()
            cursor.execute("""
                INSERT INTO Clientes
                    (Nome, Telefone, WhatsApp, Endereco,
                     Observacao, UsuarioCadastroId)
                OUTPUT INSERTED.Id
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                nome,
                telefone,
                campos["whatsapp"].get().strip(),
                campos["endereco"].get().strip(),
                campos["observacao"].get().strip(),
                usuario_logado["id"]
            )

            cliente_id = cursor.fetchone()[0]
            conexao.commit()

            cliente_selecionado = {
                "id": cliente_id,
                "nome": nome,
                "telefone": telefone
            }

            campo_telefone.delete(0, tk.END)
            campo_telefone.insert(0, telefone)
            label_cliente.config(
                text=f"Selecionado: {nome} | {telefone}"
            )

            messagebox.showinfo(
                "Sucesso",
                "Cliente cadastrado!",
                parent=cadastro
            )
            cadastro.destroy()

        except Exception as erro:
            conexao.rollback()
            messagebox.showerror(
                "Erro",
                f"Não foi possível cadastrar o cliente.\n\n{erro}",
                parent=cadastro
            )
        finally:
            conexao.close()

    ttk.Button(
        cadastro,
        text="Salvar cliente",
        command=salvar_cliente
    ).grid(row=len(definicoes), column=1, pady=15, sticky="e")


# =========================================================
# PRODUTOS E ITENS DO PEDIDO
# =========================================================

def carregar_produtos():
    global produtos

    produtos = obter_produtos()
    combo_produto["values"] = [
        f"{p['nome']} - {dinheiro(p['preco'])}"
        for p in produtos
    ]

    if produtos:
        combo_produto.current(0)


def atualizar_tabela_itens():
    for item in tabela_itens.get_children():
        tabela_itens.delete(item)

    total = Decimal("0.00")

    for indice, item in enumerate(itens_pedido):
        subtotal = item["preco"] * item["quantidade"]
        total += subtotal

        tabela_itens.insert(
            "",
            "end",
            iid=str(indice),
            values=(
                item["nome"],
                item["quantidade"],
                dinheiro(item["preco"]),
                dinheiro(subtotal)
            )
        )

    label_total.config(text=f"TOTAL: {dinheiro(total)}")


def adicionar_item():
    if not produtos or combo_produto.current() < 0:
        messagebox.showwarning(
            "Atenção",
            "Cadastre ou selecione um produto ativo.",
            parent=janela
        )
        return

    try:
        quantidade = int(campo_quantidade.get())
        if quantidade <= 0:
            raise ValueError
    except ValueError:
        messagebox.showwarning(
            "Quantidade inválida",
            "Digite uma quantidade inteira maior que zero.",
            parent=janela
        )
        return

    produto = produtos[combo_produto.current()]

    itens_pedido.append({
        "id": produto["id"],
        "nome": produto["nome"],
        "preco": produto["preco"],
        "quantidade": quantidade
    })

    atualizar_tabela_itens()
    campo_quantidade.delete(0, tk.END)
    campo_quantidade.insert(0, "1")


def remover_item():
    selecao = tabela_itens.selection()

    if not selecao:
        messagebox.showwarning(
            "Atenção",
            "Selecione o item que deseja remover.",
            parent=janela
        )
        return

    indice = int(selecao[0])

    if 0 <= indice < len(itens_pedido):
        itens_pedido.pop(indice)

    atualizar_tabela_itens()


def salvar_pedido():
    global cliente_selecionado
    if not cliente_selecionado:
        messagebox.showwarning(
            "Atenção",
            "Busque ou cadastre um cliente antes de salvar.",
            parent=janela
        )
        return

    if not itens_pedido:
        messagebox.showwarning(
            "Atenção",
            "Adicione pelo menos um produto.",
            parent=janela
        )
        return

    origem = combo_origem.get()
    pagamento = combo_pagamento.get()

    total = sum(
        (item["preco"] * item["quantidade"] for item in itens_pedido),
        Decimal("0.00")
    )

    conexao = None

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()

        cursor.execute("""
            INSERT INTO Pedidos
                (ClienteId, Origem, Status, FormaPagamento,
                 ValorTotal, UsuarioId)
            OUTPUT INSERTED.Id
            VALUES (?, ?, 'Pendente', ?, ?, ?)
        """,
            cliente_selecionado["id"],
            origem,
            pagamento,
            total,
            usuario_logado["id"]
        )

        pedido_id = cursor.fetchone()[0]

        for item in itens_pedido:
            cursor.execute("""
                INSERT INTO ItensPedido
                    (PedidoId, ProdutoId, Quantidade, PrecoUnitario)
                VALUES (?, ?, ?, ?)
            """,
                pedido_id,
                item["id"],
                item["quantidade"],
                item["preco"]
            )

        conexao.commit()

        messagebox.showinfo(
            "Pedido salvo",
            f"Pedido #{pedido_id} salvo com sucesso!\n"
            f"Total: {dinheiro(total)}",
            parent=janela
        )

        itens_pedido.clear()
        atualizar_tabela_itens()

        cliente_selecionado = None
        label_cliente.config(text="Nenhum cliente selecionado")
        campo_telefone.delete(0, tk.END)

    except Exception as erro:
        if conexao:
            conexao.rollback()

        messagebox.showerror(
            "Erro",
            f"Não foi possível salvar o pedido.\n\n{erro}",
            parent=janela
        )
    finally:
        if conexao:
            conexao.close()


# =========================================================
# HISTORICO, STATUS, EXCLUSAO E CANCELAMENTO
# =========================================================

def abrir_historico():
    historico = tk.Toplevel(janela)
    historico.title("Histórico de pedidos")
    historico.geometry("1100x650")

    colunas = (
        "id", "cliente", "data", "origem",
        "status", "total", "usuario"
    )

    tabela = ttk.Treeview(
        historico,
        columns=colunas,
        show="headings",
        height=12
    )

    titulos = {
        "id": "Pedido",
        "cliente": "Cliente",
        "data": "Data",
        "origem": "Origem",
        "status": "Status",
        "total": "Total",
        "usuario": "Funcionário"
    }

    larguras = {
        "id": 70,
        "cliente": 190,
        "data": 150,
        "origem": 100,
        "status": 140,
        "total": 100,
        "usuario": 170
    }

    for coluna in colunas:
        tabela.heading(coluna, text=titulos[coluna])
        tabela.column(
            coluna,
            width=larguras[coluna],
            anchor="w"
        )

    tabela.pack(fill="both", expand=True, padx=10, pady=10)

    def carregar_historico():
        for item in tabela.get_children():
            tabela.delete(item)

        conexao = conectar_banco()
        try:
            cursor = conexao.cursor()
            cursor.execute("""
                SELECT
                    P.Id,
                    C.Nome,
                    P.DataPedido,
                    P.Origem,
                    P.Status,
                    P.ValorTotal,
                    U.Nome
                FROM Pedidos P
                INNER JOIN Clientes C ON C.Id = P.ClienteId
                LEFT JOIN Usuarios U ON U.Id = P.UsuarioId
                ORDER BY P.Id DESC
            """)

            for linha in cursor.fetchall():
                data = (
                    linha.DataPedido.strftime("%d/%m/%Y %H:%M")
                    if linha.DataPedido else ""
                )

                tabela.insert(
                    "",
                    "end",
                    iid=str(linha.Id),
                    values=(
                        linha.Id,
                        linha.Nome,
                        data,
                        linha.Origem or "",
                        linha.Status or "",
                        dinheiro(linha.ValorTotal or 0),
                        linha[6] or "Não identificado"
                    )
                )
        finally:
            conexao.close()

    def pedido_selecionado():
        selecao = tabela.selection()
        if not selecao:
            messagebox.showwarning(
                "Atenção",
                "Selecione um pedido.",
                parent=historico
            )
            return None
        return int(selecao[0])

    def ver_itens():
        pedido_id = pedido_selecionado()
        if pedido_id is None:
            return

        conexao = conectar_banco()
        try:
            cursor = conexao.cursor()
            cursor.execute("""
                SELECT PR.Nome, I.Quantidade, I.PrecoUnitario,
                       I.Quantidade * I.PrecoUnitario AS Subtotal
                FROM ItensPedido I
                INNER JOIN Produtos PR ON PR.Id = I.ProdutoId
                WHERE I.PedidoId = ?
            """, pedido_id)

            linhas = cursor.fetchall()
        finally:
            conexao.close()

        detalhe = tk.Toplevel(historico)
        detalhe.title(f"Itens do pedido #{pedido_id}")
        detalhe.geometry("600x350")

        tabela_detalhe = ttk.Treeview(
            detalhe,
            columns=("produto", "qtd", "preco", "subtotal"),
            show="headings"
        )

        for coluna, titulo, largura in [
            ("produto", "Produto", 250),
            ("qtd", "Quantidade", 90),
            ("preco", "Preço unitário", 120),
            ("subtotal", "Subtotal", 120)
        ]:
            tabela_detalhe.heading(coluna, text=titulo)
            tabela_detalhe.column(coluna, width=largura)

        tabela_detalhe.pack(fill="both", expand=True, padx=10, pady=10)

        for linha in linhas:
            tabela_detalhe.insert(
                "",
                "end",
                values=(
                    linha.Nome,
                    linha.Quantidade,
                    dinheiro(linha.PrecoUnitario),
                    dinheiro(linha.Subtotal)
                )
            )

    def atualizar_status():
        pedido_id = pedido_selecionado()
        if pedido_id is None:
            return

        status = combo_status.get()
        if not status:
            return

        conexao = conectar_banco()
        try:
            cursor = conexao.cursor()
            cursor.execute(
                "UPDATE Pedidos SET Status = ? WHERE Id = ?",
                status, pedido_id
            )
            conexao.commit()
        except Exception as erro:
            conexao.rollback()
            messagebox.showerror(
                "Erro",
                str(erro),
                parent=historico
            )
        finally:
            conexao.close()

        carregar_historico()

    def excluir_ou_cancelar():
        pedido_id = pedido_selecionado()
        if pedido_id is None:
            return

        conexao = conectar_banco()
        try:
            cursor = conexao.cursor()
            cursor.execute(
                "SELECT Status FROM Pedidos WHERE Id = ?",
                pedido_id
            )
            registro = cursor.fetchone()
        finally:
            conexao.close()

        if not registro:
            messagebox.showerror(
                "Erro",
                "Pedido não encontrado.",
                parent=historico
            )
            return

        status_atual = registro.Status or ""

        if status_atual == "Pendente":
            confirmar = messagebox.askyesno(
                "Excluir pedido",
                f"Excluir permanentemente o pedido #{pedido_id}?\n"
                "Essa ação não poderá ser desfeita.",
                parent=historico
            )

            if not confirmar:
                return

            conexao = conectar_banco()
            try:
                cursor = conexao.cursor()
                cursor.execute(
                    "DELETE FROM ItensPedido WHERE PedidoId = ?",
                    pedido_id
                )
                cursor.execute(
                    "DELETE FROM Pedidos WHERE Id = ?",
                    pedido_id
                )
                conexao.commit()
            except Exception as erro:
                conexao.rollback()
                messagebox.showerror(
                    "Erro",
                    f"Não foi possível excluir.\n{erro}",
                    parent=historico
                )
                return
            finally:
                conexao.close()

        else:
            confirmar = messagebox.askyesno(
                "Cancelar pedido",
                f"O pedido #{pedido_id} já não está pendente.\n"
                "Deseja alterar o status para Cancelado e manter "
                "o histórico?",
                parent=historico
            )

            if not confirmar:
                return

            conexao = conectar_banco()
            try:
                cursor = conexao.cursor()
                cursor.execute(
                    "UPDATE Pedidos SET Status = 'Cancelado' WHERE Id = ?",
                    pedido_id
                )
                conexao.commit()
            except Exception as erro:
                conexao.rollback()
                messagebox.showerror(
                    "Erro",
                    str(erro),
                    parent=historico
                )
                return
            finally:
                conexao.close()

        carregar_historico()

    barra = ttk.Frame(historico, padding=10)
    barra.pack(fill="x")

    ttk.Button(
        barra,
        text="Ver itens",
        command=ver_itens
    ).pack(side="left", padx=4)

    ttk.Label(
        barra,
        text="Novo status:"
    ).pack(side="left", padx=(12, 4))

    global combo_status
    combo_status = ttk.Combobox(
        barra,
        values=[
            "Pendente",
            "Em preparo",
            "Saiu para entrega",
            "Concluido",
            "Cancelado"
        ],
        state="readonly",
        width=20
    )
    combo_status.set("Pendente")
    combo_status.pack(side="left", padx=4)

    ttk.Button(
        barra,
        text="Atualizar status",
        command=atualizar_status
    ).pack(side="left", padx=4)

    ttk.Button(
        barra,
        text="Excluir / cancelar",
        command=excluir_ou_cancelar
    ).pack(side="left", padx=4)

    ttk.Button(
        barra,
        text="Atualizar lista",
        command=carregar_historico
    ).pack(side="right", padx=4)

    carregar_historico()


# =========================================================
# GERENCIAMENTO DE USUARIOS (ADMINISTRADOR)
# =========================================================

def abrir_usuarios():
    if usuario_logado["perfil"] != "Administrador":
        messagebox.showerror(
            "Acesso negado",
            "Somente o administrador pode gerenciar usuários.",
            parent=janela
        )
        return

    tela = tk.Toplevel(janela)
    tela.title("Gerenciar usuários")
    tela.geometry("800x520")

    colunas = ("id", "nome", "login", "perfil", "ativo")
    tabela = ttk.Treeview(
        tela,
        columns=colunas,
        show="headings",
        height=10
    )
    for coluna, titulo, largura in [
        ("id", "ID", 60),
        ("nome", "Nome", 240),
        ("login", "Login", 180),
        ("perfil", "Perfil", 150),
        ("ativo", "Ativo", 90)
    ]:
        tabela.heading(coluna, text=titulo)
        tabela.column(coluna, width=largura)

    tabela.pack(fill="both", expand=True, padx=10, pady=10)

    def carregar_usuarios():
        for item in tabela.get_children():
            tabela.delete(item)

        conexao = conectar_banco()
        try:
            cursor = conexao.cursor()
            cursor.execute("""
                SELECT Id, Nome, Login, Perfil, Ativo
                FROM Usuarios
                ORDER BY Nome
            """)
            for linha in cursor.fetchall():
                tabela.insert(
                    "",
                    "end",
                    iid=str(linha.Id),
                    values=(
                        linha.Id,
                        linha.Nome,
                        linha.Login,
                        linha.Perfil,
                        "Sim" if linha.Ativo else "Não"
                    )
                )
        finally:
            conexao.close()

    def criar_usuario():
        formulario = tk.Toplevel(tela)
        formulario.title("Novo usuário")
        formulario.geometry("370x350")
        formulario.transient(tela)
        formulario.grab_set()

        campos = {}
        for linha, rotulo, chave in [
            (0, "Nome", "nome"),
            (1, "Login", "login"),
            (2, "Senha (mínimo 8 caracteres)", "senha")
        ]:
            ttk.Label(formulario, text=rotulo).grid(
                row=linha, column=0, padx=10, pady=10, sticky="w"
            )
            campo = ttk.Entry(
                formulario,
                width=28,
                show="*" if chave == "senha" else ""
            )
            campo.grid(row=linha, column=1, padx=10, pady=10)
            campos[chave] = campo

        ttk.Label(formulario, text="Perfil").grid(
            row=3, column=0, padx=10, pady=10, sticky="w"
        )
        perfil = ttk.Combobox(
            formulario,
            values=["Atendente", "Administrador"],
            state="readonly",
            width=25
        )
        perfil.set("Atendente")
        perfil.grid(row=3, column=1, padx=10, pady=10)

        def gravar():
            nome = campos["nome"].get().strip()
            login = campos["login"].get().strip()
            senha = campos["senha"].get()

            if not nome or not login or not senha:
                messagebox.showwarning(
                    "Atenção",
                    "Preencha todos os campos.",
                    parent=formulario
                )
                return

            if len(senha) < 8:
                messagebox.showwarning(
                    "Senha fraca",
                    "A senha precisa ter pelo menos 8 caracteres.",
                    parent=formulario
                )
                return

            try:
                salvar_usuario(nome, login, senha, perfil.get())
                messagebox.showinfo(
                    "Sucesso",
                    "Usuário cadastrado.",
                    parent=formulario
                )
                formulario.destroy()
                carregar_usuarios()

            except pyodbc.IntegrityError:
                messagebox.showerror(
                    "Erro",
                    "Esse login já existe.",
                    parent=formulario
                )
            except Exception as erro:
                messagebox.showerror(
                    "Erro",
                    str(erro),
                    parent=formulario
                )

        ttk.Button(
            formulario,
            text="Cadastrar usuário",
            command=gravar
        ).grid(row=4, column=1, pady=15, sticky="e")

    def alternar_ativo():
        selecao = tabela.selection()
        if not selecao:
            messagebox.showwarning(
                "Atenção",
                "Selecione um usuário.",
                parent=tela
            )
            return

        usuario_id = int(selecao[0])

        if usuario_id == usuario_logado["id"]:
            messagebox.showwarning(
                "Atenção",
                "Você não pode desativar a própria conta.",
                parent=tela
            )
            return

        conexao = conectar_banco()
        try:
            cursor = conexao.cursor()
            cursor.execute(
                "SELECT Ativo FROM Usuarios WHERE Id = ?",
                usuario_id
            )
            registro = cursor.fetchone()

            if not registro:
                return

            novo_ativo = 0 if registro.Ativo else 1

            cursor.execute(
                "UPDATE Usuarios SET Ativo = ? WHERE Id = ?",
                novo_ativo, usuario_id
            )
            conexao.commit()

        except Exception as erro:
            conexao.rollback()
            messagebox.showerror("Erro", str(erro), parent=tela)
        finally:
            conexao.close()

        carregar_usuarios()

    botoes = ttk.Frame(tela, padding=10)
    botoes.pack(fill="x")

    ttk.Button(
        botoes,
        text="Cadastrar usuário",
        command=criar_usuario
    ).pack(side="left", padx=5)

    ttk.Button(
        botoes,
        text="Ativar / desativar selecionado",
        command=alternar_ativo
    ).pack(side="left", padx=5)

    ttk.Button(
        botoes,
        text="Atualizar",
        command=carregar_usuarios
    ).pack(side="right", padx=5)

    carregar_usuarios()


# =========================================================
# INICIAR A APLICACAO
# =========================================================

janela = tk.Tk()
janela.withdraw()
abrir_login()
janela.mainloop()
