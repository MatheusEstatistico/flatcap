"""
A pasta do projeto no disco: decidir o que criar e depois criar.

Primeira camada que **compõe** as outras: junta `config`, `redcap`, `modelo` e
`nomes` para responder a uma pergunta só — o que acontece quando chega uma
solicitação nova. A separação interna é a regra da casa:

    plano = preparar(cfg, record_id)   # lê o REDCap, decide tudo, não toca no disco
    executar(plano)                    # só escreve; não decide mais nada

É o que faz o `--dry-run` valer alguma coisa: os dois modos percorrem o mesmo
`Plano`, o modo simulação apenas não chama `executar`.
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
from .modelo import CAMPO_ANEXO, CAMPOS_REDCAP, Cliente, normalizar
from .nomes import NomeInvalidoError, localizar_pasta, nome_pasta, sanitizar
from .redcap import ArquivoAusenteError, ArquivoRedcap, exportar_arquivo, exportar_registros

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


class ClienteIncompletoError(ProjetoError):
    """
    O registro existe, mas não dá para nomear a pasta a partir dele.

    A automação cria pasta apenas para registro bem formado. Quem diagnostica é o
    `flatcap listar`, que já marca esses casos em amarelo; o `novo` apenas se
    recusa a produzir uma pasta que você teria de renomear depois.
    """


class ProjetoExistenteError(ProjetoError):
    """
    Já existe pasta para essa matrícula. Nada foi mudado. 

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

    @property
    def tem_anexo(self) -> bool:
        return self.banco is not None


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
    raiz = _destino(cfg, cliente)
    anexo = _baixar_anexo(cfg, cliente)
    return _montar_plano(cliente, raiz, anexo, quando)

def executar(plano: Plano) -> Resultado:
    """
    Escreve o plano no disco. Escritor puro: não decide, não consulta a rede.
    """
    criados: list[Path] = []
    avisos: list[str] = []

    try:
        plano.raiz.mkdir(parents=True)
    except FileExistsError as erro:
        raise ProjetoExistenteError(
            f"A pasta apareceu no disco entre a simulação e a execução: {plano.raiz}\n"
            "Nada foi alterado. Rode `flatcap novo` de novo para ver o estado atual.",
            plano.raiz,
        ) from erro
    
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

    cliente = normalizar(registros[0])
    # O `record_id` normalizado vem do corpo da resposta; se por alguma razão vier
    # vazio, o que o usuário digitou é a melhor identificação que temos.
    return cliente if cliente.record_id else replace(cliente, record_id=pedido)

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

def _destino(cfg: Config, cliente: Cliente) -> Path:
    """
    Decide onde a pasta vai ficar e garante que ainda não existe. A conferência é por matrícula, via
    `localizar_pasta`.
    """
    existente = localizar_pasta(Path(cfg.root), cliente.matricula)
    if existente is not None:
        raise ProjetoExistenteError(
            f"Já existe pasta para a matrícula {cliente.matricula}:\n"
            f"  {existente}\n"
            "Nada foi alterado. O `novo` nunca escreve sobre pasta existente",
            existente,
        )

    try:
        destino = Path(cfg.root) / nome_pasta(cliente.matricula, cliente.nome)
    except NomeInvalidoError as erro:
        raise ClienteIncompletoError(
            f"Da matrícula {cliente.matricula!r} do registro {cliente.record_id} não\n"
            "sobrou nada depois da limpeza de caracteres.\n"
            "Corrija o registro no REDCap."
        ) from erro

    if destino.exists():
        raise ProjetoExistenteError(
            f"Já existe algo neste caminho: {destino}\nNada foi alterado.",
            destino,
        )
    return destino

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
    raiz: Path,
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

_CABECALHO_YAML = """
# projeto.yaml — a ficha deste atendimento, escrita pelo `flatcap novo`.
#
# Este arquivo é seu: edite à vontade. O FlatCap lê o que está aqui e não
# sobrescreve o que você escreveu.
#
#   prazo     10 dias úteis contados da reunião. A data da reunião está no
#             calendário, não no REDCap — preencha depois de agendá-la.
#   status    novo | em_analise | entregue
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
    """
    titulo = nome_pasta(cliente.matricula, cliente.nome)

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




