# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
A aritmética da amostragem — o z, o tamanho e a perda —, como números.

É a fronteira do `hipoteses.py` com o `comparacao.py`, aplicada à amostra. Este módulo
recebe números e devolve números; quem lê o `desenho.yaml`, converte os percentuais, monta a
tabela e escreve o relatório da amostra é o `amostragem.py`. Três consequências:

* **só biblioteca padrão** — `math` e `statistics`. Sem `pandas`, `numpy` nem `scipy`: o
  comando da amostragem parte rápido, e o `test_amostral.py` confere as contas sem projeto,
  ficha nem banco;
* **frações, e não percentuais** — 0,95, 0,05, 0,5. O `95` é como o cliente fala e como a
  ficha se escreve; a conversão é de quem lê a ficha, e uma conta que aceitasse as duas
  formas teria de adivinhar qual veio;
* **nenhuma formatação** — o 278 sai daqui como `int`, e a forma dele na tabela é decisão de
  quem escreve a tabela.

## A conta

Para estimar uma proporção, com V = p(1 − p); para estimar uma média, com V = σ²:

    n₀ = z²·V / e²                            população grande, sem correção
    n  = N·z²·V / [(N − 1)·e² + z²·V]          com a população N

A segunda é o n₀ corrigido pela população, na forma que o OpenEpi usa, e é igual a
`n₀ / [1 + (n₀ − 1)/N]`. A perda esperada entra por último — `⌈n / (1 − perda)⌉` —, e o
resultado nunca passa de N: uma amostra do tamanho da população é um censo.

## Por que `NormalDist`, e não o `scipy`

O z é o quantil bilateral da normal, o `qnorm(1 − α/2)` do R. O `statistics.NormalDist` da
biblioteca padrão implementa o mesmo algoritmo do `qnorm` — o AS241 de Wichura (1988) —, e
trazer o `scipy` só para um quantil faria o comando pagar a partida dele por nada.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

# A folga do arredondamento para cima. Ver `para_cima`.
TOLERANCIA = 1e-9


@dataclass(frozen=True)
class Tamanho:
    """
    O tamanho da amostra, e como ele saiu.

    `n` é o tamanho que dá a precisão pedida — corrigido pela população quando há uma —, e
    `n_final` é o que vai a campo: com a perda somada e no máximo N. Os dois já arredondados
    para cima. `n0` e `n_corrigido` guardam as contas sem arredondar, para o manifesto.

    No tamanho escrito à mão (`tamanho_decidido`) não há conta: `z`, `n0` e `n_corrigido`
    ficam `None`, e `n` é o que foi escrito.
    """

    n: int
    n_final: int
    populacao: int | None = None
    perda: float = 0.0
    z: float | None = None
    n0: float | None = None
    n_corrigido: float | None = None

    @property
    def censo(self) -> bool:
        """A amostra é a população inteira."""
        return self.populacao is not None and self.n_final >= self.populacao

    @property
    def decidido(self) -> bool:
        """O tamanho foi escrito à mão, e não calculado."""
        return self.n0 is None


def z_da_confianca(confianca: float) -> float:
    """
    O quantil bilateral da normal padrão: o `qnorm(1 − (1 − confianca)/2)` do R.

    `confianca` é uma fração, entre 0 e 1 sem as pontas: 0,95 dá 1,959964.
    """
    if not 0 < confianca < 1:
        raise ValueError(f"a confiança é uma fração entre 0 e 1, e veio {confianca}")
    return NormalDist().inv_cdf(1 - (1 - confianca) / 2)


def variancia_da_proporcao(proporcao: float) -> float:
    """
    O p(1 − p) da conta de uma proporção: 0,25 com p = 0,5, que é o maior possível.

    Por isso 50% é o valor de quem não sabe o que esperar — é o que dá o maior tamanho.
    """
    if not 0 < proporcao < 1:
        raise ValueError(f"a proporção é uma fração entre 0 e 1, e veio {proporcao}")
    return proporcao * (1 - proporcao)


def para_cima(valor: float) -> int:
    """
    Arredonda para cima, sem que o resto de ponto flutuante vire uma unidade a mais.

    Um tamanho de amostra se arredonda sempre para cima: 277,1 pessoas não dão a precisão
    pedida, e 278 dão. Mas uma conta que devia dar 278 exatos pode chegar como
    278,00000000000006, e o `math.ceil` cru faria dela 279. A folga de 1e-9 está muito abaixo
    de qualquer diferença que importe numa contagem de pessoas, e muito acima do resto de
    ponto flutuante de uma conta destas.
    """
    return math.ceil(valor - TOLERANCIA)


def com_perda(n: int, perda: float) -> int:
    """
    O tamanho que vai a campo para que, perdida a fração `perda`, sobrem `n`.

    `⌈n / (1 − perda)⌉`: com perda de 10%, 292 viram 325 — e 325 × 0,9 = 292,5.
    """
    if not 0 <= perda < 1:
        raise ValueError(f"a perda é uma fração entre 0 e 1, sem o 1, e veio {perda}")
    if perda == 0:
        return n
    return para_cima(n / (1 - perda))


def tamanho_aas(
    *,
    confianca: float,
    margem: float,
    variancia: float,
    populacao: int | None = None,
    perda: float = 0.0,
) -> Tamanho:
    """
    O tamanho da amostra aleatória simples, sem reposição.

    Args:
        confianca: o nível de confiança, em fração — 0,95.
        margem: a margem de erro, na escala da estimativa: 0,05 (5 pontos percentuais) para
            uma proporção; na unidade da variável para uma média.
        variancia: p(1 − p) para uma proporção (`variancia_da_proporcao`); σ² para uma
            média.
        populacao: o N; `None` é a população grande, sem correção.
        perda: a fração que se espera perder, de 0 a 1 sem o 1.

    Raises:
        ValueError: um valor fora do domínio. Quem chega aqui pelo `amostragem.py` já passou
            pelas recusas da ficha, com a frase de cada uma.
    """
    if margem <= 0:
        raise ValueError(f"a margem de erro precisa ser positiva, e veio {margem}")
    if variancia <= 0:
        raise ValueError(f"a variância precisa ser positiva, e veio {variancia}")
    _conferir_populacao(populacao)

    z = z_da_confianca(confianca)
    termo = z * z * variancia
    n0 = termo / (margem * margem)
    corrigido = None
    if populacao is not None:
        corrigido = populacao * termo / ((populacao - 1) * margem * margem + termo)
    n = para_cima(corrigido if corrigido is not None else n0)
    return _fechar(n, populacao, perda, z=z, n0=n0, n_corrigido=corrigido)


def tamanho_decidido(n: int, *, populacao: int | None = None, perda: float = 0.0) -> Tamanho:
    """
    O tamanho escrito à mão, no lugar da conta, com a perda somada a ele.

    A perda soma porque o `n` escrito é o tamanho necessário — o que precisa sobrar no fim —,
    como na conta. Quem quer o número que vai a campo escreve a perda zero.
    """
    if n < 1:
        raise ValueError(f"o tamanho precisa ser pelo menos 1, e veio {n}")
    _conferir_populacao(populacao)
    if populacao is not None and n > populacao:
        raise ValueError(f"o tamanho {n} passa da população, {populacao}")
    return _fechar(n, populacao, perda)


def _conferir_populacao(populacao: int | None) -> None:
    if populacao is not None and populacao < 1:
        raise ValueError(f"a população precisa ter pelo menos uma unidade, e veio {populacao}")


def _fechar(
    n: int,
    populacao: int | None,
    perda: float,
    *,
    z: float | None = None,
    n0: float | None = None,
    n_corrigido: float | None = None,
) -> Tamanho:
    """
    A perda somada, e o teto de N.

    O teto vale para o `n_final`, e não para o `n`: com a correção de população finita o `n`
    nunca passa de N, e no tamanho decidido isso já foi recusado. Quem passa é o `n` com a
    perda — 169 de 300 com metade de perda dariam 338 —, e aí a amostra é a população
    inteira.
    """
    final = com_perda(n, perda)
    if populacao is not None:
        final = min(final, populacao)
    return Tamanho(
        n=n,
        n_final=final,
        populacao=populacao,
        perda=perda,
        z=z,
        n0=n0,
        n_corrigido=n_corrigido,
    )


__all__ = [
    "TOLERANCIA",
    "Tamanho",
    "com_perda",
    "para_cima",
    "tamanho_aas",
    "tamanho_decidido",
    "variancia_da_proporcao",
    "z_da_confianca",
]
