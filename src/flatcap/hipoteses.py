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

`t.test`, `wilcox.test`, `oneway.test` e `kruskal.test` devolvem o mesmo objeto —
`statistic`, `parameter`, `p.value`, `conf.int`, `estimate`, `null.value` e
`method` —, e é por isso que ele serve de contrato para todos os testes de
comparação. Os campos do `Resultado` são esses, com os nomes da casa. O
`Coeficiente` da correlação já era quase ele.

**Sempre bilateral.** Como na correlação: um teste unilateral escolhido depois de
olhar os dados é o p dividido por dois, e a ficha não tem como dizer que a direção
foi decidida antes.

## Quando importar, e quando escrever

A régua é a que a Fase 7 aprendeu teste a teste, em três degraus:

1. **o `scipy` faz o que o R faz** → importar. É o caso do t: `ttest_1samp`,
   `ttest_ind` e o `confidence_interval()` deles dão o t, os graus de liberdade, o p e
   o intervalo do `t.test`, conferidos até a décima quarta casa — no de duas amostras,
   inclusive com um grupo de um valor só. O `f_oneway` dá o F e o p do `oneway.test`,
   mas não os graus de liberdade, e a ANOVA desce um degrau: ver `anova_de_um_fator`;
2. **o `scipy` calcula igual e escolhe diferente** → escrever a escolha do R e
   importar a conta. É o caso do Wilcoxon e do Mann-Whitney, que vêm depois: o R usa
   o p exato só com menos de 50 casos, sem empate e sem zero, e a aproximação normal
   com correção de continuidade nos outros casos; o `scipy` decide o exato por outro
   critério e não corrige;
3. **nem isso basta** → transcrever a aritmética do R, como o AS 89 do Spearman e o
   algoritmo de rede do Fisher.

## O que ele recusa

Com `ValueError`, e só o que o próprio R recusa: menos de dois valores (`not enough
'x' observations`), valores que não variam (`data are essentially constant`), e
valor ausente ou infinito no vetor. No t de Student de duas amostras, o mínimo é o do
R para ele: um valor em cada grupo e três no total (`not enough observations`); no de
Welch, dois em cada grupo (`not enough 'x' observations`), porque cada grupo entra com
a sua variância, e a de um valor só não existe; na ANOVA — as duas —, dois em cada grupo
também, que é o `not enough observations` do `oneway.test`. Quem
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
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

# O nível do intervalo. O mesmo 95% da correlação e do `conf.level` padrão do R.
CONFIANCA = 0.95

# O menor número de valores com que o `t.test` do R calcula o t de uma amostra.
MINIMO_T = 2

# O menor número de valores, somados os dois grupos, com que o `t.test` do R calcula o
# t de Student de duas amostras: um em cada grupo, e um grau de liberdade que sobre.
MINIMO_STUDENT = 3

# O nome de cada teste, como ele vai para a coluna `teste` da tabela. É o `method`
# do `htest`, em português.
T_DE_STUDENT = "t de Student"
T_DE_WELCH = "t de Welch"
ANOVA = "ANOVA"
ANOVA_DE_WELCH = "ANOVA de Welch"


@dataclass(frozen=True)
class Resultado:
    """
    O que um teste de hipótese devolve — o `htest` do R, com os nomes da casa.

    `estatistica` é a do R, com o nome dela em `nome_da_estatistica`: t no t de
    Student, V no Wilcoxon, W no Mann-Whitney, F na ANOVA, o qui-quadrado de
    Kruskal-Wallis. `gl` é uma tupla porque o número de graus de liberdade muda de
    teste para teste: `(14.0,)` no t, fracionário no de Welch, `(2.0, 25.0)` na
    ANOVA, vazio nos testes de postos. `calculo_do_p` diz em palavras como o p saiu,
    porque nos testes de postos são dois caminhos conforme o n e os empates.

    `estimativa` é o que o teste estima — a média, a diferença de médias, a
    pseudomediana —, com o nome em `nome_da_estimativa`; `ic` é o intervalo dela,
    como o `conf.int` do R; `referencia` é o `mu` da hipótese nula.
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
    "MINIMO_STUDENT",
    "MINIMO_T",
    "ANOVA",
    "ANOVA_DE_WELCH",
    "T_DE_STUDENT",
    "T_DE_WELCH",
    "Resultado",
    "anova_de_um_fator",
    "anova_de_welch",
    "sem_variacao",
    "sem_variacao_em_duas",
    "sem_variacao_nos_grupos",
    "t_de_student",
    "t_de_welch",
    "t_uma_amostra",
]
