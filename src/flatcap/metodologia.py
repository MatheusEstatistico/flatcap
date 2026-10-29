# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
A metodologia — o parágrafo da primeira página que o cliente leva para o artigo.

O relatório abre com a finalidade e os objetivos, que vieram do REDCap. Este módulo
escreve o que vem logo depois: um subtítulo — "Metodologia Estatística (texto padrão)" —
e um parágrafo curto, no registro de uma seção de métodos, dizendo como os números do
documento foram produzidos — para o cliente copiar, ajustar e levar para o artigo.

## O parágrafo sai das rodadas, e não de um texto fixo

Um texto fixo diria "qui-quadrado ou exato de Fisher, Pearson, Spearman ou Kendall,
t, ANOVA, Mann-Whitney, Kruskal-Wallis…" em todo relatório, e a seção de métodos de
um artigo que cita um teste que não aparece em resultado nenhum é a primeira coisa que
o parecerista marca. Então cada análise com rodada em `3. Análises/` contribui com uma
frase, e a frase nomeia **só os testes que rodaram** — lidos do manifesto, onde cada
análise já escreve o teste de cada par, de cada item e de cada delineamento.

É a mesma régua do resto do relatório: **nada aqui abre o banco.** O que o parágrafo
afirma está no `manifesto.json` da rodada — o teste de cada linha (`detalhes`), o alfa
e a correção para comparações múltiplas (`regras`), a versão do Python (`ambiente`).
Rodar a análise de novo reescreve o manifesto, e o parágrafo acompanha sem ninguém
lembrar de editá-lo.

## O que se edita, e onde

A redação mora no bloco emoldurado logo abaixo, como o `TEXTO_PADRAO` do
`relatorio.py`: o subtítulo, a frase de cada análise, o nome de cada teste. Mudar uma
palavra é mudar uma string. O que muda de projeto para projeto — quais testes, a versão
do Python, o alfa — vem do manifesto e não se escreve à mão.

O subtítulo sai separado do parágrafo, no `Metodologia.titulo`, e não colado na frente
dele: é o `documento.py` quem o escreve no estilo de subtítulo do modelo (o
`FlatCap Subtitulo`, o mesmo da linha `matrícula - nome`), que se ajusta no Word.

## Os nomes dos testes são os do manifesto

Este módulo não importa as análises: elas trazem o `pandas` e o `scipy`, e o
`relatorio.py` — que importa este — tem um teste em subprocesso que falha se o
`pandas` for carregado. Os nomes que o manifesto grava (`t de Welch`,
`Kruskal-Wallis`, `Qui-quadrado com correção de Yates`) estão escritos aqui como
texto, e o `test_metodologia.py` confere que são, letra por letra, as constantes das
análises. Um teste novo que entre numa análise sem entrar aqui aparece nesse teste,
e não num artigo.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from .manifesto import (
    ANALISE_ASSOCIACAO,
    ANALISE_COMPARACAO,
    ANALISE_CORRELACAO,
    ANALISE_CRUZAMENTO,
    ANALISE_DESCRITIVA,
    ANALISE_NORMALIDADE,
    Manifesto,
)

# ─────────────────────────────────────────────────────────────────────────────
#  O TEXTO DA METODOLOGIA — é aqui que se escreve.
#
#  O parágrafo é a soma das frases das análises que têm rodada, na ordem da
#  `ORDEM` abaixo, mais a do nível de significância e a do Python. Cada frase
#  só nomeia o que rodou: os testes saem do manifesto, e os nomes deles, deste
#  bloco. Mudar a redação é mudar as strings; nada no resto do módulo depende do
#  que está escrito nelas.
#
#  Em `{}`, o que o manifesto preenche. Uma chave escrita errada aqui é um
#  `KeyError` no primeiro teste, e não um `{versao}` impresso no documento.
# ─────────────────────────────────────────────────────────────────────────────

# O subtítulo acima do parágrafo, no estilo de subtítulo do documento. `""` tira o
# subtítulo, e o parágrafo vem logo depois dos objetivos.
TITULO = "Metodologia Estatística (texto padrão)"

# A ordem das frases é a de uma seção de métodos — descrever, cruzar, testar —, e não
# a das seções do relatório, que é a da lista `analises:` da ficha.
ORDEM: tuple[str, ...] = (
    ANALISE_DESCRITIVA,
    ANALISE_CRUZAMENTO,
    ANALISE_ASSOCIACAO,
    ANALISE_NORMALIDADE,
    ANALISE_CORRELACAO,
    ANALISE_COMPARACAO,
)

# A descritiva: como cada tipo do dicionário foi resumido. Com mais de um tipo, o
# primeiro vira o sujeito da frase e os outros vêm depois dele, elípticos: «As
# variáveis categóricas foram descritas por …, e as numéricas, por …». Cada tipo traz
# as duas formas — a de sujeito e a elíptica — e o como.
DESCRICAO: dict[str, tuple[str, str, str]] = {
    "categorica": (
        "As variáveis categóricas", "as categóricas", "por frequências absolutas e relativas"
    ),
    "numerica": (
        "As variáveis numéricas",
        "as numéricas",
        "por média e desvio padrão, mediana e quartis",
    ),
    "data": ("As datas", "as datas", "pelo período e pela distribuição no tempo"),
}
FRASE_DESCRITIVA = "{sujeito} foram descritas {como}"

FRASE_CRUZAMENTO = "Pares de variáveis categóricas foram cruzados em tabelas de contingência."

FRASE_ASSOCIACAO = (
    "A associação entre variáveis categóricas foi avaliada {testes}, e a sua intensidade, "
    "pelo V de Cramér."
)
QUI_QUADRADO = "pelo teste qui-quadrado de Pearson"
YATES = ", com a correção de Yates nas tabelas 2×2"
FISHER = "pelo teste exato de Fisher"
# Quando os dois rodaram, a frase diz quando foi um e quando foi o outro: a regra de
# Cochran, como o `associacao.py` a aplica.
FISHER_PELA_REGRA = (
    " ou, quando alguma frequência esperada era menor que 1 ou mais de 20% delas eram "
    "menores que 5, pelo teste exato de Fisher"
)

FRASE_NORMALIDADE = (
    "A normalidade das variáveis numéricas foi avaliada pelo teste de Shapiro-Wilk{e_qq}."
)
E_QQ = " e pelo gráfico quantil-quantil"

FRASE_CORRELACAO = "As correlações foram estimadas {metodos}, com intervalos de confiança de 95%."
CORRELACOES: dict[str, str] = {
    "Pearson": "pelo coeficiente de Pearson",
    "Spearman": "pelo coeficiente de Spearman",
    "Kendall": "pelo tau-b de Kendall",
}
# Por que a regra escolheu cada um. Saem só quando mais de um método rodou e a ficha
# não escreveu nenhum: com um método só não há escolha a explicar, e com o método
# escrito na ficha a escolha não foi da regra.
POR_QUE: dict[str, str] = {
    "Spearman": "quando {ordinal}o teste de Shapiro-Wilk rejeitou a normalidade de alguma "
    "das variáveis",
    "Kendall": "quando alguma das variáveis tinha até 10 valores distintos",
}
ORDINAL = "uma das variáveis era ordinal ou "

# A comparação: o que se comparou, e com quais testes. As chaves de dentro são os
# nomes que o manifesto grava; os valores, como eles se escrevem na frase.
DELINEAMENTOS: dict[str, str] = {
    "uma_amostra": "na comparação com um valor de referência",
    "dois_grupos": "entre dois grupos",
    "k_grupos": "entre três grupos ou mais",
    "repetidas": "entre medidas repetidas",
}
COMPARACOES: dict[str, dict[str, str]] = {
    "uma_amostra": {
        "t de Student": "o teste t de Student para uma amostra",
        "Wilcoxon": "o teste de Wilcoxon",
    },
    "dois_grupos": {
        "t de Welch": "o teste t de Welch",
        "t de Student": "o teste t de Student",
        "Mann-Whitney": "o teste de Mann-Whitney",
    },
    "k_grupos": {
        "ANOVA de Welch": "a ANOVA de Welch",
        "ANOVA": "a ANOVA de um fator",
        "Kruskal-Wallis": "o teste de Kruskal-Wallis",
    },
    "repetidas": {
        "ANOVA de medidas repetidas": (
            "a ANOVA de medidas repetidas, com a correção de Greenhouse-Geisser"
        ),
        "Friedman": "o teste de Friedman",
    },
}
# Sai quando a regra escolheu algum teste. Com algum escrito na ficha, a frase abre
# com a exceção, porque ali a escolha não foi da regra.
FRASE_REGRA_DA_COMPARACAO = (
    "o teste paramétrico foi usado quando o de Shapiro-Wilk não rejeitou a normalidade em "
    "nenhum grupo ou medida, e o de postos nos demais casos."
)
EXCECAO = "Exceto quando o teste foi definido de antemão, "

FRASE_SIGNIFICANCIA = "Adotou-se o nível de significância de {alfa}%{multiplas}."
SEM_CORRECAO = ", sem correção para comparações múltiplas"

# A última frase. `{versao}` é o `VERSAO` com a versão do Python das rodadas — o
# `VERSOES`, quando elas rodaram em Pythons diferentes —, e some quando o manifesto
# não registra o Python.
FRASE_PROGRAMAS = "As análises foram feitas usando a linguagem Python{versao}."
VERSAO = " versão {python}"
VERSOES = " versões {python}"

# ─────────────────────────────────────────────────────────────────────────────

# As análises que testam hipótese, e por isso pedem a frase do nível de significância.
_TESTAM = (ANALISE_ASSOCIACAO, ANALISE_NORMALIDADE, ANALISE_CORRELACAO, ANALISE_COMPARACAO)

# O alfa de quem não o registra: a associação só relata o p. É o das outras análises.
_ALFA_PADRAO = 0.05

_QUI_QUADRADOS = frozenset({"Qui-quadrado", "Qui-quadrado com correção de Yates"})
_YATES = "Qui-quadrado com correção de Yates"
_FISHER = "Exato de Fisher"


@dataclass(frozen=True)
class Metodologia:
    """
    O subtítulo, o parágrafo, e o que ficou sem frase.

    `paragrafos` é o que vai para a primeira página — um parágrafo, ou nenhum —, e
    `titulo` o subtítulo que vem acima dele, vazio quando não há parágrafo. `sem_frase`
    são as análises com rodada que não deram frase porque o manifesto delas não diz o que
    rodou: um aviso de terminal, e não um texto inventado no documento.
    """

    paragrafos: tuple[str, ...] = ()
    titulo: str = ""
    sem_frase: tuple[str, ...] = ()

    @property
    def texto(self) -> str:
        return "\n".join(self.paragrafos)


def montar_metodologia(manifestos: Iterable[Manifesto]) -> Metodologia:
    """
    O parágrafo de metodologia das rodadas, na ordem de uma seção de métodos.

    Recebe os manifestos — e não o banco, nem a ficha: o que o parágrafo afirma é o que
    as rodadas registraram. Uma análise fora da `ORDEM` (uma que venha depois desta
    versão) não quebra nada: ela fica sem frase e aparece em `sem_frase`.
    """
    por_analise: dict[str, Manifesto] = {}
    for manifesto in manifestos:
        por_analise.setdefault(manifesto.analise, manifesto)

    frases: list[str] = []
    com_frase: list[str] = []
    sem_frase: list[str] = []
    for analise in (*ORDEM, *sorted(set(por_analise) - set(ORDEM))):
        manifesto = por_analise.get(analise)
        if manifesto is None:
            continue
        escrever = _FRASES.get(analise)
        frase = escrever(manifesto) if escrever else ""
        if frase:
            frases.append(frase)
            com_frase.append(analise)
        elif escrever is None or not _nada_testado(manifesto):
            sem_frase.append(analise)

    if not frases:
        return Metodologia(sem_frase=tuple(sem_frase))

    # O nível de significância só quando alguma frase nomeou um teste: uma comparação
    # em que toda linha saiu "não testado" não tem p a ler contra ele.
    testam = [por_analise[nome] for nome in _TESTAM if nome in com_frase]
    if testam:
        frases.append(_significancia(testam))
    frases.append(_programas(list(por_analise.values())))

    return Metodologia(
        paragrafos=(" ".join(frases),), titulo=TITULO, sem_frase=tuple(sem_frase)
    )


# As frases


def _descritiva(manifesto: Manifesto) -> str:
    tipos = [tipo for tipo in DESCRICAO if any(item.tipo == tipo for item in manifesto.itens)]
    if not tipos:
        return ""
    sujeito, _, como = DESCRICAO[tipos[0]]
    abertura = FRASE_DESCRITIVA.format(sujeito=sujeito, como=como)
    resto = [f"{elipse}, {como}" for _, elipse, como in (DESCRICAO[t] for t in tipos[1:])]
    if not resto:
        return f"{abertura}."
    if len(resto) == 1:
        return f"{abertura}, e {resto[0]}."
    return f"{abertura}; " + "; ".join(resto[:-1]) + f"; e {resto[-1]}."


def _cruzamento(manifesto: Manifesto) -> str:
    return FRASE_CRUZAMENTO if manifesto.itens else ""


def _associacao(manifesto: Manifesto) -> str:
    testes = {str(par.get("teste") or "") for par in _linhas(manifesto, "pares")}
    qui = bool(testes & _QUI_QUADRADOS)
    yates = YATES if _YATES in testes else ""
    fisher = _FISHER in testes
    if qui and fisher:
        trecho = QUI_QUADRADO + yates + FISHER_PELA_REGRA
    elif qui:
        trecho = QUI_QUADRADO + yates
    elif fisher:
        trecho = FISHER
    else:
        return ""
    return FRASE_ASSOCIACAO.format(testes=trecho)


def _normalidade(manifesto: Manifesto) -> str:
    if not manifesto.itens or _nada_testado(manifesto):
        return ""
    graficos = bool(manifesto.regras.get("graficos"))
    return FRASE_NORMALIDADE.format(e_qq=E_QQ if graficos else "")


def _correlacao(manifesto: Manifesto) -> str:
    pares = [par for par in _linhas(manifesto, "pares") if par.get("metodo") in CORRELACOES]
    if not pares:
        return ""
    metodos = [nome for nome in CORRELACOES if any(par["metodo"] == nome for par in pares)]
    pela_regra = len(metodos) > 1 and not any(par.get("escrito_na_ficha") for par in pares)
    if not pela_regra:
        return FRASE_CORRELACAO.format(metodos=_lista([CORRELACOES[m] for m in metodos]))

    # «pelo coeficiente de Pearson ou, quando …, pelo de Spearman»: o primeiro é o da
    # regra quando nada a desvia; os outros vêm com o porquê, e sem repetir o nome.
    ordinal = any(
        "categorica" in (par.get("tipo_1"), par.get("tipo_2"))
        for par in pares
        if par["metodo"] == "Spearman"
    )
    texto = CORRELACOES[metodos[0]]
    for metodo in metodos[1:]:
        porque = POR_QUE[metodo].format(ordinal=ORDINAL if ordinal else "")
        nome = CORRELACOES[metodo].replace("pelo coeficiente de", "pelo de")
        texto += f" ou, {porque}, {nome}"
    return FRASE_CORRELACAO.format(metodos=texto)


def _comparacao(manifesto: Manifesto) -> str:
    detalhes = _detalhes(manifesto)
    partes: list[tuple[str, list[str]]] = []
    testadas: list[dict[str, Any]] = []
    for delineamento, nomes in COMPARACOES.items():
        linhas = [
            linha
            for linha in detalhes.get(delineamento) or ()
            if isinstance(linha, dict) and linha.get("teste") in nomes
        ]
        if not linhas:
            continue
        testadas += linhas
        usados = [nome for nome in nomes if any(linha["teste"] == nome for linha in linhas)]
        partes.append((delineamento, [nomes[nome] for nome in usados]))
    if not partes:
        return ""

    # O verbo concorda com os testes do primeiro delineamento, que é o sujeito dele; nos
    # outros ele fica subentendido: «usou-se o t para uma amostra; entre dois grupos, …».
    verbo = "usou-se" if len(partes[0][1]) == 1 else "usaram-se"
    blocos = []
    for posicao, (delineamento, testes) in enumerate(partes):
        onde = DELINEAMENTOS[delineamento]
        quais = _lista(_sem_repetir_teste(testes))
        blocos.append(
            f"{_maiuscula(onde)}, {verbo} {quais}" if posicao == 0 else f"{onde}, {quais}"
        )
    if len(blocos) == 1:
        frase = blocos[0] + "."
    else:
        frase = "; ".join(blocos[:-1]) + f"; e {blocos[-1]}."

    pela_regra = [linha for linha in testadas if not linha.get("escrito_na_ficha")]
    if not pela_regra:
        return frase
    if len(pela_regra) < len(testadas):
        return f"{frase} {EXCECAO}{FRASE_REGRA_DA_COMPARACAO}"
    return f"{frase} {_maiuscula(FRASE_REGRA_DA_COMPARACAO)}"


_FRASES = {
    ANALISE_DESCRITIVA: _descritiva,
    ANALISE_CRUZAMENTO: _cruzamento,
    ANALISE_ASSOCIACAO: _associacao,
    ANALISE_NORMALIDADE: _normalidade,
    ANALISE_CORRELACAO: _correlacao,
    ANALISE_COMPARACAO: _comparacao,
}


def _significancia(manifestos: Sequence[Manifesto]) -> str:
    alfas = {
        float(manifesto.regras["alfa"])
        for manifesto in manifestos
        if isinstance(manifesto.regras.get("alfa"), int | float)
    }
    alfa = alfas.pop() if len(alfas) == 1 else _ALFA_PADRAO
    quantos = sum(_testados(manifesto) for manifesto in manifestos)
    sem_correcao = quantos > 1 and any(
        str(manifesto.regras.get("comparacoes_multiplas", "")).startswith("nenhuma")
        for manifesto in manifestos
    )
    return FRASE_SIGNIFICANCIA.format(
        alfa=_numero(alfa * 100), multiplas=SEM_CORRECAO if sem_correcao else ""
    )


def _programas(manifestos: Sequence[Manifesto]) -> str:
    """
    "As análises foram feitas usando a linguagem Python versão 3.11."

    A versão vem do `ambiente` de cada rodada, sem o último número: o 3.11.15 de uma
    máquina e o 3.11.9 de outra são o mesmo Python para quem lê o artigo.
    """
    versoes = sorted(
        {
            ".".join(str(manifesto.ambiente["python"]).split(".")[:2])
            for manifesto in manifestos
            if manifesto.ambiente.get("python")
        },
        key=_chave_de_versao,
    )
    if not versoes:
        versao = ""
    elif len(versoes) == 1:
        versao = VERSAO.format(python=versoes[0])
    else:
        versao = VERSOES.format(python=_lista(versoes))
    return FRASE_PROGRAMAS.format(versao=versao)


# Miúdos


def _detalhes(manifesto: Manifesto) -> dict[str, Any]:
    """
    Os `detalhes` do item da rodada. As análises que testam escrevem um item só, com
    todos os pares, linhas e delineamentos dentro dele.
    """
    for item in manifesto.itens:
        if isinstance(item.detalhes, dict) and item.detalhes:
            return item.detalhes
    return {}


def _linhas(manifesto: Manifesto, chave: str) -> list[dict[str, Any]]:
    valor = _detalhes(manifesto).get(chave)
    if not isinstance(valor, list):
        return []
    return [linha for linha in valor if isinstance(linha, dict)]


def _testados(manifesto: Manifesto) -> int:
    """
    Quantos testes de hipótese a rodada fez — para a frase das comparações múltiplas.

    A normalidade não conta: o Shapiro-Wilk ali é pressuposto, e não resultado.
    """
    if manifesto.analise == ANALISE_NORMALIDADE:
        return 0
    detalhes = _detalhes(manifesto)
    for chave in ("testados", "testadas"):
        if isinstance(detalhes.get(chave), int):
            return int(detalhes[chave])
    return 0


def _nada_testado(manifesto: Manifesto) -> bool:
    """
    A rodada não deu frase porque não testou nada — e o manifesto diz isso.

    É o caso da comparação em que toda linha saiu "não testado": a tabela está no
    documento com o motivo, e o parágrafo não tem teste a nomear. Diferente de um
    manifesto que não registra o que rodou, que vira aviso.
    """
    detalhes = _detalhes(manifesto)
    return any(detalhes.get(chave) == 0 for chave in ("testados", "testadas"))


def _sem_repetir_teste(testes: list[str]) -> list[str]:
    """«o teste t de Welch e o de Mann-Whitney»: o segundo «teste» fica subentendido."""
    saida: list[str] = []
    for posicao, teste in enumerate(testes):
        anterior = testes[posicao - 1] if posicao else ""
        if anterior.startswith("o teste ") and teste.startswith("o teste de "):
            teste = "o " + teste.removeprefix("o teste ")
        saida.append(teste)
    return saida


def _maiuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _lista(itens: Sequence[str]) -> str:
    """`["a"]` → «a»; `["a", "b", "c"]` → «a, b e c»."""
    itens = [item for item in itens if item]
    if len(itens) <= 1:
        return itens[0] if itens else ""
    return ", ".join(itens[:-1]) + f" e {itens[-1]}"


def _numero(valor: float) -> str:
    """5.0 → «5»; 2.5 → «2,5». O alfa em percentual, sem zero sobrando."""
    return f"{valor:.4f}".rstrip("0").rstrip(".").replace(".", ",")


def _chave_de_versao(versao: str) -> tuple[int, ...]:
    return tuple(int(parte) for parte in re.findall(r"\d+", versao))


__all__ = [
    "COMPARACOES",
    "CORRELACOES",
    "DELINEAMENTOS",
    "Metodologia",
    "ORDEM",
    "TITULO",
    "montar_metodologia",
]
