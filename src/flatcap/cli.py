"""
Interface de linha de comando do FlatCap.

Esta camada não contém regras de negócio, ela lê argumentos, chama as camadas de baixo, formata a saída e escolhe o código de saída do processo.
Manter isso firme desde o início permite testar tudo sem simular terminal. 
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__
from .config import Config, ConfigError, carregar
from .redcap import RedcapError, exportar_projeto

app = typer.Typer(
    name="flatcap",
    help="Orquestrador de fluxo para atendimento estatistico: REDCap -> pastas -> analise -> relatorio.docx.",
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

def _abortar(titulo: str, mensagem: str) -> typer.Exit:
  """
  Imprime o erro em um painel e devolve a exceção que encerra o comando.
  `Text(...)` em vez de uma string crua: impede que colchetes vindos da mensagem de erro sejam interpretados como marcação do rich.
  """
  erro_console.print(Panel(Text(mensagem), title=titulo, border_style="red"))
  return typer.Exit(code=1)

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

  É o primeiro comando a rodar quando algo parecer errado: responde se o problema está na configuração, na rede ou no token.
  """
  tabela = Table(show_header = True, header_style = "bold")
  tabela.add_column("Verificação", no_wrap = True)
  tabela.add_column("Resultado")
  tabela.add_column("Detalhe", overflow = "fold")

  # 1. Configuração 
  try: 
    cfg: Config = carregar(env_file = env, criar_root = criar_root)
  except ConfigError as e:
    raise _abortar("configuração", str(e)) from e

  tabela.add_row("Arquivo .env", OK, cfg.origem_env or "(variáveis do ambiente do sistema)")
  tabela.add_row("REDCAP_API_URL", OK, cfg.api_url)
  tabela.add_row("REDCAP_TOKEN", OK, cfg.token_mascarado)
  tabela.add_row("FLATCAP_ROOT", OK, STR(cfg.root))

  # 2. Conexão com o REDCap 
  try: 
    projeto = exportar_projeto(cfg)
  except RedcapError as e: 
    tabela.add_row("Conexão REDCap", FALHA, "ver detalhe abaixo")
    console.print(tabela)
    raise _abortar("Conexão com o REDCap", str(e)) from e

  titulo = projeto.get("project_file", "(sem título)")
  tabela.add_row("Conexão REDCap", OK, f"{titulo} (id {projeto.get("project_id", "?")})")

  console.print(tabela)
  console.print(f"\n[green]Tudo certo.[/green] Projeto conectado: [bold]{titulo}[/bold]")

if __name__ == "__main__":
  app()
