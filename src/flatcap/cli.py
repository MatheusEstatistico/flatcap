"""
Interface de linha de comando do FlatCap.

Esta camada não contém regras de negócio, ela lê argumentos, chama as camadas de baixo, 
formata a saída e escolhe o código de saída do processo.
Manter isso firme desde o início permite testar tudo sem simular terminal. 
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

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
from .ficha import IMPLEMENTACAO, FichaError, localizar_projeto
from .modelo import ALUNO, CAMPO_ANEXO, CAMPOS_REDCAP, INDEFINIDO, Cliente, normalizar_varios
from .nomes import localizar_pasta
from .projeto import (
    ARQUIVO_HISTORICO,
    ARQUIVO_PROJETO,
    PASTA_ANTIGAS,
    PASTA_DADOS,
    ClienteIncompletoError,
    Plano,
    ProjetoExistenteError,
    RegistroNaoEncontradoError,
    executar,
    preparar,
    tamanho_legivel,
)
from .redcap import RedcapError, exportar_projeto, exportar_registros, tem_arquivo

app = typer.Typer(
    name="flatcap",
    help="Orquestrador de fluxo para atendimento estatistico",
    no_args_is_help=True,
    add_completion=False,
)

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
  `Text(...)` em vez de uma string crua: impede que colchetes vindos da mensagem de erro sejam interpretados como marcação do rich.
  """
  erro_console.print(Panel(Text(mensagem), title=titulo, border_style="red"))
  return typer.Exit(code=1)

def _configuracao(env: str | None, criar_root: bool = False) -> Config:
  """
  Carrega a configuração ou ecerra o comeando com a mensagem do arquivo `config.py`.
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
  Testar as credenciais, a conecção com o REDCap e a pasta de dados.

  É o primeiro comando a rodar quando algo parecer errado: 
    responde se o problema está na configuração, na rede ou no token.
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
  console.print(f"\n[green]Tudo certo.[/green] Projeto conectado: [bold]{titulo}[/bold]")

@app.command()
def listar(
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
  Mostra o que chego ude novo de um lado e o que já virou pasta dentro do FLATCAP_ROOT.
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

  if conferir_anexos:
    clientes = _reconferir_anexos(cfg, clientes)

  console.print(_tabela_de_clientes(cfg, clientes))
  console.print(_resumo(cfg, clientes))

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
          Text(f"Não foi possível conferir o anexo do registro {cliente.record_id}: {erro}",
               style = "yellow")
        )

  return [
    replace(c, tem_anexo = True) if c.record_id in confirmados else c
    for c in clientes
  ]


def _tabela_de_clientes(cfg: Config, clientes: list[Cliente]) -> Table:
  """
  Monta a tabela que sai do comando `listar`.
  Valores que vem do REDCap entram como `Text`, nunca como string crua: um
  nome com colchete viraria marcação do rich e sumiria da tela.
  """
  tabela = Table(show_header = True, header_style = "bold")
  tabela.add_column("id", justify = "right", no_wrap = True)
  tabela.add_column("Tipo", no_wrap = True)
  tabela.add_column("Matrícula", no_wrap = True)
  tabela.add_column("Nome", overflow = "fold")
  tabela.add_column("Anexo", justify = "center", no_wrap = True)
  tabela.add_column("Pasta local", overflow = "fold")

  for cliente in clientes:
    pasta = localizar_pasta(cfg.root, cliente.matricula)
    tabela.add_row(
      Text(cliente.record_id or "?"),
      Text(cliente.tipo, style = "yellow" if cliente.tipo == INDEFINIDO else ""),
      Text(cliente.matricula or "—", style = "" if cliente.matricula else "yellow"),
      Text(cliente.nome or "(sem nome)", style = "" if cliente.nome else "yellow"),
      Text("sim", style = "green") if cliente.tem_anexo else Text("não", style = "yellow"),
      Text(pasta.name, style = "green") if pasta else Text("—", style = "dim"),
    )

  return tabela

def _resumo(cfg: Config, clientes: list[Cliente]) -> str:
  """
    Uma linha com o que exige atenção, para não ter que contar a tabela na mão.
  """
  pendentes = [c for c in clientes if not localizar_pasta(cfg.root, c.matricula)]
  sem_anexo = [c for c in clientes if not c.tem_anexo]
  incompletos = [c for c in clientes if not c.identificado]
  alunos = [c for c in clientes if c.tipo == ALUNO]

  partes = [
    f"[bold]{len(clientes)}[/bold] solicitações",
    f"[bold]{len(pendentes)}[/bold] sem pasta local",
  ]
  if sem_anexo:
    partes.append(f"[yellow]{len(sem_anexo)} sem anexo[/yellow]")
  if incompletos:
    partes.append(f"[yellow]{len(incompletos)} com cadastro incompleto[/yellow]")
  if alunos:
    partes.append(f"{len(alunos)} de alunos")

  return "\n" + " · ".join(partes)

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

  POR PADRÃO APENAS SIMULA: desenha a árvore que seria criada e não escreve nada. Repita com --sim para executar.
  """
  cfg = _configuracao(env)

  try: 
    plano = preparar(cfg, record_id)
  except ProjetoExistenteError as erro: 
    console.print(Panel(Text(str(erro)), title = "Nada para fazer", border_style = "yellow"))
    return
  except (RegistroNaoEncontradoError, ClienteIncompletoError) as erro:
    raise _abortar("Solicitação", str(erro)) from erro
  except RedcapError as erro:
    raise _abortar("Conexão com o REDCap", str(erro)) from erro

  console.print(_cabecalho_do_plano(plano))
  console.print(_arvore_do_plano(cfg, plano))

  if not plano.tem_anexo:
    console.print(
      Text(
        f"Este registro não tem anexo no campo '{CAMPO_ANEXO}'." 
        "A pasta é criada assim mesmo — o banco entra depois, pela Fase 3.",
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
    console.print(Panel(Text(str(erro)), title = "Nada para fazer", border_style = "yellow"))
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
  """
  arvore = Tree(Text(str(cfg.root), style = "dim"))
  raiz = arvore.add(Text(plano.raiz.name, style = "bold green"))

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



if __name__ == "__main__":
  app()
