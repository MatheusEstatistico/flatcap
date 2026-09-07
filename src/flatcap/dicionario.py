"""
O `dicionario.csv` — a decisão da reunião, escrita em um arquivo.

É a decisão de arquitetura nº 2 do roteiro: "esta variável é categórica, aquela é
numérica, esta eu ignoro, aquelas faixas são estas" é decisão sua, tomada com o
cliente na frente. Mas ela não pode ficar só na sua cabeça nem espalhada em
condicionais dentro do script. Aqui ela vira uma tabela, e a partir da Fase 5 a
automação inteira obedece a essa tabela.

Três coisas ao mesmo tempo: a **entrada** que dirige a descritiva, a
**documentação** do que foi combinado, e o **ponto de ajuste** quando o cliente
pedir mudança — reagrupar categorias vira editar uma célula, não caçar código.

## A regra que manda em tudo aqui: a automação propõe, você decide

O `flatcap perfil` roda mais de uma vez no mesmo projeto — antes da reunião, e de
novo quando o cliente mandar o banco revisado. Entre uma vez e outra, você
preencheu o arquivo. Então a segunda passada **funde**, e a fusão tem uma regra
só:

    Linha que já existe no arquivo não é tocada. Nunca. Nem um campo.

Variável nova do banco entra no fim com a sugestão automática; variável que sumiu
do banco **continua no arquivo**, marcada em `no_banco`, porque apagá-la jogaria
fora a decisão que você tomou na reunião — e o cliente que removeu uma coluna
sem avisar costuma devolvê-la na versão seguinte.

É a mesma regra do `acrescentar_versao` da Fase 3: alterar a ficha sem destruir o
que o usuário escreveu.

## Formato

Seis colunas. As cinco primeiras são as do roteiro; `no_banco` é do FlatCap.

    variavel           o nome exato da coluna no banco. É a chave.
    rotulo             como a variável aparece nas tabelas e no relatório.
    tipo               categorica | numerica | data | ignorar
    categorias_ordem   a ordem em que as categorias aparecem, separadas por `|`
    faixas             os cortes das faixas etárias e afins, separados por `|`
    no_banco           sim | nao — recalculado a cada perfil; não é decisão sua

**Colunas a mais que você acrescentar são preservadas.** Se você criar uma coluna
`nota` para anotar o que foi combinado sobre cada variável, ela volta intacta na
gravação seguinte, na mesma posição.

### Por que `;` entre campos e `|` dentro das listas

O roteiro escreve `Feminino;Masculino` em `categorias_ordem`, e isso pressupõe
que o separador de campos seja a vírgula. Só que este arquivo é editado no Excel
em português, onde o separador de listas do sistema é `;` — um `.csv` com vírgula
aberto com dois cliques cai todo em uma coluna só. Um arquivo que você precisa
editar em toda reunião não pode abrir errado.

Com `;` entre campos, o `;` dentro da lista precisaria de aspas, e um arquivo cujo
significado depende de aspas digitadas à mão é um arquivo que quebra na primeira
edição em bloco de notas. Daí `|` dentro das listas, que não aparece em nome de
categoria de banco de saúde nenhum.

A leitura é tolerante e a escrita é estrita: na leitura, o separador de campos é
descoberto (`;` ou `,`) e tanto `|` quanto `;` valem dentro das listas; na
gravação, sempre `;` e `|`. Assim um arquivo salvo por outra ferramenta continua
abrindo, e o arquivo que o FlatCap escreve é sempre o mesmo.
"""

from __future__ import annotations

import csv
import io
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .ficha import escrever_atomico

ARQUIVO_DICIONARIO = "dicionario.csv"

CATEGORICA = "categorica"
NUMERICA = "numerica"
DATA = "data"
IGNORAR = "ignorar"

TIPOS: tuple[str, ...] = (CATEGORICA, NUMERICA, DATA, IGNORAR)

COLUNAS: tuple[str, ...] = (
    "variavel",
    "rotulo",
    "tipo",
    "categorias_ordem",
    "faixas",
    "no_banco",
)

SEPARADOR_CAMPO = ";"
SEPARADOR_LISTA = "|"
CODIFICACAO = "utf-8-sig"

# O BOM vai no texto, e não na codificação da gravação, porque quem grava é o
# `escrever_atomico` do `ficha.py` — que existe para o `projeto.yaml` e escreve
# sempre em UTF-8. Com o caractere no começo da string, o arquivo sai com os
# mesmos bytes e a invariante "o texto é o arquivo" continua valendo, que é o que
# faz a simulação mostrar o que será gravado. É ele que faz o Excel em português
# abrir o arquivo em UTF-8 em vez de cp1252 — sem isso, `Condição` vira `CondiÃ§Ã£o`
# no arquivo que você mais edita à mão.
_BOM = "\ufeff"

_SEPARADORES_LISTA = ("|", ";")
_SIM, _NAO = "sim", "nao"

_CABECALHO_EXPLICATIVO = (
    "# dicionario.csv — o que fazer com cada variável do banco.",
    "# Escrito pelo `flatcap perfil` e preenchido por você na reunião.",
    "#",
    "#   tipo               categorica | numerica | data | ignorar",
    "#   categorias_ordem   a ordem das categorias, separadas por |",
    "#   faixas             os cortes, separados por | (ex.: 0|18|30|45|60|120)",
    "#   no_banco           preenchido pelo FlatCap; nao = a coluna sumiu do banco",
    "#",
    "# Linha que você editar não é sobrescrita: o `perfil` só acrescenta variável",
    "# nova e recalcula `no_banco`. Coluna a mais que você criar é preservada.",
)


class DicionarioError(RuntimeError):
    """
    Falha ao ler ou escrever o `dicionario.csv`, já traduzida para o usuário.
    """


class DicionarioInvalidoError(DicionarioError):
    """
    O arquivo existe e não dá para interpretar.

    Recusar é deliberado. Um dicionário meio lido produziria uma descritiva com
    metade das variáveis, e nada na saída denunciaria a metade que faltou.
    """

    def __init__(self, mensagem: str, caminho: Path) -> None:
        super().__init__(mensagem)
        self.caminho = caminho


@dataclass(frozen=True)
class Linha:
    """
    Uma variável no dicionário.

    Imutável como todo dado que circula no FlatCap. A fusão não altera linha:
    ela escolhe entre a que existe e a proposta, e a que existe sempre ganha.
    """

    variavel: str
    rotulo: str = ""
    tipo: str = CATEGORICA
    categorias_ordem: tuple[str, ...] = ()
    faixas: tuple[str, ...] = ()
    no_banco: bool = True
    extras: tuple[tuple[str, str], ...] = ()

    @property
    def analisavel(self) -> bool:
        """
        Se esta variável entra na descritiva da Fase 5.
        """
        return self.no_banco and self.tipo != IGNORAR


@dataclass(frozen=True)
class Fusao:
    """
    O resultado de cruzar o dicionário que existe com o que o banco mostra agora.
    """

    linhas: tuple[Linha, ...]
    existia: bool
    novas: tuple[str, ...] = ()
    preservadas: tuple[str, ...] = ()
    ausentes: tuple[str, ...] = ()
    reaparecidas: tuple[str, ...] = ()
    colunas: tuple[str, ...] = COLUNAS

    @property
    def total(self) -> int:
        return len(self.linhas)

    @property
    def mudou(self) -> bool:
        return not self.existia or bool(self.novas or self.ausentes or self.reaparecidas)


# Localização


def caminho_do_dicionario(raiz: Path) -> Path:
    return Path(raiz) / ARQUIVO_DICIONARIO


# Leitura


def ler(raiz: Path) -> tuple[Linha, ...]:
    """
    Lê o `dicionario.csv` de um projeto. Devolve vazio quando o arquivo não existe.

    Raises:
        DicionarioInvalidoError: cabeçalho irreconhecível, tipo fora da lista,
            variável repetida, faixas que não são números em ordem crescente, ou
            linha com mais campos do que o cabeçalho.
    """
    caminho = caminho_do_dicionario(Path(raiz))
    if not caminho.is_file():
        return ()
    return ler_arquivo(caminho)


def ler_arquivo(caminho: Path) -> tuple[Linha, ...]:
    """
    Lê um `dicionario.csv` a partir do caminho, sem passar pela pasta do projeto.
    """
    caminho = Path(caminho)
    texto = _ler_texto(caminho)
    campos, registros = _tabela(texto, caminho)

    linhas: list[Linha] = []
    vistas: dict[str, int] = {}

    for numero, registro in registros:
        variavel = (registro.get("variavel") or "").strip()
        if not variavel:
            continue

        if variavel in vistas:
            raise DicionarioInvalidoError(
                f"A variável `{variavel}` aparece duas vezes em {caminho.name}, nas "
                f"linhas {vistas[variavel]} e {numero}.\n"
                "Duas linhas para a mesma variável é ambiguidade: a descritiva não teria "
                "como saber qual das duas decisões vale. Apague a errada.",
                caminho,
            )
        vistas[variavel] = numero

        linhas.append(
            Linha(
                variavel=variavel,
                rotulo=(registro.get("rotulo") or "").strip(),
                tipo=_tipo(registro.get("tipo"), variavel, numero, caminho),
                categorias_ordem=_lista(registro.get("categorias_ordem")),
                faixas=_faixas(registro.get("faixas"), variavel, numero, caminho),
                no_banco=_booleano(registro.get("no_banco")),
                extras=tuple(
                    (nome, (registro.get(nome) or "").strip())
                    for nome in campos
                    if nome not in COLUNAS
                ),
            )
        )

    return tuple(linhas)


# Fusão


def fundir(existentes: tuple[Linha, ...], sugestoes: tuple[Linha, ...]) -> Fusao:
    """
    Cruza o dicionário que já existe com o que o banco mostra agora.

    Args:
        existentes: o que está no arquivo hoje. Vazio na primeira vez.
        sugestoes: uma por coluna do banco, na ordem em que elas aparecem lá.

    A ordem de saída segue a ordem das colunas no banco, e as variáveis que não
    estão mais no banco vão para o fim, na ordem em que estavam. Isso mantém o
    arquivo lado a lado com a planilha na tela — e junta no rodapé o que já não
    tem correspondência, em vez de deixar buracos no meio.
    """
    por_nome = {linha.variavel: linha for linha in existentes}
    no_banco = {linha.variavel for linha in sugestoes}

    linhas: list[Linha] = []
    novas: list[str] = []
    preservadas: list[str] = []
    reaparecidas: list[str] = []

    for sugestao in sugestoes:
        atual = por_nome.get(sugestao.variavel)
        if atual is None:
            linhas.append(sugestao)
            novas.append(sugestao.variavel)
            continue
        # A linha que existe vence inteira; `no_banco` é o único campo que o
        # FlatCap mantém, porque não é decisão de ninguém — é um fato do banco.
        if not atual.no_banco:
            reaparecidas.append(atual.variavel)
        linhas.append(_com_no_banco(atual, True))
        preservadas.append(atual.variavel)

    ausentes = [linha.variavel for linha in existentes if linha.variavel not in no_banco]
    linhas.extend(
        _com_no_banco(por_nome[nome], False) for nome in ausentes
    )

    return Fusao(
        linhas=tuple(linhas),
        existia=bool(existentes),
        novas=tuple(novas),
        preservadas=tuple(preservadas),
        ausentes=tuple(ausentes),
        reaparecidas=tuple(reaparecidas),
        colunas=_colunas_de(linhas),
    )


# Escrita


def texto_do_dicionario(linhas: tuple[Linha, ...], colunas: tuple[str, ...] = COLUNAS) -> str:
    """
    Monta o conteúdo do arquivo. Sem tocar no disco, para o `--sim` poder mostrá-lo.
    """
    buffer = io.StringIO(newline="")
    escritor = csv.writer(
        buffer, delimiter=SEPARADOR_CAMPO, lineterminator="\n", quoting=csv.QUOTE_MINIMAL
    )

    escritor.writerow(list(colunas))
    for linha in linhas:
        escritor.writerow([_campo(linha, nome) for nome in colunas])

    cabecalho = "\n".join(_CABECALHO_EXPLICATIVO)
    return f"{_BOM}{cabecalho}\n{buffer.getvalue()}"


def escrever(raiz: Path, fusao: Fusao) -> Path:
    """
    Grava o `dicionario.csv`. Escrita atômica, pela mesma razão do `projeto.yaml`:
    o arquivo guarda as decisões da reunião, e meio arquivo é pior do que nenhum.
    """
    caminho = caminho_do_dicionario(Path(raiz))
    escrever_atomico(caminho, texto_do_dicionario(fusao.linhas, fusao.colunas))
    return caminho


# Backend: leitura


def _ler_texto(caminho: Path) -> str:
    """
    Lê aceitando UTF-8 com e sem BOM, e cp1252 para o arquivo salvo pelo Excel.
    """
    bruto = caminho.read_bytes()
    for codificacao in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return bruto.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return bruto.decode("latin-1")


def _tabela(texto: str, caminho: Path) -> tuple[tuple[str, ...], list[tuple[int, dict[str, str]]]]:
    """
    Separa cabeçalho e registros, descobrindo o separador de campos.

    As linhas iniciadas por `#` são o cabeçalho explicativo que o FlatCap escreve.
    Elas são descartadas na leitura e reescritas na gravação — o que também
    significa que um comentário que você acrescente no meio do arquivo não
    sobrevive. É o limite conhecido do formato: `.csv` não tem comentário.
    """
    linhas = [linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")]
    conteudo = "\n".join(linhas).strip()

    if not conteudo:
        raise DicionarioInvalidoError(
            f"{caminho.name} está vazio — não tem nem o cabeçalho das colunas.\n"
            "Apague o arquivo e rode `flatcap perfil` de novo para gerá-lo.",
            caminho,
        )

    separador = _separador_de_campos(linhas)
    leitor = csv.reader(io.StringIO(conteudo), delimiter=separador)
    registros: list[tuple[int, dict[str, str]]] = []

    try:
        campos = tuple(_normalizar_nome(nome) for nome in next(leitor))
    except StopIteration:  # pragma: no cover - `conteudo` não vazio garante uma linha
        campos = ()

    if "variavel" not in campos:
        raise DicionarioInvalidoError(
            f"{caminho.name} não tem a coluna `variavel`.\n"
            f"Cabeçalho lido: {', '.join(campos) or '(vazio)'}\n"
            f"Esperado, no mínimo: {', '.join(COLUNAS)}\n\n"
            "Se o cabeçalho parece certo, o separador de campos pode ser outro: o FlatCap "
            f"grava com `{SEPARADOR_CAMPO}` e aceita `,` na leitura.",
            caminho,
        )

    for numero, valores in enumerate(leitor, start=2):
        if not any(valor.strip() for valor in valores):
            continue
        if len(valores) > len(campos):
            raise DicionarioInvalidoError(
                _mensagem_campos_demais(caminho, numero, campos, valores), caminho
            )
        valores = list(valores) + [""] * (len(campos) - len(valores))
        registros.append((numero, dict(zip(campos, valores, strict=True))))

    return campos, registros


def _separador_de_campos(linhas: list[str]) -> str:
    """
    `;` ou `,`. Decide pela linha de cabeçalho, que é a que tem os dois nomes fixos.
    """
    cabecalho = next((linha for linha in linhas if linha.strip()), "")
    return SEPARADOR_CAMPO if cabecalho.count(";") >= cabecalho.count(",") else ","


def _normalizar_nome(nome: str) -> str:
    """
    `Categorias_Ordem` e `categorias ordem` são a mesma coluna. O arquivo é editado
    no Excel, e o Excel ajuda a mudar maiúscula sem que ninguém peça.
    """
    limpo = _sem_acento(str(nome or "").strip().lower())
    return limpo.replace(" ", "_").replace("-", "_")


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def _tipo(valor: str | None, variavel: str, numero: int, caminho: Path) -> str:
    """
    Aceita `Categórica`, `CATEGORICA` e `categorica`; recusa o resto, dizendo o que vale.
    """
    bruto = (valor or "").strip()
    if not bruto:
        return CATEGORICA

    normalizado = _sem_acento(bruto.lower())
    if normalizado in TIPOS:
        return normalizado

    raise DicionarioInvalidoError(
        f"A variável `{variavel}` (linha {numero} de {caminho.name}) tem "
        f"tipo `{bruto}`, que não existe.\n"
        f"Os tipos são: {', '.join(TIPOS)}.\n\n"
        "`ignorar` é o tipo das colunas que não entram na descritiva — identificador, "
        "campo de observação livre, coluna auxiliar. Marcar é melhor do que deixar de "
        "fora: fica registrado que a decisão foi consciente.",
        caminho,
    )


def _lista(valor: str | None) -> tuple[str, ...]:
    """
    Quebra `Feminino|Masculino` — e também `Feminino;Masculino`, que é o que o
    roteiro escreve e o que sai quando o campo vem entre aspas de outra ferramenta.
    """
    bruto = (valor or "").strip()
    if not bruto:
        return ()

    separador = next(
        (s for s in _SEPARADORES_LISTA if s in bruto), _SEPARADORES_LISTA[0]
    )
    return tuple(parte.strip() for parte in bruto.split(separador) if parte.strip())


def _faixas(valor: str | None, variavel: str, numero: int, caminho: Path) -> tuple[str, ...]:
    """
    As faixas precisam ser números em ordem crescente, e é aqui que isso é conferido.

    Conferir na leitura e não na Fase 5 é deliberado: o erro é de digitação, e o
    momento de descobrir uma digitação errada é enquanto o arquivo está aberto na
    sua frente — não daqui a duas semanas, no meio da geração das tabelas.
    """
    partes = _lista(valor)
    if not partes:
        return ()

    numeros: list[float] = []
    for parte in partes:
        try:
            numeros.append(float(parte.replace(",", ".")))
        except ValueError as erro:
            raise DicionarioInvalidoError(
                f"A variável `{variavel}` (linha {numero} de {caminho.name}) tem "
                f"`{parte}` em `faixas`, que não é número.\n"
                "As faixas são os cortes, separados por `|`. Para 0–17, 18–29 e 30 ou "
                "mais, escreva `0|18|30|120`.",
                caminho,
            ) from erro

    if any(b <= a for a, b in zip(numeros, numeros[1:], strict=False)):
        raise DicionarioInvalidoError(
            f"As faixas da variável `{variavel}` (linha {numero} de {caminho.name}) não "
            f"estão em ordem crescente: {' | '.join(partes)}.\n"
            "Os cortes precisam subir, e sem repetir — senão uma faixa fica vazia ou "
            "duas se sobrepõem, e o mesmo caso cairia em duas linhas da tabela.",
            caminho,
        )

    return partes


def _booleano(valor: str | None) -> bool:
    """
    `no_banco` ausente vale `sim`: um dicionário escrito à mão, ou herdado de uma
    versão anterior do formato, descreve variáveis que existem.
    """
    bruto = _sem_acento((valor or "").strip().lower())
    if not bruto:
        return True
    return bruto not in {"nao", "no", "false", "0", "n"}


def _mensagem_campos_demais(
    caminho: Path, numero: int, campos: tuple[str, ...], valores: list[str]
) -> str:
    return (
        f"A linha {numero} de {caminho.name} tem {len(valores)} campos e o cabeçalho tem "
        f"{len(campos)}.\n\n"
        f"Quase sempre é um `{SEPARADOR_CAMPO}` digitado dentro de `categorias_ordem` ou "
        f"`faixas`, que o leitor entende como fim de campo. Dentro dessas duas colunas o "
        f"separador é `{SEPARADOR_LISTA}`:\n"
        "  Fundamental|Médio|Superior\n"
        "  0|18|30|45|60|120\n\n"
        f"Início da linha: {SEPARADOR_CAMPO.join(valores[:3])}"
    )


# Backend: escrita


def _com_no_banco(linha: Linha, presente: bool) -> Linha:
    if linha.no_banco == presente:
        return linha
    return Linha(
        variavel=linha.variavel,
        rotulo=linha.rotulo,
        tipo=linha.tipo,
        categorias_ordem=linha.categorias_ordem,
        faixas=linha.faixas,
        no_banco=presente,
        extras=linha.extras,
    )


def _colunas_de(linhas: list[Linha]) -> tuple[str, ...]:
    """
    As seis colunas do formato, mais as que o usuário tenha criado, na ordem em
    que apareceram.
    """
    extras: list[str] = []
    for linha in linhas:
        for nome, _ in linha.extras:
            if nome not in extras:
                extras.append(nome)
    return COLUNAS + tuple(extras)


def _campo(linha: Linha, nome: str) -> str:
    if nome == "variavel":
        return linha.variavel
    if nome == "rotulo":
        return linha.rotulo
    if nome == "tipo":
        return linha.tipo
    if nome == "categorias_ordem":
        return SEPARADOR_LISTA.join(linha.categorias_ordem)
    if nome == "faixas":
        return SEPARADOR_LISTA.join(linha.faixas)
    if nome == "no_banco":
        return _SIM if linha.no_banco else _NAO
    return dict(linha.extras).get(nome, "")


# Usado pelo `perfil.py` para montar a sugestão sem conhecer o formato do arquivo.


@dataclass(frozen=True)
class Sugestao:
    """
    O que a automação propõe para uma variável, antes de encontrar o que já existe.

    Existe para que `perfil.py` não precise construir `Linha` diretamente: quem
    propõe não deveria saber que o arquivo tem uma coluna `no_banco` nem que as
    listas são separadas por `|`.
    """

    variavel: str
    rotulo: str = ""
    tipo: str = CATEGORICA
    categorias_ordem: tuple[str, ...] = ()
    faixas: tuple[str, ...] = ()

    def como_linha(self) -> Linha:
        return Linha(
            variavel=self.variavel,
            rotulo=self.rotulo,
            tipo=self.tipo,
            categorias_ordem=self.categorias_ordem,
            faixas=self.faixas,
            no_banco=True,
        )