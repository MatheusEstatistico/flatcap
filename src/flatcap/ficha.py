"""
Leitura e escrita do `projeto.yaml` — a ficha do atendimento.

Este é o primeiro módulo do FlatCap que **lê** o disco. Até a Fase 2 o disco era
só destino: o `novo` decidia tudo a partir do REDCap e escrevia. Da Fase 3 em
diante a pasta do projeto passa a ser uma fonte de informação — qual é a versão
vigente do banco, o que já foi registrado, o que o cliente combinou. É a mesma
ideia que a Fase 8 chama de "índice reconstruível": a fonte da verdade é sempre
o disco, e qualquer cache pode ser jogado fora e refeito.

Duas consequências de projeto vêm daí:

1. **O `dados adicionar` não fala com o REDCap.** A pasta já sabe de quem é.
   Pedir a rede para uma operação de arquivo local acrescentaria uma forma de
   falhar (token, VPN, servidor fora do ar) a um comando que não precisa dela.
   Por isso as funções daqui recebem `Path`, e não `Config`: a assinatura diz
   que este módulo não tem nada a ver com credenciais.

2. **A escrita é atômica.** O `projeto.yaml` é a memória do projeto. Um
   `write_text` que morre na metade — falta de espaço, unidade de rede que cai,
   OneDrive sincronizando — deixa o arquivo truncado e a ficha perdida. Aqui a
   gravação escreve um arquivo temporário ao lado e só então o troca de nome por
   cima do original, com `os.replace`, que é uma operação atômica no POSIX e no
   Windows: ou o arquivo antigo continua inteiro, ou o novo está inteiro. Nunca
   metade dos dois.

## Por que ruamel.yaml e não o PyYAML

Os dois convivem no projeto, e a divisão de trabalho é clara: o `projeto.py`
escreve a ficha do zero com o PyYAML, e este módulo a **altera** com o
`ruamel.yaml` em modo round-trip.

A diferença está em quem lê o arquivo de volta. O PyYAML descarta comentário no
parser — para ele, comentário não é dado —, então um `safe_load` seguido de
`dump` devolveria os mesmos valores e nenhuma das anotações que você escreveu
ao lado de `prazo` ou de `analises`. O ruamel em `typ="rt"` carrega os
comentários, a ordem das chaves e o estilo de aspas presos aos dados, e os
devolve na gravação. É o que sustenta literalmente a promessa do cabeçalho da
ficha: "edite à vontade, o FlatCap não sobrescreve o que você escreveu".

Toda a persistência do `projeto.yaml` está atrás das quatro funções públicas
abaixo — `ler`, `acrescentar_versao`, `localizar_projeto` e `caminho_da_ficha`.
`dados.py` e `cli.py` importam só isso e não sabem qual biblioteca está em uso.

Há uma quinta função pública, `escrever_atomico`, e ela **não** faz parte desse
contrato: é o utilitário de gravação que a Fase 4 passou a compartilhar para o
`dicionario.csv` e o `perfil.md`. Ela mora aqui porque foi aqui que a garantia
precisou existir primeiro, e porque duas implementações de escrita atômica no
mesmo pacote é como uma delas deixa de receber a próxima correção. Quem trocar
esta implementação de YAML por outra precisa levá-la junto.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError

from .nomes import localizar_pasta, sanitizar
from .projeto import ARQUIVO_PROJETO

IMPLEMENTACAO = "ruamel.yaml (round-trip — preserva comentários e formatação)"

CHAVE_DADOS = "dados"

# Ordem em que os campos de uma versão aparecem no arquivo. Fixa de propósito:
# o `projeto.yaml` é lido por humanos, e coluna que muda de lugar cansa.
CAMPOS_VERSAO = ("arquivo", "origem", "sha256", "tamanho_bytes", "data")


class FichaError(RuntimeError):
    """
    Falha ao lidar com o `projeto.yaml`, já traduzida para o usuário.

    Erro próprio pelo mesmo motivo de `ConfigError`, `RedcapError` e
    `ProjetoError`: a CLI captura esta classe e transforma em painel. Qualquer
    outra exceção é bug de verdade e deve subir com o traceback inteiro.
    """


class ProjetoNaoEncontradoError(FichaError):
    """
    Nenhuma pasta em `FLATCAP_ROOT` corresponde ao identificador pedido.
    """


class FichaAusenteError(FichaError):
    """
    A pasta existe, mas não tem `projeto.yaml`.

    Acontece com pasta criada à mão, antes do FlatCap existir. Não é erro do
    usuário: é um projeto que ainda não foi adotado pela ferramenta.
    """

    def __init__(self, mensagem: str, pasta: Path) -> None:
        super().__init__(mensagem)
        self.pasta = pasta


class FichaInvalidaError(FichaError):
    """
    O `projeto.yaml` existe mas não é YAML válido, ou não tem o formato esperado.
    """

    def __init__(self, mensagem: str, caminho: Path) -> None:
        super().__init__(mensagem)
        self.caminho = caminho


@dataclass(frozen=True)
class Versao:
    """
    Uma versão do banco, do jeito que ela é registrada em `dados:`.

    Imutável como `Config`, `Cliente` e `Plano`. O `sha256` é o recibo: é o que
    responde "o arquivo que o cliente reenviou é diferente do anterior, ou ele
    mandou o mesmo de novo?" sem abrir planilha nenhuma.
    """

    arquivo: str
    origem: str
    sha256: str
    tamanho_bytes: int
    data: date | None = None

    @property
    def sequencia(self) -> int | None:
        """
        O número do prefixo (`00`, `01`, `02`...), ou `None` se o nome não seguir
        a convenção. É o índice da versão na história do projeto.
        """
        return sequencia_do_nome(self.arquivo)


@dataclass(frozen=True)
class Ficha:
    """
    O conteúdo do `projeto.yaml` que o FlatCap precisa conhecer.

    Deliberadamente **não** carrega tudo o que está no arquivo. `prazo`,
    `status` e `analises` são seus, e as fases seguintes leem o que precisarem.
    O que entra aqui é o mínimo para identificar o projeto e versionar o banco.
    """

    raiz: Path
    record_id: str
    matricula: str
    nome: str
    tipo: str
    status: str
    dados: tuple[Versao, ...]

    @property
    def versao_redcap(self) -> Versao | None:
        """
        A versão baixada do REDCap — a intocável. Identificada pela origem, e não
        pelo prefixo `00_`, porque a origem é o fato e o nome é convenção.
        """
        for versao in self.dados:
            if versao.origem == "redcap":
                return versao
        return None

    @property
    def ultima_versao(self) -> Versao | None:
        return self.dados[-1] if self.dados else None


def versao_vigente(ficha: Ficha) -> Versao | None:
    """
    A versão do banco que vale hoje: a de maior número de sequência.

    Não é `ficha.dados[-1]`. A ordem da lista é a ordem em que as versões foram
    registradas, e a ficha é editada à mão — uma entrada acrescentada fora de
    ordem faria a última da lista deixar de ser a mais nova. O número do prefixo,
    esse, é o índice da versão por construção da Fase 3.

    Empate (duas entradas sem prefixo reconhecível) resolve pela ordem da lista,
    que é a melhor informação que sobra.

    Mora aqui desde a Fase 6, e não no `banco.py`, onde nasceu. A pergunta "qual
    versão vale?" se responde lendo a ficha: não precisa do `pandas`, não abre
    arquivo nenhum. Deixá-la no módulo que importa o `pandas` obrigava o
    `relatorio.py` — que existe justamente para **não** abrir o banco — a pagar
    meio segundo de partida para consultar uma lista que ele já tinha na mão. O
    `banco.py` reexporta o nome, então nenhum chamador mudou.
    """
    if not ficha.dados:
        return None
    return max(
        ficha.dados,
        key=lambda versao: (
            versao.sequencia if versao.sequencia is not None else -1,
            ficha.dados.index(versao),
        ),
    )


# Localização do projeto no disco


def caminho_da_ficha(raiz: Path) -> Path:
    return Path(raiz) / ARQUIVO_PROJETO


def localizar_projeto(root: Path, identificador: str) -> Path:
    """
    Encontra a pasta do projeto a partir de um `record_id` ou de uma matrícula.

    A busca é feita **no disco**, lendo o `record_id` e a `matricula` de cada
    `projeto.yaml`. Aceitar os dois identificadores não é conveniência gratuita:
    o `record_id` é o que aparece no `flatcap listar` e o que você tem em mãos
    logo depois de criar a pasta; a matrícula é o que está no nome da pasta e o
    que você tem em mãos seis meses depois, olhando para o disco. Os dois
    identificam o mesmo projeto, e qual deles está à mão depende do dia.

    Raises:
        ProjetoNaoEncontradoError: nada bateu.
        FichaAusenteError: a pasta foi encontrada pelo nome, mas não tem ficha.
    """
    root = Path(root)
    procurado = sanitizar(str(identificador))
    if not procurado:
        raise ProjetoNaoEncontradoError(
            "Identificador vazio. Informe o `record_id` (como aparece no "
            "`flatcap listar`) ou a matrícula do cliente."
        )

    achados: list[Path] = []
    ilegiveis: list[tuple[Path, FichaInvalidaError]] = []

    for pasta in sorted(p for p in root.iterdir() if p.is_dir()):
        if not caminho_da_ficha(pasta).exists():
            continue
        try:
            ficha = ler(pasta)
        except FichaInvalidaError as erro:
            ilegiveis.append((pasta, erro))
            continue
        if procurado in {ficha.record_id, ficha.matricula}:
            achados.append(pasta)

    if len(achados) == 1:
        return achados[0]

    if len(achados) > 1:
        lista = "\n".join(f"  {p}" for p in achados)
        raise ProjetoNaoEncontradoError(
            f"Mais de uma pasta responde por {identificador!r}:\n{lista}\n"
            "Duas fichas com o mesmo record_id ou a mesma matrícula é sinal de "
            "pasta duplicada. Resolva no disco antes de continuar."
        )

    # Nada bateu. Antes de dizer "não existe", a busca pelo nome da pasta: a
    # matrícula está no nome, e a pasta pode ter sido criada à mão.
    pasta = localizar_pasta(root, procurado)
    if pasta is not None:
        for candidata, erro in ilegiveis:
            if candidata == pasta:
                raise erro
        raise FichaAusenteError(
            f"Encontrei a pasta {pasta.name}, mas ela não tem {ARQUIVO_PROJETO}.\n"
            "Pastas criadas à mão, antes do FlatCap, não têm ficha — e sem ficha "
            "não há onde registrar as versões do banco.\n"
            "Crie a pasta pelo `flatcap novo` ou copie um `projeto.yaml` de outro "
            "projeto e ajuste os campos de identificação.",
            pasta,
        )

    # Uma ficha ilegível não é uma nota de rodapé: enquanto houver uma, a busca
    # não pode afirmar que o projeto não existe — ele pode ser justamente aquele
    # que não deu para ler. Então o erro que sobe é o diagnóstico da ficha
    # quebrada, que diz o que fazer, e não um "não encontrei" que manda o usuário
    # procurar erro de digitação onde não há.
    if ilegiveis:
        pasta, erro = ilegiveis[0]
        raise FichaInvalidaError(
            f"Não consegui ler a ficha de {pasta.name}, então não dá para afirmar "
            f"se {identificador!r} é este projeto ou nenhum.\n\n{erro}"
            + (
                f"\n\nOutras {len(ilegiveis) - 1} ficha(s) também estão ilegíveis."
                if len(ilegiveis) > 1
                else ""
            ),
            erro.caminho,
        )

    raise ProjetoNaoEncontradoError(
        f"Nenhum projeto com record_id ou matrícula {identificador!r} em {root}.\n"
        "Confira o identificador no `flatcap listar`, ou a matrícula no nome da "
        "pasta."
    )


# Leitura


def ler(raiz: Path) -> Ficha:
    """
    Lê o `projeto.yaml` de uma pasta de projeto.

    Raises:
        FichaAusenteError, FichaInvalidaError
    """
    raiz = Path(raiz)
    caminho = caminho_da_ficha(raiz)

    if not caminho.exists():
        raise FichaAusenteError(
            f"A pasta {raiz.name} não tem {ARQUIVO_PROJETO}.", raiz
        )

    documento = _carregar_documento(caminho)

    if not isinstance(documento, dict):
        raise FichaInvalidaError(
            f"{caminho} não contém um mapeamento de campos.\n"
            f"O arquivo deveria começar com `record_id:`, `tipo:`, `matricula:`... "
            f"e o que veio foi um {type(documento).__name__}.",
            caminho,
        )

    return Ficha(
        raiz=raiz,
        record_id=_texto(documento, "record_id"),
        matricula=_texto(documento, "matricula"),
        nome=_texto(documento, "nome"),
        tipo=_texto(documento, "tipo"),
        status=_texto(documento, "status"),
        dados=_versoes(documento, caminho),
    )


# Escrita


def acrescentar_versao(raiz: Path, versao: Versao) -> None:
    """
    Acrescenta uma entrada ao fim da lista `dados:`, preservando o resto.

    Não é um "reescreve o arquivo com os campos que eu conheço". O `projeto.yaml`
    é editado à mão — o cabeçalho gerado pelo `novo` promete isso literalmente —
    e um comando que apagasse o `prazo` que você preencheu, ou a lista `analises`
    que você combinou na reunião, tornaria a promessa falsa.
    """
    caminho = caminho_da_ficha(Path(raiz))
    if not caminho.exists():
        raise FichaAusenteError(
            f"Não há {ARQUIVO_PROJETO} em {raiz}. Nada foi registrado.", Path(raiz)
        )

    documento = _carregar_documento(caminho)
    if not isinstance(documento, dict):
        raise FichaInvalidaError(
            f"{caminho} não contém um mapeamento de campos; não sei onde "
            "acrescentar a versão.",
            caminho,
        )

    lista = documento.get(CHAVE_DADOS)
    if not isinstance(lista, list):
        # Chave ausente, `dados:` vazio (que vira None) ou sobrescrito por engano.
        lista = CommentedSeq()
        documento[CHAVE_DADOS] = lista

    lista.append(_mapa_da_versao(versao))

    # Uma lista que veio do arquivo como `dados: []` mantém o estilo em linha, e
    # a entrada nova sairia toda espremida em uma linha só. Bloco é o formato em
    # que este arquivo é lido e editado.
    if hasattr(lista, "fa"):
        lista.fa.set_block_style()

    _gravar_documento(caminho, documento)


# Backend: ruamel.yaml


def _construtor() -> YAML:
    """
    O leitor/escritor round-trip, configurado.

    `typ="rt"` é o modo que carrega comentários e formatação junto com os dados
    e os devolve na hora de gravar. `preserve_quotes` mantém `matricula: "00742"`
    entre aspas — sem isso a matrícula voltaria como o número 742 e a pasta
    deixaria de bater com o registro. E `width` alto impede que o ruamel quebre
    um nome de arquivo longo em duas linhas: é YAML válido, mas ilegível em um
    arquivo feito para ser aberto no editor.
    """
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=2, offset=0)
    yaml.representer.add_representer(type(None), _representar_nulo)
    return yaml


def _representar_nulo(dumper, _dados):
    """
    Escreve o vazio como `null`, e não como uma linha terminada em dois-pontos.

    O ruamel, por padrão, grava `prazo:` — que o parser lê como nulo, mas que
    parece uma linha que alguém começou e não terminou. `prazo: null` diz que o
    campo está deliberadamente vazio. É também o que o PyYAML escreve, o que
    mantém as duas implementações de `ficha.py` produzindo o mesmo arquivo.
    """
    return dumper.represent_scalar("tag:yaml.org,2002:null", "null")


def _carregar_documento(caminho: Path):
    texto = _ler_texto(caminho)
    try:
        return _construtor().load(texto)
    except YAMLError as erro:
        raise FichaInvalidaError(_diagnostico(texto, caminho, erro), caminho) from erro


def _gravar_documento(caminho: Path, documento) -> None:
    import io

    buffer = io.StringIO()
    _construtor().dump(documento, buffer)
    escrever_atomico(caminho, buffer.getvalue())


def _mapa_da_versao(versao: Versao) -> CommentedMap:
    """
    Converte a `Versao` no mapeamento que vai para o arquivo, na ordem fixa.
    """
    mapa = CommentedMap()
    mapa["arquivo"] = versao.arquivo
    mapa["origem"] = versao.origem
    mapa["sha256"] = versao.sha256
    mapa["tamanho_bytes"] = int(versao.tamanho_bytes)
    mapa["data"] = versao.data
    return mapa


# Auxiliares comuns às duas implementações


def sequencia_do_nome(nome: str) -> int | None:
    """
    Extrai o prefixo numérico de `02_revisado_2026-03-14_banco.xlsx` → 2.

    Devolve `None` para nome que não segue a convenção — arquivo que o cliente
    largou na pasta à mão, por exemplo. `None` e `0` são coisas diferentes aqui,
    e é por isso que a função não devolve `-1` nem `0` como "não sei".
    """
    texto = str(nome or "")
    if len(texto) < 3 or texto[2] != "_" or not texto[:2].isdigit():
        return None
    return int(texto[:2])


def _ler_texto(caminho: Path) -> str:
    """
    Lê sempre em UTF-8, nunca na codificação do sistema.

    No Windows em português o padrão é cp1252, e o campo `nome` com acento
    voltaria diferente do que foi gravado — ou estouraria na leitura.
    """
    try:
        return caminho.read_text(encoding="utf-8")
    except UnicodeDecodeError as erro:
        raise FichaInvalidaError(
            f"{caminho} não está em UTF-8.\n"
            "O FlatCap sempre grava em UTF-8; um arquivo salvo por outro programa "
            "com codificação diferente precisa ser convertido antes.\n"
            f"Detalhe técnico: {erro}",
            caminho,
        ) from erro


def escrever_atomico(caminho: Path, texto: str) -> None:
    """
    Grava o arquivo inteiro ou não grava nada.

    Pública desde a Fase 4: o `dicionario.csv` guarda as decisões da reunião e o
    `perfil.md` é o documento que você leva para ela. Os dois merecem a mesma
    garantia que o `projeto.yaml`, e duas implementações de escrita atômica no
    mesmo pacote é como uma delas deixa de receber a próxima correção.

    O temporário é criado **na mesma pasta** do destino de propósito: `os.replace`
    só é atômico dentro do mesmo sistema de arquivos, e um temporário em `/tmp`
    poderia estar em outro disco — aí a troca vira cópia, que pode falhar pela
    metade. O `fsync` força o conteúdo para o disco antes da troca; sem ele, uma
    queda de energia logo depois pode deixar o nome novo apontando para um
    arquivo vazio.
    """
    caminho = Path(caminho)
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=caminho.parent,
            prefix=caminho.name + ".",
            suffix=".tmp",
            delete=False,
        ) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(texto)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
        temporario = None
    finally:
        if temporario is not None and temporario.exists():
            temporario.unlink(missing_ok=True)


def _texto(documento, chave: str) -> str:
    valor = documento.get(chave)
    if valor is None:
        return ""
    return str(valor).strip()


def _versoes(documento, caminho: Path) -> tuple[Versao, ...]:
    """
    Traduz a lista `dados:` para objetos, recusando o que não dá para interpretar.
    """
    bruto = documento.get(CHAVE_DADOS)
    if bruto is None:
        return ()
    if not isinstance(bruto, list):
        raise FichaInvalidaError(
            f"A chave `{CHAVE_DADOS}` de {caminho} deveria ser uma lista de "
            f"versões e é um {type(bruto).__name__}.",
            caminho,
        )

    versoes: list[Versao] = []
    for posicao, item in enumerate(bruto, start=1):
        if not isinstance(item, dict):
            raise FichaInvalidaError(
                f"A {posicao}ª entrada de `{CHAVE_DADOS}` em {caminho} não é um "
                "conjunto de campos. Cada versão precisa de `arquivo:`, `origem:`, "
                "`sha256:`, `tamanho_bytes:` e `data:`.",
                caminho,
            )
        versoes.append(
            Versao(
                arquivo=_texto(item, "arquivo"),
                origem=_texto(item, "origem"),
                sha256=_texto(item, "sha256").lower(),
                tamanho_bytes=_inteiro(item.get("tamanho_bytes")),
                data=_data(item.get("data")),
            )
        )
    return tuple(versoes)


def _inteiro(valor) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def _data(valor) -> date | None:
    """
    O YAML já entrega `date` quando a data está sem aspas. Com aspas vem texto,
    e é isso que esta função resgata — o arquivo é editado à mão, e digitar
    `data: "2026-03-14"` é natural.
    """
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor).strip()[:10])
    except ValueError:
        return None


def _diagnostico(texto: str, caminho: Path, erro: Exception) -> str:
    """
    Traduz o estouro do parser, com um caso especial que vale ouro.

    Versões do `flatcap novo` anteriores à 0.4.0 escreviam uma barra solta na
    primeira linha do arquivo (uma continuação de linha `\\` digitada como `/`
    no cabeçalho). O YAML gerado é sintaticamente impossível, e a mensagem crua
    do parser fala de `<document start>` — que não diz nada a quem abrir o
    arquivo e vir um `/` inofensivo na primeira linha.
    """
    primeira = next((linha for linha in texto.splitlines() if linha.strip()), "")
    if primeira.strip() == "/":
        return (
            f"{caminho} começa com uma barra solta na primeira linha.\n\n"
            "É um defeito conhecido das versões do `flatcap novo` anteriores à "
            "0.4.0: o cabeçalho de comentários saía com um `/` antes do primeiro "
            "`#`, e isso torna o arquivo inteiro ilegível.\n\n"
            "Conserto: apague a linha que contém só `/`. Para consertar todas as "
            "pastas de uma vez, rode `python reparar_fichas.py`.\n\n"
            f"Detalhe técnico: {erro}"
        )
    return (
        f"{caminho} não é um YAML válido.\n\n"
        "Isso costuma ser edição à mão: indentação com tabulação em vez de "
        "espaços, dois-pontos dentro de um valor sem aspas (`nome: Fulano: o "
        "Segundo`) ou um alias `*id001` que ficou órfão.\n\n"
        f"Detalhe técnico: {erro}"
    )