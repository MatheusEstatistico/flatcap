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

if TYPE_CHECKING:  # só para as anotações: ver o comentário em `perfil`
    from .perfil import Achado, Perfil, PlanoPerfil

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
  tabela.add_row("Leitura de bancos", OK, _versoes_de_leitura())

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

def _versoes_de_leitura() -> str:
  """
  Quais versões abrem o banco do cliente hoje.

  Registrar isso no `doctor` é barato e evita a pergunta mais difícil de
  responder da Fase 5: um gráfico saiu diferente do que saía antes — mudaram os
  dados ou mudou a biblioteca?
  """
  import openpyxl
  import pandas

  return f"pandas {pandas.__version__} · openpyxl {openpyxl.__version__}"

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

  console.print(_tabela_de_clientes(cfg, clientes))
  console.print(_resumo(cfg, clientes, total))

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
  Valores que vêm do REDCap entram como `Text`, nunca como string crua: 
      um nome com colchete viraria marcação do rich e sumiria da tela.
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

def _resumo(cfg: Config, clientes: list[Cliente], total: int | None = None) -> str:
  """
  Uma linha com o que exige atenção, para não ter que contar a tabela na mão.
  """
  total = len(clientes) if total is None else total
  pendentes = [c for c in clientes if not localizar_pasta(cfg.root, c.matricula)]
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
    ("Projeto ", "dim"), (ficha.raiz.name, "bold"),
    ("  ·  ", "dim"), ("registro ", "dim"), (ficha.record_id or "?", "bold"),
    ("  ·  ", "dim"), ("status ", "dim"), (ficha.status or "?", ""),
  )


def _cabecalho_da_ficha(tempo: LinhaDoTempo) -> Text:
  ficha = tempo.ficha
  return Text.assemble(
    ("Projeto ", "dim"), (ficha.raiz.name, "bold"),
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
    ("Projeto ", "dim"), (ficha.raiz.name, "bold"),
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


if __name__ == "__main__":
    app()