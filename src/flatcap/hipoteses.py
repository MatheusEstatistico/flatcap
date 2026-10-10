# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-FileCopyrightText: 1995-2019 The R Core Team
# SPDX-FileCopyrightText: 1998 B. D. Ripley
# SPDX-License-Identifier: GPL-3.0-or-later
"""
A aritmética dos testes de hipótese — como o R os calcula, e mais nada.

Recebe números e devolve um `Resultado`. Não sabe o que é ficha, dicionário, banco,
manifesto nem formatação: quem decide **qual** teste rodar, sobre **quais** valores,
e o que escrever na tabela é o `comparacao.py`. Este módulo responde uma pergunta
só — "dado este vetor e esta referência, o que o R diria?" — e responde do mesmo
jeito para qualquer análise que um dia precisar dele.

## Por que a aritmética mora fora da análise

Na correlação e na associação a conta ficou dentro do módulo da análise, e lá
funcionou: cada uma tem uma pergunta e três ou dois métodos. A comparação vai
crescer em outra direção — uma amostra, pareado, dois grupos, k grupos, cada um com
um teste paramétrico e um sem o pressuposto da normal —, e três coisas pedem a
fronteira:

* **o pareado é a uma amostra sobre as diferenças.** `t.test(x, y, paired = TRUE)`
  é `t.test(x - y, mu = 0)`, e o Wilcoxon pareado é o de uma amostra sobre `x - y`.
  O motor que entra agora é o do pareado depois, e ele precisa estar num lugar que
  os dois delineamentos alcancem;
* **o `test_hipoteses.py` confere contra o R sem projeto, banco nem ficha.** A
  referência entra, o número sai — é onde cabem os valores do R que cada teste novo
  traz;
* **o `comparacao.py` não vira um arquivo de cinco mil linhas** quando a lista de
  testes estiver inteira.

É o "importar a aritmética, escrever as decisões" da normalidade, virando fronteira
de arquivo.

## O `Resultado` é o `htest` do R

`t.test`, `wilcox.test`, `oneway.test`, `kruskal.test` e `friedman.test` devolvem o
mesmo objeto — `statistic`, `parameter`, `p.value`, `conf.int`, `estimate`,
`null.value` e `method` —, e é por isso que ele serve de contrato para todos os testes
de comparação. Os campos do `Resultado` são esses, com os nomes da casa. O
`Coeficiente` da correlação já era quase ele.

**Sempre bilateral.** Como na correlação: um teste unilateral escolhido depois de
olhar os dados é o p dividido por dois, e a ficha não tem como dizer que a direção
foi decidida antes.

## Os testes de postos

Os quatro que dispensam a normal — o Wilcoxon de uma amostra, o Mann-Whitney, o
Kruskal-Wallis e o Friedman — trocam os valores pelos postos deles, com o posto médio
nos empates, como o `rank` do R. Os dois primeiros são o `wilcox.test` do R, e os dois
saem **com a estimativa e o intervalo**, o `conf.int = TRUE` — que não é o padrão do
R, e é o que dá o tamanho do efeito na unidade da variável, como o intervalo do t: a
pseudomediana de Hodges-Lehmann no Wilcoxon, a diferença de locação no Mann-Whitney.
O Kruskal-Wallis e o Friedman não estimam nada, como a ANOVA.

**O caminho do p é a escolha do R, escrita**: exato — pela distribuição do posto
sinalizado ou da soma dos postos — com menos de 50 valores (na uma amostra, os que não
são iguais à referência; no Mann-Whitney, em cada grupo), sem empate e sem zero; nos
outros casos, a aproximação normal, com a variância corrigida para os empates e a
correção de continuidade. O Kruskal-Wallis e o Friedman só têm a aproximação do
qui-quadrado, no R e aqui.

## Quando importar, e quando escrever

A régua é a que a Fase 7 aprendeu teste a teste, em três degraus:

1. **o `scipy` faz o que o R faz** → importar. É o caso do t: `ttest_1samp`,
   `ttest_ind` e o `confidence_interval()` deles dão o t, os graus de liberdade, o p e
   o intervalo do `t.test`, conferidos até a décima quarta casa — no de duas amostras,
   inclusive com um grupo de um valor só. E do Kruskal-Wallis: o `kruskal` dá o
   qui-quadrado e o p do `kruskal.test`, com a mesma correção para empates;
2. **o `scipy` dá o número, mas não tudo o que vai para a tabela** → escrever a
   fórmula, e do `scipy` importar só a cauda. O `f_oneway` dá o F e o p do
   `oneway.test`, mas não os graus de liberdade: ver `anova_de_um_fator`. O
   `friedmanchisquare` dá o qui-quadrado do `friedman.test`, mas recusa duas medidas,
   que o R aceita: ver `friedman`. A função do `scipy` fica nos testes, como
   conferência;
3. **nem isso basta** → transcrever a aritmética do R, como o AS 89 do Spearman e o
   algoritmo de rede do Fisher — e a ANOVA de medidas repetidas, que o `scipy` não
   tem: ver `anova_de_medidas_repetidas`. **O Wilcoxon e o Mann-Whitney estão aqui**,
   e não no segundo degrau, como o desenho previa: o `wilcoxon` e o `mannwhitneyu` do
   `scipy` dão o p do R quando recebem a escolha do R, mas o intervalo pede os quantis
   das distribuições exatas — que o `scipy` não expõe — e, no caminho aproximado, a
   busca de raiz do `wilcox.test`, que o R faz com o `uniroot`. As distribuições são
   contadas aqui, em inteiros, e servem ao p e ao intervalo ao mesmo tempo; a busca é
   o `uniroot` do R transcrito: ver `_raiz`.

## O que ele recusa

Com `ValueError`, e só o que o próprio R recusa: menos de dois valores (`not enough
'x' observations`), valores que não variam (`data are essentially constant`), e
valor ausente ou infinito no vetor. No t de Student de duas amostras, o mínimo é o do
R para ele: um valor em cada grupo e três no total (`not enough observations`); no de
Welch, dois em cada grupo (`not enough 'x' observations`), porque cada grupo entra com
a sua variância, e a de um valor só não existe; na ANOVA — as duas —, dois em cada grupo
também, que é o `not enough observations` do `oneway.test`; nas medidas repetidas, dois
casos com todas as medidas. Nos testes de postos, os mínimos do R são menores — um
valor no Wilcoxon, um em cada grupo no Mann-Whitney e no Kruskal-Wallis; no Friedman,
dois casos, como na ANOVA —, e as barreiras que o R não tem são as do resultado sem
sentido, onde ele devolve `NaN`: todos os valores iguais à referência no Wilcoxon,
todos iguais no Kruskal-Wallis, e cada caso com as medidas todas iguais no Friedman. Quem
chega aqui pelo `comparacao.py` já passou por essas barreiras, uma a uma, com a frase
de cada uma na tabela; o `ValueError` é para quem chamar a função direto — em teste,
ou no dia em que outra análise precisar dela —, e é erro de programação: dado que não
dá teste não é resultado.

**Nenhuma função daqui começa com `test`.** `t_uma_amostra`, e não `teste_t`: o
`pytest` coleta como caso de teste qualquer objeto `test*` importado num arquivo de
teste, que é a armadilha em que o `testar` da normalidade caiu antes de virar
`avaliar`.

O `scipy` é importado **dentro** de cada função, como no resto do pacote: nenhum
comando que não faz teste deve pagar o import. O `numpy` não é dependência nova — o
`pandas` já o exige.
"""

from __future__ import annotations

import math
import sys
import warnings
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from typing import Any

# O nível do intervalo. O mesmo 95% da correlação e do `conf.level` padrão do R.
CONFIANCA = 0.95

# O menor número de valores com que o `t.test` do R calcula o t de uma amostra.
MINIMO_T = 2

# O menor número de valores, somados os dois grupos, com que o `t.test` do R calcula o
# t de Student de duas amostras: um em cada grupo, e um grau de liberdade que sobre.
MINIMO_STUDENT = 3

# O nome de cada teste, como ele vai para a coluna `teste` da tabela. É o `method`
# do `htest`, em português — e, nos testes de postos, o nome pelo qual cada um é
# conhecido: o `wilcox.test` de duas amostras, que o R chama de soma de postos de
# Wilcoxon, é o Mann-Whitney.
T_DE_STUDENT = "t de Student"
T_DE_WELCH = "t de Welch"
ANOVA = "ANOVA"
ANOVA_DE_WELCH = "ANOVA de Welch"
ANOVA_DE_MEDIDAS_REPETIDAS = "ANOVA de medidas repetidas"
WILCOXON = "Wilcoxon"
MANN_WHITNEY = "Mann-Whitney"
KRUSKAL_WALLIS = "Kruskal-Wallis"
FRIEDMAN = "Friedman"

# O `exact <- (n < 50)` do `wilcox.test` do R: com menos valores do que isto — na uma
# amostra, os que não são iguais à referência; no Mann-Whitney, em cada grupo —, sem
# empate e sem zero, o p é exato; nos outros casos, a aproximação normal.
LIMITE_DO_EXATO = 50

# A busca do intervalo e da estimativa no caminho aproximado: o `tol.root = 1e-4` do
# `wilcox.test` e o `maxiter = 1000` do `uniroot`. O intervalo aproximado do R é exato
# até essa tolerância, e não além dela — e o daqui é o mesmo número, e não um melhor.
TOLERANCIA_DA_RAIZ = 1e-4
MAXIMO_DE_ITERACOES = 1000


@dataclass(frozen=True)
class Resultado:
    """
    O que um teste de hipótese devolve — o `htest` do R, com os nomes da casa.

    `estatistica` é a do R, com o nome dela em `nome_da_estatistica`: t no t de
    Student, V no Wilcoxon, W no Mann-Whitney, F na ANOVA, o qui-quadrado no
    Kruskal-Wallis e no Friedman. `gl` é uma tupla porque o número de graus de
    liberdade muda de teste para teste: `(14.0,)` no t, fracionário no de Welch,
    `(2.0, 25.0)` na ANOVA, vazio no Wilcoxon e no Mann-Whitney. `calculo_do_p` diz em
    palavras como o p saiu, porque nos testes de postos são dois caminhos conforme o n
    e os empates; `exato` diz qual deles — o `exact` do `method` do R —, e fica `None`
    nos testes que só têm um.

    `estimativa` é o que o teste estima — a média, a diferença de médias, a
    pseudomediana —, com o nome em `nome_da_estimativa`; `ic` é o intervalo dela,
    como o `conf.int` do R, e `confianca_do_ic`, o nível dele — o 95% pedido, ou menos,
    quando o R não o alcança: com poucos valores, a distribuição exata não tem um
    intervalo de 95%, e o R devolve o de nível mais alto que ela tem, com um aviso.
    `referencia` é o `mu` da hipótese nula.

    `epsilon` é o ε de Greenhouse-Geisser das medidas repetidas — o quanto a correção
    encolheu os graus de liberdade, que em `gl` já saem corrigidos. É o único campo que
    não está no `htest`: o R o dá no `anova.mlm`, que não é um.
    """

    metodo: str
    estatistica: float
    nome_da_estatistica: str
    p: float
    gl: tuple[float, ...] = ()
    calculo_do_p: str = ""
    estimativa: float | None = None
    nome_da_estimativa: str = ""
    ic: tuple[float, float] | None = None
    referencia: float | None = None
    epsilon: float | None = None
    exato: bool | None = None
    confianca_do_ic: float | None = None


# O t de Student


def t_uma_amostra(x: Sequence[float], mu: float) -> Resultado:
    """
    O `t.test(x, mu = mu)` do R: bilateral, t com n − 1 graus de liberdade e o
    intervalo de 95% **da média** — não da diferença para a referência, que é como o
    R o dá na uma amostra.

        t = (média − mu) / (DP / √n)
        IC = média ± t(0,975; n − 1) · DP / √n

    Pelo `scipy`, que faz o mesmo que o R aqui: é o primeiro degrau da régua do topo
    do módulo.

    Raises:
        ValueError: menos de dois valores, valores que não variam, valor ausente ou
            infinito, ou referência que não é um número finito.
    """
    from scipy import stats

    valores = _vetor(x)
    referencia = float(mu)
    if not math.isfinite(referencia):
        raise ValueError(f"a referência precisa ser um número finito, e veio {mu!r}")
    if valores.shape[0] < MINIMO_T:
        raise ValueError(
            f"o t de uma amostra precisa de pelo menos {MINIMO_T} valores, e vieram "
            f"{valores.shape[0]}"
        )
    if sem_variacao(valores):
        raise ValueError("os valores não variam: o t é 0/0")

    resultado = stats.ttest_1samp(valores, referencia)
    intervalo = resultado.confidence_interval(confidence_level=CONFIANCA)
    return Resultado(
        metodo=T_DE_STUDENT,
        estatistica=float(resultado.statistic),
        nome_da_estatistica="t",
        p=min(1.0, float(resultado.pvalue)),
        gl=(float(resultado.df),),
        calculo_do_p="t de Student com n − 1 graus de liberdade",
        estimativa=float(valores.mean()),
        nome_da_estimativa="média",
        ic=(float(intervalo.low), float(intervalo.high)),
        referencia=referencia,
        confianca_do_ic=CONFIANCA,
    )


def t_de_student(x: Sequence[float], y: Sequence[float]) -> Resultado:
    """
    O `t.test(x, y, var.equal = TRUE)` do R: duas amostras independentes, a variância
    dos dois grupos combinada, bilateral, n₁ + n₂ − 2 graus de liberdade, e o intervalo
    de 95% **da diferença das médias**, `média(x) − média(y)` — a ordem dos dois
    vetores é a do sinal.

        s² = [(n₁ − 1) s₁² + (n₂ − 1) s₂²] / (n₁ + n₂ − 2)
        t  = (x̄ − ȳ) / √[s² (1/n₁ + 1/n₂)]

    Pelo `scipy`, como o de uma amostra: `ttest_ind(equal_var=True)` e o
    `confidence_interval()` dele dão o t, os gl, o p e os dois limites do R. Conferido
    também no caso de canto que o R aceita e o de Welch não: um grupo de um valor só,
    em que a variância combinada é toda do outro grupo.

    Raises:
        ValueError: grupo vazio, menos de três valores somados os dois grupos, valores
            que não variam, ou valor ausente ou infinito.
    """
    from scipy import stats

    primeiro, segundo = _vetor(x), _vetor(y)
    n1, n2 = primeiro.shape[0], segundo.shape[0]
    if n1 < 1 or n2 < 1:
        raise ValueError(
            f"o t de Student precisa de pelo menos um valor em cada grupo, e vieram {n1} e {n2}"
        )
    if n1 + n2 < MINIMO_STUDENT:
        raise ValueError(
            f"o t de Student precisa de pelo menos {MINIMO_STUDENT} valores somados os dois "
            f"grupos, e vieram {n1 + n2}"
        )
    if sem_variacao_em_duas(primeiro, segundo, variancias_iguais=True):
        raise ValueError("os valores não variam dentro dos grupos: o t é uma divisão por zero")

    with _sem_o_aviso_de_precisao():
        resultado = stats.ttest_ind(primeiro, segundo, equal_var=True)
        intervalo = resultado.confidence_interval(confidence_level=CONFIANCA)
    return Resultado(
        metodo=T_DE_STUDENT,
        estatistica=float(resultado.statistic),
        nome_da_estatistica="t",
        p=min(1.0, float(resultado.pvalue)),
        gl=(float(resultado.df),),
        calculo_do_p="t de Student com n₁ + n₂ − 2 graus de liberdade",
        estimativa=float(primeiro.mean() - segundo.mean()),
        nome_da_estimativa="diferença de médias",
        ic=(float(intervalo.low), float(intervalo.high)),
        referencia=0.0,
        confianca_do_ic=CONFIANCA,
    )


def t_de_welch(x: Sequence[float], y: Sequence[float]) -> Resultado:
    """
    O `t.test(x, y)` do R — o padrão dele, `var.equal = FALSE`: cada grupo com a sua
    variância, bilateral, os graus de liberdade de Welch-Satterthwaite, fracionários, e
    o intervalo de 95% da diferença das médias, `média(x) − média(y)`.

        t  = (x̄ − ȳ) / √(s₁²/n₁ + s₂²/n₂)
        gl = (s₁²/n₁ + s₂²/n₂)² / [(s₁²/n₁)² / (n₁ − 1) + (s₂²/n₂)² / (n₂ − 1)]

    Pelo `scipy`, `ttest_ind(equal_var=False)`, que dá os gl fracionários, o p e o
    intervalo do R — o primeiro degrau da régua. Um grupo que não varia entra com
    variância zero, e o t existe, com os gl do outro grupo: o R calcula, e aqui também.

    Raises:
        ValueError: menos de dois valores em algum grupo, valores que não variam, ou
            valor ausente ou infinito.
    """
    from scipy import stats

    primeiro, segundo = _vetor(x), _vetor(y)
    n1, n2 = primeiro.shape[0], segundo.shape[0]
    if n1 < MINIMO_T or n2 < MINIMO_T:
        raise ValueError(
            f"o t de Welch precisa de pelo menos {MINIMO_T} valores em cada grupo, e vieram "
            f"{n1} e {n2}"
        )
    if sem_variacao_em_duas(primeiro, segundo, variancias_iguais=False):
        raise ValueError("os valores não variam dentro dos grupos: o t é uma divisão por zero")

    with _sem_o_aviso_de_precisao():
        resultado = stats.ttest_ind(primeiro, segundo, equal_var=False)
        intervalo = resultado.confidence_interval(confidence_level=CONFIANCA)
    return Resultado(
        metodo=T_DE_WELCH,
        estatistica=float(resultado.statistic),
        nome_da_estatistica="t",
        p=min(1.0, float(resultado.pvalue)),
        gl=(float(resultado.df),),
        calculo_do_p="t de Welch, com os graus de liberdade de Welch-Satterthwaite",
        estimativa=float(primeiro.mean() - segundo.mean()),
        nome_da_estimativa="diferença de médias",
        ic=(float(intervalo.low), float(intervalo.high)),
        referencia=0.0,
        confianca_do_ic=CONFIANCA,
    )


# A ANOVA


def anova_de_um_fator(grupos: Sequence[Sequence[float]]) -> Resultado:
    """
    O `oneway.test(y ~ g, var.equal = TRUE)` do R — a ANOVA de um fator, a clássica: a
    variância dentro dos grupos combinada, e o F com k − 1 e N − k graus de liberdade.

        F = [Σ nᵢ (x̄ᵢ − x̄)² / (k − 1)] / [Σ (nᵢ − 1) sᵢ² / (N − k)]

    É o `aov` também, sempre que cada grupo tem dois valores ou mais — o `oneway.test`
    recusa grupo de um valor, e o `aov` não; a régua aqui é o primeiro, que é o mesmo
    da ANOVA de Welch.

    **Escrita, e não importada.** O `f_oneway` do `scipy` dá o F e o p do R, mas não
    devolve os graus de liberdade, e eles vão para a nota da tabela. Com a fórmula do
    `oneway.test` escrita aqui — são quatro linhas —, os gl impressos são os mesmos que
    deram o p, e não uma segunda conta ao lado da do `scipy`; o `f_oneway` fica nos
    testes, como conferência. Do `scipy` vem só a cauda da F.

    Raises:
        ValueError: menos de dois grupos, menos de dois valores em algum grupo, valores
            que não variam dentro dos grupos, ou valor ausente ou infinito.
    """
    from scipy import stats

    vetores = _grupos_da_anova(grupos)
    if sem_variacao_nos_grupos(vetores, variancias_iguais=True):
        raise ValueError(
            "os valores não variam dentro dos grupos: o F é uma divisão por zero"
        )

    k = len(vetores)
    tamanhos = [int(vetor.shape[0]) for vetor in vetores]
    total = sum(tamanhos)
    geral = sum(float(vetor.sum()) for vetor in vetores) / total
    entre = sum(
        n * (float(vetor.mean()) - geral) ** 2 for n, vetor in zip(tamanhos, vetores, strict=True)
    ) / (k - 1)
    dentro = sum(
        (n - 1) * float(vetor.var(ddof=1)) for n, vetor in zip(tamanhos, vetores, strict=True)
    ) / (total - k)
    estatistica = entre / dentro
    gl = (float(k - 1), float(total - k))
    return Resultado(
        metodo=ANOVA,
        estatistica=estatistica,
        nome_da_estatistica="F",
        p=min(1.0, float(stats.f.sf(estatistica, *gl))),
        gl=gl,
        calculo_do_p="F com k − 1 e N − k graus de liberdade",
    )


def anova_de_welch(grupos: Sequence[Sequence[float]]) -> Resultado:
    """
    O `oneway.test(y ~ g)` do R — o padrão dele, `var.equal = FALSE`: cada grupo pesado
    pelo inverso da variância da sua média, e os graus de liberdade do denominador pela
    aproximação de Welch (1951), fracionários.

        wᵢ = nᵢ / sᵢ²            x̃ = Σ wᵢ x̄ᵢ / Σ wᵢ
        λ  = Σ [(1 − wᵢ / Σw)² / (nᵢ − 1)] / (k² − 1)
        F  = [Σ wᵢ (x̄ᵢ − x̃)² / (k − 1)] / [1 + 2 (k − 2) λ]
        gl = k − 1  e  1 / (3 λ)

    Escrita pela mesma razão da clássica: o `f_oneway(equal_var=False)` do `scipy` dá o
    F e o p do R, e não os graus de liberdade — que aqui, além de irem para a nota, são
    fracionários e ninguém os adivinha. Com dois grupos, o F é o t de Welch ao quadrado,
    com os mesmos gl.

    Raises:
        ValueError: menos de dois grupos, menos de dois valores em algum grupo, um grupo
            que não varia — onde o R devolve `NaN` —, ou valor ausente ou infinito.
    """
    from scipy import stats

    vetores = _grupos_da_anova(grupos)
    if sem_variacao_nos_grupos(vetores, variancias_iguais=False):
        raise ValueError(
            "um grupo não varia: o peso dele na ANOVA de Welch é n/0, e o R devolve NaN"
        )

    k = len(vetores)
    tamanhos = [int(vetor.shape[0]) for vetor in vetores]
    medias = [float(vetor.mean()) for vetor in vetores]
    pesos = [n / float(vetor.var(ddof=1)) for n, vetor in zip(tamanhos, vetores, strict=True)]
    soma = sum(pesos)
    lambda_ = sum(
        (1 - peso / soma) ** 2 / (n - 1) for peso, n in zip(pesos, tamanhos, strict=True)
    ) / (k**2 - 1)
    ponderada = sum(peso * media for peso, media in zip(pesos, medias, strict=True)) / soma
    estatistica = sum(
        peso * (media - ponderada) ** 2 for peso, media in zip(pesos, medias, strict=True)
    ) / ((k - 1) * (1 + 2 * (k - 2) * lambda_))
    gl = (float(k - 1), 1 / (3 * lambda_))
    return Resultado(
        metodo=ANOVA_DE_WELCH,
        estatistica=estatistica,
        nome_da_estatistica="F",
        p=min(1.0, float(stats.f.sf(estatistica, *gl))),
        gl=gl,
        calculo_do_p="F de Welch, com os graus de liberdade do denominador de Welch",
    )


def anova_de_medidas_repetidas(medidas: Sequence[Sequence[float]]) -> Resultado:
    """
    A ANOVA de um fator de medidas repetidas — as mesmas pessoas medidas k vezes —,
    **sempre com a correção de Greenhouse-Geisser**: o `anova(lm(Y ~ 1), X = ~1,
    test = "Spherical")` do R, a coluna `G-G Pr`. É o F do `aov(y ~ tempo +
    Error(id / tempo))`, com os graus de liberdade multiplicados pelo ε.

        SS_medidas = n Σ (x̄ⱼ − x̄)²                      gl = k − 1
        SS_erro    = Σ (xᵢⱼ − x̄ᵢ − x̄ⱼ + x̄)²             gl = (n − 1)(k − 1)
        F          = [SS_medidas / (k − 1)] / [SS_erro / (n − 1)(k − 1)]
        ε          = (tr D)² / [(k − 1) tr D²],  D = a covariância das medidas centrada
                     nas linhas e nas colunas
        p          = cauda da F com ε (k − 1) e ε (n − 1)(k − 1) graus de liberdade

    **Greenhouse-Geisser sempre, e sem o Mauchly antes**, pela razão do Welch: a
    correção custa pouco quando a esfericidade vale, protege quando não vale, e tira um
    teste preliminar da frente do teste que interessa. Com a esfericidade perfeita, ε
    é 1 e o p é o da ANOVA sem correção.

    **Transcrita, e não importada**: o `scipy` não tem ANOVA de medidas repetidas — é
    o terceiro degrau da régua do topo. Do `scipy` vem só a cauda da F. Derivada do
    `anova.mlm`, em `src/library/stats/R/mlm.R`, do R — (C) 1998-2018 The R Core Team
    e (C) 1998 B. D. Ripley, GPL-2.0-or-later. Origem, e os direitos autorais do
    original: ver o `NOTICE.md`.

    `medidas` são as k colunas, cada uma com os mesmos n casos, na mesma ordem: quem
    chama tira antes os casos com alguma medida faltando, como o `lm` do R faz.

    Raises:
        ValueError: menos de duas medidas, medidas de tamanhos diferentes, menos de dois
            casos, medidas que não variam dentro dos casos, ou valor ausente ou
            infinito.
    """
    import numpy as np
    from scipy import stats

    matriz = _matriz_das_medidas(medidas)
    if sem_variacao_entre_medidas(matriz):
        raise ValueError(
            "as medidas não variam dentro dos casos: o F é uma divisão por zero"
        )

    n, k = matriz.shape
    geral = float(matriz.mean())
    por_medida = matriz.mean(axis=0)
    por_caso = matriz.mean(axis=1)
    ss_medidas = n * float(((por_medida - geral) ** 2).sum())
    residuo = matriz - por_caso[:, None] - por_medida[None, :] + geral
    ss_erro = float((residuo**2).sum())
    gl_medidas, gl_erro = k - 1, (n - 1) * (k - 1)
    estatistica = (ss_medidas / gl_medidas) / (ss_erro / gl_erro)

    covariancia = np.cov(matriz, rowvar=False, ddof=1)
    centrada = (
        covariancia
        - covariancia.mean(axis=0)[None, :]
        - covariancia.mean(axis=1)[:, None]
        + covariancia.mean()
    )
    epsilon = float(np.trace(centrada)) ** 2 / (
        (k - 1) * float(np.trace(centrada @ centrada))
    )
    gl = (epsilon * gl_medidas, epsilon * gl_erro)
    return Resultado(
        metodo=ANOVA_DE_MEDIDAS_REPETIDAS,
        estatistica=estatistica,
        nome_da_estatistica="F",
        p=min(1.0, float(stats.f.sf(estatistica, *gl))),
        gl=gl,
        calculo_do_p=(
            "F com a correção de Greenhouse-Geisser: ε (k − 1) e ε (n − 1)(k − 1) graus "
            "de liberdade"
        ),
        epsilon=epsilon,
    )


def sem_variacao_entre_medidas(medidas: Any) -> bool:
    """
    As medidas não variam dentro dos casos: cada caso muda o mesmo tanto de uma medida
    para outra, ou não muda nada.

    Aí a variação que sobra depois de tirar a média de cada caso e a de cada medida é
    zero, e o F é uma divisão por zero. O R não barra: devolve um F de 10²³ feito de
    ruído de arredondamento, ou um F de 72 para medidas idênticas — conferido. O
    critério é o do `t.test`, levado para cá: o desvio padrão residual abaixo de dez
    épsilons vezes a maior média em valor absoluto.

    Recebe as colunas, ou a matriz n × k já montada.
    """
    matriz = _matriz_das_medidas(medidas, conferir=False)
    n, k = matriz.shape
    if n < MINIMO_T or k < 2:
        return False
    geral = float(matriz.mean())
    por_medida = matriz.mean(axis=0)
    residuo = matriz - matriz.mean(axis=1)[:, None] - por_medida[None, :] + geral
    desvio = math.sqrt(float((residuo**2).sum()) / ((n - 1) * (k - 1)))
    maior = float(abs(por_medida).max())
    return desvio == 0 or desvio < 10 * sys.float_info.epsilon * maior


def _matriz_das_medidas(
    medidas: Any, conferir: bool = True, teste: str = "a ANOVA de medidas repetidas"
) -> Any:
    """
    As medidas como matriz n × k — os casos nas linhas, as medidas nas colunas —, com
    as barreiras: duas medidas ou mais, todas do mesmo tamanho, e dois casos ou mais —
    o mínimo do R na ANOVA de medidas repetidas e no Friedman. `teste` é o nome que vai
    para a frase.
    """
    import numpy as np

    if isinstance(medidas, np.ndarray) and medidas.ndim == 2:
        vetores = [_vetor(medidas[:, j]) for j in range(medidas.shape[1])]
    else:
        vetores = [_vetor(medida) for medida in medidas]
    if len(vetores) < 2:
        raise ValueError(
            f"{teste} precisa de pelo menos 2 medidas, e vieram {len(vetores)}"
        )
    tamanhos = {int(vetor.shape[0]) for vetor in vetores}
    if len(tamanhos) != 1:
        raise ValueError(
            "as medidas precisam ter os mesmos casos, na mesma ordem, e vieram tamanhos "
            + ", ".join(str(int(vetor.shape[0])) for vetor in vetores)
        )
    n = tamanhos.pop()
    if conferir and n < MINIMO_T:
        raise ValueError(
            f"{teste} precisa de pelo menos {MINIMO_T} casos com todas as medidas, e "
            f"vieram {n}"
        )
    return np.column_stack(vetores)


def sem_variacao_nos_grupos(
    grupos: Sequence[Sequence[float]], variancias_iguais: bool = True
) -> bool:
    """
    Os valores não variam dentro dos grupos, para a ANOVA.

    O `oneway.test` do R não tem critério nenhum: com a variância dentro dos grupos
    zero, ele devolve F infinito, e p zero, e a tabela sairia com um `< 0,001` que é
    uma divisão por zero. O critério aqui é o do `t.test`, levado para a ANOVA: o
    desvio padrão combinado abaixo de dez épsilons vezes a maior média em valor
    absoluto — zero, ou só o último bit.

    Com `variancias_iguais=False` — a ANOVA de Welch —, basta **um** grupo que não
    varia: o Welch pesa cada grupo por n/s², e o peso de um grupo constante é
    infinito; o R devolve `NaN`.
    """
    vetores = [_vetor(grupo) for grupo in grupos]
    if not variancias_iguais:
        return any(vetor.shape[0] >= MINIMO_T and sem_variacao(vetor) for vetor in vetores)
    total = sum(int(vetor.shape[0]) for vetor in vetores)
    if len(vetores) < 2 or total <= len(vetores):
        return False
    dentro = sum(
        (int(vetor.shape[0]) - 1) * float(vetor.var(ddof=1))
        for vetor in vetores
        if vetor.shape[0] > 1
    ) / (total - len(vetores))
    maior = max(abs(float(vetor.mean())) for vetor in vetores if vetor.shape[0])
    desvio = math.sqrt(dentro)
    return desvio == 0 or desvio < 10 * sys.float_info.epsilon * maior


def _grupos_da_anova(grupos: Sequence[Sequence[float]]) -> list[Any]:
    """
    Os grupos como vetores, com as duas barreiras do `oneway.test`: dois grupos ou mais
    (`not enough groups`), e dois valores ou mais em cada um (`not enough
    observations`).
    """
    vetores = [_vetor(grupo) for grupo in grupos]
    if len(vetores) < 2:
        raise ValueError(f"a ANOVA precisa de pelo menos 2 grupos, e vieram {len(vetores)}")
    tamanhos = [int(vetor.shape[0]) for vetor in vetores]
    if min(tamanhos) < MINIMO_T:
        raise ValueError(
            f"a ANOVA precisa de pelo menos {MINIMO_T} valores em cada grupo, e vieram "
            + ", ".join(str(n) for n in tamanhos)
        )
    return vetores


# Os testes de postos


def wilcoxon_uma_amostra(x: Sequence[float], mu: float) -> Resultado:
    """
    O `wilcox.test(x, mu = mu, conf.int = TRUE)` do R: o teste do posto sinalizado de
    Wilcoxon, bilateral, com a pseudomediana de Hodges-Lehmann e o intervalo de 95% dela.

        d = x − mu, sem os zeros            V = Σ postos de |d| onde d > 0

    Os valores iguais à referência saem antes de tudo, como no R: um zero não tem
    sinal. O p é exato — pela distribuição do posto sinalizado — com menos de
    `LIMITE_DO_EXATO` valores restantes, sem empate em |d| e sem zero; nos outros casos,
    a aproximação normal, com a variância corrigida para os empates e a correção de
    continuidade:

        z = [V − n(n + 1)/4 − ½ sinal(V − n(n + 1)/4)] / √[n(n + 1)(2n + 1)/24 − Σ(t³ − t)/48]

    **A estimativa e o intervalo.** No caminho exato, a mediana das médias de Walsh —
    (xᵢ + xⱼ)/2, com i ≤ j — e o intervalo entre duas delas, nas posições que o quantil
    da mesma distribuição dá. No aproximado, o valor que zera a estatística padronizada
    e os que a levam aos quantis da normal, achados como o R os acha: ver
    `_ic_assintotico_da_pseudomediana`. Os valores iguais à referência ficam de fora do
    intervalo também, como no R.

    Derivada do `wilcox.test.default`, em `src/library/stats/R/wilcox.test.R`, do R —
    (C) 1995-2019 The R Core Team, GPL-2.0-or-later. Origem, e os direitos autorais do
    original: ver o `NOTICE.md`.

    Raises:
        ValueError: nenhum valor, todos iguais à referência — onde o R devolve `NaN` —,
            valor ausente ou infinito, ou referência que não é um número finito.
    """
    import numpy as np
    from scipy import stats

    valores = _vetor(x)
    referencia = float(mu)
    if not math.isfinite(referencia):
        raise ValueError(f"a referência precisa ser um número finito, e veio {mu!r}")
    if valores.shape[0] < 1:
        raise ValueError("o Wilcoxon precisa de pelo menos 1 valor, e não veio nenhum")

    diferencas = valores - referencia
    zeros = bool((diferencas == 0).any())
    diferencas = diferencas[diferencas != 0]
    n = int(diferencas.shape[0])
    if n == 0:
        raise ValueError(
            "todos os valores são iguais à referência: não há posto a somar, e o R "
            "devolve NaN"
        )
    postos = _postos(np.abs(diferencas))
    estatistica = float(postos[diferencas > 0].sum())
    empates = _soma_dos_empates(postos) > 0
    exato = n < LIMITE_DO_EXATO and not empates and not zeros
    # O `x <- x + mu` do R: o intervalo é sobre os valores, e não sobre as diferenças —
    # refeitos pela mesma conta dele, e não lidos de novo do vetor original.
    restantes = diferencas + referencia

    if exato:
        contagens = _contagens_do_posto_sinalizado(n)
        total = 2**n
        p = _p_exato(contagens, total, estatistica, n * (n + 1) / 4)
        walsh = np.sort(np.add.outer(restantes, restantes)[np.triu_indices(n)]) / 2
        ic, confianca = _ic_exato(walsh, contagens, total, arredondar=True)
        estimativa: float | None = float(np.median(walsh))
        calculo = "exato"
    else:
        nucleo = estatistica - n * (n + 1) / 4
        sigma = math.sqrt(n * (n + 1) * (2 * n + 1) / 24 - _soma_dos_empates(postos) / 48)
        z = (nucleo - _sinal(nucleo) * 0.5) / sigma
        p = 2 * min(float(stats.norm.cdf(z)), float(stats.norm.sf(z)))
        ic, estimativa, confianca = _ic_assintotico_da_pseudomediana(restantes)
        motivos = [
            motivo
            for motivo, vale in (
                (f"{LIMITE_DO_EXATO} valores ou mais", n >= LIMITE_DO_EXATO),
                ("empates", empates),
                ("valores iguais à referência", zeros),
            )
            if vale
        ]
        calculo = f"{_APROXIMADO}, porque há {_em_frase(motivos)}"

    # Sem o `min(1.0, …)` dos outros testes: o teto de 1 já veio do `_p_exato`, como no
    # R, e a aproximação normal dobra uma cauda que não passa de ½.
    return Resultado(
        metodo=WILCOXON,
        estatistica=estatistica,
        nome_da_estatistica="V",
        p=p,
        calculo_do_p=calculo,
        estimativa=estimativa,
        nome_da_estimativa="pseudomediana",
        ic=ic,
        referencia=referencia,
        exato=exato,
        confianca_do_ic=confianca,
    )


def mann_whitney(x: Sequence[float], y: Sequence[float]) -> Resultado:
    """
    O `wilcox.test(x, y, conf.int = TRUE)` do R — que ele chama de teste da soma de
    postos de Wilcoxon, e que é o de Mann-Whitney —: bilateral, com a diferença de
    locação de Hodges-Lehmann e o intervalo de 95% dela.

        W = Σ postos de x − n₁(n₁ + 1)/2

    W é o U de Mann-Whitney do primeiro grupo, como o R o imprime: quantos pares
    (xᵢ, yⱼ) têm xᵢ > yⱼ, com meio ponto por empate. O p é exato — pela distribuição da
    soma dos postos — com menos de `LIMITE_DO_EXATO` valores em cada grupo e sem
    empate; nos outros casos, a aproximação normal, com a variância corrigida para os
    empates e a correção de continuidade:

        z = [W − n₁n₂/2 − ½ sinal(W − n₁n₂/2)] / σ
        σ² = n₁n₂/12 · [n₁ + n₂ + 1 − Σ(t³ − t) / ((n₁ + n₂)(n₁ + n₂ − 1))]

    **A estimativa e o intervalo.** No caminho exato, a mediana das n₁n₂ diferenças
    xᵢ − yⱼ e o intervalo entre duas delas, nas posições que o quantil da mesma
    distribuição dá; no aproximado, como o R os acha: ver
    `_ic_assintotico_da_diferenca`. **A diferença de locação não é a diferença das
    medianas** dos dois grupos: é a mediana das diferenças entre um valor de cada um, e
    estima o deslocamento de um grupo em relação ao outro quando as duas distribuições
    têm a mesma forma. A ordem dos dois vetores é a do sinal, como no t.

    Derivada do `wilcox.test.default`, em `src/library/stats/R/wilcox.test.R`, do R —
    (C) 1995-2019 The R Core Team, GPL-2.0-or-later. Origem: ver o `NOTICE.md`.

    Raises:
        ValueError: grupo vazio, ou valor ausente ou infinito.
    """
    import numpy as np
    from scipy import stats

    primeiro, segundo = _vetor(x), _vetor(y)
    n1, n2 = int(primeiro.shape[0]), int(segundo.shape[0])
    if n1 < 1 or n2 < 1:
        raise ValueError(
            f"o Mann-Whitney precisa de pelo menos 1 valor em cada grupo, e vieram {n1} "
            f"e {n2}"
        )
    postos = _postos(np.concatenate([primeiro, segundo]))
    estatistica = float(postos[:n1].sum()) - n1 * (n1 + 1) / 2
    empates = _soma_dos_empates(postos)
    exato = n1 < LIMITE_DO_EXATO and n2 < LIMITE_DO_EXATO and not empates

    if exato:
        contagens = _contagens_da_soma_dos_postos(min(n1, n2), max(n1, n2))
        total = math.comb(n1 + n2, n1)
        p = _p_exato(contagens, total, estatistica, n1 * n2 / 2)
        diferencas = np.sort(np.subtract.outer(primeiro, segundo).ravel())
        ic, confianca = _ic_exato(diferencas, contagens, total, arredondar=False)
        estimativa: float | None = float(np.median(diferencas))
        calculo = "exato"
    else:
        nucleo = estatistica - n1 * n2 / 2
        sigma = math.sqrt(
            (n1 * n2 / 12) * ((n1 + n2 + 1) - empates / ((n1 + n2) * (n1 + n2 - 1)))
        )
        z = (nucleo - _sinal(nucleo) * 0.5) / sigma
        p = 2 * min(float(stats.norm.cdf(z)), float(stats.norm.sf(z)))
        ic, estimativa, confianca = _ic_assintotico_da_diferenca(primeiro, segundo)
        motivos = [
            motivo
            for motivo, vale in (
                (
                    f"{LIMITE_DO_EXATO} valores ou mais num grupo",
                    max(n1, n2) >= LIMITE_DO_EXATO,
                ),
                ("empates", bool(empates)),
            )
            if vale
        ]
        calculo = f"{_APROXIMADO}, porque há {_em_frase(motivos)}"

    # O teto de 1, como no Wilcoxon, já veio do `_p_exato`.
    return Resultado(
        metodo=MANN_WHITNEY,
        estatistica=estatistica,
        nome_da_estatistica="W",
        p=p,
        calculo_do_p=calculo,
        estimativa=estimativa,
        nome_da_estimativa="diferença de locação",
        ic=ic,
        referencia=0.0,
        exato=exato,
        confianca_do_ic=confianca,
    )


def kruskal_wallis(grupos: Sequence[Sequence[float]]) -> Resultado:
    """
    O `kruskal.test` do R: os postos de todos os valores juntos, e

        H = [12 / (N(N + 1)) · Σ Rᵢ²/nᵢ − 3(N + 1)] / [1 − Σ(t³ − t)/(N³ − N)]

    com k − 1 graus de liberdade, pela cauda do qui-quadrado — o R não tem caminho
    exato. Rᵢ é a soma dos postos do grupo i, e o denominador é a correção para os
    empates. Pelo `scipy`, que faz o mesmo: é o primeiro degrau da régua do topo. Não
    estima nada, como a ANOVA: com k grupos não há uma diferença só.

    Raises:
        ValueError: menos de dois grupos, grupo vazio, todos os valores iguais — onde o
            R devolve `NaN` —, ou valor ausente ou infinito.
    """
    import numpy as np
    from scipy import stats

    vetores = [_vetor(grupo) for grupo in grupos]
    if len(vetores) < 2:
        raise ValueError(
            f"o Kruskal-Wallis precisa de pelo menos 2 grupos, e vieram {len(vetores)}"
        )
    tamanhos = [int(vetor.shape[0]) for vetor in vetores]
    if min(tamanhos) < 1:
        raise ValueError(
            "o Kruskal-Wallis precisa de pelo menos 1 valor em cada grupo, e vieram "
            + ", ".join(str(n) for n in tamanhos)
        )
    juntos = np.concatenate(vetores)
    if float(juntos.min()) == float(juntos.max()):
        raise ValueError(
            "todos os valores são iguais: o qui-quadrado de Kruskal-Wallis é 0/0, e o R "
            "devolve NaN"
        )
    resultado = stats.kruskal(*vetores)
    return Resultado(
        metodo=KRUSKAL_WALLIS,
        estatistica=float(resultado.statistic),
        nome_da_estatistica="χ²",
        p=min(1.0, float(resultado.pvalue)),
        gl=(float(len(vetores) - 1),),
        calculo_do_p=_QUI_QUADRADO,
    )


def friedman(medidas: Sequence[Sequence[float]]) -> Resultado:
    """
    O `friedman.test` do R — as mesmas pessoas medidas k vezes, sem a normal: em cada
    caso, os postos das k medidas; Rⱼ a soma dos postos da medida j, e

        χ² = 12 Σ [Rⱼ − n(k + 1)/2]² / [n k (k + 1) − Σ(t³ − t)/(k − 1)]

    com k − 1 graus de liberdade, pela cauda do qui-quadrado, como no R. Os empates
    são os de dentro de cada caso.

    **Escrita, e não importada**, pela razão da ANOVA: o `friedmanchisquare` do `scipy`
    dá o mesmo qui-quadrado, mas recusa duas medidas, que o R aceita — e a função daqui
    é o `friedman.test`. Do `scipy` vêm só os postos e a cauda; o `friedmanchisquare`
    fica nos testes, como conferência. A fórmula é a do `friedman.test`, em
    `src/library/stats/R/friedman.test.R`, do R — (C) 1995-2015 The R Core Team,
    GPL-2.0-or-later. Origem: ver o `NOTICE.md`.

    `medidas` são as k colunas, cada uma com os mesmos n casos, na mesma ordem: quem
    chama tira antes os casos com alguma medida faltando, como o `complete.cases` do R.

    O mínimo é o do R: dois casos com todas as medidas. Com um caso só, o
    `friedman.test` para com erro — a seleção dos casos completos tira a dimensão da
    matriz de uma linha, e o `apply` não tem sobre o que andar.

    Raises:
        ValueError: menos de duas medidas, medidas de tamanhos diferentes, menos de dois
            casos, cada caso com o mesmo valor em todas as medidas — onde o R devolve
            `NaN` —, ou valor ausente ou infinito.
    """
    from scipy import stats

    matriz = _matriz_das_medidas(medidas, teste="o Friedman")
    if medidas_iguais_em_cada_caso(matriz):
        raise ValueError(
            "cada caso tem o mesmo valor em todas as medidas: não há o que ordenar, e o "
            "qui-quadrado de Friedman é 0/0 — o R devolve NaN"
        )
    n, k = matriz.shape
    postos = stats.rankdata(matriz, axis=1)
    empates = sum(_soma_dos_empates(linha) for linha in postos)
    somas = postos.sum(axis=0)
    estatistica = (12 * float(((somas - n * (k + 1) / 2) ** 2).sum())) / (
        n * k * (k + 1) - empates / (k - 1)
    )
    return Resultado(
        metodo=FRIEDMAN,
        estatistica=estatistica,
        nome_da_estatistica="χ²",
        p=min(1.0, float(stats.chi2.sf(estatistica, k - 1))),
        gl=(float(k - 1),),
        calculo_do_p=_QUI_QUADRADO,
    )


def medidas_iguais_em_cada_caso(medidas: Any) -> bool:
    """
    Cada caso tem o mesmo valor em todas as medidas — e não há o que ordenar dentro de
    caso nenhum.

    É a barreira do Friedman, e não a mesma da ANOVA de medidas repetidas
    (`sem_variacao_entre_medidas`): cada caso mudando o mesmo tanto de uma medida para
    outra deixa a ANOVA sem variação de erro, e dá ao Friedman os mesmos postos em todo
    caso — o qui-quadrado mais alto que ele tem, e não uma divisão por zero. Aqui é o
    contrário: o denominador do Friedman é zero quando todo caso está empatado inteiro,
    e o R devolve `NaN`.

    Recebe as colunas, ou a matriz n × k já montada.
    """
    matriz = _matriz_das_medidas(medidas, conferir=False)
    return bool((matriz.max(axis=1) == matriz.min(axis=1)).all())


# A frase do cálculo do p dos testes de postos: o caminho, como a frase da tabela o diz
# — `p exato`, `p aproximado pela normal, …`.
_APROXIMADO = "aproximado pela normal, com correção de continuidade"
_QUI_QUADRADO = (
    "qui-quadrado com k − 1 graus de liberdade, com a correção para empates"
)


def _ic_exato(
    ordenadas: Any, contagens: Sequence[int], total: int, arredondar: bool
) -> tuple[tuple[float, float], float]:
    """
    O intervalo exato do `wilcox.test`: entre dois valores de `ordenadas` — as médias de
    Walsh na uma amostra, as diferenças entre os grupos no Mann-Whitney —, nas posições
    que o quantil da distribuição exata dá, e o nível dele.

    A posição de baixo é o `qsignrank(α/2, n)` — ou o `qwilcox` —, e a de cima, a que
    sobra do outro lado. Com poucos valores, nem o intervalo mais largo, do menor ao
    maior, chega a 95%: o R fica com ele e baixa o nível, avisando, quando o α que ele
    alcança passa de 1,5 α. `arredondar` é a diferença entre os dois ramos do R: a uma
    amostra escreve o nível com o α em dois algarismos significativos (`signif`), e o
    Mann-Whitney, com o α inteiro.
    """
    alfa = 1 - CONFIANCA
    baixo = _quantil(contagens, total, alfa / 2)
    if baixo == 0:
        baixo = 1
    alto = (len(contagens) - 1) - baixo
    alcancado = 2 * _probabilidade(contagens, total, ate=baixo - 1)
    confianca = CONFIANCA
    if alcancado - alfa > alfa / 2:
        confianca = 1 - (float(f"{alcancado:.2g}") if arredondar else alcancado)
    return (float(ordenadas[baixo - 1]), float(ordenadas[alto])), confianca


def _ic_assintotico_da_pseudomediana(
    x: Any,
) -> tuple[tuple[float, float] | None, float | None, float | None]:
    """
    O intervalo e a estimativa da uma amostra no caminho aproximado, como o
    `wilcox.test` os acha — o algoritmo que o próprio R diz não estar publicado, e por
    isso documenta no código.

    A estatística padronizada de `x − d` cai à medida que `d` cresce, em degraus. O
    limite de baixo é o `d` em que ela cruza o quantil de cima da normal, e o de cima, o
    `d` em que cruza o de baixo; a estimativa, o `d` em que ela cruza o zero — sem a
    correção de continuidade. Os três são achados pelo `uniroot` do R, entre o menor e o
    maior valor (`_raiz`). Quando nem nos extremos a estatística alcança os quantis, o R
    dobra o α até alcançar, e baixa o nível do intervalo.

    Devolve o intervalo, a estimativa e o nível; os três `None` quando os valores — sem
    os iguais à referência — são todos iguais: não há degrau a cruzar, e o R devolve
    `NaN` no intervalo e o ponto médio dos valores no lugar da pseudomediana, que aqui
    não se imprime com o nome de outra coisa.
    """
    import numpy as np
    from scipy import stats

    def padronizada(d: float, correcao: bool = True) -> float:
        deslocadas = x - d
        deslocadas = deslocadas[deslocadas != 0]
        nx = int(deslocadas.shape[0])
        postos = _postos(np.abs(deslocadas))
        nucleo = float(postos[deslocadas > 0].sum()) - nx * (nx + 1) / 4
        sigma = math.sqrt(
            nx * (nx + 1) * (2 * nx + 1) / 24 - _soma_dos_empates(postos) / 48
        )
        if sigma == 0:
            # Só quando não sobra valor nenhum — o desvio é pelo menos √(n(n + 1)²/16),
            # com todos empatados. O núcleo é zero também, e o R devolve o NaN de 0/0.
            return math.nan
        ajuste = _sinal(nucleo) * 0.5 if correcao else 0.0
        return (nucleo - ajuste) / sigma

    menor, maior = float(x.min()), float(x.max())
    no_menor = padronizada(menor)
    no_maior = padronizada(maior) if math.isfinite(no_menor) else math.nan
    if not math.isfinite(no_maior):
        return None, None, None

    alfa = 1 - CONFIANCA
    while (
        no_menor - float(stats.norm.isf(alfa / 2)) < 0
        or no_maior - float(stats.norm.ppf(alfa / 2)) > 0
    ):
        alfa *= 2
    confianca = CONFIANCA
    if alfa >= 1 or 1 - CONFIANCA < alfa * 0.75:
        confianca = 1 - min(1.0, alfa)
    if alfa < 1:
        limites = []
        for quantil in (float(stats.norm.isf(alfa / 2)), float(stats.norm.ppf(alfa / 2))):
            limites.append(
                _raiz(
                    lambda d, q=quantil: padronizada(d) - q,
                    menor,
                    maior,
                    no_menor - quantil,
                    no_maior - quantil,
                )
            )
        ic = (limites[0], limites[1])
    else:
        mediana = float(np.median(x))
        ic = (mediana, mediana)
    estimativa = _raiz(
        lambda d: padronizada(d, correcao=False),
        menor,
        maior,
        padronizada(menor, correcao=False),
        padronizada(maior, correcao=False),
    )
    return ic, estimativa, confianca


def _ic_assintotico_da_diferenca(
    x: Any, y: Any
) -> tuple[tuple[float, float] | None, float | None, float | None]:
    """
    O intervalo e a estimativa do Mann-Whitney no caminho aproximado, como o
    `wilcox.test` os acha: a estatística padronizada dos postos de `x − d` contra `y`,
    e os `d` em que ela cruza os quantis da normal e — sem a correção de continuidade —
    o zero, entre a menor e a maior diferença possível. Quando nem no extremo ela
    alcança o quantil, o limite é o próprio extremo, como no R; aqui o nível não baixa.

    Devolve os três `None` quando os dois grupos não variam por dentro: todo valor de
    um empata com todo valor do outro num dos extremos, a estatística é 0/0, e o R para
    com erro.
    """
    import numpy as np
    from scipy import stats

    n1, n2 = int(x.shape[0]), int(y.shape[0])

    def padronizada(d: float, correcao: bool = True) -> float:
        postos = _postos(np.concatenate([x - d, y]))
        nucleo = float(postos[:n1].sum()) - n1 * (n1 + 1) / 2 - n1 * n2 / 2
        ajuste = _sinal(nucleo) * 0.5 if correcao else 0.0
        sigma = math.sqrt(
            (n1 * n2 / 12)
            * ((n1 + n2 + 1) - _soma_dos_empates(postos) / ((n1 + n2) * (n1 + n2 - 1)))
        )
        if sigma == 0:
            # Só quando todos os valores empatam: cada posto é (N + 1)/2, o núcleo é zero
            # também, e o R devolve o NaN de 0/0.
            return math.nan
        return (nucleo - ajuste) / sigma

    menor = float(x.min() - y.max())
    maior = float(x.max() - y.min())
    no_menor, no_maior = padronizada(menor), padronizada(maior)
    if not (math.isfinite(no_menor) and math.isfinite(no_maior)):
        return None, None, None

    def limite(quantil: float) -> float:
        if no_menor - quantil <= 0:
            return menor
        if no_maior - quantil >= 0:
            return maior
        return _raiz(
            lambda d: padronizada(d) - quantil,
            menor,
            maior,
            no_menor - quantil,
            no_maior - quantil,
        )

    alfa = 1 - CONFIANCA
    ic = (limite(float(stats.norm.isf(alfa / 2))), limite(float(stats.norm.ppf(alfa / 2))))
    estimativa = _raiz(
        lambda d: padronizada(d, correcao=False),
        menor,
        maior,
        padronizada(menor, correcao=False),
        padronizada(maior, correcao=False),
    )
    return ic, estimativa, CONFIANCA


def _raiz(
    funcao: Callable[[float], float],
    a: float,
    b: float,
    fa: float,
    fb: float,
    tolerancia: float = TOLERANCIA_DA_RAIZ,
    iteracoes: int = MAXIMO_DE_ITERACOES,
) -> float:
    """
    O `uniroot(f, lower = a, upper = b, f.lower = fa, f.upper = fb, tol = 1e-4)$root` do
    R: o método de Brent — bisseção, com interpolação linear ou quadrática inversa
    quando ela cai dentro do intervalo —, como o `R_zeroin2` o escreve.

    **Transcrito linha a linha**, e não trocado pelo `brentq` do `scipy`, que é o mesmo
    método com outros passos: a função aqui é uma escada — a estatística dos postos só
    muda quando `d` cruza uma média de Walsh ou uma diferença entre os grupos —, a raiz
    está num degrau, e a tolerância de 1e-4 deixa o ponto devolvido em qualquer lugar a
    até 1e-4 dele. Com outros passos, o número sai outro, e a segunda casa do intervalo
    pode virar quando o degrau cai num `,xx5`. Com os mesmos, sai o do R.

    A função é finita em todo o intervalo, e só por isso o `fcn2` e o `truncate` do
    `uniroot` — que trocam o ±∞ e o `NaN` pelo maior `double` — não estão aqui: a
    estatística padronizada só deixa de ser finita nos casos degenerados, sem valor que
    não empate, e quem chama sai antes da busca.

    Transcrito do `R_zeroin2`, em `src/library/stats/src/zeroin.c`, do R — (C)
    1999-2016 The R Core Team, GPL-2.0-or-later, a partir do `zeroin` do NETLIB
    (`c/brent.shar`), com o número máximo de iterações de Peter Dalgaard. Algoritmo de
    G. Forsythe, M. Malcolm e C. Moler, *Computer methods for mathematical
    computations* (1977). Origem: ver o `NOTICE.md`.
    """
    epsilon = sys.float_info.epsilon
    c, fc = a, fa
    if fa == 0.0:
        return a
    if fb == 0.0:
        return b

    for _ in range(iteracoes + 1):
        passo_anterior = b - a
        if abs(fc) < abs(fb):
            a, b, c = b, c, b
            fa, fb, fc = fb, fc, fb
        tolerancia_atual = 2 * epsilon * abs(b) + tolerancia / 2
        passo = (c - b) / 2

        if abs(passo) <= tolerancia_atual or fb == 0.0:
            return b

        if abs(passo_anterior) >= tolerancia_atual and abs(fa) > abs(fb):
            cb = c - b
            if a == c:
                t1 = fb / fa
                p = cb * t1
                q = 1.0 - t1
            else:
                q = fa / fc
                t1 = fb / fc
                t2 = fb / fa
                p = t2 * (cb * q * (q - t1) - (b - a) * (t1 - 1.0))
                q = (q - 1.0) * (t1 - 1.0) * (t2 - 1.0)
            if p > 0:
                q = -q
            else:
                p = -p
            if p < (0.75 * cb * q - abs(tolerancia_atual * q) / 2) and p < abs(
                passo_anterior * q / 2
            ):
                passo = p / q

        if abs(passo) < tolerancia_atual:
            passo = tolerancia_atual if passo > 0 else -tolerancia_atual
        a, fa = b, fb
        b += passo
        fb = funcao(b)
        if (fb > 0 and fc > 0) or (fb < 0 and fc < 0):
            c, fc = a, fa
    return b


@cache
def _contagens_do_posto_sinalizado(n: int) -> tuple[int, ...]:
    """
    De quantas das 2ⁿ atribuições de sinal sai cada soma V = 0, 1, …, n(n + 1)/2 — a
    distribuição exata do posto sinalizado, em inteiros: quantos subconjuntos de
    {1, …, n} somam cada valor. É o `csignrank` do R, que guarda as mesmas contagens em
    `double`.
    """
    total = n * (n + 1) // 2
    contagens = [1] + [0] * total
    for j in range(1, n + 1):
        for soma in range(min(j * (j + 1) // 2, total), j - 1, -1):
            contagens[soma] += contagens[soma - j]
    return tuple(contagens)


@cache
def _contagens_da_soma_dos_postos(m: int, n: int) -> tuple[int, ...]:
    """
    De quantas das C(m + n, m) maneiras de escolher os postos do primeiro grupo sai cada
    W = 0, 1, …, m·n — a distribuição exata da estatística de Mann-Whitney, em
    inteiros. São os coeficientes do binômio gaussiano [m + n, m], pelo produto

        Π (1 − q^(n + i)) / (1 − q^i),  i = 1, …, m

    multiplicando e dividindo como séries de potências — exato, porque o resultado é
    um polinômio de grau m·n. É o `cwilcox` do R, que guarda as contagens em `double`,
    pela recursão de Mann e Whitney. A distribuição é a mesma com os grupos trocados, e
    quem chama passa o menor primeiro.
    """
    total = m * n
    contagens = [1] + [0] * total
    for i in range(1, m + 1):
        salto = n + i
        for k in range(total, salto - 1, -1):
            contagens[k] -= contagens[k - salto]
        for k in range(i, total + 1):
            contagens[k] += contagens[k - i]
    return tuple(contagens)


def _p_exato(
    contagens: Sequence[int], total: int, estatistica: float, centro: float
) -> float:
    """
    O p bilateral exato do `wilcox.test`: a cauda do lado em que a estatística está —
    P(S ≥ s) acima do centro da distribuição, P(S ≤ s) até ele —, dobrada, e nunca
    acima de 1. Sem empates a estatística é inteira.
    """
    s = round(estatistica)
    if estatistica > centro:
        p = _probabilidade(contagens, total, de=s)
    else:
        p = _probabilidade(contagens, total, ate=s)
    return min(1.0, 2 * p)


def _probabilidade(
    contagens: Sequence[int], total: int, de: int = 0, ate: int | None = None
) -> float:
    """
    P(de ≤ S ≤ ate), em frações exatas, e um `float` só no fim: as contagens são
    inteiras, e a soma delas sobre o total não erra casa nenhuma.
    """
    ultimo = len(contagens) - 1
    ate = ultimo if ate is None else min(ate, ultimo)
    de = max(de, 0)
    if ate < de:
        return 0.0
    return float(Fraction(sum(contagens[de : ate + 1]), total))


def _quantil(contagens: Sequence[int], total: int, probabilidade: float) -> int:
    """
    O menor q com P(S ≤ q) ≥ `probabilidade` — o `qsignrank` e o `qwilcox` do R, com a
    folga de dez épsilons que os dois dão à probabilidade, no ramo de até ½, que é o
    único que o intervalo usa. A conta da acumulada é exata; a folga é a do R, para o
    quantil ser o dele também no caso em que a acumulada cai em cima do alvo.

    A busca é a do `qsignrank`, em `src/nmath/signrank.c`, e a do `qwilcox`, em
    `src/nmath/wilcox.c`, do R — (C) 1999-2014 The R Core Team, GPL-2.0-or-later.
    Origem: ver o `NOTICE.md`.
    """
    alvo = probabilidade - 10 * sys.float_info.epsilon
    acumulado = 0
    for q, contagem in enumerate(contagens):
        acumulado += contagem
        if Fraction(acumulado, total) >= alvo:
            return q
    return len(contagens) - 1


def _postos(valores: Any) -> Any:
    """
    Os postos, com o posto médio nos empates — o `rank` do R, pelo `rankdata` do
    `scipy`, que dá os mesmos números.
    """
    from scipy import stats

    return stats.rankdata(valores)


def _soma_dos_empates(postos: Any) -> int:
    """
    Σ (t³ − t) sobre os grupos de postos iguais — o `sum(NTIES^3 - NTIES)` do R, com o
    `table(r)` dele: t é quantos valores empatam em cada posto. Zero sem empate.
    """
    import numpy as np

    _, contagens = np.unique(postos, return_counts=True)
    return sum(int(t) ** 3 - int(t) for t in contagens)


def _sinal(valor: float) -> float:
    """O `sign` do R: −1, 0 ou 1."""
    return float((valor > 0) - (valor < 0))


def _em_frase(itens: Sequence[str]) -> str:
    """`A`, `A e B`, `A, B e C`."""
    lista = list(itens)
    if len(lista) <= 1:
        return "".join(lista)
    return ", ".join(lista[:-1]) + " e " + lista[-1]


def sem_variacao(x: Sequence[float]) -> bool:
    """
    Os valores não variam — o `data are essentially constant` do `t.test`.

    O critério é o do R, e não "todos iguais": o erro-padrão abaixo de dez vezes o
    épsilon da máquina vezes a média. Todos iguais é o caso de todo dia, e fica
    dentro dele; o que ele acrescenta é o vetor que varia só no último bit, onde o
    t sairia um número enorme e sem sentido. Pública porque o `comparacao.py` faz a
    mesma pergunta antes de chamar o teste, para a linha sair com o motivo escrito
    em vez de um `ValueError`.
    """
    valores = _vetor(x)
    n = valores.shape[0]
    if n < MINIMO_T:
        return False
    media = float(valores.mean())
    erro_padrao = float(valores.std(ddof=1)) / math.sqrt(n)
    return erro_padrao == 0 or erro_padrao < 10 * sys.float_info.epsilon * abs(media)


def sem_variacao_em_duas(
    x: Sequence[float], y: Sequence[float], variancias_iguais: bool = True
) -> bool:
    """
    Os valores dos dois grupos não variam — o `data are essentially constant` do
    `t.test` de duas amostras.

    O critério é o do R: o erro-padrão da diferença abaixo de dez épsilons vezes a
    maior das duas médias em valor absoluto. O erro-padrão é o do teste — com a
    variância combinada no de Student, com a soma das duas no de Welch —, e por isso
    a pergunta leva o teste junto. Dois grupos que não variam por dentro, cada um com
    o seu valor, param aqui mesmo com médias diferentes: o R recusa esse t, e não o
    devolve infinito.

    Com menos valores do que o teste exige, devolve `False`: a barreira do tamanho
    vem antes, com a frase dela.
    """
    primeiro, segundo = _vetor(x), _vetor(y)
    n1, n2 = primeiro.shape[0], segundo.shape[0]
    if variancias_iguais:
        if n1 < 1 or n2 < 1 or n1 + n2 < MINIMO_STUDENT:
            return False
        soma = 0.0
        if n1 > 1:
            soma += (n1 - 1) * float(primeiro.var(ddof=1))
        if n2 > 1:
            soma += (n2 - 1) * float(segundo.var(ddof=1))
        erro_padrao = math.sqrt(soma / (n1 + n2 - 2) * (1 / n1 + 1 / n2))
    else:
        if n1 < MINIMO_T or n2 < MINIMO_T:
            return False
        erro_padrao = math.sqrt(
            float(primeiro.var(ddof=1)) / n1 + float(segundo.var(ddof=1)) / n2
        )
    maior = max(abs(float(primeiro.mean())), abs(float(segundo.mean())))
    return erro_padrao == 0 or erro_padrao < 10 * sys.float_info.epsilon * maior


@contextmanager
def _sem_o_aviso_de_precisao() -> Iterator[None]:
    """
    Cala o «Precision loss occurred in moment calculation» do `scipy` — e só ele.

    O `scipy` o emite quando um grupo não varia, e ali a conta está certa: a variância
    de um grupo constante é zero de verdade, e o t sai igual ao do R, conferido. O caso
    em que o aviso diria a verdade — valores que variam só no último bit — para antes,
    na barreira do R (`sem_variacao_em_duas`). Solto, ele iria para o `stderr` no meio
    da saída do comando, que é o recado que o usuário aprende a ignorar; é a manobra do
    `normalidade.shapiro`, com o filtro pela mensagem.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="Precision loss occurred", category=RuntimeWarning
        )
        yield


def _vetor(x: Sequence[float]):
    """
    O vetor como `float64`, com as duas condições que nenhum teste daqui aceita.

    Valor ausente não chega aqui pelo caminho da análise — os faltantes saem antes,
    por variável —, e um `nan` que chegasse viraria um t `nan` sem aviso nenhum.
    """
    import numpy as np

    valores = np.asarray(x, dtype="float64")
    if valores.ndim != 1:
        raise ValueError("os valores precisam ser um vetor")
    if not bool(np.isfinite(valores).all()):
        raise ValueError("há valor ausente ou infinito no vetor")
    return valores


__all__ = [
    "CONFIANCA",
    "LIMITE_DO_EXATO",
    "MAXIMO_DE_ITERACOES",
    "MINIMO_STUDENT",
    "MINIMO_T",
    "TOLERANCIA_DA_RAIZ",
    "ANOVA",
    "ANOVA_DE_MEDIDAS_REPETIDAS",
    "ANOVA_DE_WELCH",
    "FRIEDMAN",
    "KRUSKAL_WALLIS",
    "MANN_WHITNEY",
    "T_DE_STUDENT",
    "T_DE_WELCH",
    "WILCOXON",
    "Resultado",
    "anova_de_medidas_repetidas",
    "anova_de_um_fator",
    "anova_de_welch",
    "friedman",
    "kruskal_wallis",
    "mann_whitney",
    "medidas_iguais_em_cada_caso",
    "sem_variacao",
    "sem_variacao_em_duas",
    "sem_variacao_entre_medidas",
    "sem_variacao_nos_grupos",
    "t_de_student",
    "t_de_welch",
    "t_uma_amostra",
    "wilcoxon_uma_amostra",
]
