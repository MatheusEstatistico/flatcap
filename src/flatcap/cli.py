"""
Interface de linha de comando do FlatCap.

Esta camada não contém regras de negócio: 
    ela lê argumentos, chama as camadas de baixo, 
    formata a saída e escolhe o código de saída do processo.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from . import __version__
from .config import Config, ConfigError, carregar
from .dados import (
    ArquivoOrigemError,
    DadosError,
    LinhaDoTempo,
    PlanoDados,
    VersaoDuplicadaError,
    executar_adicao,
    linha_do_tempo,
    preparar_adicao,
)
from .dicionario import DicionarioError
from .ficha import IMPLEMENTACAO, FichaError, localizar_projeto
from .modelo import (
    ALUNO,
    CAMPO_ANEXO,
    CAMPOS_REDCAP,
    INDEFINIDO,
    Cliente,
    mais_recentes,
    normalizar_varios,
)
from .nomes import caminho_do_projeto, projetos_do_cliente, rotulo_do_projeto
from .projeto import (
    ARQUIVO_HISTORICO,
    ARQUIVO_PROJETO,
    PASTA_ANALISES,
    PASTA_ANTIGAS,
    PASTA_DADOS,
    ClienteIncompletoError,
    LayoutAntigoError,
    Plano,
    ProjetoExistenteError,
    RegistroNaoEncontradoError,
    executar,
    preparar,
    tamanho_legivel,
)
from .redcap import RedcapError, exportar_projeto, exportar_registros, tem_arquivo

if TYPE_CHECKING:  # só para as anotações: ver o comentário em `perfil`
    from .descritiva import Descritiva, PlanoDescritiva
    from .normalidade import Normalidade, PlanoNormalidade
    from .perfil import Achado, Perfil, PlanoPerfil
    from .relatorio import PlanoRelatorio, Relatorio

app = typer.Typer(
    name="flatcap",
    help="Orquestrador de fluxo para atendimento estatistico",
    no_args_is_help=True,
    add_completion=False,
)

dados_app = typer.Typer(
    name="dados",
    help="Versões do banco de dados de um projeto.",
    no_args_is_help=True,
)
app.add_typer(dados_app, name="dados")

console = Console()
erro_console = Console(stderr = True)

OK = "[green]OK[/green]"
FALHA = "[red]FALHA[/red]"

def _versao(valor: bool) -> None:
    if valor:
        console.print(f"flatcap {__version__}")
        raise typer.Exit()

def _plural(quantidade: int, singular: str, plural: str) -> str:
    """
    Devolve o substantivo já concordado com o número.
    """
    return singular if quantidade == 1 else plural

def _abortar(titulo: str, mensagem: str) -> typer.Exit:
    """
    Imprime o erro em um painel e devolve a exceção que encerra o comando.

    `Text(...)` em vez de uma string crua:
        impede que colchetes vindos da mensagem
        de erro sejam interpretados como marcação do rich.
    """
    erro_console.print(Panel(Text(mensagem), title=titulo, border_style="red"))
    return typer.Exit(code=1)

def _nada_a_fazer(mensagem: str) -> None:
    """
    Painel amarelo e saída com código 0: houve uma recusa, mas nada deu errado.
    """
    console.print(Panel(Text(mensagem), title = "Nada para fazer", border_style = "yellow"))

def _configuracao(env: str | None, criar_root: bool = False) -> Config:
    """
    Carrega a configuração ou encerra o comando com a mensagem do `config.py`.
    """
    try:
        return carregar(env_file = env, criar_root = criar_root)
    except ConfigError as erro:
        raise _abortar("Configuração", str(erro)) from erro

@app.callback()
def principal(
    _: bool = typer.Option(
        False, "--version", "-V", callback = _versao, is_eager = True,
        help = "Mostra a versão e sai."
    ),
) -> None:
    """
    Ponto de entrada. Existe para hospedar as opções globais.
    """

@app.command()
def doctor(
    criar_root: bool = typer.Option(
        False, "--criar-root",
        help = "Cria a pasta FLATCAP_ROOT se ela ainda não existir."
    ),
    env: str | None = typer.Option(
        None, "--env",
        help = "Caminho de um .env alternativo."
    ),
) -> None:
    """
    Testar as credenciais, a conexão com o REDCap e a pasta de dados.
    Responde se o problema está na configuração, na rede ou no token.
    """
    tabela = Table(show_header = True, header_style = "bold")
    tabela.add_column("Verificação", no_wrap = True)
    tabela.add_column("Resultado")
    tabela.add_column("Detalhe", overflow = "fold")

    # 1. Configuração
    cfg = _configuracao(env, criar_root = criar_root)

    tabela.add_row("Arquivo .env", OK, cfg.origem_env or "(variáveis do ambiente do sistema)")
    tabela.add_row("REDCAP_API_URL", OK, cfg.api_url)
    tabela.add_row("REDCAP_TOKEN", OK, cfg.token_mascarado)
    tabela.add_row("FLATCAP_ROOT", OK, str(cfg.root))
    tabela.add_row("Leitura do projeto.yaml", OK, IMPLEMENTACAO)

    instaladas, faltando = _bibliotecas()
    linha = " · ".join(f"{nome} {versao}" for nome, versao in instaladas)
    if faltando:
        quais = ", ".join(f"`{nome}`" for nome in faltando)
        tabela.add_row(
            "Leitura de bancos", FALHA, f"falta {quais} — instaladas: {linha or '(nenhuma)'}"
        )
    else:
        tabela.add_row("Leitura de bancos", OK, linha)

    # 2. Conexão com o REDCap
    try:
        projeto = exportar_projeto(cfg)
    except RedcapError as e:
        tabela.add_row("Conexão REDCap", FALHA, "ver detalhe abaixo")
        console.print(tabela)
        raise _abortar("Conexão com o REDCap", str(e)) from e

    titulo = projeto.get("project_title", "(sem título)")
    tabela.add_row("Conexão REDCap", OK, f"{titulo} (id {projeto.get('project_id', '?')})")

    console.print(tabela)

    # A instalação incompleta é diagnosticada **depois** da tabela inteira, e não
    # no lugar dela: saber que a rede está de pé faz parte do diagnóstico mesmo
    # quando falta biblioteca. O `doctor` é o comando que responde "o que está
    # errado?" — ele não pode morrer no meio do próprio diagnóstico.
    if faltando:
        quais = ", ".join(f"`{nome}`" for nome in faltando)
        raise _abortar(
            "Instalação incompleta",
            f"Falta {quais}. Sem isso o FlatCap não abre o banco, não desenha os "
            "gráficos ou não escreve o relatório.\n\n"
            "Da raiz do repositório, com o .venv ativado:\n\n"
            '    pip install -e ".[dev]"'
        )

    console.print(f"\n[green]Tudo certo.[/green] Projeto conectado: [bold]{titulo}[/bold]")

# As bibliotecas que abrem o banco, calculam, desenham e escrevem o documento.
# A ordem é a do fluxo: ler, calcular, desenhar, entregar.
#
# O `scipy` entrou na Fase 7 e é a primeira dependência nova desde a Fase 6. Ele
# está aqui pelo mesmo motivo que os outros quatro: uma biblioteca que falta
# precisa sair como `FALHA` nesta tabela, e não como `ModuleNotFoundError` no meio
# de um comando — foi assim que o `matplotlib` derrubou o `doctor` na Fase 5, no
# comando que existe justamente para responder "o que está errado?".
_BIBLIOTECAS = ("pandas", "openpyxl", "scipy", "matplotlib", "docx")

# `import docx` é o pacote `python-docx`, e o nome de instalação não é o nome de
# import. Quem lê "falta `docx`" no terminal vai procurar por `docx` no pip e
# instalar outro pacote — que existe, e não é este.
_NOME_NO_PIP = {"docx": "python-docx"}


def _bibliotecas() -> tuple[list[tuple[str, str]], list[str]]:
    """
    Quais versões abrem o banco, desenham os gráficos e escrevem o documento hoje.

    Registrar isso no `doctor` é barato e evita a pergunta mais difícil de
    responder da Fase 5: um gráfico saiu diferente do que saía antes — mudaram os
    dados ou mudou a biblioteca? A resposta completa está no `manifesto.json` de
    cada rodada; esta linha é a de agora, para comparar com ela.

    Cada import é tentado por si, e a falta de uma não esconde as outras. Foi um
    defeito real: numa máquina sem `matplotlib` o comando estourava com
    `ModuleNotFoundError` em vez de dizer o que faltava — e escapou dos testes
    porque a máquina que os roda é a única em que ele nunca falha.
    """
    import importlib

    instaladas: list[tuple[str, str]] = []
    faltando: list[str] = []
    for nome in _BIBLIOTECAS:
        try:
            modulo = importlib.import_module(nome)
        except ImportError:
            faltando.append(_NOME_NO_PIP.get(nome, nome))
            continue
        instaladas.append(
            (_NOME_NO_PIP.get(nome, nome), getattr(modulo, "__version__", "?"))
        )
    return instaladas, faltando

@app.command()
def listar(
    ultimos: int | None = typer.Option(
        None, "-n", "--ultimos", min = 1, metavar = "N",
        help = "Mostra apenas as N solicitações mais recentes, isto é, "
                        "as de maior record_id. Sem esta opção mostra todas."
    ), 
    env: str | None = typer.Option(
        None, "--env",
        help = "Caminho de um .env alternativo."
    ),
    conferir_anexos: bool = typer.Option(
        False, "--conferir-anexos",
        help = "Confirma cada anexo na API. Mais lento, e só necessário se a "
               "coluna 'anexo' vier vazia para todo mundo."
    ),
) -> None:
    """
    Lista as solicitações no REDCap, e o que já foi para o disco.
        É o que coordena o fluxo diário de trabalho.
        Mostra o que chegou de novo de um lado e o que já virou pasta.
    """
    cfg = _configuracao(env)

    try:
        registros = exportar_registros(cfg, fields = CAMPOS_REDCAP)
    except RedcapError as erro:
        raise _abortar("Conexão com o REDCap", str(erro)) from erro

    clientes = normalizar_varios(registros)

    if not clientes:
        console.print("Nenhuma nova solicitação.")
        return

    total = len(clientes)
    if ultimos is not None:
        clientes = mais_recentes(clientes, ultimos)

    if conferir_anexos:
        clientes = _reconferir_anexos(cfg, clientes)

    # A busca no disco é feita **uma vez** por cliente e o resultado é passado
    # adiante. A tabela e o resumo faziam a mesma varredura em separado, o que já
    # era trabalho dobrado — e ficaria pior agora, que a busca desce dois níveis.
    pastas = {
        cliente.record_id: caminho_do_projeto(cfg.root, cliente.matricula, cliente.record_id)
        for cliente in clientes
    }

    console.print(_tabela_de_clientes(clientes, pastas))
    console.print(_resumo(clientes, pastas, total))

def _reconferir_anexos(cfg: Config, clientes: list[Cliente]) -> list[Cliente]:
    """
    Confirma na API os anexos que o export de registros não declarou.
    """
    suspeitos = [c for c in clientes if not c.tem_anexo and c.record_id]
    if not suspeitos:
        return clientes

    quantos = len(suspeitos)
    confirmados: set[str] = set()
    with console.status(
        f"Conferindo {quantos} {_plural(quantos, 'anexo', 'anexos')} na API do REDCap..."
    ):
        for cliente in suspeitos:
            try:
                if tem_arquivo(cfg, cliente.record_id, CAMPO_ANEXO):
                    confirmados.add(cliente.record_id)
            except RedcapError as erro:
                erro_console.print(
                    Text(
                        f"Não foi possível conferir o anexo do registro "
                        f"{cliente.record_id}: {erro}",
                        style = "yellow",
                    )
                )

    return [
        replace(c, tem_anexo = True) if c.record_id in confirmados else c
        for c in clientes
    ]


def _tabela_de_clientes(clientes: list[Cliente], pastas: dict[str, Path | None]) -> Table:
    """
    Monta a tabela que sai do comando `listar`.
    Valores que vêm do REDCap entram como `Text`, nunca como string crua:
        um nome com colchete viraria marcação do rich e sumiria da tela.

    A coluna "Pasta local" responde **pelo projeto**, e não pelo cliente. É a
    correção que a 1.1.0 obrigou e é o ponto em que ela se vê no dia a dia: até a
    1.0.0 a pergunta era "esta matrícula já tem pasta?", e com um cliente podendo
    ter vários trabalhos essa pergunta faria a segunda solicitação dele aparecer
    como já atendida — e ela nunca viraria pasta, porque o `listar` é o comando
    que diz o que ainda falta fazer.
    """
    tabela = Table(show_header = True, header_style = "bold")
    tabela.add_column("id", justify = "right", no_wrap = True)
    tabela.add_column("Tipo", no_wrap = True)
    tabela.add_column("Matrícula", no_wrap = True)
    tabela.add_column("Nome", overflow = "fold")
    tabela.add_column("Anexo", justify = "center", no_wrap = True)
    tabela.add_column("Pasta local", overflow = "fold")

    for cliente in clientes:
        pasta = pastas.get(cliente.record_id)
        tabela.add_row(
            Text(cliente.record_id or "?"),
            Text(cliente.tipo, style = "yellow" if cliente.tipo == INDEFINIDO else ""),
            Text(cliente.matricula or "—", style = "" if cliente.matricula else "yellow"),
            Text(cliente.nome or "(sem nome)", style = "" if cliente.nome else "yellow"),
            Text("sim", style = "green") if cliente.tem_anexo else Text("não", style = "yellow"),
            # Só o nome do projeto: a matrícula e o nome do cliente já têm coluna
            # própria duas casas atrás, e repeti-los aqui espremeria a tabela inteira
            # para dizer o que já está dito.
            Text(pasta.name, style = "green") if pasta else Text("—", style = "dim"),
        )

    return tabela

def _resumo(
    clientes: list[Cliente], pastas: dict[str, Path | None], total: int | None = None
) -> str:
    """
    Uma linha com o que exige atenção, para não ter que contar a tabela na mão.
    """
    total = len(clientes) if total is None else total
    pendentes = [c for c in clientes if not pastas.get(c.record_id)]
    sem_anexo = [c for c in clientes if not c.tem_anexo]
    incompletos = [c for c in clientes if not c.identificado]
    alunos = [c for c in clientes if c.tipo == ALUNO]

    cortado = len(clientes) != total
    contagem = (
        f"[bold]{len(clientes)}[/bold] de {total} solicitações." if cortado
        else f"[bold]{total}[/bold] solicitações."
    )

    partes = [contagem, f"[bold]{len(pendentes)}[/bold] sem pasta local."]
    if sem_anexo:
        partes.append(f"[yellow]{len(sem_anexo)} sem anexo[/yellow]")
    if incompletos:
        partes.append(f"[yellow]{len(incompletos)} com cadastro incompleto[/yellow]")
    if alunos:
        partes.append(f"{len(alunos)} de alunos")

    resumo = "\n" + " . ".join(partes)
    if cortado:
        resumo += (
            f"\n[dim]As {len(clientes)} mais recentes por record_id. "
            f"Rode `-n` para ver as {total}.[/dim]"
        )

    return resumo


@app.command()
def novo(
    record_id: str = typer.Argument(
        ...,
        help = "record_id da solicitação no REDCap, como aparece no `flatcap listar`."
    ),
    sim: bool = typer.Option(
        False, "--sim",
        help = "Executa de fato. Sem esta opção o comando apenas simula."
    ),
    env: str | None = typer.Option(
        None, "--env",
        help = "Caminho de um .env alternativo."
    ),
) -> None:
    """
    Cria a pasta do projeto a partir de uma solicitação do REDCap.
    POR PADRÃO APENAS SIMULA: 
        Desenha a árvore que seria criada e não escreve nada. 
        Repita com --sim para executar.
    """
    cfg = _configuracao(env)

    try:
        plano = preparar(cfg, record_id)
    except ProjetoExistenteError as erro:
        _nada_a_fazer(str(erro))
        return
    except LayoutAntigoError as erro:
        raise _abortar("Pasta no formato antigo", str(erro)) from erro
    except (RegistroNaoEncontradoError, ClienteIncompletoError) as erro:
        raise _abortar("Solicitação", str(erro)) from erro
    except RedcapError as erro:
        raise _abortar("Conexão com o REDCap", str(erro)) from erro

    console.print(_cabecalho_do_plano(plano))
    console.print(_arvore_do_plano(cfg, plano))

    if not plano.tem_anexo:
        console.print(
            Text(
                f"Este registro não tem anexo no campo '{CAMPO_ANEXO}'. "
                "A pasta é criada assim mesmo — o banco entra depois, pelo "
                "`flatcap dados adicionar`.",
                style = "yellow",
            )
        )

    if not sim:
        console.print(
            "\n[yellow]Simulação.[/yellow] Nada foi criado.\n"
            "Repita com [bold]--sim[/bold] para executar."
        )
        return

    try:
        resultado = executar(plano)
    except ProjetoExistenteError as erro:
        _nada_a_fazer(str(erro))
        return
    except OSError as erro:
        raise _abortar(
            "Escrita em disco",
            f"Falhei ao escrever em {plano.raiz}.\n"
            f"Detalhe técnico: {erro}\n"
            "A pasta pode ter ficado pela metade — confira antes de rodar de novo."
        ) from erro

    for aviso in resultado.avisos:
        erro_console.print(Text(aviso, style = "yellow"))

    quantos = len(resultado.criados)
    console.print(
        f"\n[green]Pasta criada.[/green] {quantos} "
        f"{_plural(quantos, 'item', 'itens')} em {plano.raiz}"
    )

def _cabecalho_do_plano(plano: Plano) -> Text:
    """
    Uma linha identificando de quem é a solicitação, antes de desenhar a árvore.
    Confirma que o `record_id` digitado é mesmo o cliente que você tinha em mente.
    """
    cliente = plano.cliente
    return Text.assemble(
        ("Registro ", "dim"), (cliente.record_id or "?", "bold"),
        ("  ·  ", "dim"), (cliente.tipo, "yellow" if cliente.tipo == INDEFINIDO else ""),
        ("  ·  ", "dim"), ("matrícula ", "dim"), (cliente.matricula, "bold"),
        ("  ·  ", "dim"), (cliente.nome, "bold"),
    )

def _arvore_do_plano(cfg: Config, plano: Plano) -> Tree:
    """
    Desenha exatamente o que `executar` criaria, lendo o próprio `Plano`.

    Três níveis desde a 1.1.0, e a linha do cliente diz se ela é nova ou se já
    estava lá. É a informação que a simulação passou a dever: "vou criar uma
    pasta" e "vou acrescentar um projeto ao cliente que já tem dois" são coisas
    diferentes, e só uma delas pede conferência antes do `--sim`.
    """
    arvore = Tree(Text(str(cfg.root), style = "dim"))

    if plano.cliente_novo:
        cliente = arvore.add(
            Text.assemble((plano.pasta_do_cliente.name, "bold green"), ("   novo", "dim"))
        )
    else:
        quantos = len(projetos_do_cliente(plano.pasta_do_cliente))
        cliente = arvore.add(
            Text.assemble(
                (plano.pasta_do_cliente.name, "bold"),
                (
                    f"   já existe · {quantos} "
                    f"{_plural(quantos, 'projeto', 'projetos')} nela",
                    "dim",
                ),
            )
        )

    raiz = cliente.add(Text(plano.raiz.name, style = "bold green"))

    for subpasta in plano.subpastas:
        ramo = raiz.add(Text(f"{subpasta.name}/"))
        if plano.banco is not None and plano.banco.caminho.parent == subpasta:
            ramo.add(
                Text.assemble(
                    (plano.banco.caminho.name, "green"),
                    (f"   {plano.banco.tamanho_legivel} · somente leitura", "dim"),
                )
            )
        elif subpasta.name.startswith("1.") and plano.banco is None:
            ramo.add(Text("(sem anexo no REDCap)", style = "yellow"))

    raiz.add(Text(ARQUIVO_HISTORICO))
    raiz.add(Text(ARQUIVO_PROJETO))
    return arvore



# flatcap dados

@dados_app.command("adicionar")
def dados_adicionar(
    identificador: str = typer.Argument(
        ...,
        help = "record_id ou matrícula do projeto, como aparece no `flatcap listar`."
    ),
    caminho: Path = typer.Argument(
        ...,
        help = "O arquivo revisado que o cliente mandou."
    ),
    sim: bool = typer.Option(
        False, "--sim",
        help = "Executa de fato. Sem esta opção o comando apenas simula."
    ),
    env: str | None = typer.Option(
        None, "--env",
        help = "Caminho de um .env alternativo."
    ),
) -> None:
    """
    Registra uma nova versão do banco na pasta do projeto.

    Copia o arquivo para `1. Dados originais/` com o próximo número da série,
    manda a versão de trabalho anterior para `2. Versões antigas/` e acrescenta a
    entrada em `dados:` no projeto.yaml. O `00_redcap_*` nunca é tocado.

    POR PADRÃO APENAS SIMULA. Repita com --sim para executar.
    """
    cfg = _configuracao(env)

    try:
        plano = preparar_adicao(cfg.root, identificador, caminho)
    except VersaoDuplicadaError as erro:
        _nada_a_fazer(str(erro))
        return
    except ArquivoOrigemError as erro:
        raise _abortar("Arquivo de origem", str(erro)) from erro
    except FichaError as erro:
        raise _abortar("Projeto", str(erro)) from erro
    except DadosError as erro:
        raise _abortar("Versionamento", str(erro)) from erro
    except OSError as erro:
        raise _abortar("Leitura em disco", f"Falhei ao ler {caminho}.\n{erro}") from erro

    console.print(_cabecalho_dos_dados(plano))
    console.print(_arvore_da_adicao(plano))

    if not sim:
        console.print(
            "\n[yellow]Simulação.[/yellow] Nada foi copiado nem movido.\n"
            "Repita com [bold]--sim[/bold] para executar."
        )
        return

    try:
        resultado = executar_adicao(plano)
    except (DadosError, FichaError) as erro:
        raise _abortar("Versionamento", str(erro)) from erro
    except OSError as erro:
        raise _abortar(
            "Escrita em disco",
            f"Falhei ao escrever em {plano.raiz}.\n"
            f"Detalhe técnico: {erro}\n"
            "O que já tinha sido feito foi desfeito — confira a pasta antes de rodar "
            "de novo."
        ) from erro

    for aviso in resultado.avisos:
        erro_console.print(Text(aviso, style = "yellow"))

    console.print(
        f"\n[green]Versão {plano.sequencia:02d} registrada.[/green] "
        f"{plano.destino.name} ({plano.tamanho_legivel})"
    )
    for de, para in resultado.movidos:
        console.print(Text(f"  {de.name} → {para.parent.name}/", style = "dim"))


@dados_app.command("listar")
def dados_listar(
    identificador: str = typer.Argument(
        ...,
        help = "record_id ou matrícula do projeto."
    ),
    rapido: bool = typer.Option(
        False, "--rapido",
        help = "Não reconfere o sha256 dos arquivos. Útil com bancos muito grandes."
    ),
    env: str | None = typer.Option(
        None, "--env",
        help = "Caminho de um .env alternativo."
    ),
) -> None:
    """
    Mostra a linha do tempo das versões do banco de um projeto.

    Além do que está registrado em `dados:`, confronta a ficha com o disco: aponta
    versão registrada que sumiu, arquivo alterado depois do registro e arquivo
    presente na pasta que a ficha desconhece.
    """
    cfg = _configuracao(env)

    try:
        raiz = localizar_projeto(cfg.root, identificador)
        tempo = linha_do_tempo(raiz, conferir = not rapido)
    except FichaError as erro:
        raise _abortar("Projeto", str(erro)) from erro
    except OSError as erro:
        raise _abortar("Leitura em disco", str(erro)) from erro

    console.print(_cabecalho_da_ficha(tempo))

    if not tempo.itens:
        console.print(
            Text(
                "\nNenhuma versão registrada ainda. Assim que o cliente mandar o banco, "
                "use `flatcap dados adicionar`.",
                style = "yellow",
            )
        )
    else:
        console.print(_tabela_da_linha_do_tempo(tempo))

    for linha in _divergencias(tempo):
        console.print(linha)


def _cabecalho_dos_dados(plano: PlanoDados) -> Text:
    ficha = plano.ficha
    return Text.assemble(
        (rotulo_do_projeto(ficha.raiz), "bold"),
        ("  ·  ", "dim"), ("registro ", "dim"), (ficha.record_id or "?", "bold"),
        ("  ·  ", "dim"), ("status ", "dim"), (ficha.status or "?", ""),
    )


def _cabecalho_da_ficha(tempo: LinhaDoTempo) -> Text:
    ficha = tempo.ficha
    return Text.assemble(
        (rotulo_do_projeto(ficha.raiz), "bold"),
        ("  ·  ", "dim"), ("registro ", "dim"), (ficha.record_id or "?", "bold"),
        ("  ·  ", "dim"), (ficha.tipo or "?", ""),
        ("  ·  ", "dim"), ("status ", "dim"), (ficha.status or "?", ""),
    )


def _arvore_da_adicao(plano: PlanoDados) -> Tree:
    """
    Desenha o que `executar_adicao` faria, lendo o próprio plano.
    """
    arvore = Tree(Text(str(plano.raiz), style = "dim"))
    saindo = {de for de, _ in plano.rotacoes}

    originais = arvore.add(Text(f"{PASTA_DADOS}/"))
    pasta = plano.raiz / PASTA_DADOS
    if pasta.is_dir():
        for arquivo in sorted(p for p in pasta.iterdir() if p.is_file()):
            if arquivo in saindo:
                originais.add(
                    Text.assemble(
                        (arquivo.name, "yellow"), ("   → vai para ", "dim"),
                        (f"{PASTA_ANTIGAS}/", "dim"),
                    )
                )
            elif arquivo.name.startswith("00_"):
                originais.add(
                    Text.assemble((arquivo.name, ""), ("   intocado", "dim"))
                )
            else:
                originais.add(Text(arquivo.name, style = "dim"))
    originais.add(
        Text.assemble(
            (plano.destino.name, "bold green"),
            (f"   {plano.tamanho_legivel} · novo", "dim"),
        )
    )

    antigas = arvore.add(Text(f"{PASTA_ANTIGAS}/"))
    if plano.rotacoes:
        for _, para in plano.rotacoes:
            antigas.add(Text.assemble((para.name, "yellow"), ("   recebe", "dim")))
    else:
        antigas.add(Text("(nada muda aqui)", style = "dim"))

    arvore.add(
        Text.assemble(
            (ARQUIVO_PROJETO, ""), ("   + 1 entrada em ", "dim"), ("dados:", "dim"),
        )
    )
    arvore.add(
        Text.assemble((ARQUIVO_HISTORICO, ""), ("   + 1 linha", "dim"))
    )
    return arvore


def _tabela_da_linha_do_tempo(tempo: LinhaDoTempo) -> Table:
    """
    A cronologia. Nomes de arquivo entram como `Text` pelo mesmo motivo de sempre.
    """
    tabela = Table(show_header = True, header_style = "bold")
    tabela.add_column("#", justify = "right", no_wrap = True)
    tabela.add_column("Arquivo", overflow = "fold")
    tabela.add_column("Origem", no_wrap = True)
    tabela.add_column("Data", no_wrap = True)
    tabela.add_column("Tamanho", justify = "right", no_wrap = True)
    tabela.add_column("Onde está", overflow = "fold")
    tabela.add_column("Integridade", no_wrap = True)

    for item in tempo.itens:
        versao = item.versao
        numero = versao.sequencia
        if item.caminho is None:
            onde = Text("ausente", style = "red")
        elif item.local == PASTA_DADOS:
            onde = Text("em uso", style = "green")
        else:
            onde = Text("arquivada", style = "dim")

        if not tempo.conferido:
            integridade = Text("—", style = "dim")
        elif item.confere is None:
            integridade = Text("—", style = "dim")
        elif item.confere:
            integridade = Text("confere", style = "green")
        else:
            integridade = Text("ALTERADO", style = "red bold")

        tabela.add_row(
            Text(f"{numero:02d}" if numero is not None else "?"),
            Text(versao.arquivo),
            Text(versao.origem or "—", style = "" if versao.origem else "yellow"),
            Text(f"{versao.data:%d/%m/%Y}" if versao.data else "—"),
            Text(tamanho_legivel(versao.tamanho_bytes)),
            onde,
            integridade,
        )
    return tabela


def _divergencias(tempo: LinhaDoTempo) -> list[Text]:
    """
    As três formas de a ficha e o disco discordarem, cada uma com o que fazer.
    """
    linhas: list[Text] = []

    for item in tempo.ausentes:
        linhas.append(
            Text(
                f"\nAusente: `{item.versao.arquivo}` está registrado na ficha e não está "
                "no disco.\n"
                "Alguém apagou ou renomeou o arquivo. O registro continua valendo como "
                "prova de que a versão existiu — não apague a entrada da ficha.",
                style = "red",
            )
        )

    for item in tempo.alterados:
        linhas.append(
            Text(
                f"\nAlterado: `{item.versao.arquivo}` está no disco com conteúdo "
                "diferente do que foi registrado.\n"
                "O arquivo foi aberto e salvo por cima depois de entrar na ficha. O "
                "sha256 gravado deixou de descrever o que está lá.\n"
                "O caminho correto é tratar o arquivo alterado como uma versão nova: "
                "copie-o para fora da pasta e rode `flatcap dados adicionar`.",
                style = "red",
            )
        )

    if tempo.nao_registrados:
        quais = "\n".join(f"  {p.parent.name}/{p.name}" for p in tempo.nao_registrados)
        linhas.append(
            Text(
                f"\nNão registrados: {len(tempo.nao_registrados)} arquivo(s) na pasta que "
                f"a ficha desconhece:\n{quais}\n"
                "Arquivo copiado à mão não entra na cronologia. Para registrar, mova-o "
                "para fora da pasta e rode `flatcap dados adicionar`.",
                style = "yellow",
            )
        )

    if tempo.itens and tempo.integra and tempo.conferido:
        linhas.append(
            Text("\nFicha e disco conferem.", style = "green")
        )
    elif tempo.itens and tempo.integra:
        linhas.append(
            Text(
                "\nTodos os arquivos registrados estão no lugar. O conteúdo não foi "
                "conferido (--rapido).",
                style = "dim",
            )
        )

    return linhas


# flatcap perfil

@app.command()
def perfil(
    identificador: str = typer.Argument(
        ...,
        help = "record_id ou matrícula do projeto, como aparece no `flatcap listar`."
    ),
    aba: str | None = typer.Option(
        None, "--aba", metavar = "NOME",
        help = "Planilha a ler, quando o .xlsx tiver mais de uma. Sem isso, a primeira."
    ),
    rapido: bool = typer.Option(
        False, "--rapido",
        help = "Não reconfere o sha256 dos arquivos. Útil com bancos muito grandes."
    ),
    sim: bool = typer.Option(
        False, "--sim",
        help = "Executa de fato. Sem esta opção o comando apenas simula."
    ),
    env: str | None = typer.Option(
        None, "--env",
        help = "Caminho de um .env alternativo."
    ),
) -> None:
    """
    Descreve o banco e prepara a reunião com o cliente.

    Abre a versão vigente registrada na ficha, mede cada variável, aponta os
    problemas conhecidos e escreve dois arquivos na pasta do projeto: o `perfil.md`,
    que é o documento que você leva para a conversa, e o `dicionario.csv`, que dirige
    a descritiva daqui em diante.

    O dicionário que já existir não é sobrescrito: as linhas que você preencheu
    ficam intactas, e só entram as variáveis novas.

    POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.
    """
    # O `pandas` sai de dentro deste import e não do topo do arquivo: ele custa uns
    # 0,4 s para carregar, contra 0,08 s do typer com o rich. O `listar`, que roda
    # várias vezes por dia e não abre banco nenhum, não deve pagar por isso.
    from .banco import BancoError
    from .perfil import executar_perfil, preparar_perfil

    cfg = _configuracao(env)

    try:
        raiz = localizar_projeto(cfg.root, identificador)
        plano = preparar_perfil(raiz, aba = aba, conferir = not rapido)
    except FichaError as erro:
        raise _abortar("Projeto", str(erro)) from erro
    except BancoError as erro:
        raise _abortar("Banco de dados", str(erro)) from erro
    except DicionarioError as erro:
        raise _abortar("Dicionário", str(erro)) from erro
    except OSError as erro:
        raise _abortar("Leitura em disco", str(erro)) from erro

    console.print(_cabecalho_do_perfil(plano.perfil))
    console.print(_tabela_do_perfil(plano.perfil))
    for bloco in _achados_no_terminal(plano.perfil):
        console.print(bloco)
    console.print(_arvore_do_perfil(plano))

    if not sim:
        console.print(
            "\n[yellow]Simulação.[/yellow] Nada foi escrito.\n"
            "Repita com [bold]--sim[/bold] para gravar os dois arquivos."
        )
        return

    try:
        resultado = executar_perfil(plano)
    except OSError as erro:
        raise _abortar(
            "Escrita em disco",
            f"Falhei ao escrever em {plano.raiz}.\n"
            f"Detalhe técnico: {erro}\n"
            "Os dois arquivos são regeráveis: rode o comando de novo depois de resolver."
        ) from erro

    for aviso in resultado.avisos:
        erro_console.print(Text(aviso, style = "yellow"))

    console.print(
        f"\n[green]Perfil escrito.[/green] {plano.caminho_perfil.name} e "
        f"{plano.caminho_dicionario.name} em {plano.raiz}"
    )
    if not plano.fusao.existia:
        console.print(
            Text(
                "Revise a coluna `tipo` do dicionário antes da Fase 5 — a sugestão é palpite.",
                style = "yellow",
            )
        )


def _cabecalho_do_perfil(perfil: Perfil) -> Text:
    """
    Quem, qual arquivo, e se dá para confiar nele. Nessa ordem.
    """
    ficha = perfil.ficha
    cabecalho = Text.assemble(
        (rotulo_do_projeto(ficha.raiz), "bold"),
        ("  ·  ", "dim"), ("registro ", "dim"), (ficha.record_id or "?", "bold"),
        ("  ·  ", "dim"), ("status ", "dim"), (ficha.status or "?", ""),
        "\n",
        ("Banco ", "dim"), (perfil.versao_arquivo, "bold"),
        ("  ·  ", "dim"), (perfil.tamanho_legivel, "dim"),
        ("  ·  ", "dim"),
        (f"{perfil.linhas} linhas × {perfil.total_colunas} colunas", ""),
    )

    if perfil.leitura.aba:
        cabecalho.append(Text.assemble(("  ·  ", "dim"), (f'planilha "{perfil.leitura.aba}"', "")))
    if perfil.leitura.separador:
        legivel = {"\t": "tabulação"}.get(perfil.leitura.separador, perfil.leitura.separador)
        cabecalho.append(
            Text.assemble(("  ·  ", "dim"), (f"separador {legivel}", "dim"),
                                        ("  ·  ", "dim"), (str(perfil.leitura.codificacao), "dim"))
        )

    cabecalho.append("\n")
    if perfil.confere is True:
        cabecalho.append(Text("Integridade confere com a ficha", style = "green"))
    elif perfil.confere is False:
        cabecalho.append(
            Text("ALTERADO: o arquivo não confere com o sha256 da ficha", style = "red bold")
        )
    else:
        cabecalho.append(Text("Integridade não conferida (--rapido)", style = "dim"))

    return cabecalho


def _tabela_do_perfil(perfil: Perfil) -> Table:
    """
    Uma linha por variável. Valores do banco entram como `Text`, nunca como string
    crua, pelo mesmo motivo do `listar`.
    """
    tabela = Table(show_header = True, header_style = "bold")
    tabela.add_column("#", justify = "right", no_wrap = True)
    tabela.add_column("Variável", overflow = "fold")
    tabela.add_column("Lido como", no_wrap = True)
    tabela.add_column("Faltantes", justify = "right", no_wrap = True)
    tabela.add_column("Únicos", justify = "right", no_wrap = True)
    tabela.add_column("Sugestão", no_wrap = True)
    tabela.add_column("Exemplos", overflow = "fold")

    for coluna in perfil.colunas:
        proporcao = coluna.proporcao_faltante
        faltantes = Text("—", style = "dim")
        if coluna.faltantes:
            faltantes = Text(
                f"{coluna.faltantes} ({proporcao * 100:.0f}%)",
                style = "yellow" if proporcao >= 0.2 else "",
            )

        tabela.add_row(
            Text(str(coluna.posicao)),
            Text(coluna.nome),
            Text(coluna.tipo_lido, style = "red" if coluna.tipo_lido == "misto" else ""),
            faltantes,
            Text(str(coluna.unicos)),
            Text(coluna.sugestao, style = "dim" if coluna.sugestao == "ignorar" else ""),
            Text(" · ".join(coluna.exemplos)),
        )

    return tabela


def _achados_no_terminal(perfil: Perfil) -> list[Panel | Text]:
    """
    Os achados agrupados pelo que fazer com eles, do mais urgente para o menos.
    """
    from .perfil import CONFIRMAR, CORRIGIR, NOTA

    if not perfil.achados:
        return [
            Text(
                "\nNenhum problema encontrado pelos detectores. Isso não quer dizer que o "
                "banco está certo — quer dizer que ele passa nos testes que o FlatCap sabe fazer.",
                style = "green",
            )
        ]

    estilos = {CORRIGIR: "red", CONFIRMAR: "yellow", NOTA: "dim"}
    titulos = {
        CORRIGIR: "Corrigir antes de começar",
        CONFIRMAR: "Confirmar com o cliente",
        NOTA: "Notas",
    }

    blocos: list[Panel | Text] = []
    for gravidade in (CORRIGIR, CONFIRMAR, NOTA):
        achados = perfil.por_gravidade(gravidade)
        if not achados:
            continue
        blocos.append(
            Panel(
                _lista_de_achados(achados),
                title = f"{titulos[gravidade]} ({len(achados)})",
                border_style = estilos[gravidade],
            )
        )
    return blocos


def _lista_de_achados(achados: tuple[Achado, ...]) -> Text:
    corpo = Text()
    for posicao, achado in enumerate(achados):
        if posicao:
            corpo.append("\n")
        if achado.variavel:
            corpo.append(achado.variavel, style = "bold")
            corpo.append(" — ")
        corpo.append(achado.titulo)
        if achado.exemplos:
            corpo.append("\n    ")
            corpo.append(" · ".join(achado.exemplos), style = "dim")
    return corpo


def _arvore_do_perfil(plano: PlanoPerfil) -> Tree:
    """
    Desenha o que `executar_perfil` escreveria, lendo o próprio plano.
    """
    arvore = Tree(Text(str(plano.raiz), style = "dim"))
    fusao = plano.fusao

    if plano.perfil_anterior is None:
        nota = "novo"
    else:
        nota = f"substitui o de {plano.perfil_anterior:%d/%m/%Y %H:%M}"
    arvore.add(
        Text.assemble((plano.caminho_perfil.name, "bold green"), (f"   {nota}", "dim"))
    )

    if not fusao.existia:
        detalhe = f"novo · {fusao.total} variáveis"
    else:
        detalhe = (
            f"{len(fusao.preservadas)} linha(s) preservada(s) · "
            f"{len(fusao.novas)} nova(s) · {len(fusao.ausentes)} fora do banco"
        )
    ramo = arvore.add(
        Text.assemble((plano.caminho_dicionario.name, "bold green"), (f"   {detalhe}", "dim"))
    )
    for nome in fusao.novas[:10]:
        ramo.add(Text.assemble(("+ ", "green"), (nome, "")))
    if len(fusao.novas) > 10:
        ramo.add(Text(f"+ … mais {len(fusao.novas) - 10}", style = "dim"))
    for nome in fusao.ausentes[:10]:
        ramo.add(Text.assemble(("~ ", "yellow"), (nome, ""), ("   fora do banco", "dim")))

    arvore.add(Text.assemble((ARQUIVO_HISTORICO, ""), ("   + 1 linha", "dim")))
    return arvore


# flatcap descritiva

@app.command()
def descritiva(
    identificador: str = typer.Argument(
        ...,
        help = "record_id ou matrícula do projeto, como aparece no `flatcap listar`."
    ),
    aba: str | None = typer.Option(
        None, "--aba", metavar = "NOME",
        help = "Planilha a ler, quando o .xlsx tiver mais de uma. Sem isso, a primeira."
    ),
    sem_graficos: bool = typer.Option(
        False, "--sem-graficos",
        help = "Escreve só as tabelas. Mais rápido, e o matplotlib nem é carregado."
    ),
    rapido: bool = typer.Option(
        False, "--rapido",
        help = "Não reconfere o sha256 dos arquivos. Útil com bancos muito grandes."
    ),
    sim: bool = typer.Option(
        False, "--sim",
        help = "Executa de fato. Sem esta opção o comando apenas simula."
    ),
    env: str | None = typer.Option(
        None, "--env",
        help = "Caminho de um .env alternativo."
    ),
) -> None:
    """
    Gera a análise descritiva obedecendo ao dicionario.csv.

    Uma tabela de frequência e um gráfico de barras por categórica; resumo, tabela
    por faixas e histograma por numérica; período e distribuição no tempo por data.
    Tudo em `3. Análises/descritiva/`, com um `manifesto.json` que diz de qual
    variável saiu cada arquivo.

    Sem `faixas` preenchida no dicionário, as faixas saem pelos quartis da própria
    variável. Numérica que chegou como texto faz o comando recusar: o caminho é
    pedir a correção ao cliente e registrar a versão nova com `dados adicionar`.

    Rodar de novo arquiva a rodada anterior inteira em `2. Versões antigas/`.

    POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.
    """
    # Mesmo motivo do `perfil`: o `pandas` custa perto de meio segundo para
    # carregar e o `matplotlib` outro tanto. O `listar`, que roda várias vezes por
    # dia, não deve pagar por um comando que ele não usa.
    from .banco import BancoError
    from .descritiva import (
        DescritivaError,
        executar_descritiva,
        preparar_descritiva,
    )

    cfg = _configuracao(env)

    try:
        raiz = localizar_projeto(cfg.root, identificador)
        plano = preparar_descritiva(
            raiz, aba = aba, conferir = not rapido, com_graficos = not sem_graficos
        )
    except FichaError as erro:
        raise _abortar("Projeto", str(erro)) from erro
    except BancoError as erro:
        raise _abortar("Banco de dados", str(erro)) from erro
    except DicionarioError as erro:
        raise _abortar("Dicionário", str(erro)) from erro
    except DescritivaError as erro:
        raise _abortar("Descritiva", str(erro)) from erro
    except OSError as erro:
        raise _abortar("Leitura em disco", str(erro)) from erro

    console.print(_cabecalho_da_descritiva(plano))
    console.print(_tabela_da_descritiva(plano.descritiva))
    for bloco in _fora_da_descritiva(plano.descritiva):
        console.print(bloco)
    for aviso in plano.descritiva.avisos:
        erro_console.print(Text(f"\n{aviso}", style = "yellow"))
    console.print(_arvore_da_descritiva(plano))

    if not sim:
        console.print(
            "\n[yellow]Simulação.[/yellow] Nada foi escrito nem arquivado.\n"
            "Repita com [bold]--sim[/bold] para gerar a pasta."
        )
        return

    try:
        resultado = executar_descritiva(plano)
    except OSError as erro:
        raise _abortar(
            "Escrita em disco",
            f"Falhei ao escrever em {plano.pasta}.\n"
            f"Detalhe técnico: {erro}\n"
            "O que já tinha sido feito foi desfeito, inclusive o arquivamento da rodada "
            "anterior — confira a pasta antes de rodar de novo."
        ) from erro

    for aviso in resultado.avisos:
        erro_console.print(Text(aviso, style = "yellow"))

    if resultado.arquivado is not None:
        console.print(
            Text(
                f"\nRodada anterior arquivada em {PASTA_ANTIGAS}/{resultado.arquivado[1].name}/",
                style = "dim",
            )
        )

    quantos = len(plano.arquivos)
    console.print(
        f"\n[green]Descritiva escrita.[/green] {quantos} "
        f"{_plural(quantos, 'arquivo', 'arquivos')} em "
        f"{PASTA_ANALISES}/{plano.pasta.name}"
    )


def _cabecalho_da_descritiva(plano: PlanoDescritiva) -> Text:
    """
    Quem, qual banco, se dá para confiar nele, e quanto do dicionário entra.
    """
    descritiva = plano.descritiva
    ficha = descritiva.ficha
    banco = descritiva.banco
    dicionario = plano.manifesto.dicionario

    cabecalho = Text.assemble(
        (rotulo_do_projeto(ficha.raiz), "bold"),
        ("  ·  ", "dim"), ("registro ", "dim"), (ficha.record_id or "?", "bold"),
        ("  ·  ", "dim"), ("status ", "dim"), (ficha.status or "?", ""),
        "\n",
        ("Banco ", "dim"), (banco.versao.arquivo, "bold"),
        ("  ·  ", "dim"), (banco.tamanho_legivel, "dim"),
        ("  ·  ", "dim"),
        (f"{banco.linhas} linhas × {banco.colunas} colunas", ""),
    )
    if banco.leitura.aba:
        cabecalho.append(Text.assemble(("  ·  ", "dim"), (f'planilha "{banco.leitura.aba}"', "")))

    cabecalho.append("\n")
    if banco.confere is True:
        cabecalho.append(Text("Integridade confere com a ficha", style = "green"))
    elif banco.confere is False:
        cabecalho.append(
            Text("ALTERADO: o arquivo não confere com o sha256 da ficha", style = "red bold")
        )
    else:
        cabecalho.append(Text("Integridade não conferida (--rapido)", style = "dim"))

    cabecalho.append(
        Text.assemble(
            ("  ·  ", "dim"),
            ("Dicionário ", "dim"),
            (f"{dicionario['variaveis']} variáveis", ""),
            (f", {len(descritiva.variaveis)} na descritiva", ""),
            (f", {len(descritiva.fora)} fora", "dim"),
        )
    )
    return cabecalho


def _tabela_da_descritiva(descritiva: Descritiva) -> Table:
    """
    Uma linha por variável, com os arquivos que ela gera.

    A coluna dos arquivos é a que importa: é o `manifesto.json` na tela, e é o que
    responde "de qual variável saiu este .csv?" antes de o .csv existir.
    """
    tabela = Table(show_header = True, header_style = "bold")
    tabela.add_column("#", justify = "right", no_wrap = True)
    tabela.add_column("Variável", overflow = "fold")
    tabela.add_column("Tipo", no_wrap = True)
    tabela.add_column("n", justify = "right", no_wrap = True)
    tabela.add_column("Faltantes", justify = "right", no_wrap = True)
    tabela.add_column("Arquivos", overflow = "fold")

    for posicao, variavel in enumerate(descritiva.variaveis, start = 1):
        proporcao = variavel.faltantes / variavel.n if variavel.n else 0.0
        faltantes = Text("—", style = "dim")
        if variavel.faltantes:
            faltantes = Text(
                f"{variavel.faltantes} ({proporcao * 100:.0f}%)",
                style = "yellow" if proporcao >= 0.2 else "",
            )

        nomes = [t.nome for t in variavel.tabelas] + [g.nome for g in variavel.graficos]
        tabela.add_row(
            Text(str(posicao)),
            Text(variavel.variavel),
            Text(variavel.tipo),
            Text(str(variavel.preenchidos)),
            faltantes,
            Text(" · ".join(nomes), style = "dim"),
        )

    return tabela


def _fora_da_descritiva(descritiva: Descritiva) -> list[Panel]:
    """
    As variáveis que não geraram artefato, e por quê.

    Aparecem na tela pelo mesmo motivo que aparecem no manifesto: "não está no
    relatório" e "ninguém reparou que ela existia" são coisas diferentes.
    """
    if not descritiva.fora:
        return []

    corpo = Text()
    for posicao, item in enumerate(descritiva.fora):
        if posicao:
            corpo.append("\n")
        corpo.append(item.variavel, style = "bold")
        corpo.append(" — ")
        corpo.append(item.motivo)
    return [
        Panel(
            corpo,
            title = f"Fora da descritiva ({len(descritiva.fora)})",
            border_style = "dim",
        )
    ]


def _arvore_da_descritiva(plano: PlanoDescritiva) -> Tree:
    """
    Desenha o que `executar_descritiva` escreveria, lendo o próprio plano.
    """
    arvore = Tree(Text(str(plano.raiz), style = "dim"))

    if plano.arquivamento is not None:
        de, para = plano.arquivamento
        quantos = len([p for p in de.iterdir()])
        ramo = arvore.add(Text(f"{PASTA_ANTIGAS}/"))
        ramo.add(
            Text.assemble(
                (f"{para.name}/", "yellow"),
                (f"   recebe a rodada anterior ({quantos} arquivo(s))", "dim"),
            )
        )

    ramo = arvore.add(
        Text.assemble(
            (f"{PASTA_ANALISES}/{plano.pasta.name}/", "bold green"),
            ("   novo" if plano.arquivamento is None else "   refeito", "dim"),
        )
    )
    for tabela in plano.tabelas[:12]:
        ramo.add(Text.assemble(("+ ", "green"), (tabela.nome, "")))
    if len(plano.tabelas) > 12:
        ramo.add(Text(f"+ … mais {len(plano.tabelas) - 12} tabela(s)", style = "dim"))

    if plano.com_graficos:
        ramo.add(
            Text.assemble(
                ("+ ", "green"), (f"{len(plano.graficos)} gráfico(s) .png", ""),
            )
        )
    else:
        ramo.add(Text("(sem gráficos: --sem-graficos)", style = "yellow"))

    ramo.add(
        Text.assemble(
            ("+ ", "green"), ("manifesto.json", "bold"),
            (
                f"   índice de {len(plano.descritiva.variaveis)} variável(is) e "
                f"{plano.manifesto.total_artefatos} artefato(s)",
                "dim",
            ),
        )
    )

    arvore.add(Text.assemble((ARQUIVO_HISTORICO, ""), ("   + 1 linha", "dim")))
    return arvore


# flatcap normalidade

@app.command()
def normalidade(
    identificador: str = typer.Argument(
        ...,
        help = "record_id ou matrícula do projeto, como aparece no `flatcap listar`."
    ),
    aba: str | None = typer.Option(
        None, "--aba", metavar = "NOME",
        help = "Planilha a ler, quando o .xlsx tiver mais de uma. Sem isso, a primeira."
    ),
    sem_graficos: bool = typer.Option(
        False, "--sem-graficos",
        help = "Escreve só a tabela. Mais rápido, e o matplotlib nem é carregado."
    ),
    rapido: bool = typer.Option(
        False, "--rapido",
        help = "Não reconfere o sha256 dos arquivos. Útil com bancos muito grandes."
    ),
    sim: bool = typer.Option(
        False, "--sim",
        help = "Executa de fato. Sem esta opção o comando apenas simula."
    ),
    env: str | None = typer.Option(
        None, "--env",
        help = "Caminho de um .env alternativo."
    ),
) -> None:
    """
    Testa a normalidade das variáveis numéricas do dicionario.csv.

    Para cada `numerica`: o teste de Shapiro-Wilk, a assimetria, a curtose e um
    gráfico Q-Q. Tudo em `3. Análises/normalidade/`, com um `manifesto.json`.

    Sai uma tabela só, com uma linha por variável — é como uma tabela de
    pressupostos se lê. O valor-p **depende do tamanho da amostra**: com poucos
    casos o teste quase não rejeita, e com muitos rejeita desvios irrelevantes. Por
    isso a assimetria, a curtose e o Q-Q saem ao lado dele, e não no lugar dele.

    Por padrão entram todas as numéricas. Uma lista `normalidade:` no projeto.yaml
    restringe às variáveis que você escrever nela.

    Rodar de novo arquiva a rodada anterior inteira em `2. Versões antigas/`.

    POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.
    """
    # Mesmo motivo do `perfil` e da `descritiva`: `pandas`, `scipy` e `matplotlib`
    # custam perto de um segundo somados, e o `listar`, que roda várias vezes por
    # dia, não deve pagar por um comando que ele não usa.
    from .banco import BancoError
    from .normalidade import (
        NormalidadeError,
        executar_normalidade,
        preparar_normalidade,
    )

    cfg = _configuracao(env)

    try:
        raiz = localizar_projeto(cfg.root, identificador)
        plano = preparar_normalidade(
            raiz, aba = aba, conferir = not rapido, com_graficos = not sem_graficos
        )
    except FichaError as erro:
        raise _abortar("Projeto", str(erro)) from erro
    except BancoError as erro:
        raise _abortar("Banco de dados", str(erro)) from erro
    except DicionarioError as erro:
        raise _abortar("Dicionário", str(erro)) from erro
    except NormalidadeError as erro:
        raise _abortar("Normalidade", str(erro)) from erro
    except OSError as erro:
        raise _abortar("Leitura em disco", str(erro)) from erro

    console.print(_cabecalho_da_normalidade(plano))
    console.print(_tabela_da_normalidade(plano.normalidade))
    console.print(_nota_da_normalidade(plano.normalidade))
    for bloco in _fora_da_normalidade(plano.normalidade):
        console.print(bloco)
    for aviso in plano.normalidade.avisos:
        erro_console.print(Text(f"\n{aviso}", style = "yellow"))
    console.print(_arvore_da_normalidade(plano))

    if not sim:
        console.print(
            "\n[yellow]Simulação.[/yellow] Nada foi escrito nem arquivado.\n"
            "Repita com [bold]--sim[/bold] para gerar a pasta."
        )
        return

    try:
        resultado = executar_normalidade(plano)
    except OSError as erro:
        raise _abortar(
            "Escrita em disco",
            f"Falhei ao escrever em {plano.pasta}.\n"
            f"Detalhe técnico: {erro}\n"
            "O que já tinha sido feito foi desfeito, inclusive o arquivamento da rodada "
            "anterior — confira a pasta antes de rodar de novo."
        ) from erro

    for aviso in resultado.avisos:
        erro_console.print(Text(aviso, style = "yellow"))

    if resultado.arquivado is not None:
        console.print(
            Text(
                f"\nRodada anterior arquivada em {PASTA_ANTIGAS}/{resultado.arquivado[1].name}/",
                style = "dim",
            )
        )

    quantos = len(plano.arquivos)
    console.print(
        f"\n[green]Normalidade escrita.[/green] {quantos} "
        f"{_plural(quantos, 'arquivo', 'arquivos')} em "
        f"{PASTA_ANALISES}/{plano.pasta.name}"
    )


def _cabecalho_da_normalidade(plano: PlanoNormalidade) -> Text:
    """
    Quem, qual banco, se dá para confiar nele, e quantas variáveis entram.
    """
    normalidade = plano.normalidade
    ficha = normalidade.ficha
    banco = normalidade.banco

    cabecalho = Text.assemble(
        (rotulo_do_projeto(ficha.raiz), "bold"),
        ("  ·  ", "dim"), ("registro ", "dim"), (ficha.record_id or "?", "bold"),
        ("  ·  ", "dim"), ("status ", "dim"), (ficha.status or "?", ""),
        "\n",
        ("Banco ", "dim"), (banco.versao.arquivo, "bold"),
        ("  ·  ", "dim"), (banco.tamanho_legivel, "dim"),
        ("  ·  ", "dim"),
        (f"{banco.linhas} linhas × {banco.colunas} colunas", ""),
    )
    if banco.leitura.aba:
        cabecalho.append(Text.assemble(("  ·  ", "dim"), (f'planilha "{banco.leitura.aba}"', "")))

    cabecalho.append("\n")
    if banco.confere is True:
        cabecalho.append(Text("Integridade confere com a ficha", style = "green"))
    elif banco.confere is False:
        cabecalho.append(
            Text("ALTERADO: o arquivo não confere com o sha256 da ficha", style = "red bold")
        )
    else:
        cabecalho.append(Text("Integridade não conferida (--rapido)", style = "dim"))

    quantas = len(normalidade.variaveis)
    cabecalho.append(
        Text.assemble(
            ("  ·  ", "dim"),
            ("Shapiro-Wilk em ", "dim"),
            (f"{quantas} numérica(s)", ""),
            (
                ", restrita à lista do projeto.yaml" if normalidade.pedidas else "",
                "yellow" if normalidade.pedidas else "",
            ),
        )
    )
    return cabecalho


def _tabela_da_normalidade(normalidade: Normalidade) -> Table:
    """
    Uma linha por variável, na mesma ordem e com os mesmos números do `.csv`.

    O `n` vem antes de tudo de propósito: ele é o que calibra a leitura do valor-p,
    e uma tabela que o escondesse deixaria a coluna `p` parecer uma resposta. Pelo
    mesmo motivo a assimetria e a curtose vêm **antes** do W e do p, e não depois:
    elas medem o tamanho do desvio e não mudam com o tamanho da amostra.
    """
    tabela = Table(show_header = True, header_style = "bold")
    tabela.add_column("Variável", overflow = "fold")
    tabela.add_column("n", justify = "right", no_wrap = True)
    tabela.add_column("Faltantes", justify = "right", no_wrap = True)
    tabela.add_column("Assimetria", justify = "right", no_wrap = True)
    tabela.add_column("Curtose", justify = "right", no_wrap = True)
    tabela.add_column("W", justify = "right", no_wrap = True)
    tabela.add_column("p", justify = "right", no_wrap = True)
    tabela.add_column("Leitura", overflow = "fold")

    for posicao, variavel in enumerate(normalidade.variaveis):
        # A tabela do terminal lê as mesmas células do `.csv` que vai para o disco, e
        # não reformata número nenhum: dois formatadores para a mesma grandeza é como
        # o terminal passa a dizer `0.05` enquanto o arquivo diz `0,05`.
        celulas = normalidade.tabela.linhas[posicao]

        if not variavel.testada:
            estilo_p = "dim"
        elif variavel.rejeita:
            estilo_p = "yellow"
        else:
            estilo_p = "green"

        tabela.add_row(
            Text(celulas[0]),
            Text(celulas[1]),
            Text(
                celulas[2] if variavel.faltantes else "—",
                style = "" if variavel.faltantes else "dim",
            ),
            Text(celulas[3]),
            Text(celulas[4]),
            Text(celulas[5], style = "dim" if not variavel.testada else ""),
            Text(celulas[6], style = estilo_p),
            Text(celulas[7], style = "dim" if not variavel.testada else ""),
        )

    return tabela


def _nota_da_normalidade(normalidade: Normalidade) -> Text:
    """
    A frase que impede a tabela de ser lida como um veredito.

    Ela sai sempre, inclusive quando nada foi rejeitado, e é a mesma coisa que a nota
    do `.csv` diz. O terminal é onde você olha a tabela pela primeira vez, e é aí que
    a advertência serve para alguma coisa — depois de o documento estar pronto, ela
    vira leitura de conferência.
    """
    from .normalidade import ALFA, MINIMO_CONFIAVEL

    rejeitadas = len(normalidade.rejeitadas)
    testadas = sum(1 for v in normalidade.variaveis if v.testada)
    pequenas = [v for v in normalidade.variaveis if v.testada and v.n < MINIMO_CONFIAVEL]

    partes = [
        Text.assemble(
            ("\n", ""),
            (f"{rejeitadas} de {testadas} ", "bold"),
            ("com a normal rejeitada ao nível de ", ""),
            (f"{ALFA:.2f}".replace(".", ","), ""),
            (".", ""),
        )
    ]
    if pequenas:
        partes.append(
            Text(
                f"{len(pequenas)} variável(is) com menos de {MINIMO_CONFIAVEL} casos: aí o "
                "teste quase não rejeita, e «não rejeitou» não é evidência de normalidade.",
                style = "yellow",
            )
        )
    partes.append(
        Text(
            "O valor-p depende do n. Leia a assimetria, a curtose e o Q-Q antes de "
            "decidir qualquer coisa a partir desta tabela.",
            style = "dim",
        )
    )

    corpo = Text()
    for posicao, parte in enumerate(partes):
        if posicao:
            corpo.append("\n")
        corpo.append(parte)
    return corpo


def _fora_da_normalidade(normalidade: Normalidade) -> list[Panel]:
    """
    As variáveis que não entraram, e por quê.

    Aparecem pelo mesmo motivo da Fase 5, e aqui elas são quase todo o dicionário:
    categórica, data e `ignorar` não têm normalidade a testar. Um painel `dim` com a
    lista é o que impede a pergunta "por que `sexo` não está na tabela?".
    """
    if not normalidade.fora:
        return []

    corpo = Text()
    for posicao, item in enumerate(normalidade.fora):
        if posicao:
            corpo.append("\n")
        corpo.append(item.variavel, style = "bold")
        corpo.append(" — ")
        corpo.append(item.motivo)
    return [
        Panel(
            corpo,
            title = f"Fora da normalidade ({len(normalidade.fora)})",
            border_style = "dim",
        )
    ]


def _arvore_da_normalidade(plano: PlanoNormalidade) -> Tree:
    """
    Desenha o que `executar_normalidade` escreveria, lendo o próprio plano.
    """
    arvore = Tree(Text(str(plano.raiz), style = "dim"))

    if plano.arquivamento is not None:
        de, para = plano.arquivamento
        quantos = len([p for p in de.iterdir()])
        ramo = arvore.add(Text(f"{PASTA_ANTIGAS}/"))
        ramo.add(
            Text.assemble(
                (f"{para.name}/", "yellow"),
                (f"   recebe a rodada anterior ({quantos} arquivo(s))", "dim"),
            )
        )

    ramo = arvore.add(
        Text.assemble(
            (f"{PASTA_ANALISES}/{plano.pasta.name}/", "bold green"),
            ("   novo" if plano.arquivamento is None else "   refeito", "dim"),
        )
    )
    ramo.add(
        Text.assemble(
            ("+ ", "green"), (plano.tabela.nome, ""),
            (f"   {len(plano.normalidade.variaveis)} variável(is), uma por linha", "dim"),
        )
    )

    if plano.com_graficos:
        ramo.add(
            Text.assemble(
                ("+ ", "green"), (f"{len(plano.graficos)} gráfico(s) Q-Q .png", ""),
            )
        )
        sem_figura = len(plano.normalidade.variaveis) - len(plano.graficos)
        if sem_figura:
            ramo.add(
                Text(
                    f"({sem_figura} sem figura: não há reta de referência possível)",
                    style = "yellow",
                )
            )
    else:
        ramo.add(Text("(sem gráficos: --sem-graficos)", style = "yellow"))

    ramo.add(
        Text.assemble(
            ("+ ", "green"), ("manifesto.json", "bold"),
            (f"   índice de {plano.manifesto.total_artefatos} artefato(s)", "dim"),
        )
    )

    arvore.add(Text.assemble((ARQUIVO_HISTORICO, ""), ("   + 1 linha", "dim")))
    return arvore


# flatcap relatorio

@app.command()
def relatorio(
    identificador: str = typer.Argument(
        ...,
        help = "record_id ou matrícula do projeto, como aparece no `flatcap listar`."
    ),
    template: Path | None = typer.Option(
        None, "--template", metavar = "ARQUIVO",
        help = "Um .docx para herdar estilos, cabeçalho e capa. Sem isso, o "
               "template.docx da pasta do projeto ou do FLATCAP_ROOT."
    ),
    titulo: str | None = typer.Option(
        None, "--titulo", metavar = "TEXTO",
        help = "O título na primeira linha do documento."
    ),
    rapido: bool = typer.Option(
        False, "--rapido",
        help = "Não reconfere o sha256 do banco. Útil com bancos muito grandes."
    ),
    sim: bool = typer.Option(
        False, "--sim",
        help = "Executa de fato. Sem esta opção o comando apenas simula."
    ),
    env: str | None = typer.Option(
        None, "--env",
        help = "Caminho de um .env alternativo."
    ),
) -> None:
    """
    Monta o relatório .docx a partir das análises já rodadas.

    Varre `3. Análises/`, lê o `manifesto.json` de cada rodada que estiver lá e
    monta um documento com as seções de todas elas: a tabela, as notas de
    denominador e a figura de cada uma. A descritiva dá uma seção por variável,
    na ordem do dicionário; a normalidade dá a tabela de pressupostos e os Q-Q.

    A ordem das análises é a da lista `analises:` do `projeto.yaml` — o que foi
    combinado na reunião. O que não estiver na lista entra depois, e o que
    estiver na lista sem rodada no disco vira um aviso aqui no terminal.

    Não abre o banco e não recalcula nada: os números do documento são, letra
    por letra, os dos `.csv` que estão em `3. Análises/`.

    O documento sai na raiz da pasta do projeto como
    `Relatorio_<matrícula>_AAAA-MM-DD.docx`, e o relatório anterior vai para
    `2. Versões antigas/`.

    Quando uma rodada já não descreve o que está na pasta — banco novo, arquivo
    alterado, dicionário mexido — o documento é gerado assim mesmo, com o aviso
    escrito dentro dele.

    POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.
    """
    # Nem `pandas` nem `matplotlib` entram neste comando: o relatório lê os
    # manifestos e os `.csv` das rodadas, e é só isso. O `python-docx` entra só
    # na execução, dentro do `executar_relatorio`.
    from .manifesto import ManifestoError
    from .relatorio import (
        TITULO_PADRAO,
        RelatorioError,
        executar_relatorio,
        preparar_relatorio,
    )

    cfg = _configuracao(env)

    try:
        raiz = localizar_projeto(cfg.root, identificador)
        plano = preparar_relatorio(
            raiz,
            template = template,
            conferir = not rapido,
            titulo = titulo or TITULO_PADRAO,
        )
    except FichaError as erro:
        raise _abortar("Projeto", str(erro)) from erro
    except DicionarioError as erro:
        raise _abortar("Dicionário", str(erro)) from erro
    except ManifestoError as erro:
        raise _abortar("Manifesto da análise", str(erro)) from erro
    except RelatorioError as erro:
        raise _abortar("Relatório", str(erro)) from erro
    except OSError as erro:
        raise _abortar("Leitura em disco", str(erro)) from erro

    console.print(_cabecalho_do_relatorio(plano))
    console.print(_tabela_do_relatorio(plano.relatorio))
    for bloco in _alertas_no_terminal(plano.relatorio):
        console.print(bloco)
    for bloco in _fora_do_relatorio(plano.relatorio):
        console.print(bloco)
    for aviso in plano.relatorio.avisos:
        erro_console.print(Text(f"\n{aviso}", style = "yellow"))
    console.print(_arvore_do_relatorio(plano))

    if not sim:
        console.print(
            "\n[yellow]Simulação.[/yellow] Nada foi escrito nem arquivado.\n"
            "Repita com [bold]--sim[/bold] para gerar o documento."
        )
        return

    try:
        resultado = executar_relatorio(plano)
    except RelatorioError as erro:
        raise _abortar("Relatório", str(erro)) from erro
    except OSError as erro:
        raise _abortar(
            "Escrita em disco",
            f"Falhei ao escrever em {plano.raiz}.\n"
            f"Detalhe técnico: {erro}\n"
            "O que já tinha sido feito foi desfeito, inclusive o arquivamento do "
            "relatório anterior — confira a pasta antes de rodar de novo."
        ) from erro

    for aviso in resultado.avisos:
        erro_console.print(Text(aviso, style = "yellow"))

    for _, para in resultado.arquivados:
        console.print(
            Text(f"\nRelatório anterior arquivado em {PASTA_ANTIGAS}/{para.name}", style = "dim")
        )

    console.print(f"\n[green]Relatório escrito.[/green] {resultado.caminho.name}")
    if plano.relatorio.alertas:
        console.print(
            Text(
                f"O documento saiu com {len(plano.relatorio.alertas)} aviso(s) dentro dele. "
                "Leia antes de enviar.",
                style = "yellow",
            )
        )


@app.command()
def template(
    saida: Path | None = typer.Option(
        None, "--saida", metavar = "ARQUIVO",
        help = "Onde escrever. Sem isso, template.docx na raiz do FLATCAP_ROOT."
    ),
    sim: bool = typer.Option(
        False, "--sim",
        help = "Executa de fato. Sem esta opção o comando apenas simula."
    ),
    env: str | None = typer.Option(
        None, "--env",
        help = "Caminho de um .env alternativo."
    ),
) -> None:
    """
    Escreve o modelo .docx que o relatório usa, para você ajustar no Word.

    O modelo sai com o corpo vazio e com os estilos `FlatCap Titulo`,
    `FlatCap Secao`, `FlatCap Corpo`, `FlatCap Legenda` e `FlatCap Nota` já
    definidos. Ajuste-os no Word — fonte, cor, tamanho —, ponha o logotipo no
    cabeçalho e salve. Todo relatório gerado daí em diante sai com essa cara, sem
    uma linha de Python.

    Tudo o que você escrever no corpo do modelo aparece **antes** do relatório, em
    todo relatório. É assim que uma capa institucional continua sendo a capa.

    POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.
    """
    from .documento import ARQUIVO_TEMPLATE, escrever_template

    cfg = _configuracao(env)
    destino = Path(saida) if saida is not None else cfg.root / ARQUIVO_TEMPLATE

    existe = destino.exists()
    console.print(
        Text.assemble(
            ("Modelo ", "dim"), (str(destino), "bold"),
            ("\n", ""),
            (
                "Existe e será substituído — os seus ajustes no Word se perdem."
                if existe
                else "Novo.",
                "yellow" if existe else "dim",
            ),
        )
    )

    if not sim:
        console.print(
            "\n[yellow]Simulação.[/yellow] Nada foi escrito.\n"
            "Repita com [bold]--sim[/bold] para gravar o modelo."
        )
        return

    try:
        escrever_template(destino)
    except OSError as erro:
        raise _abortar(
            "Escrita em disco", f"Falhei ao escrever {destino}.\nDetalhe técnico: {erro}"
        ) from erro

    console.print(f"\n[green]Modelo escrito.[/green] {destino}")
    console.print(
        Text(
            "Abra no Word, ajuste os estilos `FlatCap *` e o cabeçalho, e salve. O "
            "relatório procura este arquivo na pasta do projeto e depois no "
            "FLATCAP_ROOT.",
            style = "dim",
        )
    )


def _cabecalho_do_relatorio(plano: PlanoRelatorio) -> Text:
    """
    Quem, de quais análises, sobre qual banco, com qual modelo.

    As análises entram nomeadas e na ordem em que saem no documento, porque é
    aqui que se descobre — antes de abrir o `.docx` — que a normalidade não
    entrou porque ninguém a rodou.
    """
    relatorio = plano.relatorio
    ficha = relatorio.ficha
    manifesto = relatorio.manifesto
    analises = " · ".join(relatorio.analises) or "(nenhuma)"

    cabecalho = Text.assemble(
        (rotulo_do_projeto(ficha.raiz), "bold"),
        ("  ·  ", "dim"), ("registro ", "dim"), (ficha.record_id or "?", "bold"),
        ("  ·  ", "dim"), ("status ", "dim"), (ficha.status or "?", ""),
        "\n",
        ("Análises ", "dim"), (analises, "bold"),
        ("  ·  ", "dim"), ("rodada ", "dim"),
        (f"{manifesto.gerado_em:%d/%m/%Y %H:%M}", ""),
        ("  ·  ", "dim"), ("banco ", "dim"),
        (str(manifesto.banco.get("arquivo", "?")), ""),
        "\n",
        (f"{len(relatorio.secoes)} seção(ões)", ""),
        ("  ·  ", "dim"),
        (f"{plano.total_tabelas} tabela(s) e {plano.total_figuras} figura(s)", ""),
        ("  ·  ", "dim"), ("modelo ", "dim"),
        (
            str(plano.template) if plano.template else "(nenhum — estilos padrão)",
            "" if plano.template else "dim",
        ),
    )
    return cabecalho


def _tabela_do_relatorio(relatorio: Relatorio) -> Table:
    """
    Uma linha por seção do documento, com os arquivos que entram nela.

    É a mesma coluna de arquivos da descritiva, e serve para a mesma conferência:
    saber de qual variável saiu cada tabela **antes** de abrir o documento.

    A coluna `Análise` entrou quando a pasta passou a ter mais de uma rodada: a
    pergunta deixou de ser «o que entrou?» e passou a ser «o que entrou, e de
    qual rodada?». O nome aparece uma vez por bloco, e não repetido em toda
    linha — o que se lê na tela é onde uma análise acaba e a outra começa.
    """
    tabela = Table(show_header = True, header_style = "bold")
    tabela.add_column("#", justify = "right", no_wrap = True)
    tabela.add_column("Análise", no_wrap = True)
    tabela.add_column("Seção", overflow = "fold")
    tabela.add_column("Tipo", no_wrap = True)
    tabela.add_column("n", justify = "right", no_wrap = True)
    tabela.add_column("Faltantes", justify = "right", no_wrap = True)
    tabela.add_column("No documento", overflow = "fold")

    # `rodadas` vazio é o `Relatorio` montado à mão — em teste, ou por uma
    # camada de cima que não passou pela varredura. A tabela continua saindo,
    # sem o nome da análise, em vez de sair vazia.
    if relatorio.rodadas:
        pares = [
            (rodada.analise, secao)
            for rodada in relatorio.rodadas
            for secao in rodada.secoes
        ]
    else:
        pares = [("", secao) for secao in relatorio.secoes]

    anterior = ""
    for posicao, (analise, secao) in enumerate(pares, start = 1):
        proporcao = secao.faltantes / secao.n if secao.n else 0.0
        faltantes = Text("—", style = "dim")
        if secao.faltantes:
            faltantes = Text(
                f"{secao.faltantes} ({proporcao * 100:.0f}%)",
                style = "yellow" if proporcao >= 0.2 else "",
            )

        nomes = [t.arquivo for t in secao.tabelas] + [f.arquivo for f in secao.figuras]
        tabela.add_row(
            Text(str(posicao)),
            Text(analise if analise != anterior else "", style = "dim"),
            Text(secao.rotulo),
            Text(secao.tipo),
            Text(str(secao.preenchidos)),
            faltantes,
            Text(" · ".join(nomes), style = "dim"),
        )
        anterior = analise

    return tabela


def _alertas_no_terminal(relatorio: Relatorio) -> list[Panel]:
    """
    Os avisos que também vão para dentro do documento.

    Aparecem aqui **e** lá de propósito: o terminal você vê agora, o documento é o
    que sobra depois de o arquivo ser anexado a um e-mail.
    """
    if not relatorio.alertas:
        return []

    corpo = Text()
    for posicao, alerta in enumerate(relatorio.alertas):
        if posicao:
            corpo.append("\n\n")
        corpo.append(alerta.titulo, style = "bold")
        if alerta.detalhe:
            corpo.append("\n")
            corpo.append(alerta.detalhe, style = "")
    return [
        Panel(
            corpo,
            title = f"Vai escrito no documento ({len(relatorio.alertas)})",
            border_style = "yellow",
        )
    ]


def _fora_do_relatorio(relatorio: Relatorio) -> list[Panel]:
    """
    As variáveis que **nenhuma** análise descreveu, e por quê.

    Nenhuma, e não «a descritiva»: a lista `fora` da normalidade tem toda
    categórica do banco, e imprimi-la aqui diria que `sexo` ficou de fora do
    documento logo acima da linha da seção `Sexo`. Quem faz essa conta é o
    `relatorio._variaveis_de_fora`.

    Não entram no `.docx` — são diagnóstico seu, não conteúdo do cliente —, mas
    aparecem aqui pelo mesmo motivo da Fase 5: "não está no relatório" e "ninguém
    reparou que ela existia" são coisas diferentes.
    """
    if not relatorio.fora:
        return []

    corpo = Text()
    for posicao, item in enumerate(relatorio.fora):
        if posicao:
            corpo.append("\n")
        corpo.append(item.variavel, style = "bold")
        corpo.append(" — ")
        corpo.append(item.motivo)
    return [
        Panel(
            corpo,
            title = f"Fora do documento ({len(relatorio.fora)})",
            border_style = "dim",
        )
    ]


def _arvore_do_relatorio(plano: PlanoRelatorio) -> Tree:
    """
    Desenha o que `executar_relatorio` escreveria, lendo o próprio plano.
    """
    arvore = Tree(Text(str(plano.raiz), style = "dim"))

    if plano.arquivamentos:
        ramo = arvore.add(Text(f"{PASTA_ANTIGAS}/"))
        for _, para in plano.arquivamentos:
            ramo.add(Text.assemble((para.name, "yellow"), ("   recebe o anterior", "dim")))

    arvore.add(
        Text.assemble(
            (plano.destino.name, "bold green"),
            (
                "   novo" if not plano.arquivamentos else "   refeito",
                "dim",
            ),
        )
    )
    arvore.add(Text.assemble((ARQUIVO_HISTORICO, ""), ("   + 1 linha", "dim")))
    return arvore


if __name__ == "__main__":
    app()