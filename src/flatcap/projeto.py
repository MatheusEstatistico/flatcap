"""
A pasta do projeto no disco: decidir o que criar e depois criar.

Primeira camada que **compõe** as outras: junta `config`, `redcap`, `modelo` e
`nomes` para responder a uma pergunta só — o que acontece quando chega uma
solicitação nova. A separação interna é a regra da casa:

    plano = preparar(cfg, record_id)   # lê o REDCap, decide tudo, não toca no disco
    executar(plano)                    # só escreve; não decide mais nada

É o que faz o `--dry-run` valer alguma coisa: os dois modos percorrem o mesmo
`Plano`, o modo simulação apenas não chama `executar`.

## O que mudou na 1.1.0: a pasta do cliente deixou de ser a pasta do projeto

    FLATCAP_ROOT/
    └── 00742 - José Antônio de Sá/      do CLIENTE — pode já existir
        └── Projeto 006/                 do PROJETO — é esta que o `novo` cria
            ├── projeto.yaml
            ├── historico.md
            ├── 1. Dados originais/
            ├── 2. Versões antigas/
            └── 3. Análises/

O mesmo cliente volta ao REDCap com um estudo novo, e o formulário lhe dá um
`record_id` novo. Antes, a segunda solicitação batia na recusa "já existe pasta
para essa matrícula" e não tinha para onde ir.

**A idempotência mudou de sujeito, e não de regra.** Ela continua sendo "o
`novo` nunca escreve sobre pasta existente" — o que mudou é qual pasta responde
pela pergunta. Pasta do cliente já existente passou a ser o caso normal (é o
cliente que voltou) e é reaproveitada; quem faz o comando sair com código 0
avisando é a pasta `Projeto NNN`.

Uma consequência que vale registrar: a pasta do cliente é reaproveitada **como
ela estiver no disco**, mesmo que o nome não seja mais o que `nome_pasta`
produziria hoje — nome corrigido à mão, grafia arrumada depois. É a mesma
decisão da Fase 2 (a matrícula é a parte que não muda), e é o que impede o
FlatCap de criar uma segunda pasta para um cliente que já tem uma.
"""

from __future__ import annotations

import hashlib
import mimetypes
import stat
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

import yaml

from .config import Config
from .modelo import (
    CAMPO_ANEXO,
    CAMPO_FINALIDADE,
    CAMPOS_REDCAP,
    Cliente,
    mapa_de_rotulos,
    normalizar,
)
from .nomes import (
    PREFIXO_PROJETO,
    SEPARADOR_ROTULO,
    NomeInvalidoError,
    localizar_pasta,
    localizar_projeto_por_record,
    nome_do_projeto,
    nome_pasta,
    sanitizar,
)
from .redcap import (
    ArquivoAusenteError,
    ArquivoRedcap,
    RedcapError,
    exportar_arquivo,
    exportar_metadados,
    exportar_registros,
)

SUBPASTAS: tuple[str, ...] = (
    "1. Dados originais",
    "2. Versões antigas",
    "3. Análises",
)

ARQUIVO_PROJETO = "projeto.yaml"
ARQUIVO_HISTORICO = "historico.md"

PASTA_DADOS = SUBPASTAS[0]    # onde vive a versão vigente do banco
PASTA_ANTIGAS = SUBPASTAS[1]  # para onde a versão anterior é rodada na Fase 3
PASTA_ANALISES = SUBPASTAS[2] # onde a Fase 5 escreve a pasta `descritiva/`
# O .docx da Fase 6 fica na raiz da pasta do projeto — não há `4. Relatórios/`.

# A rodada da descritiva. Mora aqui, e não no `descritiva.py` onde nasceu, desde
# a Fase 6: o desenho da pasta é assunto deste módulo, e o `relatorio.py` precisa
# saber onde a rodada está sem importar o módulo que carrega o `pandas` para
# calculá-la. O `descritiva.py` reexporta o nome, então nenhum chamador mudou.
PASTA_DESCRITIVA = "descritiva"

# A rodada da normalidade, a primeira análise da Fase 7. Mora ao lado da
# descritiva pelo mesmo motivo: o desenho da pasta é assunto deste módulo, e o
# `relatorio.py` precisa saber onde as rodadas estão sem importar os módulos que
# carregam o `pandas` e o `scipy` para calculá-las.
PASTA_NORMALIDADE = "normalidade"

# A rodada do cruzamento. Mesmo motivo das duas de cima, e o mesmo nome em três
# lugares: a pasta, o campo `analise` do manifesto e a chave da ficha — a lista
# `analises:` e o bloco `cruzamento:` com os pares.
PASTA_CRUZAMENTO = "cruzamento"

# A rodada da associação. O mesmo nome nos três lugares, como o cruzamento: a
# pasta, o campo `analise` do manifesto e a chave da ficha — a lista `analises:` e
# o bloco `associacao:` com os pares.
PASTA_ASSOCIACAO = "associacao"

# A rodada da correlação. O mesmo nome nos três lugares, como as duas de cima: a
# pasta, o campo `analise` do manifesto e a chave da ficha — a lista `analises:` e
# o bloco `correlacao:` com os pares.
PASTA_CORRELACAO = "correlacao"

# A rodada da comparação. O mesmo nome nos três lugares, como as de cima: a pasta,
# o campo `analise` do manifesto e a chave da ficha — a lista `analises:` e o bloco
# `comparacao:` com os itens. Uma pasta só para todos os testes de comparação: o
# teste é escolhido dentro da análise, e não é uma análise por teste.
PASTA_COMPARACAO = "comparacao"

# O modelo do relatório. Mora aqui pelo mesmo motivo das pastas: o nome de um
# arquivo que o FlatCap procura dentro da pasta do projeto é desenho de pasta.
# Ele estava escrito duas vezes — no `documento.py`, que é quem o grava, e no
# `relatorio.py`, que não podia importar o `documento.py` sem trazer o
# `python-docx` junto para uma simulação que não escreve documento nenhum. Os
# dois passaram a importá-lo daqui, e o `documento.py` reexporta o nome.
ARQUIVO_TEMPLATE = "template.docx"

# As extensões que um banco do cliente pode ter.
#
# Moram aqui, e não no `banco.py` que as usa para abrir, pelo mesmo motivo que
# `PASTA_DESCRITIVA`: quem precisa da resposta **sem** abrir o banco é o
# `dados.py`, que confronta a ficha com o disco e precisa distinguir o que, na
# pasta, é candidato a versão do que é um relatório arquivado. E o `dados.py`
# não pode importar o `banco.py` — é o `banco.py` que importa o `dados.py`.
EXTENSOES_DE_BANCO: tuple[str, ...] = (".xlsx", ".csv")


def pastas_das_analises(raiz: Path) -> tuple[Path, ...]:
    """
    As pastas de rodada que existem em `3. Análises/`, em ordem de nome.

    É a varredura que o `relatorio.py` faz para descobrir **quais** análises
    foram rodadas neste projeto, em vez de procurar uma pasta de nome fixo. Foi
    a falta dela que deixou a normalidade escrever `normalidade.csv` e os
    `qq_*.png` no disco sem que nada disso entrasse no `.docx` — e teria feito o
    mesmo com o teste t e o qui-quadrado.

    Só o primeiro nível, e só diretório: o que está **dentro** de uma rodada é
    assunto do `manifesto.json` dela. Quem decide se a pasta é mesmo uma rodada é
    quem a lê — aqui a pergunta é só qual pasta existe.
    """
    pasta = Path(raiz) / PASTA_ANALISES
    if not pasta.is_dir():
        return ()
    return tuple(sorted(item for item in pasta.iterdir() if item.is_dir()))


def pasta_da_analise(raiz: Path, analise: str) -> Path:
    """
    Onde mora a rodada vigente de uma análise: `3. Análises/<analise>/`.

    Uma função e não uma concatenação em cada módulo, porque é aqui que a resposta
    muda no dia em que ela mudar — e porque é ela que o `relatorio.py` vai usar
    para varrer `3. Análises/*/` em vez de procurar uma pasta com nome fixo.

    O nome da análise é o mesmo que vai escrito no `manifesto.json` (o campo
    `analise`) e o mesmo que se escreve na lista `analises:` da ficha. Um nome só
    para as três coisas é o que faz a lista da reunião, a pasta no disco e a ordem
    das seções do documento se encontrarem sem tradução no meio.
    """
    return Path(raiz) / PASTA_ANALISES / analise

PREFIXO_REDCAP = "00_redcap_" # feito dessa forma para manter uma ordem cronológica

STATUS_INICIAL = "novo"

_MIMES_GENERICOS = {"", "application/octet-stream", "binary/octet-stream"}

class ProjetoError(RuntimeError):
    """
    Falha ao montar a pasta do projeto, já traduzida para o usuário.

    Erro próprio pelo mesmo motivo de `ConfigError` e `RedcapError`: a CLI captura
    esta classe e transforma em painel; qualquer outra exceção é bug de verdade e
    deve subir com o traceback inteiro.
    """


class RegistroNaoEncontradoError(ProjetoError):
    """
    O REDCap não tem nenhum registro com este `record_id`.
    """


class LayoutAntigoError(ProjetoError):
    """
    A pasta do cliente ainda tem o `projeto.yaml` na raiz — o formato anterior
    à 1.1.0, de quando um cliente tinha um projeto só.

    Recusa e não conserta: mover pasta do usuário é operação que o FlatCap
    nunca fez sozinho, e a mensagem diz exatamente o que mover. O `ficha.py`
    tem um erro homônimo, com o mesmo texto, para o mesmo diagnóstico do lado
    de quem só lê o disco — ver `texto_da_migracao`.
    """


class ClienteIncompletoError(ProjetoError):
    """
    O registro existe, mas não dá para nomear a pasta a partir dele.

    A automação cria pasta apenas para registro bem formado. Quem diagnostica é o
    `flatcap listar`, que já marca esses casos em amarelo; o `novo` apenas se
    recusa a produzir uma pasta que você teria de renomear depois.
    """


class ProjetoExistenteError(ProjetoError):
    """
    Já existe pasta para **este projeto**. Nada foi mudado.

    Até a 1.0.0 a pergunta era "esta matrícula já tem pasta?". Agora é "este
    `record_id` já tem pasta?", porque a matrícula passou a poder ter várias:
    recusar pela matrícula tornaria impossível criar o segundo projeto de um
    cliente, que é justamente o caso que esta versão existe para atender.

    O caminho fica gravado em `.pasta`, isso previne erros de quando a pasta é criada manualmente.
    """

    def __init__(self, mensagem: str, pasta: Path) -> None:
        super().__init__(mensagem)
        self.pasta = pasta


@dataclass(frozen = True)
class ArquivoPlanejado: 
    """
    Um arquivo já baixado com destino e o recibo pronto -> ainda na memória. 

    O `sha256` é calculado aqui. É a diferença entre o recibo e uma anotação.  
    """
    caminho: Path
    conteudo: bytes
    sha256: str

    @property
    def tamanho(self) -> int:
        return len(self.conteudo)

    @property
    def tamanho_legivel(self) -> str:
        """
        Tamanho formatado para o terminal e para o `historico.md`.
        """
        return tamanho_legivel(self.tamanho)


@dataclass(frozen = True)
class Plano:
    """
    Tudo o que será criado, decidido e pronto para escrever.

    Imutável como `Config` e `Cliente`: entre a simulação e a execução ningué, altera um caminho em
    trânsito.
    O conteúdo dos dois arquivos de texto já vem montado, para que `executar` não precise tomar
    nenhuma decisão.
    """
    cliente: Cliente
    raiz: Path
    subpastas: tuple[Path, ...]
    banco: ArquivoPlanejado | None
    projeto_yaml: str
    historico_md: str
    quando: datetime
    pasta_cliente: Path | None = None
    cliente_novo: bool = True

    @property
    def tem_anexo(self) -> bool:
        return self.banco is not None

    @property
    def pasta_do_cliente(self) -> Path:
        """
        A pasta do cliente, que é onde a pasta do projeto vai morar.

        Deduzida da raiz quando não vier no plano: `pasta_cliente` tem default
        para que um `Plano` montado à mão em teste antigo continue válido.
        """
        return self.pasta_cliente if self.pasta_cliente is not None else self.raiz.parent


@dataclass(frozen = True)
class Resultado:
    """
    O que `executar` de fato criou, e o que não foi planejado.

    O `avisos` existe para o caso de somente-leitura: em unidades de rede ou pasta sincronizada em
    nuvem o `chmod` pode não pegar.
    """
    criados: tuple[Path, ...]
    avisos: tuple[str, ...] = ()


# Casos de uso
def preparar(
        cfg: Config,
        record_id: str,
        agora: datetime | None = None,
) -> Plano:
    """
    Lê o REDCap e devolve o plano completo na pasta. Nada de novo. 

    Args; 
        agora: relógio injetável. Sem ele, os testes não teriam como comparar o nome do arquivo, que
        carrega a data.

    Raises: 
        RegistroNaoEncontradoError, ClienteIncompletoError, ProjetoExistenteError
        RedcapError: falha de rede, token ou permissão.
    """
    quando = agora or datetime.now()
    cliente = _buscar_cliente(cfg, record_id)
    _conferir_identificacao(cliente)
    pasta_cliente, raiz, cliente_novo = _destino(cfg, cliente)
    anexo = _baixar_anexo(cfg, cliente)
    return _montar_plano(cliente, pasta_cliente, raiz, cliente_novo, anexo, quando)

def executar(plano: Plano) -> Resultado:
    """
    Escreve o plano no disco. Escritor puro: não decide, não consulta a rede.
    """
    criados: list[Path] = []
    avisos: list[str] = []

    # `parents=True` cria a pasta do cliente quando ela não existe e a aceita
    # quando existe — mas continua estourando `FileExistsError` se a **última**
    # pasta do caminho já estiver lá. É exatamente a regra que se quer aqui: o
    # cliente que voltou reaproveita a pasta dele, e o projeto repetido recusa.
    cliente_novo = plano.cliente_novo and not plano.pasta_do_cliente.exists()

    try:
        plano.raiz.mkdir(parents=True)
    except FileExistsError as erro:
        raise ProjetoExistenteError(
            f"A pasta apareceu no disco entre a simulação e a execução: {plano.raiz}\n"
            "Nada foi alterado. Rode `flatcap novo` de novo para ver o estado atual.",
            plano.raiz,
        ) from erro

    if cliente_novo:
        criados.append(plano.pasta_do_cliente)
    criados.append(plano.raiz)

    for subpasta in plano.subpastas:
        subpasta.mkdir()
        criados.append(subpasta)

    if plano.banco is not None:
        plano.banco.caminho.write_bytes(plano.banco.conteudo)
        criados.append(plano.banco.caminho)
        if not marcar_somente_leitura(plano.banco.caminho):
            avisos.append(
                f"Não consegui marcar {plano.banco.caminho.name} como somente-leitura.\n"
                "O arquivo está lá, mas sem a barreira contra edição acidental no Excel."
            )

    for nome_arquivo, conteudo in (
        (ARQUIVO_PROJETO, plano.projeto_yaml),
        (ARQUIVO_HISTORICO, plano.historico_md),
    ):
        caminho = plano.raiz / nome_arquivo
        _escrever_texto(caminho, conteudo)
        criados.append(caminho)

    return Resultado(criados = tuple(criados), avisos = tuple(avisos))

def anotar(raiz: Path, acao: str, agora: datetime | None = None) -> None:
    """
    Acrescenta uma linha para o `historico.md`. 
    """
    with (raiz / ARQUIVO_HISTORICO).open("a", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(_linha_historico(acao, agora or datetime.now()))

def marcar_somente_leitura(caminho: Path) -> bool:
    """
    Tira a permissão de escrita do arquivo. Devolve se conseguiu.
    """
    try:
        modo = caminho.stat().st_mode
        caminho.chmod(modo & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    except OSError:
        return False
    return True

def nome_do_banco(anexo: ArquivoRedcap, quando: date, record_id: str = "") -> str:
    """
    Monta `00_redcap_AAAA-MM-DD_<nome original>`.
    """
    base = sanitizar(anexo.nome)
    if not base:
        base = f"banco_{sanitizar(record_id) or 'sem_id'}"
    if not Path(base).suffix:
        base += _extensao_do_mime(anexo.tipo_mime)
    return f"{PREFIXO_REDCAP}{quando:%Y-%m-%d}_{base}"


# Backend de `preparar`

def _buscar_cliente(cfg: Config, record_id: str) -> Cliente:
    """
    Traz um único registro do REDCap e normaliza.
    """
    pedido = str(record_id).strip()
    registros = exportar_registros(cfg, fields=CAMPOS_REDCAP, records=[pedido])

    if not registros:
        raise RegistroNaoEncontradoError(
            f"Não existe registro {pedido!r} neste projeto do REDCap.\n"
            "Rode `flatcap listar` para ver os record_id disponíveis."
        )

    cliente = normalizar(registros[0], _rotulos_do_formulario(cfg))
    # O `record_id` normalizado vem do corpo da resposta; se por alguma razão vier
    # vazio, o que o usuário digitou é a melhor identificação que temos.
    return cliente if cliente.record_id else replace(cliente, record_id=pedido)

def _rotulos_do_formulario(cfg: Config) -> dict[str, dict[str, str]]:
    """
    Os rótulos das opções do `fin`, para que a ficha guarde texto e não código.

    Uma segunda chamada à API, e é a única do fluxo que pode falhar sozinha: há
    token do REDCap com permissão de exportar registros e sem permissão de
    exportar o dicionário de variáveis. Falhar aqui derrubaria o `flatcap novo`
    inteiro por causa de uma linha da primeira página, então a falha é engolida
    e a `finalidade` sai vazia.

    Vazia, e não com o código cru: `finalidade: 2` na ficha é um valor que
    ninguém consegue ler e que ninguém percebe estar errado, enquanto o campo em
    branco cai no alerta `texto_ausente` do relatório e aparece na sua frente.
    """
    try:
        metadados = exportar_metadados(cfg, fields=[CAMPO_FINALIDADE])
    except RedcapError:
        return {}
    return mapa_de_rotulos(metadados, campos=[CAMPO_FINALIDADE])


def _conferir_identificacao(cliente: Cliente) -> None:
    """
    Recusa registro sem matrícula ou sem nome, dizendo qual dos dois falta.
    """
    faltando = [
        rotulo
        for rotulo, valor in (("matrícula", cliente.matricula), ("nome", cliente.nome))
        if not valor
    ]
    if not faltando:
        return

    raise ClienteIncompletoError(
        f"O registro {cliente.record_id} não tem {' nem '.join(faltando)}.\n"
        "Sem isso, a pasta sairia com um nome que você teria de corrigir à mão\n"
        "depois — e o `flatcap listar` deixaria de reencontrá-la.\n"
        "Complete o registro no REDCap e rode de novo."
        "O `flatcap listar` marca em amarelo os cadastros incompletos."
    )

def _destino(cfg: Config, cliente: Cliente) -> tuple[Path, Path, bool]:
    """
    Decide onde a pasta vai ficar. Devolve (pasta do cliente, raiz, cliente é novo).

    Três conferências, nesta ordem, e cada uma responde a uma pergunta diferente:

    1. **O cliente já tem pasta?** Por matrícula, via `localizar_pasta`. Se tem,
       é reaproveitada — é o cliente voltando com um trabalho novo, e é o caso
       que esta versão existe para atender. Se não tem, o nome é montado agora.

    2. **A pasta do cliente ainda está no formato antigo?** `projeto.yaml` na
       raiz dela quer dizer que a migração para dois níveis não chegou ali.
       Criar `Projeto NNN` dentro mesmo assim deixaria a pasta com duas fichas
       em níveis diferentes, e a busca do `ficha.localizar_projeto` passaria a
       encontrar a nova e ignorar a antiga — a história do primeiro trabalho
       some da vista sem nada dizer que sumiu. Recusa, com o conserto escrito.

    3. **Este `record_id` já tem pasta em algum lugar?** Não só dentro desta
       pasta de cliente: em todo o root. É o caso da matrícula corrigida no
       REDCap depois de a pasta existir — a busca por matrícula não acha mais o
       cliente, e sem esta conferência o mesmo trabalho ganharia duas pastas,
       cada uma com metade da história.
    """
    root = Path(cfg.root)

    pasta_cliente = localizar_pasta(root, cliente.matricula)
    cliente_novo = pasta_cliente is None

    if pasta_cliente is None:
        try:
            pasta_cliente = root / nome_pasta(cliente.matricula, cliente.nome)
        except NomeInvalidoError as erro:
            raise ClienteIncompletoError(
                f"Da matrícula {cliente.matricula!r} do registro {cliente.record_id} não\n"
                "sobrou nada depois da limpeza de caracteres.\n"
                "Corrija o registro no REDCap."
            ) from erro
    elif (pasta_cliente / ARQUIVO_PROJETO).exists():
        raise LayoutAntigoError(texto_da_migracao(pasta_cliente))

    try:
        destino = pasta_cliente / nome_do_projeto(cliente.record_id)
    except NomeInvalidoError as erro:
        raise ClienteIncompletoError(
            f"O registro {cliente.record_id!r} não tem um `record_id` que sirva de\n"
            "nome de pasta. A pasta do projeto é nomeada por ele.\n"
            "Confira o registro no REDCap."
        ) from erro

    if destino.exists():
        raise ProjetoExistenteError(
            f"Já existe pasta para o registro {cliente.record_id}:\n"
            f"  {destino}\n"
            "Nada foi alterado. O `novo` nunca escreve sobre pasta existente.",
            destino,
        )

    noutro_lugar = localizar_projeto_por_record(root, cliente.record_id)
    if noutro_lugar is not None:
        raise ProjetoExistenteError(
            f"O registro {cliente.record_id} já tem pasta, em outro cliente:\n"
            f"  {noutro_lugar}\n"
            f"E a matrícula {cliente.matricula} deste registro aponta para:\n"
            f"  {pasta_cliente}\n\n"
            "Nada foi alterado. Isso costuma ser a matrícula corrigida no REDCap "
            "depois de a pasta ter sido criada. Renomeie a pasta do cliente para a "
            "matrícula nova — a pasta do projeto, dentro dela, não muda.",
            noutro_lugar,
        )

    return pasta_cliente, destino, cliente_novo


def texto_da_migracao(pasta_do_cliente: Path, record_id: str = "") -> str:
    """
    O diagnóstico da pasta que ficou no formato de antes da 1.1.0.

    Mora aqui, e é usado também pelo `ficha.py`, porque a mensagem descreve o
    **desenho da pasta**, que é assunto deste módulo. Cada um dos dois levanta o
    seu próprio erro — a regra da casa continua sendo um erro por módulo —, e
    nenhum dos dois reescreve o texto por conta própria: duas versões da mesma
    instrução de conserto é como uma delas fica desatualizada.
    """
    alvo = nome_do_projeto(record_id) if sanitizar(str(record_id)) else f"{PREFIXO_PROJETO}NNN"
    numero = (
        ""
        if sanitizar(str(record_id))
        else "\n  (NNN é o `record_id` que está escrito no `projeto.yaml` dessa pasta)"
    )
    subpastas = "\n".join(f"      {nome}/" for nome in SUBPASTAS)
    return (
        f"A pasta {Path(pasta_do_cliente).name} está no formato anterior à versão "
        f"1.1.0, com o {ARQUIVO_PROJETO} na raiz dela.\n\n"
        "A partir da 1.1.0 um cliente pode ter mais de um projeto, então a pasta "
        "do cliente virou um contêiner e cada projeto mora em uma subpasta "
        "própria:\n\n"
        f"  {Path(pasta_do_cliente).name}/\n"
        f"  └── {alvo}/{numero}\n"
        f"      {ARQUIVO_PROJETO}\n"
        f"      {ARQUIVO_HISTORICO}\n"
        f"{subpastas}\n\n"
        f"Conserto: crie a pasta `{alvo}` dentro de "
        f"`{Path(pasta_do_cliente).name}` e mova para dentro dela tudo o que está "
        "lá hoje — as três subpastas numeradas, o `projeto.yaml`, o "
        "`historico.md`, o `perfil.md`, o `dicionario.csv` e os `.docx` de "
        "relatório.\n"
        "A exceção é o `template.docx`: deixado na pasta do cliente, ele passa a "
        "valer para todos os projetos dele."
    )

def _baixar_anexo(cfg: Config, cliente: Cliente) -> ArquivoRedcap | None:
    """
    Baixa o banco anexado. Devolve `None` quando o registro não tem anexo.
    """
    try:
        return exportar_arquivo(cfg, cliente.record_id, CAMPO_ANEXO)
    except ArquivoAusenteError:
        return None

def _montar_plano(
    cliente: Cliente,
    pasta_cliente: Path,
    raiz: Path,
    cliente_novo: bool,
    anexo: ArquivoRedcap | None,
    quando: datetime,
) -> Plano:
    """
    Converte cliente + anexo em um `Plano` inteiramente resolvido.
    """
    hoje = quando.date()
    banco = None

    if anexo is not None:
        banco = ArquivoPlanejado(
            caminho=raiz / PASTA_DADOS / nome_do_banco(anexo, hoje, cliente.record_id),
            conteudo=anexo.conteudo,
            sha256=hashlib.sha256(anexo.conteudo).hexdigest(),
        )

    return Plano(
        cliente=cliente,
        raiz=raiz,
        subpastas=tuple(raiz / nome for nome in SUBPASTAS),
        banco=banco,
        projeto_yaml=_texto_projeto_yaml(cliente, banco, hoje),
        historico_md=_texto_historico(cliente, banco, quando),
        quando=quando,
        pasta_cliente=pasta_cliente,
        cliente_novo=cliente_novo,
    )


# Conteúdo de arquivos de texto 

class _SemAncoras(yaml.SafeDumper):
    """
    Dumper que nunca cria âncora nem alias.
    
    O PyYAML deduplica valores repetidos: como `criado_em` e a `data` do banco são a mesma data, o
    arquivo saía com `criado_em: &id001 2026-08-29` e `data: *id001`.
    Subclasse de `SafeDumper`, então a garantia de não instanciar objeto arbitrário na leitura
    continua valendo.
    """
    def ignore_aliases(self, data: object) -> bool:  # noqa: ARG002
        return True


def _texto_em_bloco(dumper: yaml.SafeDumper, dado: str) -> yaml.ScalarNode:
    """
    Texto com quebra de linha sai como bloco literal, e não entre aspas.

    Sem isso os `objetivos` do cliente saem assim:

        objetivos: "Objetivo geral: avaliar o perfil.\\n\\nObjetivos específicos:\\n..."

    que é YAML perfeitamente válido e ilegível num arquivo cujo cabeçalho convida
    a editá-lo. Com isso saem assim:

        objetivos: |
          Objetivo geral: avaliar o perfil.

          Objetivos específicos:
          ...

    O PyYAML só aceita o bloco literal se nenhuma linha terminar em espaço e não
    houver `\\r` no meio — quem garante isso é o `modelo._texto_longo`, na
    fronteira onde o texto entra.
    """
    estilo = "|" if "\n" in dado else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", dado, style=estilo)


_SemAncoras.add_representer(str, _texto_em_bloco)

_CABECALHO_YAML = """
# projeto.yaml — a ficha deste atendimento, escrita pelo `flatcap novo`.
#
# Este arquivo é seu: edite à vontade. O FlatCap lê o que está aqui e não
# sobrescreve o que você escreveu.
#
#   prazo     10 dias úteis contados da reunião. A data da reunião está no
#             calendário, não no REDCap — preencha depois de agendá-la.
#   status    novo | em_analise | entregue
#
#   finalidade  para que o cliente pediu a análise — o campo `fin` do
#   objetivos   formulário, e o `obj1`, como ele escreveu. Os dois saem
#               impressos na primeira página de todo relatório deste projeto,
#               então corrija aqui o que vier truncado, abreviado ou com erro
#               de digitação: o que está escrito neste arquivo é o que o
#               cliente vai ler. `null` faz o documento sair com um marcador
#               visível e um aviso dentro dele, e não em silêncio.
#
#   analises  o que foi combinado na reunião. A Fase 7 lê esta lista para
#             saber quais módulos rodar.
#   dados     uma entrada por versão do banco, em ordem cronológica.
"""

def _texto_projeto_yaml(cliente: Cliente, banco: ArquivoPlanejado | None, hoje:date) -> str:
    """
    Monta o `projeto.yaml`.
    """
    dados: list[dict[str, object]] = []
    if banco is not None:
        dados.append(
            {
                "arquivo": banco.caminho.name,
                "origem": "redcap",
                "sha256": banco.sha256,
                "tamanho_bytes": banco.tamanho,
                "data": hoje,
            }
        )

    corpo: dict[str, object] = {
        "record_id": cliente.record_id,
        "tipo": cliente.tipo,
        "matricula": cliente.matricula,
        "nome": cliente.nome,
        "criado_em": hoje,
        "prazo": None,
        "status": STATUS_INICIAL,
        # `or None` para que o campo em branco saia `finalidade: null`, do mesmo
        # jeito que o `prazo` — uma linha terminada em dois-pontos parece uma
        # linha que alguém começou e não terminou.
        "finalidade": cliente.finalidade or None,
        "objetivos": cliente.objetivos or None,
        "analises": [],
        "dados": dados,
    }

    corpo_yaml = yaml.dump(
        corpo,
        Dumper=_SemAncoras,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return f"{_CABECALHO_YAML}\n{corpo_yaml}"

def _texto_historico(cliente: Cliente, banco: ArquivoPlanejado | None, quando: datetime) -> str:
    """
    Monta o `historico.md` com a primeira linha de log já escrita.

    O título carrega cliente **e** projeto desde a 1.1.0: um `historico.md` que
    se apresentasse só como `Projeto 006` não diria de quem ele é, e o arquivo
    existe justamente para ser aberto seis meses depois.
    """
    titulo = (
        f"{nome_pasta(cliente.matricula, cliente.nome)}"
        f"{SEPARADOR_ROTULO}{nome_do_projeto(cliente.record_id)}"
    )

    if banco is not None:
        acao = (
            f"`flatcap novo {cliente.record_id}` — pasta criada; anexo "
            f"`{banco.caminho.name}` ({banco.tamanho_legivel}) baixado do "
            f"campo `{CAMPO_ANEXO}`."
        )
    else:
        acao = (
            f"`flatcap novo {cliente.record_id}` — pasta criada. O registro não tem "
            f"anexo no campo `{CAMPO_ANEXO}`; o banco ainda precisa ser recebido."
        )

    return (
        f"# Histórico — {titulo}\n"
        "\n"
        "Uma linha por ação do FlatCap nesta pasta, em ordem cronológica.\n"
        "\n"
        f"{_linha_historico(acao, quando)}"
    )

def _linha_historico(acao: str, quando: datetime) -> str:
    return f"- **{quando:%Y-%m-%d %H:%M}** — {acao}\n"


# Funções auxiliares 

def _escrever_texto(caminho: Path, conteudo: str) -> None:
    """
    Escreve texto sempre em UTF-8 e sempre com `\\n`.
    """
    caminho.write_text(conteudo, encoding="utf-8", newline="\n")

def _extensao_do_mime(tipo_mime: str) -> str:
    tipo = (tipo_mime or "").strip().lower()
    if tipo in _MIMES_GENERICOS:
        return ""
    return mimetypes.guess_extension(tipo) or ""

def tamanho_legivel(bytes_: int) -> str:
    """
    Formata o tamanho para leitura humana, com vírgula decimal.

    Pública porque a Fase 3 imprime a mesma coluna na linha do tempo das
    versões: dois formatadores diferentes para a mesma grandeza é como um
    relatório acaba com "1,5 MiB" numa tabela e "1572864" na seguinte.
    """
    tamanho = float(bytes_)
    for unidade in ("B", "KiB", "MiB", "GiB"):
        if tamanho < 1024 or unidade == "GiB":
            if unidade == "B":
                return f"{int(tamanho)} B"
            return f"{tamanho:.1f} {unidade}".replace(".", ",")
        tamanho /= 1024
    return f"{bytes_} B"




