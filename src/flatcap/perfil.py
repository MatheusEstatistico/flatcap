"""
O perfil do banco — o que você leva para a reunião.

Responde ao passo 2c do fluxo: abrir o banco com o cliente e apontar os ajustes
necessários. A diferença que a fase faz é de dinâmica, não de tecnologia. Sem
ela, a reunião é rolar a planilha procurando problema ao vivo. Com ela, você
chega com a lista pronta — "há 12% de faltantes em `idade`, a coluna `peso` está
como texto, e `sexo` tem quatro grafias diferentes" — e o cliente sai sabendo
exatamente o que corrigir.

Segue o padrão das Fases 2 e 3, decidir e escrever separados:

    plano = preparar_perfil(root, identificador)   # abre o banco, diagnostica
    executar_perfil(plano)                         # só escreve

E, como a Fase 3, **não fala com o REDCap**. A pasta do projeto já tem tudo: a
ficha diz qual é a versão vigente, e o banco está em `1. Dados originais/`. Um
comando que só lê arquivo local não deve poder falhar por token expirado — há
teste que roda o `perfil` com token inválido de propósito.

## Dois produtos, um comando

**`perfil.md`** é para a reunião: um documento impresso, ordenado pelo que exige
decisão, com os valores observados de cada categórica e o resumo de cada
numérica — que é exatamente o que se precisa ter na frente para decidir a ordem
das categorias e os cortes das faixas.

**`dicionario.csv`** é para a máquina: a partir da Fase 5, a descritiva obedece a
ele e a nada mais. Sai preenchido com uma sugestão por variável, e a sugestão é
palpite — a coluna `tipo` existe para você corrigir. A automação propõe, você
decide.

## O que o diagnóstico não faz

Não conserta. Vírgula decimal continua vírgula decimal, número guardado como
texto continua texto. Duas razões: o arquivo é do cliente e a correção é dele —
consertar aqui deixaria a versão dele diferente da sua para sempre; e a Fase 3
já tem o lugar certo para uma versão corrigida entrar, que é o
`flatcap dados adicionar`, com número de sequência e `sha256`.

## Um módulo sem erro próprio

Todos os outros módulos do FlatCap declaram uma exceção própria — `ConfigError`,
`RedcapError`, `ProjetoError`, `FichaError`, `DadosError`, `BancoError`,
`DicionarioError` — que a CLI captura e transforma em painel. Este não declara
nenhuma, e a ausência é informação: **o perfil não tem como falhar por conta
própria**. Ou o projeto não abre (`FichaError`), ou o banco não abre
(`BancoError`), ou o dicionário que está lá não é interpretável
(`DicionarioError`). O que sobra aqui é contar, medir e formatar, e nada disso
recusa nada.

## Simula por padrão

Como o `novo` e o `dados adicionar`, e pelo mesmo motivo, que aqui é um só e é
específico: o `perfil.md` é um documento que você leva impresso para a reunião e
onde você **rabisca**. Regerá-lo apaga o rabisco. A simulação mostra o
diagnóstico inteiro na tela — nunca é uma rodada perdida — e diz quando o
`perfil.md` que está lá vai ser substituído, e de quando ele é.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import __version__
from .banco import Banco, Leitura, abrir, formato_de_data
from .dicionario import (
    CATEGORICA,
    DATA,
    IGNORAR,
    NUMERICA,
    Fusao,
    Sugestao,
    caminho_do_dicionario,
    escrever,
    fundir,
    texto_do_dicionario,
)
from .dicionario import ler as ler_dicionario
from .ficha import Ficha, escrever_atomico
from .ficha import ler as ler_ficha
from .projeto import anotar, tamanho_legivel

ARQUIVO_PERFIL = "perfil.md"

# Gravidade de um achado. Não é "erro/aviso": é o que fazer com ele na reunião.
CORRIGIR = "corrigir"  # o banco precisa mudar antes de a análise começar
CONFIRMAR = "confirmar"  # é decisão do cliente, e ele precisa ser perguntado
NOTA = "nota"  # fica registrado, não exige conversa

_ORDEM_GRAVIDADE = (CORRIGIR, CONFIRMAR, NOTA)

_TITULOS = {
    CORRIGIR: "Corrigir antes de começar",
    CONFIRMAR: "Confirmar com o cliente",
    NOTA: "Notas",
}

# Limiares. Todos aqui em cima, com nome, porque um número solto no meio de uma
# função é uma decisão que ninguém consegue rever depois.
PROPORCAO_PARA_AFIRMAR = 0.9  # "esta coluna é número/data escrito como texto"
LIMITE_CATEGORIAS = 25  # acima disso, a lista de valores não vai por extenso
LIMITE_EXEMPLOS = 5
LIMITE_UNICOS_CODIGO = 10  # numérica inteira com até 10 valores: candidata a código
LIMITE_VALOR_CODIGO = 20  # ...e valores pequenos: código é 0/1, 1/2, 1 a 5
LIMITE_FALTANTES = 0.20  # a partir daqui, faltante vira assunto de reunião
PROPORCAO_TEXTO_LIVRE = 0.90  # quase todo valor diferente: texto livre ou identificador
MINIMO_PARA_HEURISTICA = 20  # abaixo disso, proporção não quer dizer nada

_SENTINELAS_NUMERICAS = (99, 999, 9999, -99, -999)
_SENTINELAS_TEXTUAIS = frozenset(
    {
        "-",
        "--",
        ".",
        "?",
        "sem informacao",
        "nao informado",
        "nao informada",
        "nao consta",
        "nao se aplica",
        "ignorado",
        "desconhecido",
        "ni",
        "n/i",
        "nd",
        "n/d",
        "s/i",
        "nsa",
    }
)

_NOMES_DE_IDENTIFICADOR = (
    "id",
    "codigo",
    "cod",
    "record",
    "prontuario",
    "matricula",
    "cpf",
    "rg",
    "nome",
    "paciente",
    "email",
    "telefone",
    "obs",
    "observacao",
    "observacoes",
    "comentario",
    "comentarios",
)

# A lista de formatos de data e a detecção passaram para `banco.py` na Fase 5: o
# detector `data_como_texto` daqui e a conversão que a descritiva faz precisam dar
# a mesma resposta, e duas listas é como uma delas deixa de receber a próxima
# correção. Ver a justificativa em `banco.formato_de_data`.
_formato_de_data = formato_de_data

# `1.234,56` e `1234,56` — o jeito brasileiro.
_NUMERO_PTBR = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3})+(?:,\d+)?$|^[+-]?\d+(?:,\d+)?$")
# `1,234.56` e `1234.56` — o jeito que sai de ferramenta em inglês.
_NUMERO_EN = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$|^[+-]?\d+(?:\.\d+)?$")
_VIRGULA_DECIMAL = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3})*,\d+$")
_ESPACOS = re.compile(r"\s+")

_MARCA_GERACAO = "<!-- flatcap perfil"


@dataclass(frozen=True)
class Achado:
    """
    Uma coisa observada no banco que exige atenção.

    `exemplos` não é enfeite: "a coluna sexo tem quatro grafias" faz o cliente
    procurar; "a coluna sexo tem F, f, Feminino e feminino " faz ele achar.
    """

    codigo: str
    gravidade: str
    titulo: str
    detalhe: str = ""
    variavel: str | None = None
    exemplos: tuple[str, ...] = ()

    @property
    def peso(self) -> int:
        return _ORDEM_GRAVIDADE.index(self.gravidade)


@dataclass(frozen=True)
class Coluna:
    """
    Uma variável do banco, já medida.
    """

    nome: str
    posicao: int
    dtype: str
    tipo_lido: str
    total: int
    faltantes: int
    unicos: int
    exemplos: tuple[str, ...] = ()
    categorias: tuple[tuple[str, int], ...] = ()
    resumo: tuple[tuple[str, float], ...] = ()
    sugestao: str = CATEGORICA
    motivo: str = ""
    categorias_sugeridas: tuple[str, ...] = ()
    achados: tuple[Achado, ...] = ()

    @property
    def preenchidos(self) -> int:
        return self.total - self.faltantes

    @property
    def proporcao_faltante(self) -> float:
        return self.faltantes / self.total if self.total else 0.0

    @property
    def resumo_numerico(self) -> dict[str, float]:
        return dict(self.resumo)

    def como_sugestao(self) -> Sugestao:
        return Sugestao(
            variavel=self.nome,
            rotulo=self.nome,
            tipo=self.sugestao,
            categorias_ordem=self.categorias_sugeridas,
        )


@dataclass(frozen=True)
class Perfil:
    """
    O banco inteiro, medido. É daqui que saem o `perfil.md` e o terminal.
    """

    ficha: Ficha
    leitura: Leitura
    versao_arquivo: str
    tamanho_bytes: int
    confere: bool | None
    linhas: int
    colunas: tuple[Coluna, ...]
    duplicadas: int
    achados: tuple[Achado, ...]
    avisos: tuple[str, ...]
    quando: datetime

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def total_colunas(self) -> int:
        return len(self.colunas)

    @property
    def tamanho_legivel(self) -> str:
        return tamanho_legivel(self.tamanho_bytes)

    def por_gravidade(self, gravidade: str) -> tuple[Achado, ...]:
        return tuple(achado for achado in self.achados if achado.gravidade == gravidade)

    @property
    def a_corrigir(self) -> tuple[Achado, ...]:
        return self.por_gravidade(CORRIGIR)

    @property
    def a_confirmar(self) -> tuple[Achado, ...]:
        return self.por_gravidade(CONFIRMAR)

    @property
    def limpo(self) -> bool:
        return not (self.a_corrigir or self.a_confirmar)


@dataclass(frozen=True)
class PlanoPerfil:
    """
    Tudo o que o `perfil` faria, decidido e ainda não escrito.

    O conteúdo dos dois arquivos já vem montado, como no `Plano` da Fase 2, para
    que `executar_perfil` não decida mais nada — e para que a simulação mostre
    exatamente o que seria gravado, e não uma aproximação.
    """

    perfil: Perfil
    fusao: Fusao
    caminho_perfil: Path
    caminho_dicionario: Path
    texto_perfil: str
    texto_dicionario: str
    perfil_anterior: datetime | None = None

    @property
    def raiz(self) -> Path:
        return self.perfil.raiz

    @property
    def dicionario_existia(self) -> bool:
        return self.fusao.existia


@dataclass(frozen=True)
class ResultadoPerfil:
    """
    O que a execução de fato escreveu.
    """

    criados: tuple[Path, ...] = ()
    avisos: tuple[str, ...] = ()


# Casos de uso


def preparar_perfil(
    raiz: Path,
    aba: str | None = None,
    conferir: bool = True,
    agora: datetime | None = None,
) -> PlanoPerfil:
    """
    Abre a versão vigente do banco, diagnostica e monta os dois arquivos.

    Não escreve nada. Não toca na rede.

    Args:
        raiz: a pasta do projeto.
        aba: planilha do `.xlsx`, quando houver mais de uma.
        conferir: reler o `sha256` das versões e comparar com a ficha.
        agora: relógio injetável — sem ele os testes não teriam como comparar o
            cabeçalho do `perfil.md`, que carrega a data.

    Raises:
        FichaError, BancoError, DicionarioInvalidoError
    """
    raiz = Path(raiz)
    quando = agora or datetime.now()

    banco = abrir(raiz, aba=aba, conferir=conferir)
    ficha = ler_ficha(raiz)
    perfil = perfilar(banco, ficha, quando)

    fusao = fundir(
        ler_dicionario(raiz),
        tuple(coluna.como_sugestao().como_linha() for coluna in perfil.colunas),
    )

    return PlanoPerfil(
        perfil=perfil,
        fusao=fusao,
        caminho_perfil=Path(raiz) / ARQUIVO_PERFIL,
        caminho_dicionario=caminho_do_dicionario(raiz),
        texto_perfil=texto_do_perfil(perfil, fusao),
        texto_dicionario=texto_do_dicionario(fusao.linhas, fusao.colunas),
        perfil_anterior=_geracao_anterior(Path(raiz) / ARQUIVO_PERFIL),
    )


def executar_perfil(plano: PlanoPerfil) -> ResultadoPerfil:
    """
    Escreve o `dicionario.csv` e o `perfil.md`. Não decide mais nada.

    O dicionário vem primeiro porque é o arquivo que guarda decisão; o `perfil.md`
    é um relatório e sempre pode ser regerado. Nenhum dos dois precisa de reversão
    como a da Fase 3: os dois são idempotentes — a fusão preserva o que já existe
    e o relatório descreve o que acabou de ser lido —, então rodar de novo depois
    de uma falha no meio resolve, em vez de agravar.
    """
    criados: list[Path] = []
    avisos: list[str] = []

    escrever(plano.raiz, plano.fusao)
    criados.append(plano.caminho_dicionario)

    escrever_atomico(plano.caminho_perfil, plano.texto_perfil)
    criados.append(plano.caminho_perfil)

    try:
        anotar(plano.raiz, _acao_do_historico(plano), plano.perfil.quando)
    except OSError as erro:
        avisos.append(
            f"Os arquivos foram escritos, mas não consegui escrever no historico.md: {erro}"
        )

    return ResultadoPerfil(criados=tuple(criados), avisos=tuple(avisos))


def perfilar(banco: Banco, ficha: Ficha, quando: datetime | None = None) -> Perfil:
    """
    Mede o banco. Função pura: recebe o quadro aberto, devolve o diagnóstico.

    Separada de `preparar_perfil` porque é o miolo testável — dá para jogar um
    `DataFrame` montado à mão aqui dentro e afirmar sobre os achados, sem pasta de
    projeto, sem ficha e sem disco.
    """
    quadro = banco.quadro
    linhas = int(quadro.shape[0])

    # `quadro.iloc[:, i]` e não `quadro[nome]`: nome repetido devolveria um
    # `DataFrame` no lugar de uma coluna, e o perfil quebraria justamente no banco
    # que mais precisa de diagnóstico.
    colunas = tuple(
        _perfilar_coluna(quadro.iloc[:, posicao - 1], nome, posicao, linhas)
        for posicao, nome in enumerate(quadro.columns, start=1)
    )

    duplicadas = int(quadro.duplicated().sum())
    achados = _achados_gerais(quadro, colunas, duplicadas, linhas)
    achados += tuple(achado for coluna in colunas for achado in coluna.achados)

    return Perfil(
        ficha=ficha,
        leitura=banco.leitura,
        versao_arquivo=banco.versao.arquivo,
        tamanho_bytes=banco.versao.tamanho_bytes,
        confere=banco.confere,
        linhas=linhas,
        colunas=colunas,
        duplicadas=duplicadas,
        achados=tuple(sorted(achados, key=lambda a: (a.peso, a.variavel or ""))),
        avisos=banco.avisos,
        quando=quando or datetime.now(),
    )


# Perfil de uma coluna


def _perfilar_coluna(serie: pd.Series, nome: object, posicao: int, linhas: int) -> Coluna:
    nome = str(nome)
    preenchidos = serie.dropna()
    faltantes = linhas - int(preenchidos.shape[0])
    unicos = int(preenchidos.nunique())

    achados: list[Achado] = []
    categorias: tuple[tuple[str, int], ...] = ()
    resumo: tuple[tuple[str, float], ...] = ()
    textos = _textos(preenchidos)

    if _e_numerica(serie):
        resumo = _resumo_numerico(preenchidos)
        achados += _achados_numericos(nome, preenchidos)
    else:
        achados += _achados_mistos(nome, serie)
        achados += _achados_textuais(nome, textos)

    if unicos and unicos <= LIMITE_CATEGORIAS:
        categorias = _contagem(preenchidos)

    achados += _achados_de_preenchimento(nome, faltantes, linhas, unicos)

    tipo, motivo = _sugerir(nome, serie, textos, unicos, faltantes, linhas)
    sugeridas = _categorias_sugeridas(tipo, categorias, unicos, tuple(achados))
    if tipo == CATEGORICA and not sugeridas and any("|" in valor for valor, _ in categorias):
        achados.append(
            Achado(
                codigo="categoria_com_barra",
                gravidade=NOTA,
                variavel=nome,
                titulo="categoria com `|` no valor",
                detalhe=(
                    "A ordem das categorias ficou em branco no dicionário porque `|` é o "
                    "separador da lista. Preencha `categorias_ordem` à mão, ou peça ao "
                    "cliente para tirar a barra do valor."
                ),
            )
        )

    return Coluna(
        nome=nome,
        posicao=posicao,
        dtype=str(serie.dtype),
        tipo_lido=_tipo_lido(serie),
        total=linhas,
        faltantes=faltantes,
        unicos=unicos,
        exemplos=_exemplos(preenchidos),
        categorias=categorias,
        resumo=resumo,
        sugestao=tipo,
        motivo=motivo,
        categorias_sugeridas=sugeridas,
        achados=tuple(achados),
    )


# Detectores


def _achados_gerais(
    quadro: pd.DataFrame, colunas: tuple[Coluna, ...], duplicadas: int, linhas: int
) -> tuple[Achado, ...]:
    """
    O que se vê olhando o banco inteiro, e não uma coluna de cada vez.
    """
    achados: list[Achado] = []

    if duplicadas:
        achados.append(
            Achado(
                codigo="linhas_duplicadas",
                gravidade=CONFIRMAR,
                titulo=f"{duplicadas} linha(s) idêntica(s) a outra",
                detalhe=(
                    "Linha repetida de ponta a ponta costuma ser digitação em dobro ou "
                    "exportação com junção errada — mas pode ser dado legítimo (duas "
                    "consultas iguais no mesmo dia). Pergunte antes de remover: excluir "
                    "muda o denominador de todas as tabelas."
                ),
            )
        )

    nomes = [str(nome) for nome in quadro.columns]

    vazios = [nome for nome in nomes if nome.startswith("Unnamed:") or not nome.strip()]
    if vazios:
        achados.append(
            Achado(
                codigo="cabecalho_vazio",
                gravidade=CORRIGIR,
                titulo=f"{len(vazios)} coluna(s) sem nome no cabeçalho",
                detalhe=(
                    "Coluna sem nome quase sempre significa que a primeira linha da "
                    "planilha não é o cabeçalho — há um título, uma linha em branco ou "
                    "células mescladas acima dos dados. Peça o arquivo com o cabeçalho na "
                    "primeira linha."
                ),
                exemplos=tuple(vazios[:LIMITE_EXEMPLOS]),
            )
        )

    repetidos = _nomes_repetidos(nomes)
    if repetidos:
        achados.append(
            Achado(
                codigo="cabecalho_repetido",
                gravidade=CORRIGIR,
                titulo=f"{len(repetidos)} nome(s) de coluna repetido(s)",
                detalhe=(
                    "Duas colunas com o mesmo nome (ou diferindo só por acento, caixa ou "
                    "espaço) não podem ser distinguidas no dicionário, que usa o nome como "
                    "chave. O leitor renomeia a segunda para `nome.1`, e nada na tabela "
                    "diz o que ela era. Peça nomes distintos."
                ),
                exemplos=tuple(repetidos[:LIMITE_EXEMPLOS]),
            )
        )

    com_espaco = [nome for nome in nomes if nome != nome.strip() or "\n" in nome]
    if com_espaco:
        achados.append(
            Achado(
                codigo="cabecalho_com_espaco",
                gravidade=NOTA,
                titulo=f"{len(com_espaco)} nome(s) de coluna com espaço ou quebra de linha",
                detalhe=(
                    "O nome vai para o `dicionario.csv` exatamente como está aqui, "
                    "inclusive o espaço — que é invisível na tela e faz a variável parecer "
                    "não encontrada. Vale pedir a limpeza."
                ),
                exemplos=tuple(repr(nome) for nome in com_espaco[:LIMITE_EXEMPLOS]),
            )
        )

    identificadores = [
        coluna
        for coluna in colunas
        if _parece_identificador(coluna.nome)
        and coluna.unicos
        and coluna.unicos < coluna.preenchidos
        and coluna.preenchidos >= MINIMO_PARA_HEURISTICA
    ]
    for coluna in identificadores:
        repetidas = coluna.preenchidos - coluna.unicos
        achados.append(
            Achado(
                codigo="identificador_repetido",
                gravidade=CONFIRMAR,
                variavel=coluna.nome,
                titulo=f"identificador com {repetidas} valor(es) repetido(s)",
                detalhe=(
                    "O nome sugere identificador e há valores que aparecem mais de uma vez. "
                    "Ou o banco tem mais de uma linha por indivíduo — o que muda toda a "
                    "descritiva —, ou houve duplicação na exportação."
                ),
            )
        )

    if linhas and linhas < MINIMO_PARA_HEURISTICA:
        achados.append(
            Achado(
                codigo="poucas_linhas",
                gravidade=NOTA,
                titulo=f"o banco tem {linhas} linha(s)",
                detalhe=(
                    "Com tão poucos casos, as sugestões de tipo deste perfil valem menos: "
                    "elas se apoiam em proporções (quantos valores distintos, quantos "
                    "faltantes) que não significam grande coisa nesse tamanho. Confira "
                    "cada linha do dicionário."
                ),
            )
        )

    return tuple(achados)


def _achados_numericos(nome: str, preenchidos: pd.Series) -> tuple[Achado, ...]:
    """
    O código de faltante disfarçado de número — 99, 999 — é o achado clássico.
    """
    achados: list[Achado] = []

    for sentinela in _SENTINELAS_NUMERICAS:
        quantos = int((preenchidos == sentinela).sum())
        if not quantos:
            continue
        restantes = preenchidos[preenchidos != sentinela]
        if restantes.empty:
            continue
        limite = float(restantes.abs().max()) * 2
        if abs(sentinela) > max(limite, 0.0):
            achados.append(
                Achado(
                    codigo="sentinela_numerica",
                    gravidade=CONFIRMAR,
                    variavel=nome,
                    titulo=f"o valor {sentinela} aparece {quantos} vez(es) e destoa do resto",
                    detalhe=(
                        "Valor muito acima de todos os outros costuma ser código de "
                        "faltante herdado de outro sistema. Se for, ele precisa virar "
                        "célula vazia antes da análise — somado como número, ele "
                        "contamina média, desvio e faixas."
                    ),
                )
            )

    return tuple(achados)


def _achados_textuais(nome: str, textos: list[str]) -> tuple[Achado, ...]:
    """
    Os detectores do roteiro que se aplicam a coluna de texto, mais os que
    aparecem sempre junto com eles.
    """
    achados: list[Achado] = []
    if not textos:
        return ()

    numericos = [texto for texto in textos if _e_numero(texto)]
    proporcao = len(numericos) / len(textos)

    if proporcao >= PROPORCAO_PARA_AFIRMAR:
        com_virgula = [texto for texto in numericos if _VIRGULA_DECIMAL.match(texto)]
        if com_virgula:
            achados.append(
                Achado(
                    codigo="virgula_decimal",
                    gravidade=CORRIGIR,
                    variavel=nome,
                    titulo="números com vírgula decimal, lidos como texto",
                    detalhe=(
                        "A coluna é numérica, mas a vírgula faz o leitor tratar cada valor "
                        "como palavra: nenhuma média sai daqui. No Excel isso costuma ser "
                        "célula formatada como texto, ou o arquivo salvo em uma "
                        "configuração regional e aberto em outra."
                    ),
                    exemplos=tuple(com_virgula[:LIMITE_EXEMPLOS]),
                )
            )
        else:
            achados.append(
                Achado(
                    codigo="numero_como_texto",
                    gravidade=CORRIGIR,
                    variavel=nome,
                    titulo="números guardados como texto",
                    detalhe=(
                        "Todos os valores são números, e mesmo assim a coluna chegou como "
                        "texto — célula formatada como texto no Excel, apóstrofo à frente "
                        "do número, ou espaço sobrando. Enquanto estiver assim, a variável "
                        "não entra em nenhuma conta."
                    ),
                    exemplos=tuple(numericos[:LIMITE_EXEMPLOS]),
                )
            )

    formato, quantas = _formato_de_data(textos)
    if formato is not None:
        achados.append(
            Achado(
                codigo="data_como_texto",
                gravidade=CORRIGIR,
                variavel=nome,
                titulo=f"datas escritas como texto ({formato})",
                detalhe=(
                    f"{quantas} de {len(textos)} valores são datas no formato `{formato}`, "
                    "mas a coluna é texto. Ordenar, calcular idade ou agrupar por mês "
                    "exige data de verdade — no Excel, formatar a coluna como Data resolve."
                ),
                exemplos=tuple(textos[:LIMITE_EXEMPLOS]),
            )
        )

    variacoes = _variacoes_de_grafia(textos)
    if variacoes:
        exemplos = [" / ".join(sorted(grupo)) for grupo in variacoes[:LIMITE_EXEMPLOS]]
        achados.append(
            Achado(
                codigo="variacao_de_grafia",
                gravidade=CONFIRMAR,
                variavel=nome,
                titulo=f"{len(variacoes)} categoria(s) com mais de uma grafia",
                detalhe=(
                    "Valores que significam a mesma coisa e são contados separadamente: "
                    "cada grafia vira uma linha na tabela de frequência, e o total de cada "
                    "uma sai menor do que a realidade. Combine com o cliente qual grafia "
                    "vale e peça a padronização."
                ),
                exemplos=tuple(exemplos),
            )
        )

    espacos = sorted({texto for texto in textos if texto != texto.strip()})
    if espacos and not variacoes:
        achados.append(
            Achado(
                codigo="espaco_sobrando",
                gravidade=CONFIRMAR,
                variavel=nome,
                titulo=f"{len(espacos)} valor(es) com espaço no começo ou no fim",
                detalhe=(
                    'Espaço invisível: `"Sim "` e `"Sim"` são categorias diferentes para '
                    "qualquer contagem, e iguais para quem olha a planilha."
                ),
                exemplos=tuple(repr(texto) for texto in espacos[:LIMITE_EXEMPLOS]),
            )
        )

    sentinelas = sorted(
        {texto for texto in textos if _chave(texto) in _SENTINELAS_TEXTUAIS}
    )
    if sentinelas:
        achados.append(
            Achado(
                codigo="sentinela_textual",
                gravidade=CONFIRMAR,
                variavel=nome,
                titulo="valores que parecem ausência escrita à mão",
                detalhe=(
                    "Estes valores dizem 'não tem informação', mas são contados como "
                    "categoria. Vire célula vazia se for ausência de verdade — e mantenha "
                    "como categoria se 'não se aplica' for uma resposta com significado. "
                    "É uma decisão do cliente, e ela muda o denominador."
                ),
                exemplos=tuple(sentinelas[:LIMITE_EXEMPLOS]),
            )
        )

    return tuple(achados)


def _achados_de_preenchimento(
    nome: str, faltantes: int, linhas: int, unicos: int
) -> tuple[Achado, ...]:
    achados: list[Achado] = []

    if linhas and faltantes == linhas:
        achados.append(
            Achado(
                codigo="coluna_vazia",
                gravidade=CONFIRMAR,
                variavel=nome,
                titulo="coluna inteiramente vazia",
                detalhe=(
                    "Nenhum valor preenchido. Ou a variável não chegou a ser coletada, ou "
                    "os dados ficaram em outra planilha. Marcada como `ignorar` no "
                    "dicionário."
                ),
            )
        )
    elif linhas and faltantes / linhas >= LIMITE_FALTANTES:
        achados.append(
            Achado(
                codigo="muitos_faltantes",
                gravidade=CONFIRMAR,
                variavel=nome,
                titulo=f"{_porcentagem(faltantes / linhas)} de faltantes ({faltantes} de {linhas})",
                detalhe=(
                    "Acima de "
                    f"{_porcentagem(LIMITE_FALTANTES)}, o faltante deixa de ser detalhe: "
                    "ele muda o denominador e precisa aparecer no relatório. Pergunte se a "
                    "ausência tem significado (não perguntado? não se aplica?)."
                ),
            )
        )

    if linhas and unicos == 1 and faltantes < linhas:
        achados.append(
            Achado(
                codigo="coluna_constante",
                gravidade=NOTA,
                variavel=nome,
                titulo="um único valor em todas as linhas",
                detalhe=(
                    "Uma variável que não varia não descreve nada e não entra em "
                    "cruzamento nenhum. Costuma ser critério de inclusão do estudo — vale "
                    "citar no texto e deixar fora das tabelas."
                ),
            )
        )

    return tuple(achados)


def _achados_mistos(nome: str, serie: pd.Series) -> tuple[Achado, ...]:
    """
    Tipos misturados na mesma coluna: número e texto convivendo.

    Só é detectável em coluna `object`, que é onde o `pandas` guarda o que não
    conseguiu uniformizar. Uma coluna que ele conseguiu ler inteira como texto
    não tem mistura para encontrar.
    """
    if serie.dtype != object:
        return ()

    preenchidos = serie.dropna()
    tipos: dict[str, list[str]] = {}
    for valor in preenchidos:
        tipos.setdefault(type(valor).__name__, []).append(str(valor))

    if len(tipos) < 2:
        return ()

    descricao = ", ".join(
        f"{_TIPO_PYTHON.get(nome_tipo, nome_tipo)} ({len(valores)})"
        for nome_tipo, valores in sorted(tipos.items(), key=lambda par: -len(par[1]))
    )
    exemplos = [valores[0] for valores in tipos.values()]

    return (
        Achado(
            codigo="tipos_misturados",
            gravidade=CORRIGIR,
            variavel=nome,
            titulo=f"tipos misturados na mesma coluna: {descricao}",
            detalhe=(
                "A coluna tem valores de naturezas diferentes — normalmente números com "
                "uma observação escrita no meio ('não realizado', '<0,5', '12 (repetido)'). "
                "Enquanto conviverem, a coluna não é numérica nem categórica. O caminho "
                "usual é criar uma segunda coluna para a observação."
            ),
            exemplos=tuple(exemplos[:LIMITE_EXEMPLOS]),
        ),
    )


_TIPO_PYTHON = {
    "str": "texto",
    "int": "número inteiro",
    "float": "número decimal",
    "bool": "lógico",
    "Timestamp": "data",
    "datetime": "data",
    "date": "data",
}


# Sugestão de tipo


def _sugerir(
    nome: str,
    serie: pd.Series,
    textos: list[str],
    unicos: int,
    faltantes: int,
    linhas: int,
) -> tuple[str, str]:
    """
    A sugestão que vai para o `dicionario.csv`, e o motivo dela.

    A ordem das regras é a decisão: a primeira que casa vence. O motivo viaja
    junto porque uma sugestão sem justificativa não dá para conferir — e conferir
    é literalmente o que se pede que você faça com este arquivo.
    """
    if linhas and faltantes == linhas:
        return IGNORAR, "coluna vazia"

    if _e_data(serie):
        return DATA, "lida como data"

    if _e_booleana(serie):
        return CATEGORICA, "valores lógicos (verdadeiro/falso)"

    preenchidos = linhas - faltantes

    if _e_numerica(serie):
        # Três testes, e os dois últimos são o que segura o palpite. Só "poucos
        # valores distintos" classificaria como código toda coluna numérica de um
        # banco de seis linhas. Os valores também precisam **se repetir**, e
        # precisam ser **pequenos**: código é 0/1, 1/2, uma escala de 1 a 5 —
        # nunca 27, 38, 61, que é a cara de uma idade em um banco pequeno.
        valores = serie.dropna()
        if (
            _so_inteiros(valores)
            and unicos <= LIMITE_UNICOS_CODIGO
            and unicos * 2 <= preenchidos
            and float(valores.max()) <= LIMITE_VALOR_CODIGO
        ):
            return (
                CATEGORICA,
                f"números inteiros pequenos, {unicos} valor(es) distinto(s) que se "
                "repetem — costuma ser código",
            )
        return NUMERICA, "lida como número"

    if _tipos_de(serie) > 1:
        return (
            CATEGORICA,
            "tipos misturados na coluna — reveja depois de o cliente corrigi-la",
        )

    if textos:
        numericos = sum(1 for texto in textos if _e_numero(texto))
        if numericos / len(textos) >= PROPORCAO_PARA_AFIRMAR:
            return NUMERICA, "os valores são números, guardados como texto"
        if _formato_de_data(textos)[0] is not None:
            return DATA, "os valores são datas, guardadas como texto"

    if _parece_identificador(nome) and unicos == preenchidos and preenchidos:
        return IGNORAR, "o nome sugere identificador e nenhum valor se repete"

    if (
        preenchidos >= MINIMO_PARA_HEURISTICA
        and unicos / preenchidos >= PROPORCAO_TEXTO_LIVRE
    ):
        return (
            IGNORAR,
            f"{unicos} valores distintos em {preenchidos} — texto livre ou identificador",
        )

    return CATEGORICA, f"{unicos} valor(es) distinto(s)"


def _categorias_sugeridas(
    tipo: str,
    categorias: tuple[tuple[str, int], ...],
    unicos: int,
    achados: tuple[Achado, ...],
) -> tuple[str, ...]:
    """
    A ordem proposta para `categorias_ordem`: da mais frequente para a menos.

    Coluna que precisa ser corrigida antes não recebe proposta nenhuma: os
    valores que ela tem hoje — `120` e `não realizado` na mesma coluna, `Sim` e
    `sim ` contados em separado — são exatamente os que vão deixar de existir
    quando o cliente corrigir. Propor uma ordem sobre eles é encher o arquivo de
    linha para apagar.

    Frequência decrescente porque é a ordem em que uma tabela descritiva nominal
    se lê. Escala ordinal — Fundamental, Médio, Superior — sai errada de
    propósito: não há como adivinhar ordem de grandeza a partir dos dados, e uma
    ordem errada que você corrige é melhor do que uma coluna em branco que você
    precisa preencher do zero. Empate resolve em ordem alfabética, para que duas
    execuções seguidas produzam o mesmo arquivo.

    Fica em branco quando algum valor contém `|`, que é o separador da lista.
    """
    if tipo != CATEGORICA or not categorias or unicos > LIMITE_CATEGORIAS:
        return ()
    if any(achado.gravidade == CORRIGIR for achado in achados):
        return ()
    if any("|" in valor for valor, _ in categorias):
        return ()
    return tuple(valor for valor, _ in categorias)


# Auxiliares de leitura da série


def _e_numerica(serie: pd.Series) -> bool:
    return bool(
        pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie)
    )


def _e_data(serie: pd.Series) -> bool:
    return bool(pd.api.types.is_datetime64_any_dtype(serie))


def _e_booleana(serie: pd.Series) -> bool:
    return bool(pd.api.types.is_bool_dtype(serie))


def _tipos_de(serie: pd.Series) -> int:
    """
    Quantos tipos de Python convivem na coluna. Um só, quase sempre.
    """
    if serie.dtype != object:
        return 1
    return len({type(valor).__name__ for valor in serie.dropna()}) or 1


def _tipo_lido(serie: pd.Series) -> str:
    """
    Como o leitor entendeu a coluna, em português, para a tabela do perfil.
    """
    if serie.notna().sum() == 0:
        # Coluna sem nenhum valor chega como `float64` por convenção do pandas, e
        # anunciá-la como "decimal" seria descrever a convenção, não o banco.
        return "vazia"
    if _e_booleana(serie):
        return "lógico"
    if _e_data(serie):
        return "data"
    if _e_numerica(serie):
        return "inteiro" if _so_inteiros(serie.dropna()) else "decimal"
    if serie.dtype == object:
        return "misto"
    return "texto"


def _so_inteiros(preenchidos: pd.Series) -> bool:
    if preenchidos.empty:
        return False
    if pd.api.types.is_integer_dtype(preenchidos):
        return True
    try:
        return bool((preenchidos.astype("float64") % 1 == 0).all())
    except (TypeError, ValueError):
        return False


def _textos(preenchidos: pd.Series) -> list[str]:
    """
    Os valores como texto, sem tirar espaço: o espaço sobrando é um dos achados.
    """
    if _e_numerica(preenchidos) or _e_data(preenchidos):
        return []
    return [str(valor) for valor in preenchidos]


def _exemplos(preenchidos: pd.Series) -> tuple[str, ...]:
    """
    Alguns valores para reconhecer a coluna.

    Número sai no formato brasileiro. Ele não veio de um texto — veio já como
    número —, então não há fidelidade a preservar: `20.5` em um documento em
    português ao lado de `20,5` na tabela do resumo é ruído, e ruído em um
    documento que vai para a mesa da reunião custa uma pergunta.
    """
    numerica = _e_numerica(preenchidos)
    vistos: list[str] = []
    for valor in preenchidos:
        texto = _encurtar(_numero(float(valor)) if numerica else str(valor))
        if texto not in vistos:
            vistos.append(texto)
        if len(vistos) >= LIMITE_EXEMPLOS:
            break
    return tuple(vistos)


def _contagem(preenchidos: pd.Series) -> tuple[tuple[str, int], ...]:
    """
    Valores e quantas vezes cada um aparece, do mais frequente para o menos.

    Empate em ordem alfabética, e não na ordem que o `value_counts` devolver: o
    `dicionario.csv` é gerado a partir daqui, e um arquivo que muda de ordem
    entre duas execuções idênticas é um arquivo que produz diff falso.
    """
    contagem = preenchidos.value_counts()
    pares = [(str(valor), int(quantos)) for valor, quantos in contagem.items()]
    return tuple(sorted(pares, key=lambda par: (-par[1], par[0])))


def _resumo_numerico(preenchidos: pd.Series) -> tuple[tuple[str, float], ...]:
    if preenchidos.empty:
        return ()
    try:
        valores = preenchidos.astype("float64")
    except (TypeError, ValueError):  # pragma: no cover - dtype numérico sempre converte
        return ()
    return (
        ("minimo", float(valores.min())),
        ("q1", float(valores.quantile(0.25))),
        ("mediana", float(valores.median())),
        ("q3", float(valores.quantile(0.75))),
        ("maximo", float(valores.max())),
        ("media", float(valores.mean())),
        ("desvio", float(valores.std()) if len(valores) > 1 else 0.0),
    )


# Auxiliares de texto


def _e_numero(texto: str) -> bool:
    limpo = texto.strip().replace("\xa0", "").replace(" ", "")
    if not limpo:
        return False
    return bool(_NUMERO_PTBR.match(limpo) or _NUMERO_EN.match(limpo))


def _variacoes_de_grafia(textos: list[str]) -> list[tuple[str, ...]]:
    """
    Agrupa valores que só diferem em acento, caixa ou espaço.
    """
    grupos: dict[str, set[str]] = {}
    for texto in textos:
        chave = _chave(texto)
        if chave:
            grupos.setdefault(chave, set()).add(texto)
    return [
        tuple(sorted(valores))
        for _, valores in sorted(grupos.items())
        if len(valores) > 1
    ]


def _chave(texto: str) -> str:
    """
    A forma canônica de um texto: sem acento, sem caixa, sem espaço sobrando.
    """
    limpo = _ESPACOS.sub(" ", str(texto)).strip().lower()
    decomposto = unicodedata.normalize("NFKD", limpo)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def _parece_identificador(nome: str) -> bool:
    partes = re.split(r"[^0-9a-z]+", _chave(nome))
    return any(parte in _NOMES_DE_IDENTIFICADOR for parte in partes if parte)


def _nomes_repetidos(nomes: list[str]) -> list[str]:
    """
    Nomes de coluna que colidem, das duas formas em que isso acontece.

    A primeira é o leitor já ter resolvido por conta própria: duas colunas
    `sexo` chegam como `sexo` e `sexo.1`, e o `.1` é a única pista de que houve
    colisão. A segunda é a colisão que só existe para quem lê: `Sexo` e `sexo `
    são nomes diferentes para o `pandas` e a mesma variável para o cliente.
    """
    conjunto = set(nomes)
    achados: list[str] = []

    for nome in nomes:
        casamento = re.match(r"^(?P<base>.+)\.\d+$", nome)
        if casamento and casamento.group("base") in conjunto:
            achados.append(f"{casamento.group('base')} / {nome}")

    vistos: dict[str, str] = {}
    for nome in nomes:
        chave = _chave(nome)
        if chave in vistos:
            par = f"{vistos[chave]} / {nome}"
            if par not in achados:
                achados.append(par)
        else:
            vistos[chave] = nome

    return achados


def _encurtar(texto: str, limite: int = 32) -> str:
    limpo = _ESPACOS.sub(" ", texto).strip()
    return limpo if len(limpo) <= limite else limpo[: limite - 1] + "…"


def _porcentagem(fracao: float) -> str:
    return f"{fracao * 100:.0f}%".replace(".", ",")


def _numero(valor: float) -> str:
    """
    Número no formato brasileiro, sem zero à toa: `52,5` e não `52,50`.
    """
    if not math.isfinite(valor):
        return "—"

    arredondado = round(valor, 2)
    if arredondado == int(arredondado) and abs(arredondado) < 1e15:
        return f"{int(arredondado):,}".replace(",", ".")

    inteiro, _, decimal = f"{arredondado:,.2f}".rstrip("0").partition(".")
    return f"{inteiro.replace(',', '.')},{decimal}"


# O perfil.md


def texto_do_perfil(perfil: Perfil, fusao: Fusao) -> str:
    """
    Monta o `perfil.md` inteiro. Sem tocar no disco, para o `--sim` mostrá-lo.
    """
    partes = [
        _md_cabecalho(perfil),
        _md_avisos(perfil),
        _md_checklist(perfil),
        _md_variaveis(perfil),
        _md_categoricas(perfil),
        _md_numericas(perfil),
        _md_dicionario(perfil, fusao),
    ]
    return "\n".join(parte for parte in partes if parte).rstrip() + "\n"


def _md_cabecalho(perfil: Perfil) -> str:
    ficha = perfil.ficha
    titulo = ficha.raiz.name

    if perfil.confere is True:
        integridade = "confere com o `sha256` registrado na ficha"
    elif perfil.confere is False:
        integridade = "**não confere** com o `sha256` registrado na ficha"
    else:
        integridade = "não conferida (`--rapido`)"

    linhas = [
        f"{_MARCA_GERACAO} {perfil.quando.isoformat(timespec='seconds')} -->",
        f"# Perfil do banco — {titulo}",
        "",
        f"Gerado por `flatcap perfil` em {perfil.quando:%d/%m/%Y às %H:%M} "
        f"· FlatCap {__version__}",
        "",
        "| | |",
        "|---|---|",
        f"| Registro | {ficha.record_id or '?'} · {ficha.tipo or '?'} · status "
        f"{ficha.status or '?'} |",
        f"| Arquivo | {perfil.leitura.descrever()} |",
        f"| Tamanho | {perfil.tamanho_legivel} · {perfil.linhas} linhas × "
        f"{perfil.total_colunas} colunas |",
        f"| Integridade | {integridade} |",
    ]

    if perfil.duplicadas:
        linhas.append(f"| Linhas duplicadas | {perfil.duplicadas} |")

    faltantes = sum(coluna.faltantes for coluna in perfil.colunas)
    celulas = perfil.linhas * perfil.total_colunas
    if celulas:
        linhas.append(
            f"| Células vazias | {faltantes} de {celulas} "
            f"({_porcentagem(faltantes / celulas)}) |"
        )

    linhas.append("")
    return "\n".join(linhas)


def _md_avisos(perfil: Perfil) -> str:
    if not perfil.avisos:
        return ""
    linhas = ["## Avisos da leitura", ""]
    for aviso in perfil.avisos:
        linhas.append(f"> {_ESPACOS.sub(' ', aviso).strip()}")
        linhas.append("")
    return "\n".join(linhas)


def _md_checklist(perfil: Perfil) -> str:
    """
    A parte que existe para ser lida em voz alta na reunião.

    Vem antes das tabelas de propósito: é o que exige decisão. As tabelas são
    consulta, e consulta se procura quando precisa.
    """
    linhas = ["## O que levar para a reunião", ""]

    if not perfil.achados:
        linhas += [
            "Nenhum problema encontrado nos detectores automáticos. Isso não é o mesmo "
            "que dizer que o banco está certo — quer dizer que ele passa nos testes que "
            "esta ferramenta sabe fazer.",
            "",
        ]
        return "\n".join(linhas)

    for gravidade in _ORDEM_GRAVIDADE:
        achados = perfil.por_gravidade(gravidade)
        if not achados:
            continue
        linhas.append(f"### {_TITULOS[gravidade]} ({len(achados)})")
        linhas.append("")
        for achado in achados:
            alvo = f"**{achado.variavel}** — " if achado.variavel else ""
            linhas.append(f"- [ ] {alvo}{achado.titulo}")
            if achado.detalhe:
                linhas.append(f"      {achado.detalhe}")
            if achado.exemplos:
                # Mais folgado do que na tabela: aqui o exemplo é o que faz o
                # cliente encontrar o valor na planilha, e cortado pela metade
                # ele deixa de servir para isso.
                exemplos = " · ".join(_encurtar(e, 60) for e in achado.exemplos)
                linhas.append(f"      *exemplos:* {exemplos}")
            linhas.append("")

    return "\n".join(linhas)


def _md_variaveis(perfil: Perfil) -> str:
    linhas = [
        "## Variáveis",
        "",
        "| # | variável | lido como | faltantes | únicos | sugestão | por quê | exemplos |",
        "|---:|---|---|---:|---:|---|---|---|",
    ]

    for coluna in perfil.colunas:
        faltantes = (
            f"{coluna.faltantes} ({_porcentagem(coluna.proporcao_faltante)})"
            if coluna.faltantes
            else "—"
        )
        linhas.append(
            "| {pos} | `{nome}` | {lido} | {faltantes} | {unicos} | {sugestao} | "
            "{motivo} | {exemplos} |".format(
                pos=coluna.posicao,
                nome=_celula(coluna.nome),
                lido=coluna.tipo_lido,
                faltantes=faltantes,
                unicos=coluna.unicos,
                sugestao=coluna.sugestao,
                motivo=_celula(coluna.motivo),
                exemplos=_celula(" · ".join(coluna.exemplos)) or "—",
            )
        )

    linhas += [
        "",
        "> Faltante é célula vazia e também o que o leitor entende como ausência: "
        "`NA`, `N/A`, `NULL`, `None`, `NaN` e `#N/A`. Um valor desses digitado à mão "
        "não aparece como categoria em lugar nenhum deste relatório.",
        "",
    ]
    return "\n".join(linhas)


def _md_categoricas(perfil: Perfil) -> str:
    """
    Os valores observados de cada categórica, que é o que se olha para preencher
    `categorias_ordem`.
    """
    candidatas = [
        coluna
        for coluna in perfil.colunas
        if coluna.categorias and coluna.sugestao == CATEGORICA
    ]
    if not candidatas:
        return ""

    linhas = ["## Valores observados", ""]
    for coluna in candidatas:
        preenchidos = coluna.preenchidos or 1
        linhas.append(f"**`{coluna.nome}`** — {coluna.unicos} valor(es)")
        linhas.append("")
        linhas.append("| valor | n | % dos preenchidos |")
        linhas.append("|---|---:|---:|")
        for valor, quantos in coluna.categorias:
            fatia = f"{quantos / preenchidos * 100:.1f}".replace(".", ",")
            linhas.append(f"| {_celula(valor)} | {quantos} | {fatia}% |")
        if coluna.faltantes:
            linhas.append(f"| *(vazio)* | {coluna.faltantes} | — |")
        linhas.append("")

    linhas += [
        "> Variáveis com mais de "
        f"{LIMITE_CATEGORIAS} valores distintos não são listadas por extenso.",
        "",
    ]
    return "\n".join(linhas)


def _md_numericas(perfil: Perfil) -> str:
    """
    O resumo de cada numérica, que é o que se olha para decidir as faixas.
    """
    numericas = [coluna for coluna in perfil.colunas if coluna.resumo]
    if not numericas:
        return ""

    linhas = [
        "## Resumo das numéricas",
        "",
        "| variável | n | mínimo | q1 | mediana | q3 | máximo | média | desvio |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for coluna in numericas:
        resumo = coluna.resumo_numerico
        valores = " | ".join(
            _numero(resumo[chave])
            for chave in ("minimo", "q1", "mediana", "q3", "maximo", "media", "desvio")
        )
        linhas.append(f"| `{_celula(coluna.nome)}` | {coluna.preenchidos} | {valores} |")

    linhas += [
        "",
        "> As faixas ficam em branco no dicionário: sem elas, a Fase 5 usa a regra "
        "padrão. Preencha `faixas` quando o cliente pedir cortes específicos — os "
        "quartis acima são o ponto de partida da conversa.",
        "",
    ]
    return "\n".join(linhas)


def _md_dicionario(perfil: Perfil, fusao: Fusao) -> str:
    analisaveis = sum(1 for linha in fusao.linhas if linha.analisavel)
    linhas = [
        "## O dicionário",
        "",
        f"`dicionario.csv` — {fusao.total} variável(is), {analisaveis} marcada(s) para "
        "entrar na descritiva.",
        "",
    ]

    if not fusao.existia:
        linhas.append(
            "Foi criado agora, com uma sugestão por variável. **Revise a coluna `tipo`** "
            "antes da Fase 5: a automação propõe e você decide. `ignorar` é o tipo das "
            "colunas que não entram na descritiva — identificador, texto livre, coluna "
            "auxiliar; marcar é melhor do que deixar de fora, porque fica registrado que "
            "a decisão foi consciente."
        )
    else:
        linhas.append(
            f"Já existia e foi preservado: {len(fusao.preservadas)} linha(s) intacta(s), "
            f"{len(fusao.novas)} acrescentada(s)."
        )
        if fusao.novas:
            linhas.append("")
            linhas.append(
                "Variáveis novas nesta versão do banco: "
                + ", ".join(f"`{nome}`" for nome in fusao.novas)
                + "."
            )
        if fusao.ausentes:
            linhas.append("")
            linhas.append(
                "No dicionário e **fora** desta versão do banco (marcadas `no_banco = nao`, "
                "não apagadas): "
                + ", ".join(f"`{nome}`" for nome in fusao.ausentes)
                + "."
            )
        if fusao.reaparecidas:
            linhas.append("")
            linhas.append(
                "Voltaram ao banco: "
                + ", ".join(f"`{nome}`" for nome in fusao.reaparecidas)
                + "."
            )

    linhas.append("")
    return "\n".join(linhas)


def _celula(texto: str) -> str:
    """
    Um valor do banco dentro de uma célula de tabela markdown.

    A barra vertical é o separador de coluna: um valor que a contenha parte a
    linha em duas e desalinha a tabela inteira. É o mesmo cuidado que o `cli.py`
    toma com colchete e o `rich`.
    """
    return _ESPACOS.sub(" ", str(texto)).replace("|", "\\|").strip()


def _geracao_anterior(caminho: Path) -> datetime | None:
    """
    Quando o `perfil.md` que está no disco foi gerado.

    Serve para a simulação dizer *o que* vai ser substituído, e não só que algo
    será. Um `perfil.md` de hoje de manhã é uma coisa; um de três semanas atrás,
    com as suas anotações da reunião, é outra.
    """
    if not caminho.is_file():
        return None
    try:
        with caminho.open(encoding="utf-8") as arquivo:
            primeira = arquivo.readline()
    except OSError:
        return None

    if not primeira.startswith(_MARCA_GERACAO):
        return None
    marca = primeira[len(_MARCA_GERACAO) :].strip().removesuffix("-->").strip()
    try:
        return datetime.fromisoformat(marca)
    except ValueError:
        return None


def _acao_do_historico(plano: PlanoPerfil) -> str:
    perfil = plano.perfil
    partes = [
        f"`flatcap perfil {perfil.ficha.record_id}` — perfil de "
        f"`{perfil.versao_arquivo}` ({perfil.linhas} linhas × {perfil.total_colunas} "
        f"colunas, {len(perfil.a_corrigir)} a corrigir, {len(perfil.a_confirmar)} a "
        "confirmar)."
    ]
    if not plano.fusao.existia:
        partes.append(f"`dicionario.csv` criado com {plano.fusao.total} variáveis.")
    else:
        partes.append(
            f"`dicionario.csv` atualizado: {len(plano.fusao.novas)} nova(s), "
            f"{len(plano.fusao.preservadas)} preservada(s)."
        )
    return " ".join(partes)