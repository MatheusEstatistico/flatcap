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
    categorias_ordem   a ordem das categorias, separadas por `|`, e o rótulo de
                       cada uma depois de um `=` quando a coluna for de código
    faixas             os cortes das faixas etárias e afins, separados por `|`
    no_banco           sim | nao — recalculado a cada perfil; não é decisão sua

**Colunas a mais que você acrescentar são preservadas.** Se você criar uma coluna
`nota` para anotar o que foi combinado sobre cada variável, ela volta intacta na
gravação seguinte, na mesma posição.

### O rótulo de cada categoria, e por que ele mora dentro do `categorias_ordem`

Metade dos bancos chega com a categórica codificada: `sexo` vale `1` e `2`, e o
que cada um quer dizer está na cabeça do cliente. Até a 1.2.0 não havia onde
escrever isso, e a tabela, o gráfico e o documento saíam com `1` e `2` — a lacuna
mais visível da ferramenta para quem lê o relatório.

    sexo;Sexo;categorica;1=Feminino|2=Masculino;;sim
    escolaridade;Escolaridade;categorica;Fundamental|Médio|Superior;;sim

A regra é uma linha: **`codigo=rótulo` quando houver `=`; sem `=`, o valor é o
próprio rótulo.** A segunda linha acima é um dicionário de antes desta versão, e
continua valendo sem mudar um caractere — a fusão nunca toca linha preenchida,
então o rótulo entra quando você chegar nele, e não há migração.

Dentro da mesma célula, e **não** em uma sétima coluna. Uma sétima coluna ligaria
`1|2` a `Feminino|Masculino` pela posição, e reordenar uma sem a outra poria
`Feminino` em cima da contagem de `2` — sem erro, sem aviso, e conferível só
lendo o banco. Na mesma célula o desalinhamento é impossível: a ordem e o rótulo
são a mesma decisão, tomada de uma vez, na frente do cliente.

**Os rótulos não vêm do REDCap.** O `DataDictionary.xlsx` descreve o formulário
de solicitação, não o banco do cliente — que chega como anexo e não tem
dicionário nenhum. Eles são digitados por você, na reunião, olhando a tabela
"Valores observados" do `perfil.md`, que existe exatamente para essa pergunta.

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
descoberto (`;` ou `,`) e o `;` só vale dentro das listas **quando não for o
separador de campos daquele arquivo**; na gravação, sempre `;` e `|`. Assim um
arquivo salvo por outra ferramenta continua abrindo, e o arquivo que o FlatCap
escreve é sempre o mesmo.

A ressalva do `;` é o conserto de um round-trip quebrado. Com `;` entre campos, o
`csv.writer` grava `Alta; a pedido` entre aspas — corretamente, e a categoria é
uma só. A leitura, aceitando `;` dentro da lista, devolvia duas: `Alta` e
`a pedido`. O arquivo voltava do disco diferente do que tinha sido gravado, que é
exatamente o que a fusão existe para impedir.
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

# Entre o valor que está no banco e o texto que sai na tabela:
# `categorias_ordem = 1=Feminino|2=Masculino`.
#
# Dentro da mesma célula do `categorias_ordem`, e não em uma sétima coluna. A
# justificativa inteira está em `_categorias`, e o resumo é que uma sétima coluna
# ligaria `1|2` a `Feminino|Masculino` **pela posição** — e reordenar uma sem a
# outra trocaria os rótulos no relatório sem erro nenhum.
SEPARADOR_ROTULO = "="
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
    "# Coluna de código? Escreva o que cada um quer dizer, com = :",
    "#     categorias_ordem = 1=Feminino|2=Masculino",
    "# Antes do = vai o valor como ele está no banco; depois, como ele deve sair",
    "# na tabela, no gráfico e no relatório. Sem =, o valor é o próprio rótulo.",
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
    # Os **códigos**, na ordem, do jeito que eles aparecem no banco. É por eles
    # que a descritiva casa a tabela com a coluna; o rótulo é outra coisa e mora
    # logo abaixo.
    categorias_ordem: tuple[str, ...] = ()
    faixas: tuple[str, ...] = ()
    no_banco: bool = True
    extras: tuple[tuple[str, str], ...] = ()
    # `(código, rótulo)`, só para os códigos que ganharam um. Pares e não `dict`
    # porque tudo o que circula no FlatCap é imutável, e um `dict` dentro de uma
    # `dataclass` frozen é imutável só por educação.
    rotulos_das_categorias: tuple[tuple[str, str], ...] = ()

    @property
    def analisavel(self) -> bool:
        """
        Se esta variável entra na descritiva da Fase 5.
        """
        return self.no_banco and self.tipo != IGNORAR

    @property
    def tem_rotulos(self) -> bool:
        return any(rotulo for _, rotulo in self.rotulos_das_categorias)

    def rotulo_de(self, codigo: str) -> str:
        """
        Como esta categoria se escreve na tabela e no gráfico.

        Cai no próprio código quando não há rótulo, e é isso que faz uma coluna
        de texto (`Feminino|Masculino`) e uma coluna de código
        (`1=Feminino|2=Masculino`) atravessarem o mesmo caminho: na primeira o
        valor **é** o rótulo, e não há nada a resolver.

        Quem chama não precisa saber qual das duas está lidando — que é a razão
        de isto ser um método aqui e não um `if` em cada lugar que imprime.
        """
        for chave, rotulo in self.rotulos_das_categorias:
            if chave == codigo:
                # `1=` (o `=` digitado e o rótulo esquecido) cai no código. O
                # par continua guardado, porque é ele que permite à descritiva
                # avisar que você começou a escrever e não terminou — e é ele
                # que faz o arquivo voltar ao disco do jeito que você o deixou.
                return rotulo or codigo
        return codigo


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
    campos, registros, separador = _tabela(texto, caminho)

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

        codigos, rotulos = _categorias(
            registro.get("categorias_ordem"), variavel, numero, caminho, separador
        )

        linhas.append(
            Linha(
                variavel=variavel,
                rotulo=(registro.get("rotulo") or "").strip(),
                tipo=_tipo(registro.get("tipo"), variavel, numero, caminho),
                categorias_ordem=codigos,
                rotulos_das_categorias=rotulos,
                faixas=_faixas(
                    registro.get("faixas"), variavel, numero, caminho, separador
                ),
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


def _tabela(
    texto: str, caminho: Path
) -> tuple[tuple[str, ...], list[tuple[int, dict[str, str]]], str]:
    """
    Separa cabeçalho e registros, descobrindo o separador de campos.

    Devolve o separador junto, e não só a tabela: quem lê uma célula de lista
    precisa saber qual caractere já foi gasto para separar campos, senão volta a
    partir `Alta; a pedido` em duas categorias. Ver `_lista`.

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

    return campos, registros, separador


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


def _lista(
    valor: str | None,
    separador_de_campos: str = SEPARADOR_CAMPO,
    aparar: bool = True,
) -> tuple[str, ...]:
    """
    Quebra `Feminino|Masculino` — e também `Feminino;Masculino`, que é o que o
    roteiro escreve e o que sai quando o campo vem entre aspas de outra ferramenta.

    ## O `;` só é separador de lista quando não é separador de campos

    Aceitá-lo sempre quebrava o round-trip do arquivo que o próprio FlatCap
    grava. Com `;` entre campos, uma categoria chamada `Alta; a pedido` sai do
    `csv.writer` entre aspas, que é o certo — e voltava da leitura como duas
    categorias, `Alta` e `a pedido`. O arquivo lido deixava de ser o arquivo
    escrito, e a fusão, que nunca reescreve linha preenchida, gravava a divisão
    de volta no disco.

    Num arquivo separado por vírgula o `;` continua valendo dentro da lista: lá
    ele não é ambíguo, e é o que o roteiro escreve.

    ## `aparar` — e por que a categoria não é aparada

    `faixas` são números, e `  18` é o mesmo corte que `18`: ali o espaço é
    digitação. Uma categoria não: `"Sim "` e `"Sim"` são duas contagens
    diferentes no banco — é o que o detector `espaco_sobrando` do `perfil.py`
    denuncia —, e aparar a declarada fazia a linha do relatório sair com `n = 0`
    justamente na coluna suja que se estava tentando descrever.

    O preço é conhecido e vale registrar: quem escrever `Sim | Não` por estética
    declara as categorias `"Sim "` e `" Não"`, que não casam com o banco. A
    descritiva avisa — `valor(es) no banco fora da ordem declarada` e
    `categoria(s) do dicionário sem nenhum caso` —, e é um aviso que aponta para
    a célula certa. O contrário não tem conserto: aparando, a categoria com
    espaço fica impossível de declarar, e nada na saída diz por quê.
    """
    bruto = valor if valor is not None else ""
    if aparar:
        bruto = bruto.strip()
    if not bruto.strip():
        return ()

    candidatos = tuple(
        s for s in _SEPARADORES_LISTA if s != separador_de_campos
    ) or (SEPARADOR_LISTA,)
    separador = next((s for s in candidatos if s in bruto), candidatos[0])

    partes = bruto.split(separador)
    if aparar:
        return tuple(parte.strip() for parte in partes if parte.strip())
    return tuple(parte for parte in partes if parte.strip())


def _categorias(
    valor: str | None,
    variavel: str,
    numero: int,
    caminho: Path,
    separador_de_campos: str = SEPARADOR_CAMPO,
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """
    Separa `1=Feminino|2=Masculino` no código e no rótulo de cada categoria.

    Devolve `(códigos, pares)`. Os códigos são o que a descritiva compara com a
    coluna do banco; os pares são o que ela imprime. Uma célula sem `=` devolve
    os códigos e nenhum par — e é assim que um dicionário escrito antes desta
    versão continua valendo sem mudar um caractere.

    ## Por que o rótulo mora aqui, e não em uma sétima coluna

    Foi a decisão de 17/09/2026, e o argumento é o desalinhamento. Uma sétima
    coluna guardaria `1|2` numa célula e `Feminino|Masculino` na outra, ligadas
    **pela posição** — e no dia em que alguém reordenasse uma e esquecesse a
    outra, o relatório sairia com `Feminino` em cima da contagem de `2`. Sem erro,
    sem aviso, e conferível só lendo o banco.

    Na mesma célula isso é impossível por construção: a ordem e o rótulo são a
    mesma decisão, tomada de uma vez, na frente do cliente.

    ## A divisão é no primeiro `=`, e só nele

    Mesma regra que o `modelo._opcoes` usa para a primeira vírgula dos rótulos do
    REDCap, e pelo mesmo motivo: `1=Sim = confirmado` é um rótulo com `=` dentro,
    não duas categorias. Partir em todos devolveria um rótulo cortado no meio.

    ## O espaço é do valor, menos ao redor do `=`

    Sem `=`, a parte inteira é o valor como ele está no banco, espaço e tudo:
    `"Sim "` e `"Sim"` são duas colunas diferentes de uma tabela de frequência,
    e o `espaco_sobrando` do `perfil.py` existe justamente para você poder
    declarar a primeira. Com `=`, o sinal é a fronteira e o espaço ao redor dele
    é digitação: `1 = Feminino` é o código `1`.

    Raises:
        DicionarioInvalidoError: código repetido na mesma célula, ou `=` sem
            código antes dele.
    """
    partes = _lista(valor, separador_de_campos, aparar=False)
    codigos: list[str] = []
    rotulos: list[tuple[str, str]] = []
    vistos: set[str] = set()

    for parte in partes:
        codigo, tem_rotulo, rotulo = parte.partition(SEPARADOR_ROTULO)
        if tem_rotulo:
            codigo, rotulo = codigo.strip(), rotulo.strip()

        if not codigo.strip():
            raise DicionarioInvalidoError(
                f"A variável `{variavel}` (linha {numero} de {caminho.name}) tem uma "
                f"categoria que começa com `{SEPARADOR_ROTULO}`: `{parte}`.\n\n"
                "Antes do sinal vai o valor como ele está **no banco**, e depois "
                "vai como ele deve aparecer na tabela:\n"
                f"  1{SEPARADOR_ROTULO}Feminino{SEPARADOR_LISTA}"
                f"2{SEPARADOR_ROTULO}Masculino\n\n"
                "Se a coluna do banco já tem o texto, não precisa de sinal nenhum:\n"
                f"  Feminino{SEPARADOR_LISTA}Masculino",
                caminho,
            )

        if codigo in vistos:
            raise DicionarioInvalidoError(
                f"A variável `{variavel}` (linha {numero} de {caminho.name}) declara a "
                f"categoria `{codigo}` duas vezes.\n\n"
                "Duas linhas para a mesma categoria é ambiguidade: a descritiva não "
                "teria como saber qual rótulo vale, nem em qual das duas posições "
                "contar os casos. Apague a errada.\n\n"
                "Quando a intenção é **juntar** duas categorias em uma, o caminho é "
                "outro: dois códigos diferentes com o mesmo rótulo — "
                f"`1{SEPARADOR_ROTULO}Sim{SEPARADOR_LISTA}2{SEPARADOR_ROTULO}Sim` —, "
                "e aí a descritiva avisa que você agrupou, em vez de recusar.",
                caminho,
            )

        vistos.add(codigo)
        codigos.append(codigo)
        if tem_rotulo:
            rotulos.append((codigo, rotulo))

    return tuple(codigos), tuple(rotulos)


def _faixas(
    valor: str | None,
    variavel: str,
    numero: int,
    caminho: Path,
    separador_de_campos: str = SEPARADOR_CAMPO,
) -> tuple[str, ...]:
    """
    As faixas precisam ser números em ordem crescente, e é aqui que isso é conferido.

    Conferir na leitura e não na Fase 5 é deliberado: o erro é de digitação, e o
    momento de descobrir uma digitação errada é enquanto o arquivo está aberto na
    sua frente — não daqui a duas semanas, no meio da geração das tabelas.
    """
    partes = _lista(valor, separador_de_campos)
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
        rotulos_das_categorias=linha.rotulos_das_categorias,
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


def _escrever_categoria(linha: Linha, codigo: str) -> str:
    for chave, rotulo in linha.rotulos_das_categorias:
        if chave == codigo:
            return f"{codigo}{SEPARADOR_ROTULO}{rotulo}"
    return codigo


def _campo(linha: Linha, nome: str) -> str:
    if nome == "variavel":
        return linha.variavel
    if nome == "rotulo":
        return linha.rotulo
    if nome == "tipo":
        return linha.tipo
    if nome == "categorias_ordem":
        # Remonta `codigo=rotulo` para os que têm rótulo, e devolve o código
        # sozinho para os que não têm. É o que faz o arquivo voltar ao disco
        # exatamente como você o deixou — a promessa do cabeçalho da ficha vale
        # aqui também, e um `=` que some na primeira gravação é uma edição sua
        # desfeita pelo programa.
        return SEPARADOR_LISTA.join(
            _escrever_categoria(linha, codigo) for codigo in linha.categorias_ordem
        )
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