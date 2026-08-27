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

app = typer.Typer()

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

  """
  pass

@app.callback()
def principal()


@app.command()
def doctor()





if __name__ == "__main__":
  app()

