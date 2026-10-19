# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
A comparação — uma variável contra um valor de referência, entre os grupos de outra,
ou entre medidas repetidas nos mesmos casos —, com o teste que os pressupostos pedem:
o paramétrico, ou o de postos, que dispensa a normal.

Responde ao passo 2b do fluxo. Cada item da ficha é uma pergunta, e cada delineamento
tem a sua tabela, na mesma pasta:

    uma_amostra.csv
    variável       n  média (DP)         IC 95% da média  referência  teste         p-valor
    IMC (kg/m²)  116  26,43 (4,59)       25,58 a 27,27    25          t de Student    0,001
    PAS (mmHg)   120  128,4 (14,2)       125,83 a 130,97  120         t de Student  < 0,001

    dois_grupos.csv
    variável     grupo        n  média (DP)    diferença (IC 95%)     teste         p-valor
    IMC (kg/m²)  Sexo       116                -1,52 (-3,24 a 0,20)   t de Welch      0,083
                 Feminino    60  25,70 (4,41)
                 Masculino   56  27,22 (4,70)

    k_grupos.csv
    variável     grupo          n  média (DP)    teste            p-valor
    PAS (mmHg)   Escolaridade 114                ANOVA de Welch     0,011
                 Fundamental   34  128,1 (15,2)
                 Médio         52  131,0 (16,9)
                 Superior      28  138,4 (16,1)

    repetidas.csv
    medida        n  média (DP)     teste                        p-valor
    PAS basal    40  131,2 (16,6)   ANOVA de medidas repetidas     0,003
    PAS 30 dias  40  128,4 (15,1)
    PAS 90 dias  40  125,9 (14,8)

Nas linhas de um teste de postos — o Wilcoxon, o Mann-Whitney, o Kruskal-Wallis e o
Friedman —, o resumo é a mediana e os quartis, `2982,62 [1774,62 a 5013,54]`, e o
intervalo é o de Hodges-Lehmann: o da pseudomediana na uma amostra, e o da diferença de
locação entre dois grupos, `-921,57 (-2414,48 a 406,97)`. O cabeçalho de cada coluna diz
o que ela tem — ver "O resumo, linha a linha", abaixo.

Segue o padrão das Fases 2 a 6, decidir e escrever separados:

    plano = preparar_comparacao(raiz)   # abre o banco, calcula, não toca no disco
    executar_comparacao(plano)          # só escreve

E, como elas, **não fala com o REDCap**. Recebe `Path`, não `Config`.

## Uma análise, e o teste escolhido dentro dela

`comparacao` é uma análise só — uma chave na ficha, um comando, uma pasta em
`3. Análises/`, uma seção no documento —, e cada teste é uma entrada num registro
dentro dela, e não um módulo por teste. O que se escreve na reunião é a **pergunta**
("a média do IMC difere de 25?", "o IMC difere entre os sexos?"), e não o teste: qual
teste responde é consequência do **delineamento**, que sai da forma do item e dos
tipos do dicionário, e dos **pressupostos**, que saem do banco. É a lição da
correlação — a ficha lista as perguntas, a regra escolhe o método, e o terceiro nome
discorda quando você discordar.

O registro são três dicionários aqui em cima. A `REGRA` diz, para cada delineamento,
o teste quando a normal se sustenta e o teste quando não; o `_CALCULO` diz quais deles
já têm a aritmética no `hipoteses.py`; o `METODOS` diz o que cada nome escrito no item
quer dizer em cada delineamento. Um teste que está na regra e não no cálculo é um
teste que a regra sabe escolher e o FlatCap ainda não sabe fazer, e a linha dele sai
sem teste, com o motivo escrito; quando ele chega, entra uma linha no `_CALCULO`, e
as linhas "não testado" viram linhas dele. Foi assim que os paramétricos e, na 1.14.0,
os quatro testes de postos entraram, um por um; desde ela, todo teste da regra tem a
aritmética, e o caminho fica para o próximo que entrar.

## O delineamento

A forma do item e os tipos das variáveis dizem qual comparação é:

    [imc, 25]                  numérica, e um número       uma amostra
    [imc, sexo]                numérica, categórica        dois grupos
    [imc, escolaridade]        numérica, categórica        três grupos ou mais
    repetidas: [pas_0, pas_1, pas_2]   três numéricas ou mais      medidas repetidas
    repetidas: [pas_0, pas_1]          duas numéricas              pareado (depois)

**O número de grupos sai do banco, e não do dicionário.** Os grupos são os rótulos
com resposta entre os casos que responderam as duas variáveis — pelas mesmas
`serie_de_texto` e `rotulo_de` do cruzamento e da associação: dois códigos com o
mesmo rótulo (`1=Sim|2=Sim`) são um grupo só, e uma categoria declarada que ninguém
marcou não é grupo. Dois grupos são a tabela dos dois grupos; três ou mais, a dos k
grupos. Um grupo só dá linha sem teste, na tabela que o dicionário promete.

**Os faltantes são por comparação**: entra quem respondeu as duas variáveis. É o
`na.omit` da fórmula do R. Nas medidas repetidas, entra quem tem todas as medidas do
item: a ANOVA compara cada pessoa com ela mesma, e um caso com uma medida faltando sai
inteiro — como no `lm` do R.

**As medidas repetidas têm a marca na ficha.** Duas numéricas lado a lado,
`[pas_0, pas_1]`, seriam um pareado — ou `[idade, imc]` escrito por engano,
comparando médias de unidades diferentes sem erro nenhum. A marca `repetidas:` diz que
são a mesma medida, feita mais de uma vez nas mesmas pessoas.

## A regra dos pressupostos

Três passos, como na correlação:

1. **o Shapiro-Wilk sobre o vetor do delineamento.** Na uma amostra, os valores
   preenchidos da variável; entre grupos, **cada grupo**, separado — é a normalidade
   que o t supõe, e não a da coluna inteira. Não rejeitou em nenhum → o paramétrico;
2. **rejeitou em algum, ou não pôde ser verificado em algum** (menos de três valores,
   ou um grupo que não varia) → o teste de postos, que dispensa a normal: o Wilcoxon
   na uma amostra, o Mann-Whitney entre dois grupos, o Kruskal-Wallis entre três ou
   mais, o Friedman nas medidas repetidas;
3. **o método escrito no item manda**: `[imc, 25, t]` roda o t contra a regra, e
   `[imc, 25, wilcoxon]` o Wilcoxon, com um aviso e a frase nas notas do `.csv`.

**Entre dois grupos, o paramétrico da regra é o t de Welch**, e não o de Student: é o
padrão do `t.test` do R, perde pouco quando as variâncias são iguais e protege quando
não são (Delacre, Lakens e Leys, 2017) — e dispensa o teste de Levene, que seria um
teste preliminar a mais antes do teste que interessa. O de Student roda quando está
escrito no item, `[imc, sexo, student]`, e o aviso diz quanto os desvios padrão dos
grupos diferem.

**Entre três grupos ou mais, pela mesma razão, a ANOVA de Welch** — o padrão do
`oneway.test` do R —, e a clássica, de Fisher, quando está escrita no item:
`[imc, escolaridade, anova]`, com o mesmo aviso das variâncias do t de Student. A
ANOVA diz se as médias diferem, e não quais: o pós-teste ainda não está no FlatCap.

**Nas medidas repetidas, a ANOVA com a correção de Greenhouse-Geisser, sempre** — a
mesma lógica do Welch: a correção custa pouco quando a esfericidade vale e protege
quando não vale, e o teste de Mauchly, preliminar, sai da frente. O Shapiro-Wilk roda
em cada medida, sobre os casos completos.

**A normalidade é a função, e não a rodada.** O teste é o `normalidade.shapiro`, o
mesmo que a correlação chama, com as mesmas barreiras e os mesmos avisos — e não o
`manifesto.json` da rodada de normalidade. O vetor que se testa muda com o
delineamento, e uma escolha que dependesse da outra rodada dependeria da ordem dos
comandos e da idade dela. Na uma amostra o vetor **é** a coluna sem os faltantes, então
o p que decide é o mesmo da tabela de normalidade — por construção.

**O Shapiro-Wilk não garante o pressuposto**, e o módulo não finge que garante: é a
regra que o projeto adotou, com os limites dela escritos no topo do `normalidade.py`.
Abaixo de 20 valores ele quase não rejeita, e o paramétrico escolhido ali sai com
aviso; com n grande ele rejeita desvio irrelevante, e a linha vai para o teste de
postos — que continua valendo, e custa pouco. Quando você concluir que o paramétrico
vale ali — n grande e assimetria pequena, por exemplo —, o método escrito no item
manda. A decisão é sua, e fica registrada contra a regra.

## Os testes de postos

São os do R, pela aritmética do `hipoteses.py`: o `wilcox.test` — de uma amostra e de
duas, que é o Mann-Whitney —, o `kruskal.test` e o `friedman.test`. O Wilcoxon e o
Mann-Whitney saem **com a estimativa de Hodges-Lehmann e o intervalo dela**, o
`conf.int = TRUE` do R: a pseudomediana, lida contra a referência como o intervalo da
média; a diferença de locação entre dois grupos, lida contra o zero como a diferença
das médias. **A diferença de locação não é a diferença das medianas** dos grupos — é a
mediana das diferenças entre um valor de cada grupo —, e a nota da tabela diz isso. O
Kruskal-Wallis e o Friedman, como a ANOVA, dizem se há diferença, e não quanto.

Com poucos valores, a distribuição exata pode não ter um intervalo de 95% — o mais
largo, do menor ao maior valor, fica abaixo disso —, e o menor p que o teste consegue
dar pode passar de 0,05: o teste não rejeita com dado nenhum. Os dois casos saem com
aviso, e o intervalo que não chega a 95% fica fora da tabela, que promete 95%.

## O resumo, linha a linha

Cada linha descreve a variável na medida que o teste dela usa: **média (DP)** nas
linhas do t e da ANOVA, **mediana [Q1 a Q3]** nas dos testes de postos — como o
`compareGroups` do R faz. O teste é o da linha: o que rodou, ou o que a regra escolheu
quando ele não pôde rodar; sem teste nenhum, a média. As duas formas saem pelo
`descritiva.resumo_numerico` e pelo `numero()`, letra por letra as do
`resumo_<variável>.csv`. Os colchetes separam os quartis do desvio padrão na leitura de
relance, e o cabeçalho diz o que a coluna tem: `média (DP)`, `mediana [Q1 a Q3]`, ou as
duas, quando a tabela mistura. O mesmo vale para o intervalo da uma amostra — `IC 95% da
média`, `da pseudomediana`, ou só `IC 95%` — e para a diferença entre dois grupos:
`diferença (IC 95%)` no t, `diferença de locação (IC 95%)` no Mann-Whitney. As notas,
que dizem o que é a diferença de locação, ficam no `.csv`; o documento leva a tabela, e
é o cabeçalho que impede a leitura dela como a diferença das medianas ao lado. Uma tabela
só de paramétricos sai com os cabeçalhos de antes.

## A ficha

    comparacao:
      - [imc, 25]                # a média do IMC difere de 25?
      - [pas, 120, t]            # o t, mesmo que a regra discorde
      - [renda, 3000, wilcoxon]  # o Wilcoxon, mesmo que a regra escolhesse o t
      - [imc, sexo]              # o IMC difere entre os sexos?
      - [pas, sexo, student]     # pelo t de Student, que supõe variâncias iguais
      - sexo: [imc, idade]       # uma contra várias: imc e idade, entre os sexos
      - repetidas: [pas_0, pas_1, pas_2]   # a PAS mudou entre as três medidas?
      - repetidas: [pad_0, pad_1, pad_2]
        metodo: anova                      # a ANOVA, mesmo que a regra discorde

**A referência é obrigatória.** O padrão do R é `mu = 0`, que nunca é a hipótese de
uma variável clínica; o valor vem da literatura ou do protocolo, e é decidido na
reunião. **A vírgula decimal quebra a lista**: `[imc, 24,9]` é lido como três itens,
`imc`, `24` e `9`, e a recusa reconhece esse caso e escreve a forma certa —
`[imc, 24.9]`, ou `[imc, "24,9"]`, que entre aspas é aceito. **A variável comparada
vem primeiro**, e a de grupo depois; na forma com dois-pontos, a de grupo vem antes
deles, e o método não se escreve — ele ficaria misturado aos nomes. **Sempre
bilateral**: um teste unilateral escolhido depois de olhar os dados é o p dividido por
dois.

## O que ele reaproveita

As recusas de dicionário e de tipo são as da descritiva, com a classe de erro deste
módulo. O Shapiro-Wilk e o formatador do p são os da normalidade. A média e o desvio
padrão — e a mediana e os quartis — saem pelo `descritiva.resumo_numerico` e pelo
`numero()`: o resumo da uma amostra é, letra por letra, o do `resumo_<variável>.csv`.
Os grupos saem pela `serie_de_texto` da descritiva, pelo `rotulo_de` do dicionário e
pela ordem da associação. A aritmética dos testes é a do `hipoteses.py`, que confere
com o `t.test`, o `oneway.test`, o `wilcox.test`, o `kruskal.test` e o `friedman.test`
do R.

## O que ele deliberadamente não faz

**Não desenha.** O histograma da descritiva e o Q-Q da normalidade são as figuras
destas variáveis; as caixas por grupo são uma espécie nova no `graficos.py`, e ficam
para quando a comparação entre grupos estiver inteira.

**Não imprime o d de Cohen**, nem um r de efeito nos testes de postos. O intervalo —
da média ou da pseudomediana, lido contra a referência; da diferença, lido contra o
zero — já é o tamanho do efeito, na unidade que o cliente entende.

**Não roda o Levene**, pela razão do Welch, acima.

**Não corrige para comparações múltiplas.** Cada comparação é um teste, e isso está
escrito nas notas e no terminal.
"""

from __future__ import annotations

import math
import re
import sys
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__
from .associacao import na_ordem_do_dicionario
from .banco import Banco, abrir, casas_do_resumo
from .descritiva import arquivamento as arquivamento_da_rodada
from .descritiva import (
    conferir_dicionario,
    numero,
    recusar_incompativeis,
    resumo_numerico,
    serie_de_texto,
)
from .dicionario import ARQUIVO_DICIONARIO, CATEGORICA, IGNORAR, NUMERICA, Linha
from .ficha import Ficha, bloco, escrever_atomico
from .ficha import ler as ler_ficha
from .hipoteses import (
    ANOVA,
    ANOVA_DE_MEDIDAS_REPETIDAS,
    ANOVA_DE_WELCH,
    CONFIANCA,
    FRIEDMAN,
    KRUSKAL_WALLIS,
    LIMITE_DO_EXATO,
    MANN_WHITNEY,
    MINIMO_STUDENT,
    MINIMO_T,
    T_DE_STUDENT,
    T_DE_WELCH,
    WILCOXON,
    Resultado,
    anova_de_medidas_repetidas,
    anova_de_um_fator,
    anova_de_welch,
    friedman,
    kruskal_wallis,
    mann_whitney,
    medidas_iguais_em_cada_caso,
    sem_variacao,
    sem_variacao_em_duas,
    sem_variacao_entre_medidas,
    sem_variacao_nos_grupos,
    t_de_student,
    t_de_welch,
    t_uma_amostra,
    wilcoxon_uma_amostra,
)
from .manifesto import (
    ANALISE_COMPARACAO,
    ARQUIVO_MANIFESTO,
    SEMENTE,
    Artefato,
    ItemDoManifesto,
    Manifesto,
    Tabela,
    texto_do_manifesto,
)
from .nomes import rotulo_do_projeto
from .normalidade import (
    ALFA,
    MENOR_P,
    MINIMO_CONFIAVEL,
    MINIMO_SHAPIRO,
    POUCOS_DISTINTOS,
    shapiro,
    valor_p,
)
from .projeto import (
    ARQUIVO_PROJETO,
    PASTA_ANALISES,
    PASTA_ANTIGAS,
    PASTA_COMPARACAO,
    anotar,
    pasta_da_analise,
)

# Os delineamentos, na ordem em que as tabelas saem. Cada um tem a sua tabela, porque
# as colunas mudam de um para outro: a uma amostra tem a referência; os grupos, uma
# linha por grupo e a diferença.
UMA_AMOSTRA = "uma_amostra"
DOIS_GRUPOS = "dois_grupos"
K_GRUPOS = "k_grupos"
REPETIDAS = "repetidas"
DELINEAMENTOS = (UMA_AMOSTRA, DOIS_GRUPOS, K_GRUPOS, REPETIDAS)

# As chaves do item de medidas repetidas — a marca, e o método, que ali não tem um
# terceiro lugar na lista para morar:
#
#     - repetidas: [pas_0, pas_1, pas_2]
#       metodo: anova
CHAVE_REPETIDAS = "repetidas"
CHAVE_METODO = "metodo"

# O menor número de medidas da ANOVA de medidas repetidas nesta versão. Com duas, a
# pergunta é a do t pareado, que usa a mesma forma de item e ainda não está no FlatCap.
MINIMO_DE_MEDIDAS = 3

# A forma do item entre grupos, antes de o banco dizer quantos são. A `Pergunta` sai
# da ficha com ela, e a `VariavelComparada` sai do banco com o delineamento de fato.
GRUPOS = "grupos"
_DOS_GRUPOS = (DOIS_GRUPOS, K_GRUPOS)

ARQUIVO_TABELA = "uma_amostra.csv"
ARQUIVO_DOIS_GRUPOS = "dois_grupos.csv"
ARQUIVO_K_GRUPOS = "k_grupos.csv"
ARQUIVO_REPETIDAS = "repetidas.csv"
ARQUIVOS: dict[str, str] = {
    UMA_AMOSTRA: ARQUIVO_TABELA,
    DOIS_GRUPOS: ARQUIVO_DOIS_GRUPOS,
    K_GRUPOS: ARQUIVO_K_GRUPOS,
    REPETIDAS: ARQUIVO_REPETIDAS,
}

# A regra: para cada delineamento, o teste quando a normal se sustenta e o teste
# quando não — o de postos. Entre grupos o paramétrico é o de Welch — o padrão do
# `t.test` e do `oneway.test` do R. Os nomes, e a aritmética, vêm do `hipoteses.py`.
REGRA: dict[str, tuple[str, str]] = {
    UMA_AMOSTRA: (T_DE_STUDENT, WILCOXON),
    DOIS_GRUPOS: (T_DE_WELCH, MANN_WHITNEY),
    K_GRUPOS: (ANOVA_DE_WELCH, KRUSKAL_WALLIS),
    REPETIDAS: (ANOVA_DE_MEDIDAS_REPETIDAS, FRIEDMAN),
}

# O que já tem aritmética. Um teste da `REGRA` que não está aqui é escolhido pela
# regra e sai sem teste, com o motivo. O t de Student e a ANOVA clássica estão aqui
# sem estar na regra: eles rodam quando o item os pede.
_CALCULO: dict[tuple[str, str], Callable[..., Resultado]] = {
    (UMA_AMOSTRA, T_DE_STUDENT): t_uma_amostra,
    (UMA_AMOSTRA, WILCOXON): wilcoxon_uma_amostra,
    (DOIS_GRUPOS, T_DE_WELCH): t_de_welch,
    (DOIS_GRUPOS, T_DE_STUDENT): t_de_student,
    (DOIS_GRUPOS, MANN_WHITNEY): mann_whitney,
    (K_GRUPOS, ANOVA_DE_WELCH): anova_de_welch,
    (K_GRUPOS, ANOVA): anova_de_um_fator,
    (K_GRUPOS, KRUSKAL_WALLIS): kruskal_wallis,
    (REPETIDAS, ANOVA_DE_MEDIDAS_REPETIDAS): anova_de_medidas_repetidas,
    (REPETIDAS, FRIEDMAN): friedman,
}

# Os testes de postos: os que dispensam a normal, e cujas linhas resumem a variável
# pela mediana e pelos quartis, e não pela média e pelo desvio.
TESTES_DE_POSTOS: frozenset[str] = frozenset(
    {WILCOXON, MANN_WHITNEY, KRUSKAL_WALLIS, FRIEDMAN}
)

# Como cada método se escreve no item — o terceiro nome —, e o teste que ele quer
# dizer em cada delineamento. Sem acento, minúsculo e sem hífen, que é como `_chave`
# deixa o que se digitou. `t` é o t que o R roda sem argumento: o de uma amostra, e o
# de Welch entre dois grupos — o `var.equal = FALSE` padrão do `t.test`. `welch` é o
# de Welch do número de grupos que o banco trouxer: o t com dois, a ANOVA com mais.
# `wilcoxon` é o `wilcox.test` do R: o do posto sinalizado contra uma referência, e o
# Mann-Whitney entre dois grupos — que o R chama de soma de postos de Wilcoxon.
METODOS: dict[str, dict[str, str]] = {
    "t": {UMA_AMOSTRA: T_DE_STUDENT, DOIS_GRUPOS: T_DE_WELCH},
    "student": {UMA_AMOSTRA: T_DE_STUDENT, DOIS_GRUPOS: T_DE_STUDENT},
    "welch": {DOIS_GRUPOS: T_DE_WELCH, K_GRUPOS: ANOVA_DE_WELCH},
    "anova": {K_GRUPOS: ANOVA, REPETIDAS: ANOVA_DE_MEDIDAS_REPETIDAS},
    "wilcoxon": {UMA_AMOSTRA: WILCOXON, DOIS_GRUPOS: MANN_WHITNEY},
    "mannwhitney": {DOIS_GRUPOS: MANN_WHITNEY},
    "kruskal": {K_GRUPOS: KRUSKAL_WALLIS},
    "friedman": {REPETIDAS: FRIEDMAN},
}

# Os nomes que a regra ainda não conhece em delineamento nenhum desta versão. Escritos
# na ficha, recusam com a frase certa, em vez de "não é um método". Vazio nesta versão:
# cada nome conhecido tem o seu delineamento; o lugar fica para o próximo.
PREVISTOS: dict[str, str] = {}

# O método de um número de grupos escrito para outro: o que se escreve no lugar dele,
# e por quê. O banco é que diz quantos grupos há, e a recusa ensina a troca.
_EQUIVALENTES: dict[tuple[str, str], tuple[str, str]] = {
    ("student", K_GRUPOS): ("anova", "o t de Student compara dois grupos"),
    ("t", K_GRUPOS): ("welch", "o t compara dois grupos"),
    ("anova", DOIS_GRUPOS): (
        "student",
        "com dois grupos, o F da ANOVA é o t de Student ao quadrado",
    ),
    ("mannwhitney", K_GRUPOS): ("kruskal", "o Mann-Whitney compara dois grupos"),
    ("wilcoxon", K_GRUPOS): (
        "kruskal",
        "o Wilcoxon entre grupos é o Mann-Whitney, que compara dois",
    ),
    ("kruskal", DOIS_GRUPOS): ("mannwhitney", "com dois grupos, o teste é o Mann-Whitney"),
}

# Outras grafias do mesmo método. `welsh` é a troca mais comum de letra no nome do
# Welch, e ninguém a escreve querendo outra coisa.
_SINONIMOS: dict[str, str] = {
    "welsh": "welch",
    "tdewelch": "welch",
    "twelch": "welch",
    "tdestudent": "student",
    "tstudent": "student",
    "anovadewelch": "welch",
    "welchanova": "welch",
    "anovademedidasrepetidas": "anova",
    "anovarepetidas": "anova",
    "mannwhitneyu": "mannwhitney",
    "udemannwhitney": "mannwhitney",
    "mannwhitneywilcoxon": "mannwhitney",
    "wilcoxonranksum": "mannwhitney",
    "wilcox": "wilcoxon",
    "kruskalwallis": "kruskal",
    "friedmann": "friedman",
}
# O `signed rank` fica de fora de propósito: o `wilcoxon` entre dois grupos é o
# Mann-Whitney, e um sinônimo dele levaria quem escreveu o posto sinalizado — o teste
# de uma amostra, ou do pareado — ao da soma de postos sem aviso. Escrito, ele recusa,
# e a recusa ensina o `wilcoxon`.

# Os testes que supõem a mesma variância nos grupos. Quando um deles roda, o aviso diz
# quanto o maior desvio padrão passa do menor — acima de duas vezes, a regra de bolso
# que os livros dão para a igualdade de variâncias ainda valer.
_VARIANCIAS_IGUAIS: frozenset[tuple[str, str]] = frozenset(
    {(DOIS_GRUPOS, T_DE_STUDENT), (K_GRUPOS, ANOVA)}
)
RAZAO_DE_DESVIOS = 2.0

# O intervalo sai com casas fixas: ele não existe na descritiva, e uma célula com
# `25,8 a 27,02` — um limite com uma casa, outro com duas — não se lê de relance. A
# média e o desvio não: eles têm de sair letra por letra como no `resumo`. As casas
# são duas, ou as da variável quando a escala dela é pequena: até a 1.14.0, uma
# concentração na casa de 0,003 saía «0,00 (0,00 a 0,00)» ao lado de um p < 0,001.
CASAS_IC = 2

# O cabeçalho da coluna do resumo, conforme o que ela tem: a média e o desvio nas
# linhas do t e da ANOVA, a mediana e os quartis nas dos testes de postos — e as duas
# formas no cabeçalho quando a tabela mistura. Os colchetes separam os quartis do
# desvio padrão, que vem entre parênteses, na leitura de relance.
COLUNA_DA_MEDIA = "média (DP)"
COLUNA_DA_MEDIANA = "mediana [Q1 a Q3]"
COLUNA_DAS_DUAS = f"{COLUNA_DA_MEDIA} ou {COLUNA_DA_MEDIANA}"

# O cabeçalho do intervalo da uma amostra, pela mesma regra: o da média no t, o da
# pseudomediana no Wilcoxon, e só o nível quando a tabela tem os dois.
COLUNA_DO_IC_DA_MEDIA = "IC 95% da média"
COLUNA_DO_IC_DA_PSEUDOMEDIANA = "IC 95% da pseudomediana"
COLUNA_DO_IC = "IC 95%"

# O cabeçalho da diferença entre dois grupos, pela mesma regra: o de sempre no t, a de
# locação no Mann-Whitney — que não é a diferença das medianas, e que a célula ao lado
# da mediana de cada grupo convidaria a ler como tal —, e as duas quando a tabela mistura.
COLUNA_DA_DIFERENCA = "diferença (IC 95%)"
COLUNA_DA_DIFERENCA_DE_LOCACAO = "diferença de locação (IC 95%)"
COLUNA_DAS_DUAS_DIFERENCAS = "diferença de médias ou de locação (IC 95%)"

# A referência sai como foi escrita, sem arredondar para duas casas: um `0,125` da
# ficha impresso `0,12` seria uma hipótese que ninguém testou.
CASAS_REFERENCIA = 6

_AUSENTE = "—"

# Um número escrito como texto na ficha: `"24,9"`, `"24.9"`, `" 25 "`. Sem separador
# de milhar — `1.234,5` é ambíguo, e ambiguidade numa hipótese se recusa.
_NUMERO_ESCRITO = re.compile(r"^[+\-]?\d+(?:[.,]\d+)?$")

# Um texto que quer ser número e não é um que se leia sem ambiguidade: `"2.500,00"`.
# Só algarismos, pontos, vírgulas e espaços — `pas_0` tem algarismo e é um nome.
_PARECE_NUMERO = re.compile(r"^[+\-]?[\d.,\s]*\d[\d.,\s]*$")

# O exemplo que as mensagens escrevem. Um lugar só, para a recusa e o `--help` nunca
# ensinarem duas formas diferentes de escrever a mesma lista.
EXEMPLO_DA_FICHA = f"""  {PASTA_COMPARACAO}:
    - [imc, 25]
    - [pas, 120, t]
    - [imc, sexo]
    - {CHAVE_REPETIDAS}: [pas_0, pas_1, pas_2]"""


class ComparacaoError(RuntimeError):
    """
    Falha ao gerar a comparação, já traduzida para o usuário.

    Erro próprio pela regra da casa: a CLI captura esta classe e transforma em painel
    com o nome do comando que o usuário rodou. Qualquer outra exceção é bug de
    verdade e deve subir com o traceback inteiro.
    """


class DicionarioAusenteError(ComparacaoError):
    """
    O projeto não tem `dicionario.csv`. Não há o que obedecer.
    """


class DicionarioDesatualizadoError(ComparacaoError):
    """
    O banco tem colunas que o dicionário desconhece.
    """


class VariavelIncompativelError(ComparacaoError):
    """
    O dicionário promete `numerica` e a coluna chegou como texto, ou declara uma
    variável que o banco não tem.

    A mesma recusa da Fase 5, pela mesma função — aplicada só às variáveis da lista,
    como na correlação.
    """


class SemItensError(ComparacaoError):
    """
    A ficha não diz o que comparar.
    """


class ItemInvalidoError(ComparacaoError):
    """
    A lista `comparacao:` da ficha tem item que não serve.

    Formato errado, referência que não é número, a vírgula decimal que partiu o
    número em dois, método que não existe, nome fora do dicionário, tipos que não
    formam uma comparação, a mesma comparação duas vezes — ou, já com o banco aberto,
    uma variável de grupo com mais grupos do que esta versão compara. A mensagem lista
    **todos** de uma vez, pela regra da Fase 5.
    """


# O que sai no disco


@dataclass(frozen=True)
class Pedido:
    """
    Um item como a ficha o escreve: a variável e, conforme a forma, a referência ou a
    variável de grupo — e, quando houver, o método.

    `metodo` é o nome como se escreve na ficha, já na forma de `_chave` (`t`,
    `student`), e não o teste: o que `t` quer dizer depende do delineamento, e entre
    grupos o delineamento só se conhece com o banco aberto.

    Nas medidas repetidas, `medidas` são as variáveis, na ordem da ficha, e `variavel`
    é a primeira delas.
    """

    variavel: str
    referencia: float | None = None
    metodo: str = ""
    grupos: str = ""
    medidas: tuple[str, ...] = ()

    @property
    def escrito(self) -> str:
        """
        O item de volta na forma da ficha, para as mensagens. O de medidas repetidas com
        método sai na forma de uma linha só, `{repetidas: [...], metodo: anova}`, que o
        YAML lê igual à de duas linhas.
        """
        if self.medidas:
            lista = f"{CHAVE_REPETIDAS}: [{', '.join(self.medidas)}]"
            return f"{{{lista}, {CHAVE_METODO}: {self.metodo}}}" if self.metodo else lista
        metodo = f", {self.metodo}" if self.metodo else ""
        if self.grupos:
            return f"[{self.variavel}, {self.grupos}{metodo}]"
        referencia = _referencia_em_texto(self.referencia or 0.0, ponto=True)
        return f"[{self.variavel}, {referencia}{metodo}]"

    @property
    def chave(self) -> tuple[Any, ...]:
        """
        O que faz dois itens serem a mesma comparação: o método não entra — o mesmo
        item com outro método é a mesma pergunta feita duas vezes.
        """
        if self.medidas:
            return (REPETIDAS, tuple(sorted(self.medidas)))
        if self.grupos:
            return (GRUPOS, self.variavel, self.grupos)
        return (UMA_AMOSTRA, self.variavel, self.referencia)


@dataclass(frozen=True)
class Pergunta:
    """
    Um item da ficha, já conferido contra o dicionário. É a pergunta da reunião — "a
    média desta variável difere desta referência?", "difere entre estes grupos?" —
    com a forma que ela tem.

    `delineamento` é `UMA_AMOSTRA`, `GRUPOS` ou `REPETIDAS`: entre grupos, quantos são
    só se sabe com o banco aberto. `metodo` é o nome escrito na ficha, como no
    `Pedido`. Nas medidas repetidas, `medidas` são as linhas do dicionário de cada uma.
    """

    linha: Linha
    referencia: float | None = None
    metodo: str = ""
    delineamento: str = UMA_AMOSTRA
    grupos: Linha | None = None
    medidas: tuple[Linha, ...] = ()

    @property
    def linhas(self) -> tuple[Linha, ...]:
        if self.medidas:
            return self.medidas
        return (self.linha,) if self.grupos is None else (self.linha, self.grupos)


@dataclass(frozen=True)
class Normal:
    """
    O Shapiro-Wilk do vetor do delineamento.

    Os quatro campos são o que o `normalidade.shapiro` devolve: o W e o p quando o
    teste rodou, a frase do impedimento quando não rodou, e o aviso do `scipy` quando
    houve um.
    """

    w: float | None
    p: float | None
    impedimento: str = ""
    aviso: str = ""

    @property
    def testada(self) -> bool:
        return self.p is not None

    @property
    def rejeita(self) -> bool:
        return self.p is not None and self.p < ALFA


@dataclass(frozen=True)
class Grupo:
    """
    Um grupo de uma comparação entre grupos: o rótulo, quantos casos, a média e o
    desvio, e o Shapiro-Wilk dos valores dele.
    """

    rotulo: str
    n: int
    resumo: dict[str, float] | None = None
    normal: Normal | None = None


@dataclass(frozen=True)
class Escolha:
    """
    Qual teste rodou, e de onde ele veio.

    `da_regra` é o que a regra escolhe mesmo quando a ficha mandou outro, e mesmo
    quando o FlatCap ainda não o faz — é o que permite escrever "contra a regra" na
    nota, e dizer qual teste faltou. `metodo` vazio quer dizer que nenhum teste rodou:
    a regra escolheu um que ainda não tem aritmética, e a ficha não mandou outro.
    """

    metodo: str
    da_regra: str
    motivo: str
    pela_ficha: bool = False

    @property
    def contra_a_regra(self) -> bool:
        return self.pela_ficha and self.metodo != self.da_regra


@dataclass(frozen=True)
class VariavelComparada:
    """
    Uma pergunta respondida. Na uma amostra é uma linha da tabela; entre grupos, um
    bloco — a linha da comparação e uma linha por grupo.

    `resultado` fica `None` quando não houve teste; o motivo está em `motivo`, e a
    comparação **sai assim mesmo** — um item pedido que sumisse da tabela seria a falta
    em que ninguém repara. O resumo sai mesmo sem teste: ele descreve a variável, e não
    depende de pressuposto nenhum.

    Na uma amostra, `referencia`, `resumo` e `normal` são da variável inteira; entre
    grupos, `referencia` é `None`, e o resumo e o Shapiro-Wilk estão em cada `Grupo`.
    """

    variavel: str
    rotulo: str
    referencia: float | None
    total: int
    validos: int
    distintos: int = 0
    delineamento: str = UMA_AMOSTRA
    resumo: dict[str, float] | None = None
    normal: Normal | None = None
    escolha: Escolha | None = None
    resultado: Resultado | None = None
    motivo: str = ""
    avisos: tuple[str, ...] = ()
    variavel_de_grupo: str = ""
    rotulo_de_grupo: str = ""
    grupos: tuple[Grupo, ...] = ()
    medidas: tuple[str, ...] = ()
    # As casas decimais da variável, as do `resumo_<variável>.csv` da descritiva: as
    # duas de sempre, ou mais numa variável de escala pequena. Ver `_casas_da_coluna`.
    casas: int = CASAS_IC

    @property
    def faltantes(self) -> int:
        return self.total - self.validos

    @property
    def testada(self) -> bool:
        return self.resultado is not None

    @property
    def entre_grupos(self) -> bool:
        return bool(self.variavel_de_grupo)

    @property
    def repetidas(self) -> bool:
        return bool(self.medidas)

    @property
    def metodo(self) -> str:
        return self.resultado.metodo if self.resultado is not None else ""

    @property
    def colunas(self) -> tuple[str, ...]:
        """As colunas do banco que esta comparação usou."""
        if self.repetidas:
            return self.medidas
        if self.entre_grupos:
            return (self.variavel, self.variavel_de_grupo)
        return (self.variavel,)

    @property
    def cabeca(self) -> str:
        """
        Como a comparação se chama nas frases: `IMC (kg/m²) por Sexo`; nas medidas
        repetidas, os rótulos delas — `PAS basal, PAS 30 dias e PAS 90 dias`.
        """
        if self.repetidas:
            return _em_frase(grupo.rotulo for grupo in self.grupos)
        if self.entre_grupos:
            return f"{self.rotulo} por {self.rotulo_de_grupo}"
        return self.rotulo

    @property
    def n_na_frase(self) -> str:
        """
        `n = 57`, e entre grupos `n = 57 (29 em Feminino e 28 em Masculino)`. Nas medidas
        repetidas o n é um só — os casos com todas as medidas.
        """
        if self.repetidas:
            return f"n = {self.validos} com todas as medidas"
        if not self.grupos:
            return f"n = {self.validos}"
        por_grupo = _em_frase(f"{grupo.n} em {grupo.rotulo}" for grupo in self.grupos)
        return f"n = {self.validos} ({por_grupo})"

    @property
    def celula_do_teste(self) -> str:
        """
        O que vai para a coluna `teste`: o nome do teste, ou o motivo no lugar dele —
        como a coluna `método` da correlação e a `teste` da associação.
        """
        if self.resultado is not None:
            return self.resultado.metodo
        return f"não testado: {self.motivo}"

    @property
    def justificativa(self) -> str:
        """
        A frase que explica a comparação — a nota do `.csv` e a linha do terminal.

        Uma frase só, montada aqui, para que o arquivo e a tela digam a mesma coisa
        com as mesmas casas.
        """
        cabeca = f"{self.cabeca}: "
        escolha = self.escolha
        if escolha is None:
            return f"{cabeca}não testado — {self.motivo}."
        n = self.n_na_frase
        faltou = "" if _disponivel(self.delineamento, escolha.da_regra) else (
            ", que ainda não está no FlatCap"
        )
        if not escolha.metodo:
            return (
                f"{cabeca}{n}; {escolha.motivo} → {escolha.da_regra}"
                f"{faltou}: a linha sai sem teste."
            )
        escrito = _concorda(escolha.metodo, "escrito")
        if self.resultado is None:
            origem = (
                f"{escolha.metodo} {escrito} na ficha"
                if escolha.pela_ficha
                else f"{escolha.motivo} → {escolha.metodo}"
            )
            calculado = _concorda(escolha.metodo, "calculado")
            return f"{cabeca}{n}; {origem}, que não pôde ser {calculado}: {self.motivo}."
        estatistica = _estatistica_em_texto(self.resultado)
        if not escolha.pela_ficha:
            return (
                f"{cabeca}{n}; {escolha.motivo} → {escolha.metodo} "
                f"({estatistica})."
            )
        if escolha.contra_a_regra:
            return (
                f"{cabeca}{n}; {escolha.metodo} {escrito} na ficha "
                f"({estatistica}), contra a regra — ela escolheria {escolha.da_regra}"
                f"{faltou}: {escolha.motivo}."
            )
        return (
            f"{cabeca}{n}; {escolha.metodo} {escrito} na ficha "
            f"({estatistica}), o mesmo que a regra escolheria: {escolha.motivo}."
        )

    def como_detalhe(self) -> dict[str, Any]:
        """
        Os números desta comparação, para o manifesto — o que responde "de onde saiu
        esse teste, e esse p?" sem reabrir o banco.

        O intervalo vai em `ic_95` quando é o de 95% que a tabela imprime; quando o
        teste de postos não o alcança, o de nível menor que o R devolve vai em
        `ic_alcancavel`, com o nível — fora da tabela, e não perdido.
        """
        resultado = self.resultado
        escolha = self.escolha
        comum = {
            "teste": resultado.metodo if resultado else None,
            "teste_da_regra": escolha.da_regra if escolha else None,
            "escrito_na_ficha": escolha.pela_ficha if escolha else None,
            "motivo_da_regra": escolha.motivo if escolha else None,
            "estatistica": (
                {
                    "nome": resultado.nome_da_estatistica,
                    "valor": _arredondar(resultado.estatistica),
                    "gl": [_arredondar(gl) for gl in resultado.gl],
                }
                if resultado
                else None
            ),
            "estimativa": (
                {"nome": resultado.nome_da_estimativa, "valor": _arredondar(resultado.estimativa)}
                if resultado
                else None
            ),
            "ic_95": (
                [_arredondar(intervalo[0]), _arredondar(intervalo[1])]
                if (intervalo := _ic_da_tabela(resultado))
                else None
            ),
            "ic_alcancavel": (
                {
                    "confianca": _arredondar(resultado.confianca_do_ic),
                    "limites": [_arredondar(resultado.ic[0]), _arredondar(resultado.ic[1])],
                }
                if resultado and resultado.ic and not _ic_da_tabela(resultado)
                else None
            ),
            "p": _significativos(resultado.p) if resultado else None,
            "exato": resultado.exato if resultado else None,
            "calculo_do_p": resultado.calculo_do_p if resultado else None,
            "motivo": self.motivo or None,
        }
        if self.repetidas:
            return {
                "delineamento": self.delineamento,
                "medidas": list(self.medidas),
                "n": self.validos,
                "faltantes": self.faltantes,
                "distintos": self.distintos,
                "por_medida": [
                    {
                        "medida": variavel,
                        "rotulo": grupo.rotulo,
                        **_resumo_no_manifesto(grupo.resumo),
                        "shapiro": _shapiro_no_manifesto(grupo.normal),
                    }
                    for variavel, grupo in zip(self.medidas, self.grupos, strict=True)
                ],
                **comum,
                "epsilon": _arredondar(resultado.epsilon) if resultado else None,
            }
        if self.entre_grupos:
            return {
                "delineamento": self.delineamento,
                "variavel": self.variavel,
                "grupos": self.variavel_de_grupo,
                "n": self.validos,
                "faltantes": self.faltantes,
                "distintos": self.distintos,
                "por_grupo": [
                    {
                        "grupo": grupo.rotulo,
                        "n": grupo.n,
                        **_resumo_no_manifesto(grupo.resumo),
                        "shapiro": _shapiro_no_manifesto(grupo.normal),
                    }
                    for grupo in self.grupos
                ],
                **comum,
            }
        return {
            "delineamento": self.delineamento,
            "variavel": self.variavel,
            "referencia": self.referencia,
            "n": self.validos,
            "faltantes": self.faltantes,
            "distintos": self.distintos,
            **_resumo_no_manifesto(self.resumo),
            "shapiro": _shapiro_no_manifesto(self.normal),
            **comum,
        }


def _casas_da_coluna(*colunas: pd.Series) -> int:
    """
    As casas decimais da variável, decididas como a descritiva as decide: pela coluna
    inteira, e não pelos casos da comparação — a média da uma amostra sai, letra por
    letra, a do `resumo_<variável>.csv`, e a de cada grupo sai com as mesmas casas.
    Nas medidas repetidas, as da medida que pede mais, para a tabela não misturar.
    """
    casas = [
        casas_do_resumo(resumo_numerico(coluna.dropna().astype("float64")))
        for coluna in colunas
        if coluna is not None and coluna.notna().any()
    ]
    return max(casas, default=CASAS_IC)


def _resumo_no_manifesto(resumo: dict[str, float] | None) -> dict[str, float | None]:
    """
    As duas formas do resumo, sempre — a média e o desvio, a mediana e os quartis: a
    tabela imprime a do teste da linha, e o manifesto guarda as duas, para a mediana de
    um grupo, que a descritiva não tem, não morar só na célula.
    """
    resumo = resumo or {}
    return {
        chave: _arredondar(resumo.get(chave))
        for chave in ("media", "desvio", "mediana", "q1", "q3")
    }


@dataclass(frozen=True)
class ForaDaComparacao:
    """
    Uma variável do dicionário que não está em item nenhum, e por quê.
    """

    variavel: str
    tipo: str
    motivo: str


@dataclass(frozen=True)
class Comparacao:
    """
    A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.

    `tabelas` tem uma tabela por delineamento que apareceu na ficha, na ordem de
    `DELINEAMENTOS`; um delineamento sem item não tem tabela.
    """

    ficha: Ficha
    banco: Banco
    variaveis: tuple[VariavelComparada, ...]
    fora: tuple[ForaDaComparacao, ...]
    avisos: tuple[str, ...]
    quando: datetime
    tabelas: tuple[Tabela, ...]

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def linhas(self) -> int:
        return self.banco.linhas

    @property
    def colunas_usadas(self) -> tuple[str, ...]:
        vistas: list[str] = []
        for variavel in self.variaveis:
            for coluna in variavel.colunas:
                if coluna not in vistas:
                    vistas.append(coluna)
        return tuple(vistas)

    @property
    def testadas(self) -> tuple[VariavelComparada, ...]:
        return tuple(v for v in self.variaveis if v.testada)

    @property
    def sem_teste(self) -> tuple[VariavelComparada, ...]:
        return tuple(v for v in self.variaveis if not v.testada)

    @property
    def pela_ficha(self) -> tuple[VariavelComparada, ...]:
        return tuple(v for v in self.variaveis if v.escolha and v.escolha.pela_ficha)

    def quantos(self, metodo: str) -> int:
        return sum(1 for v in self.variaveis if v.metodo == metodo)

    def do_delineamento(self, delineamento: str) -> tuple[VariavelComparada, ...]:
        return tuple(v for v in self.variaveis if v.delineamento == delineamento)

    def tabela_de(self, delineamento: str) -> Tabela | None:
        return next((t for t in self.tabelas if t.especie == delineamento), None)


@dataclass(frozen=True)
class PlanoComparacao:
    """
    Tudo o que a `comparacao` faria, decidido e ainda não escrito.

    Imutável como os planos das outras fases, e pela mesma razão: entre a simulação e
    a execução ninguém altera um caminho em trânsito.
    """

    comparacao: Comparacao
    pasta: Path
    arquivamento: tuple[Path, Path] | None
    manifesto: Manifesto
    texto_manifesto: str

    @property
    def raiz(self) -> Path:
        return self.comparacao.raiz

    @property
    def tabelas(self) -> tuple[Tabela, ...]:
        return self.comparacao.tabelas

    @property
    def arquivos(self) -> tuple[str, ...]:
        return (*(tabela.nome for tabela in self.tabelas), ARQUIVO_MANIFESTO)


@dataclass(frozen=True)
class ResultadoComparacao:
    """
    O que a execução de fato escreveu.
    """

    criados: tuple[Path, ...] = ()
    arquivado: tuple[Path, Path] | None = None
    avisos: tuple[str, ...] = ()


# Casos de uso


def preparar_comparacao(
    raiz: Path,
    aba: str | None = None,
    conferir: bool = True,
    agora: datetime | None = None,
) -> PlanoComparacao:
    """
    Lê os itens da ficha, abre o banco, compara cada item e monta o plano. Não
    escreve nada.

    A lista da ficha é conferida **antes** de abrir o banco, como na correlação: um
    item escrito fora do formato — a vírgula decimal, principalmente — é o engano
    mais provável deste comando, e descobri-lo não deve custar a releitura do
    `sha256` de um banco grande.

    Args:
        raiz: a pasta do projeto (a que tem o `projeto.yaml`).
        aba: planilha do `.xlsx`, quando houver mais de uma.
        conferir: reler o `sha256` das versões e comparar com a ficha.
        agora: relógio injetável, como nas outras fases.

    Raises:
        FichaError, BancoError, DicionarioInvalidoError e as recusas declaradas
        acima.
    """
    raiz = Path(raiz)
    quando = agora or datetime.now()

    pedidos = itens_da_ficha(raiz)

    banco = abrir(raiz, aba=aba, conferir=conferir)
    ficha = ler_ficha(raiz)
    linhas = conferir_dicionario(
        raiz,
        banco,
        ausente=DicionarioAusenteError,
        desatualizado=DicionarioDesatualizadoError,
        analise="a comparação",
    )
    comparacao = comparar(banco, ficha, linhas, pedidos, quando)

    pasta = pasta_da_analise(raiz, PASTA_COMPARACAO)
    manifesto = montar_manifesto(comparacao, linhas)

    return PlanoComparacao(
        comparacao=comparacao,
        pasta=pasta,
        arquivamento=arquivamento_da_rodada(raiz, pasta, quando, PASTA_COMPARACAO),
        manifesto=manifesto,
        texto_manifesto=texto_do_manifesto(manifesto),
    )


def executar_comparacao(plano: PlanoComparacao) -> ResultadoComparacao:
    """
    Escreve o plano no disco. Não decide mais nada.

    A ordem é a da Fase 5: arquiva a rodada anterior, cria a pasta, escreve as
    tabelas, e só então o `manifesto.json` — o recibo vem depois do que ele descreve.
    Uma falha no meio desfaz o que já foi feito, inclusive devolvendo a pasta
    arquivada ao lugar, e a exceção continua subindo inteira.
    """
    criados: list[Path] = []
    avisos: list[str] = []
    desfazer: list[Any] = []
    arquivado: tuple[Path, Path] | None = None

    try:
        if plano.arquivamento is not None:
            de, para = plano.arquivamento
            para.parent.mkdir(parents=True, exist_ok=True)
            de.rename(para)
            arquivado = (de, para)
            desfazer.append(lambda d=de, p=para: p.rename(d))

        # `existia` antes do `mkdir`: a pasta só entra no desfazer quando foi este
        # comando que a criou, e o `rmdir` é registrado antes dos arquivos — o
        # desfazer roda ao contrário e a pasta sai vazia, a única forma de sair.
        existia = plano.pasta.is_dir()
        plano.pasta.mkdir(parents=True, exist_ok=True)
        criados.append(plano.pasta)
        if not existia:
            desfazer.append(lambda p=plano.pasta: p.rmdir())

        for tabela in plano.tabelas:
            caminho = plano.pasta / tabela.nome
            escrever_atomico(caminho, tabela.texto())
            criados.append(caminho)
            desfazer.append(lambda p=caminho: p.unlink(missing_ok=True))

        caminho = plano.pasta / ARQUIVO_MANIFESTO
        escrever_atomico(caminho, plano.texto_manifesto)
        criados.append(caminho)
        desfazer.append(lambda p=caminho: p.unlink(missing_ok=True))

        try:
            anotar(plano.raiz, _acao_do_historico(plano), plano.comparacao.quando)
        except OSError as erro:
            avisos.append(
                "A comparação foi escrita, mas não consegui escrever no "
                f"historico.md: {erro}"
            )

    except Exception:
        for passo in reversed(desfazer):
            try:
                passo()
            except OSError:
                avisos.append(
                    "Falhei ao desfazer uma etapa. Confira "
                    f"{PASTA_ANALISES}/{PASTA_COMPARACAO} e {PASTA_ANTIGAS} antes "
                    "de rodar de novo."
                )
        raise

    return ResultadoComparacao(
        criados=tuple(criados), arquivado=arquivado, avisos=tuple(avisos)
    )


def comparar(
    banco: Banco,
    ficha: Ficha,
    linhas_do_dicionario: Sequence[Linha],
    pedidos: Sequence[Pedido | tuple[Any, ...]],
    quando: datetime | None = None,
) -> Comparacao:
    """
    Compara cada item pedido, obedecendo ao dicionário. Função pura.

    O miolo testável, como o `correlacionar` da correlação e o `avaliar` da
    normalidade: um `DataFrame` montado à mão, uma lista de `Linha` e os itens
    entram, e as afirmações são sobre as tabelas — sem pasta de projeto e sem disco.

    Duas conferências: a da ficha contra o dicionário, antes de tocar nos valores, e a
    dos grupos contra o banco — quantos grupos a variável tem entre os casos com as
    duas respostas —, que só se faz com os valores na mão. As duas listam todos os
    problemas de uma vez.

    Args:
        pedidos: os itens como `itens_da_ficha` os devolve — ou tuplas, que é como um
            teste os escreve: `("imc", 25)`, `("imc", 25, "t")`, `("imc", "sexo")`,
            `("imc", "sexo", "student")`.

    Raises:
        SemItensError, ItemInvalidoError, VariavelIncompativelError
    """
    quadro = banco.quadro
    total = int(quadro.shape[0])

    if not pedidos:
        raise SemItensError(_mensagem_sem_itens(linhas_do_dicionario))

    perguntas = _conferir_itens(
        [_como_pedido(item) for item in pedidos], linhas_do_dicionario
    )

    # Só as variáveis da lista vão para a recusa: a conferência é a da Fase 5, e o
    # escopo é deste comando.
    envolvidas: list[Linha] = []
    for pergunta in perguntas:
        for linha in pergunta.linhas:
            if linha not in envolvidas:
                envolvidas.append(linha)
    recusar_incompativeis(quadro, envolvidas, erro=VariavelIncompativelError)

    comparadas: list[VariavelComparada] = []
    problemas: list[str] = []
    for pergunta in perguntas:
        if pergunta.medidas:
            comparadas.append(_comparar_repetidas(quadro, pergunta, total))
            continue
        if pergunta.grupos is None:
            comparadas.append(_comparar_uma_amostra(quadro, pergunta, total))
            continue
        comparada, problema = _comparar_grupos(quadro, pergunta, total)
        if comparada is None:
            problemas.append(f"  {_pedido_de(pergunta).escrito} — {problema}")
        else:
            comparadas.append(comparada)

    if problemas:
        raise ItemInvalidoError(
            f"A lista `{PASTA_COMPARACAO}:` do {ARQUIVO_PROJETO} tem {len(problemas)} "
            "item(ns) que este banco não deixa comparar. Nada foi gerado.\n\n"
            + "\n".join(problemas)
        )

    variaveis = tuple(comparadas)
    nas_perguntas = {coluna for variavel in variaveis for coluna in variavel.colunas}
    fora = tuple(
        ForaDaComparacao(linha.variavel, linha.tipo, _motivo_de_fora(linha))
        for linha in linhas_do_dicionario
        if linha.variavel not in nas_perguntas
    )

    avisos = list(banco.avisos)
    avisos += [aviso for variavel in variaveis for aviso in variavel.avisos]

    return Comparacao(
        ficha=ficha,
        banco=banco,
        variaveis=variaveis,
        fora=fora,
        avisos=tuple(avisos),
        quando=quando or datetime.now(),
        tabelas=_tabelas(variaveis, total),
    )


# Uma variável, contra a referência


def _comparar_uma_amostra(
    quadro: pd.DataFrame, pergunta: Pergunta, total: int
) -> VariavelComparada:
    """
    Mede o pressuposto, aplica a regra (ou obedece à ficha) e calcula.

    Os faltantes são **por variável**: entram os valores preenchidos desta coluna, e o
    `n` da linha é quantos são. É o mesmo tratamento da normalidade e da descritiva, e
    é o que faz a média daqui ser a do `resumo` e o p do Shapiro-Wilk ser o da tabela
    de normalidade.

    Três barreiras vêm antes da regra, e as três deixam a linha sem teste qualquer que
    seja o método escrito na ficha — são as do próprio `t.test` do R: nenhum valor,
    um valor só, e valores que não variam. Valem para o Wilcoxon também, que o R
    calcularia com um valor só, ou com todos iguais: um valor não é uma amostra, e uma
    variável que não varia não tem o que comparar.
    """
    linha = pergunta.linha
    serie = _coluna(quadro, linha.variavel)
    if serie is None:  # pragma: no cover - `recusar_incompativeis` já barrou
        raise VariavelIncompativelError(f"`{linha.variavel}` não existe no banco.")

    referencia = float(pergunta.referencia or 0.0)
    valores = serie.dropna().astype("float64")
    validos = int(valores.shape[0])
    base: dict[str, Any] = {
        "variavel": linha.variavel,
        "rotulo": _rotulo(linha),
        "referencia": referencia,
        "total": total,
        "validos": validos,
        "distintos": int(valores.nunique()),
        "delineamento": UMA_AMOSTRA,
        "resumo": resumo_numerico(valores) if validos else None,
        "casas": _casas_da_coluna(serie),
    }
    nome = f"`{linha.variavel}`"

    impedimento = _impedimento(valores, validos, base["distintos"])
    if impedimento:
        aviso = f"{nome}: {impedimento}. A linha saiu sem teste."
        if base["distintos"] == 1:
            aviso += " Uma variável que não varia costuma ser critério de inclusão do estudo."
        return VariavelComparada(**base, motivo=impedimento, avisos=(aviso,))

    normal = _normal(linha.variavel, valores)
    escolha = regra(UMA_AMOSTRA, normal)
    if pergunta.metodo:
        escolha = replace(
            escolha, metodo=metodo_escrito(pergunta.metodo, UMA_AMOSTRA), pela_ficha=True
        )

    avisos = _avisos_da_linha(nome, pergunta, escolha, normal, validos, base["distintos"])

    if not escolha.metodo:
        return VariavelComparada(
            **base,
            normal=normal,
            escolha=escolha,
            motivo=_motivo_sem_teste(normal, validos),
            avisos=avisos,
        )

    calcular = _CALCULO[(UMA_AMOSTRA, escolha.metodo)]
    resultado = calcular(valores.to_numpy(), referencia)
    return VariavelComparada(
        **base,
        normal=normal,
        escolha=escolha,
        resultado=resultado,
        avisos=avisos + _avisos_do_resultado(nome, resultado, (validos,), f"{validos} valores"),
    )


def _impedimento(valores: pd.Series, validos: int, distintos: int) -> str:
    """
    O motivo de não haver teste nenhum, ou vazio.

    As barreiras do `t.test`, com a frase de cada uma no lugar do `stop()` do R. A
    terceira usa o critério do R, e não "todos iguais": ver `hipoteses.sem_variacao`.
    """
    if not validos:
        return "nenhum valor preenchido"
    if validos < MINIMO_T:
        return f"{validos} valor — o teste precisa de pelo menos {MINIMO_T}"
    if sem_variacao(valores.to_numpy()):
        if distintos < 2:
            return "um valor só em todas as linhas"
        return "os valores praticamente não variam"
    return ""


def _normal(variavel: str, valores: pd.Series) -> Normal:
    """
    O Shapiro-Wilk da normalidade, pela mesma função, sobre os valores preenchidos.
    """
    w, p, impedimento, aviso = shapiro(variavel, valores, int(valores.shape[0]))
    return Normal(w=w, p=p, impedimento=impedimento, aviso=aviso)


def _motivo_sem_teste(normal: Normal, validos: int) -> str:
    """
    O motivo curto, para a célula da coluna `teste`, quando a regra escolheu um teste
    que ainda não existe. A frase inteira, com o p do Shapiro-Wilk, vai para as notas.

    **Sem o p na célula**, e foi a página que decidiu: na coluna estreita do documento
    `(p < 0,001)` quebrava entre o `<` e o número, e a célula ocupava quatro linhas
    para repetir o que a tabela de normalidade do mesmo documento já imprime.
    """
    if normal.testada:
        return "normal rejeitada"
    return f"normalidade não verificável com {validos} valores"


def _avisos_da_linha(
    nome: str,
    pergunta: Pergunta,
    escolha: Escolha,
    normal: Normal,
    validos: int,
    distintos: int,
) -> tuple[str, ...]:
    """
    O que a escolha precisa levar junto para o terminal e para o manifesto.

    Cinco casos, e cada um é um engano conhecido ou uma decisão que precisa de rastro:

    * **a linha sem teste porque o teste da regra ainda não existe.** O aviso diz como
      escrever `t` no item, para quando você concluir que ele vale ali;
    * **a ficha contra a regra.** A decisão é sua, e o aviso é o registro de que ela
      foi tomada contra o que a regra diria;
    * **o t pela regra com poucos valores.** Abaixo de `MINIMO_CONFIAVEL` o
      Shapiro-Wilk quase não rejeita, e a regra escolheu o t por falta de evidência
      contra ele — não por evidência a favor;
    * **a variável discreta com a normal rejeitada.** Numa escala o Shapiro-Wilk
      rejeita quase sempre, e a rejeição diz «discreta», e não «forma errada»;
    * **o recado do `scipy` sobre o Shapiro-Wilk**, repassado como ele veio.
    """
    avisos: list[str] = []
    faltou = "" if _disponivel(UMA_AMOSTRA, escolha.da_regra) else (
        ", que ainda não está no FlatCap"
    )
    if not escolha.metodo:
        avisos.append(
            f"{nome}: {escolha.motivo} — a regra escolheria {escolha.da_regra}{faltou}, e "
            "a linha saiu sem teste. Se o t vale aqui — n grande e assimetria pequena, "
            "por exemplo —, escreva o método no item: "
            f"`{replace(_pedido_de(pergunta), metodo='t').escrito}`."
        )
    if escolha.contra_a_regra:
        avisos.append(_aviso_contra_a_regra(nome, escolha, faltou))
    if (
        escolha.metodo == T_DE_STUDENT
        and not escolha.pela_ficha
        and validos < MINIMO_CONFIAVEL
    ):
        avisos.append(
            f"{nome}: t de Student com {validos} valores. Abaixo de {MINIMO_CONFIAVEL} o "
            "Shapiro-Wilk quase não rejeita — «não rejeitou» aí não é evidência de "
            "normalidade. Confira o histograma da descritiva e o Q-Q da normalidade "
            "antes de ficar com ele."
        )
    if normal.rejeita and distintos <= POUCOS_DISTINTOS and distintos < validos:
        avisos.append(_aviso_de_discreta(nome, distintos, validos))
    if normal.aviso and normal.aviso not in avisos:
        avisos.append(normal.aviso)
    return tuple(avisos)


def _aviso_contra_a_regra(nome: str, escolha: Escolha, faltou: str) -> str:
    return (
        f"{nome}: {escolha.metodo} {_concorda(escolha.metodo, 'escrito')} na ficha, contra "
        "a regra — ela escolheria "
        f"{escolha.da_regra}{faltou}: {escolha.motivo}. Fica o que está na ficha, e a "
        "frase vai para as notas do .csv."
    )


def _aviso_de_discreta(nome: str, distintos: int, validos: int) -> str:
    return (
        f"{nome}: {distintos} valores distintos em {validos} casos. O Shapiro-Wilk "
        "supõe variável contínua e rejeita a normal quase sempre numa escala — a "
        "rejeição aí diz «esta variável é discreta», e não «a forma dela está "
        "errada»."
    )


def _avisos_do_resultado(
    nome: str, resultado: Resultado, tamanhos: Sequence[int], valores: str
) -> tuple[str, ...]:
    """
    O que o Wilcoxon e o Mann-Whitney devolvem e precisa de rastro — os três casos são
    de amostra pequena, ou de amostra sem variação, e nenhum deles é erro:

    * **o menor p possível acima do α.** No caminho exato, o p mais extremo que a
      distribuição tem é 2/2ⁿ no Wilcoxon e 2/C(n₁ + n₂, n₁) no Mann-Whitney; com cinco
      valores ou menos no Wilcoxon — e, no Mann-Whitney, com um valor contra até 38,
      dois contra até sete, ou três contra até quatro —, ele passa de 0,05, e o teste não
      rejeita a igualdade com dado nenhum. Um p de 0,125 ali não é «nenhuma diferença»:
      é o menor que existe;
    * **o intervalo que não chega a 95%** — o R baixa o nível e avisa. A tabela promete
      95%, e a célula sai com o traço;
    * **o intervalo que não existe**: sem os valores iguais à referência, os que sobram
      são todos iguais; ou os dois grupos não variam por dentro. O p sai, e a célula,
      com o traço.

    `tamanhos` são os n do teste — o da uma amostra, ou o de cada grupo —, e `valores`,
    como eles se escrevem na frase.
    """
    if resultado.metodo not in (WILCOXON, MANN_WHITNEY):
        return ()
    menor = _menor_p_exato(resultado.metodo, tamanhos) if resultado.exato else 0.0
    nivel = resultado.confianca_do_ic
    sem_95 = resultado.ic is not None and nivel is not None and nivel < CONFIANCA
    if menor > ALFA or sem_95:
        partes: list[str] = []
        if menor > ALFA:
            partes.append(
                f"o menor p que ele pode dar é {valor_p(menor)}, acima de {numero(ALFA)}"
            )
        if sem_95:
            alcance = (
                f"o mais largo que existe tem {numero(100 * nivel, 1)}%"
                if nivel
                else "não há intervalo nenhum"
            )
            partes.append(f"o intervalo de 95% não é alcançável — {alcance}")
        conclusao = (
            " Com tão poucos valores, o teste não rejeita a igualdade com dado nenhum."
            if menor > ALFA
            else ""
        )
        celula = " A célula do intervalo sai com —." if sem_95 else ""
        return (
            f"{nome}: {resultado.metodo} com {valores} — {', e '.join(partes)}."
            f"{conclusao}{celula}",
        )
    if resultado.ic is None:
        if resultado.metodo == WILCOXON:
            return (
                f"{nome}: sem os valores iguais à referência, os que sobram são todos "
                "iguais — a pseudomediana e o intervalo dela não existem, e a célula sai "
                "com —. O p do Wilcoxon sai.",
            )
        return (
            f"{nome}: os grupos não variam por dentro — a diferença de locação e o "
            "intervalo dela não existem, e a célula sai com —. O p do Mann-Whitney sai.",
        )
    return ()


def _menor_p_exato(metodo: str, tamanhos: Sequence[int]) -> float:
    """
    O menor p bilateral que o caminho exato dá: as duas caudas mais extremas da
    distribuição, com uma combinação cada — 2/2ⁿ no Wilcoxon, 2/C(n₁ + n₂, n₁) no
    Mann-Whitney —, e nunca acima de 1.
    """
    if metodo == WILCOXON:
        return min(1.0, 2 / 2 ** tamanhos[0])
    primeiro, segundo = tamanhos
    return min(1.0, 2 / math.comb(primeiro + segundo, primeiro))


# Uma variável, entre os grupos de outra


def _comparar_grupos(
    quadro: pd.DataFrame, pergunta: Pergunta, total: int
) -> tuple[VariavelComparada | None, str]:
    """
    Separa os grupos, mede o pressuposto em cada um, aplica a regra (ou obedece à
    ficha) e calcula. Devolve a comparação, ou `None` e a frase do que este banco não
    deixa comparar — que o `comparar` junta às dos outros itens numa recusa só.

    **Os faltantes são por comparação**: entra quem respondeu as duas variáveis, e o
    `n` da comparação é quantos são. **O código conta, o rótulo imprime**, como no
    cruzamento e na associação: os grupos são os rótulos, e dois códigos com o mesmo
    rótulo somam no mesmo grupo. A ordem é a do dicionário, e é ela que decide o sinal
    da diferença: o primeiro grupo menos o segundo, como o `t.test` da fórmula do R
    faz com os níveis do fator.

    Três barreiras vêm antes da regra — nenhum caso com as duas respostas, um grupo
    só, um valor só em todas as linhas —, e as do teste escolhido vêm depois dela:
    cada teste tem o seu mínimo no R.
    """
    linha = pergunta.linha
    de_grupo = pergunta.grupos
    assert de_grupo is not None
    serie = _coluna(quadro, linha.variavel)
    coluna_do_grupo = _coluna(quadro, de_grupo.variavel)
    if serie is None or coluna_do_grupo is None:  # pragma: no cover - a recusa já barrou
        raise VariavelIncompativelError(
            f"`{linha.variavel}` ou `{de_grupo.variavel}` não existe no banco."
        )

    respondeu = serie.notna() & coluna_do_grupo.notna()
    valores = serie[respondeu].astype("float64")
    rotulos = pd.Series(
        [de_grupo.rotulo_de(codigo) for codigo in serie_de_texto(coluna_do_grupo[respondeu])],
        index=valores.index,
        dtype="object",
    )
    ordem = na_ordem_do_dicionario(set(rotulos), de_grupo)
    quantos = len(ordem)

    delineamento = _delineamento_dos_grupos(quantos, de_grupo)

    metodo = ""
    if pergunta.metodo and quantos >= 2:
        metodo = _teste_da_chave(pergunta.metodo, delineamento)
        problema = _problema_do_metodo(pergunta.metodo, metodo, delineamento, de_grupo, quantos)
        if problema:
            return None, problema

    amostras = tuple(valores[rotulos == rotulo] for rotulo in ordem)
    validos = int(valores.shape[0])
    distintos = int(valores.nunique())
    grupos = tuple(
        Grupo(rotulo=rotulo, n=int(amostra.shape[0]), resumo=resumo_numerico(amostra))
        for rotulo, amostra in zip(ordem, amostras, strict=True)
    )
    base: dict[str, Any] = {
        "variavel": linha.variavel,
        "rotulo": _rotulo(linha),
        "referencia": None,
        "total": total,
        "validos": validos,
        "distintos": distintos,
        "delineamento": delineamento,
        "variavel_de_grupo": de_grupo.variavel,
        "rotulo_de_grupo": _rotulo(de_grupo),
        "casas": _casas_da_coluna(serie),
    }
    nome = f"`{linha.variavel}` por `{de_grupo.variavel}`"

    impedimento = _impedimento_dos_grupos(validos, quantos, distintos)
    if impedimento:
        aviso = f"{nome}: {impedimento}. A linha saiu sem teste."
        if quantos == 1:
            aviso += (
                f" Os {validos} casos com as duas respostas são todos {ordem[0]} — não há "
                "o que comparar."
            )
        if distintos == 1:
            aviso += " Uma variável que não varia costuma ser critério de inclusão do estudo."
        return VariavelComparada(**base, grupos=grupos, motivo=impedimento, avisos=(aviso,)), ""

    grupos = tuple(
        replace(grupo, normal=_normal_do_grupo(linha.variavel, grupo.rotulo, amostra))
        for grupo, amostra in zip(grupos, amostras, strict=True)
    )
    escolha = regra(delineamento, grupos)
    if metodo:
        escolha = replace(escolha, metodo=metodo, pela_ficha=True)

    avisos = list(
        _avisos_dos_grupos(nome, pergunta, escolha, grupos, delineamento, validos, distintos)
    )

    if not escolha.metodo:
        return VariavelComparada(
            **base,
            grupos=grupos,
            escolha=escolha,
            motivo=_motivo_sem_teste_dos_grupos(escolha, grupos, delineamento),
            avisos=tuple(avisos),
        ), ""

    impedimento = _impedimento_do_teste(escolha.metodo, amostras, grupos)
    if impedimento:
        avisos.append(f"{nome}: {impedimento}. A linha saiu sem teste.")
        return VariavelComparada(
            **base, grupos=grupos, escolha=escolha, motivo=impedimento, avisos=tuple(avisos)
        ), ""

    calcular = _CALCULO[(delineamento, escolha.metodo)]
    vetores = [amostra.to_numpy() for amostra in amostras]
    resultado = calcular(vetores) if delineamento == K_GRUPOS else calcular(*vetores)
    avisos += _avisos_do_resultado(
        nome,
        resultado,
        tuple(grupo.n for grupo in grupos),
        _em_frase(f"{grupo.n} valores em {grupo.rotulo}" for grupo in grupos),
    )
    return VariavelComparada(
        **base,
        grupos=grupos,
        escolha=escolha,
        resultado=resultado,
        avisos=tuple(avisos),
    ), ""


def _delineamento_dos_grupos(quantos: int, de_grupo: Linha) -> str:
    """
    O delineamento pelo número de grupos com resposta: dois, ou três ou mais.

    Com nenhum grupo ou um só, não há teste, e a linha sai na tabela que o dicionário
    promete — a dos k grupos quando ele declara três rótulos ou mais, e a dos dois nos
    outros casos: a pergunta foi feita sobre aqueles grupos, e o banco não os tem.
    """
    if quantos == 2:
        return DOIS_GRUPOS
    if quantos >= 3:
        return K_GRUPOS
    declarados = {de_grupo.rotulo_de(codigo) for codigo in de_grupo.categorias_ordem}
    return K_GRUPOS if len(declarados) >= 3 else DOIS_GRUPOS


def _impedimento_dos_grupos(validos: int, quantos: int, distintos: int) -> str:
    """
    O motivo de não haver teste nenhum entre grupos, ou vazio. Vale para qualquer
    teste, escrito na ficha ou não.
    """
    if not validos:
        return "nenhum caso com as duas respostas"
    if quantos < 2:
        return "um grupo só"
    if distintos < 2:
        return "um valor só em todas as linhas"
    return ""


def _impedimento_do_teste(
    metodo: str, amostras: Sequence[pd.Series], grupos: Sequence[Grupo]
) -> str:
    """
    O motivo de o teste escolhido não rodar, ou vazio — as barreiras do R para ele,
    que mudam de teste para teste.

    O t de Student aceita um grupo de um valor só, desde que haja três no total: a
    variância combinada é toda do outro grupo, e o R calcula. O de Welch não: cada
    grupo entra com a sua variância, e a de um valor só não existe. Os dois recusam,
    como o R, dois grupos que não variam por dentro — mesmo com médias diferentes, o t
    seria uma divisão por zero.

    A ANOVA pede dois valores em cada grupo, como o `oneway.test` — que recusa o grupo
    de um valor, embora o `aov` o aceite. E grupos que não variam por dentro a barram
    aqui, e não no R: lá o F sai infinito, e o p, zero. Na de Welch basta **um** grupo
    que não varia — o peso dele é n/0, e o R devolve `NaN`; a clássica, com a variância
    combinada dos outros, roda.

    O Mann-Whitney e o Kruskal-Wallis não têm barreira além das que valem para todos:
    pedem um valor em cada grupo, como o R, e grupos que não variam por dentro, cada um
    com o seu valor, são para eles a separação mais clara que existe — e não uma divisão
    por zero.
    """
    if metodo == T_DE_WELCH:
        primeiro, segundo = (amostra.to_numpy() for amostra in amostras)
        pequenos = [grupo for grupo in grupos if grupo.n < MINIMO_T]
        if pequenos:
            return (
                f"{pequenos[0].rotulo} tem {pequenos[0].n} valor — o t de Welch precisa de "
                f"pelo menos {MINIMO_T} em cada grupo"
            )
        if sem_variacao_em_duas(primeiro, segundo, variancias_iguais=False):
            return _sem_variacao_nos_grupos(amostras)
    if metodo == ANOVA_DE_WELCH:
        pequenos = [grupo for grupo in grupos if grupo.n < MINIMO_T]
        if pequenos:
            return (
                f"{pequenos[0].rotulo} tem {pequenos[0].n} valor — a ANOVA de Welch precisa "
                f"de pelo menos {MINIMO_T} em cada grupo"
            )
        constantes = [
            grupo
            for grupo, amostra in zip(grupos, amostras, strict=True)
            if sem_variacao(amostra.to_numpy())
        ]
        if constantes:
            return (
                f"{constantes[0].rotulo} não varia — a ANOVA de Welch divide pela variância "
                "de cada grupo"
            )
    if metodo == ANOVA:
        pequenos = [grupo for grupo in grupos if grupo.n < MINIMO_T]
        if pequenos:
            return (
                f"{pequenos[0].rotulo} tem {pequenos[0].n} valor — a ANOVA precisa de pelo "
                f"menos {MINIMO_T} em cada grupo"
            )
        vetores = [amostra.to_numpy() for amostra in amostras]
        if sem_variacao_nos_grupos(vetores, variancias_iguais=True):
            return _sem_variacao_nos_grupos(amostras)
    if metodo == T_DE_STUDENT:
        primeiro, segundo = (amostra.to_numpy() for amostra in amostras)
        if primeiro.shape[0] + segundo.shape[0] < MINIMO_STUDENT:
            return (
                f"um valor em cada grupo — o t de Student precisa de pelo menos "
                f"{MINIMO_STUDENT} no total"
            )
        if sem_variacao_em_duas(primeiro, segundo, variancias_iguais=True):
            return _sem_variacao_nos_grupos(amostras)
    return ""


def _sem_variacao_nos_grupos(amostras: Sequence[pd.Series]) -> str:
    if all(int(amostra.nunique()) < 2 for amostra in amostras):
        return "os valores não variam dentro dos grupos"
    return "os valores praticamente não variam"


def _normal_do_grupo(
    variavel: str, rotulo: str, valores: pd.Series, onde: str = "no grupo"
) -> Normal:
    """
    O Shapiro-Wilk de um grupo — ou de uma medida, nas repetidas —, pela mesma função
    da normalidade.

    O grupo que não varia é barrado aqui, e não lá: a frase e o aviso do
    `normalidade.shapiro` para esse caso falam da **coluna** ("a coluna tem um valor
    só"), e aqui a coluna varia — quem não varia é o grupo, ou a medida entre os casos
    completos.
    """
    preenchidos = int(valores.shape[0])
    if preenchidos >= MINIMO_SHAPIRO and int(valores.nunique()) < 2:
        return Normal(w=None, p=None, impedimento=f"um valor só {onde}")
    nome = f"{variavel} em {rotulo}" if rotulo else variavel
    w, p, impedimento, aviso = shapiro(nome, valores, preenchidos)
    return Normal(w=w, p=p, impedimento=impedimento, aviso=aviso)


def _motivo_sem_teste_dos_grupos(
    escolha: Escolha, grupos: Sequence[Grupo], delineamento: str
) -> str:
    """
    O motivo curto, para a célula, quando a regra escolheu um teste que ainda não
    existe. Sem o p, pela mesma razão da uma amostra; a frase inteira vai para as
    notas.
    """
    if escolha.da_regra == REGRA[delineamento][0]:
        return f"{escolha.da_regra} ainda não está no FlatCap"
    if any(grupo.normal is not None and grupo.normal.rejeita for grupo in grupos):
        return "normal rejeitada"
    sem_teste = [g for g in grupos if g.normal is None or not g.normal.testada]
    if len(sem_teste) == 1:
        return f"normalidade não verificável em {sem_teste[0].rotulo}"
    return f"normalidade não verificável em {len(sem_teste)} {_unidades(delineamento)[1]}"


def _avisos_dos_grupos(
    nome: str,
    pergunta: Pergunta,
    escolha: Escolha,
    grupos: Sequence[Grupo],
    delineamento: str,
    validos: int,
    distintos: int,
) -> tuple[str, ...]:
    """
    Os avisos da uma amostra, na forma dos grupos, e um a mais.

    * **a linha sem teste** diz qual método escrever no item: o paramétrico da regra
      quando ele existe, senão o que existe — a `anova` clássica, onde a de Welch
      ainda falta;
    * **a ficha contra a regra**, como na uma amostra;
    * **o paramétrico pela regra com um grupo pequeno** — o Shapiro-Wilk de cada
      grupo é que quase não rejeita abaixo de `MINIMO_CONFIAVEL`;
    * **a variável discreta com a normal rejeitada**, como na uma amostra;
    * **o teste que supõe variâncias iguais**, com o maior desvio padrão contra o
      menor: é o que o de Welch dispensaria, e o número fica escrito para quem
      escolheu o de Student;
    * **o recado do `scipy`**, de cada grupo.
    """
    avisos: list[str] = []
    faltou = "" if _disponivel(delineamento, escolha.da_regra) else (
        ", que ainda não está no FlatCap"
    )
    if not escolha.metodo:
        chave, teste = _metodo_sugerido(delineamento)
        escrito = replace(_pedido_de(pergunta), metodo=chave).escrito
        if escolha.da_regra == REGRA[delineamento][0]:
            avisos.append(
                f"{nome}: {escolha.motivo} — a regra escolheria {escolha.da_regra}{faltou}, "
                f"e a linha saiu sem teste. {_com_artigo(teste, maiuscula=True)}, que supõe "
                f"a mesma variância nos grupos, roda com o método escrito no item: "
                f"`{escrito}`."
            )
        else:
            avisos.append(
                f"{nome}: {escolha.motivo} — a regra escolheria {escolha.da_regra}{faltou}, "
                f"e a linha saiu sem teste. Se {_com_artigo(teste)} vale aqui — n grande "
                f"em cada grupo e assimetria pequena, por exemplo —, escreva o método no "
                f"item: `{escrito}`."
            )
    if escolha.contra_a_regra:
        avisos.append(_aviso_contra_a_regra(nome, escolha, faltou))
    pequenos = [grupo for grupo in grupos if grupo.n < MINIMO_CONFIAVEL]
    if escolha.metodo and not escolha.pela_ficha and pequenos:
        avisos.append(
            f"{nome}: {escolha.metodo} com "
            + _em_frase(f"{grupo.n} valores em {grupo.rotulo}" for grupo in pequenos)
            + f". Abaixo de {MINIMO_CONFIAVEL} o Shapiro-Wilk quase não rejeita — «não "
            "rejeitou» aí não é evidência de normalidade. Confira a forma de cada grupo "
            "antes de ficar com ele."
        )
    rejeita = any(grupo.normal is not None and grupo.normal.rejeita for grupo in grupos)
    if rejeita and distintos <= POUCOS_DISTINTOS and distintos < validos:
        avisos.append(_aviso_de_discreta(nome, distintos, validos))
    if (delineamento, escolha.metodo) in _VARIANCIAS_IGUAIS:
        aviso = _aviso_de_variancias(nome, escolha.metodo, grupos, delineamento)
        if aviso:
            avisos.append(aviso)
    for grupo in grupos:
        if grupo.normal is not None and grupo.normal.aviso and grupo.normal.aviso not in avisos:
            avisos.append(grupo.normal.aviso)
    return tuple(avisos)


def _aviso_de_variancias(
    nome: str, metodo: str, grupos: Sequence[Grupo], delineamento: str
) -> str:
    """
    O maior desvio padrão contra o menor, quando o teste supõe variâncias iguais e
    eles passam de `RAZAO_DE_DESVIOS` — ou quando um grupo não varia.

    Só os grupos com dois valores ou mais: o desvio de um valor só sai zero no
    `resumo`, e não diz nada sobre a variância.
    """
    desvios = [
        (grupo.rotulo, float((grupo.resumo or {}).get("desvio", 0.0)))
        for grupo in grupos
        if grupo.n >= 2
    ]
    if len(desvios) < 2:
        return ""
    maior = max(desvios, key=lambda par: par[1])
    menor = min(desvios, key=lambda par: par[1])
    casas = max((casas_do_resumo(grupo.resumo) for grupo in grupos), default=CASAS_IC)
    parametrico = REGRA[delineamento][0]
    falta = "" if _disponivel(delineamento, parametrico) else (
        ", que ainda não está no FlatCap,"
    )
    suposto = f"{nome}: {_com_artigo(metodo)} supõe a mesma variância nos grupos"
    outro = f"{_com_artigo(parametrico, maiuscula=True)}{falta} não supõe."
    if menor[1] == 0:
        return f"{suposto}, e {menor[0]} não varia. {outro}"
    razao = maior[1] / menor[1]
    if razao < RAZAO_DE_DESVIOS:
        return ""
    return (
        f"{suposto}, e o desvio padrão de {maior[0]} ({numero(maior[1], casas)}) é "
        f"{numero(razao, 1)} vezes o de {menor[0]} ({numero(menor[1], casas)}). {outro}"
    )


def _metodo_sugerido(delineamento: str) -> tuple[str, str]:
    """
    O método para o aviso ensinar a escrever: o paramétrico da regra, quando ele
    existe, e senão o primeiro paramétrico que existe — o nome como se escreve e o
    teste.
    """
    parametrico = REGRA[delineamento][0]
    candidatos = [
        (chave, testes[delineamento])
        for chave, testes in METODOS.items()
        if delineamento in testes and _disponivel(delineamento, testes[delineamento])
    ]
    for chave, teste in candidatos:
        if teste == parametrico:
            return chave, teste
    return candidatos[0]


def _problema_do_metodo(
    chave: str, teste: str, delineamento: str, de_grupo: Linha, quantos: int
) -> str:
    """
    O método escrito que não serve para o número de grupos que o banco trouxe, ou
    vazio. A ficha é conferida antes de abrir o banco, mas só o banco diz quantos
    grupos há — e um método de dois grupos numa variável de três é recusado aqui.
    """
    if not teste:
        troca, porque = _EQUIVALENTES.get((chave, delineamento), ("", ""))
        da_troca = _teste_da_chave(troca, delineamento) if troca else ""
        if not da_troca or not _disponivel(delineamento, da_troca):
            troca = _metodo_sugerido(delineamento)[0]
        dica = f" — {porque}; escreva `{troca}`" if porque else f" — escreva `{troca}`"
        return (
            f"`{chave}` não se aplica a {quantos} grupos, e `{de_grupo.variavel}` tem "
            f"{quantos} entre os casos com as duas respostas{dica}"
        )
    if not _disponivel(delineamento, teste):
        return f"{_com_artigo(teste)} ainda não está no FlatCap"
    return ""


# As medidas repetidas


def _comparar_repetidas(
    quadro: pd.DataFrame, pergunta: Pergunta, total: int
) -> VariavelComparada:
    """
    As mesmas pessoas, medidas k vezes: mede o pressuposto em cada medida, aplica a
    regra (ou obedece à ficha) e calcula.

    **Os faltantes são por item, e inteiros**: entra quem tem todas as medidas — o
    caso com uma faltando sai do item, como no `lm` do R, porque a ANOVA de medidas
    repetidas compara cada pessoa com ela mesma. O Shapiro-Wilk roda em cada medida,
    sobre esses casos: é a normalidade que o teste usa, e é a checagem por momento que
    se faz no R antes de uma ANOVA de medidas repetidas.

    Duas barreiras antes da regra — nenhum caso completo, ou um só, e um valor só em
    todas as células —, e a do teste escolhido depois dela: na ANOVA, medidas que não
    variam dentro dos casos, em que o F é uma divisão por zero; no Friedman, cada caso
    com o mesmo valor em todas as medidas, em que não há o que ordenar. Ver
    `_impedimento_das_medidas`.
    """
    medidas = pergunta.medidas
    colunas = [_coluna(quadro, linha.variavel) for linha in medidas]
    if any(coluna is None for coluna in colunas):  # pragma: no cover - a recusa já barrou
        raise VariavelIncompativelError("uma das medidas não existe no banco.")

    completos = pd.concat([coluna.notna() for coluna in colunas], axis=1).all(axis=1)
    valores = [coluna[completos].astype("float64") for coluna in colunas]
    validos = int(completos.sum())
    distintos = int(pd.concat(valores).nunique()) if validos else 0
    grupos = tuple(
        Grupo(
            rotulo=_rotulo(linha),
            n=validos,
            resumo=resumo_numerico(valor) if validos else None,
        )
        for linha, valor in zip(medidas, valores, strict=True)
    )
    base: dict[str, Any] = {
        "variavel": medidas[0].variavel,
        "rotulo": _rotulo(medidas[0]),
        "referencia": None,
        "total": total,
        "validos": validos,
        "distintos": distintos,
        "delineamento": REPETIDAS,
        "medidas": tuple(linha.variavel for linha in medidas),
        "casas": _casas_da_coluna(*colunas),
    }
    nome = f"`{_pedido_de(pergunta).escrito}`"

    impedimento = _impedimento_das_repetidas(validos, distintos)
    if impedimento:
        aviso = f"{nome}: {impedimento}. A linha saiu sem teste."
        if distintos == 1:
            aviso += " Uma variável que não varia costuma ser critério de inclusão do estudo."
        return VariavelComparada(**base, grupos=grupos, motivo=impedimento, avisos=(aviso,))

    grupos = tuple(
        replace(grupo, normal=_normal_do_grupo(linha.variavel, "", valor, onde="na medida"))
        for grupo, linha, valor in zip(grupos, medidas, valores, strict=True)
    )
    escolha = regra(REPETIDAS, grupos)
    if pergunta.metodo:
        escolha = replace(
            escolha, metodo=metodo_escrito(pergunta.metodo, REPETIDAS), pela_ficha=True
        )
    avisos = list(_avisos_das_repetidas(nome, pergunta, escolha, grupos, validos, distintos))

    if not escolha.metodo:
        return VariavelComparada(
            **base,
            grupos=grupos,
            escolha=escolha,
            motivo=_motivo_sem_teste_dos_grupos(escolha, grupos, REPETIDAS),
            avisos=tuple(avisos),
        )

    vetores = [valor.to_numpy() for valor in valores]
    motivo, aviso = _impedimento_das_medidas(escolha.metodo, vetores, pergunta)
    if motivo:
        avisos.append(f"{nome}: {aviso}")
        return VariavelComparada(
            **base, grupos=grupos, escolha=escolha, motivo=motivo, avisos=tuple(avisos)
        )

    calcular = _CALCULO[(REPETIDAS, escolha.metodo)]
    return VariavelComparada(
        **base,
        grupos=grupos,
        escolha=escolha,
        resultado=calcular(vetores),
        avisos=tuple(avisos),
    )


def _impedimento_das_medidas(
    metodo: str, vetores: Sequence[Any], pergunta: Pergunta
) -> tuple[str, str]:
    """
    A barreira do teste das medidas repetidas — o motivo curto e o aviso —, ou dois
    vazios. Cada teste tem a sua, e uma não é a outra:

    * **a ANOVA, quando as medidas não variam dentro dos casos** — cada caso mudando o
      mesmo tanto de uma medida para outra. A variação de erro é zero, e o F, uma
      divisão por zero. É justamente o caso em que o Friedman tem mais a dizer: todo
      caso ordena as medidas do mesmo jeito. O aviso ensina a escrevê-lo;
    * **o Friedman, quando cada caso tem o mesmo valor em todas as medidas.** Não há o
      que ordenar dentro de caso nenhum, e o qui-quadrado é 0/0 — o R devolve `NaN`.
    """
    if metodo == ANOVA_DE_MEDIDAS_REPETIDAS and sem_variacao_entre_medidas(vetores):
        motivo = "as medidas não variam dentro dos casos"
        escrito = replace(_pedido_de(pergunta), metodo="friedman").escrito
        return motivo, (
            f"{motivo} — cada caso muda o mesmo tanto de uma medida para outra, e o F é "
            "uma divisão por zero. A linha saiu sem teste. O Friedman, que olha só a "
            "ordem das medidas dentro de cada caso, roda com o método escrito no item: "
            f"`{escrito}`."
        )
    if metodo == FRIEDMAN and medidas_iguais_em_cada_caso(vetores):
        motivo = "cada caso tem o mesmo valor em todas as medidas"
        return motivo, (
            f"{motivo} — não há o que ordenar dentro de caso nenhum, e o qui-quadrado de "
            "Friedman é 0/0. A linha saiu sem teste."
        )
    return "", ""


def _impedimento_das_repetidas(validos: int, distintos: int) -> str:
    if not validos:
        return "nenhum caso com todas as medidas"
    if validos < MINIMO_T:
        return f"{validos} caso com todas as medidas — o teste precisa de pelo menos {MINIMO_T}"
    if distintos < 2:
        return "um valor só em todas as linhas"
    return ""


def _avisos_das_repetidas(
    nome: str,
    pergunta: Pergunta,
    escolha: Escolha,
    grupos: Sequence[Grupo],
    validos: int,
    distintos: int,
) -> tuple[str, ...]:
    """
    Os avisos dos grupos, na forma das medidas: a linha sem teste ensina a escrever o
    método no item — `metodo: anova`, na linha de baixo —; a ficha contra a regra; o
    teste pela regra com menos de `MINIMO_CONFIAVEL` casos; a variável discreta; e o
    recado do `scipy`. O das variâncias não entra: a ANOVA de medidas repetidas não
    supõe variâncias iguais entre as medidas, e a correção de Greenhouse-Geisser é
    justamente para quando a covariância foge da esfericidade.
    """
    avisos: list[str] = []
    faltou = "" if _disponivel(REPETIDAS, escolha.da_regra) else (
        ", que ainda não está no FlatCap"
    )
    if not escolha.metodo:
        chave, teste = _metodo_sugerido(REPETIDAS)
        escrito = replace(_pedido_de(pergunta), metodo=chave).escrito
        avisos.append(
            f"{nome}: {escolha.motivo} — a regra escolheria {escolha.da_regra}{faltou}, e a "
            f"linha saiu sem teste. Se {_com_artigo(teste)} vale aqui — n grande e "
            f"assimetria pequena, por exemplo —, escreva o método no item: `{escrito}`."
        )
    if escolha.contra_a_regra:
        avisos.append(_aviso_contra_a_regra(nome, escolha, faltou))
    if escolha.metodo and not escolha.pela_ficha and validos < MINIMO_CONFIAVEL:
        avisos.append(
            f"{nome}: {escolha.metodo} com {validos} casos. Abaixo de {MINIMO_CONFIAVEL} o "
            "Shapiro-Wilk quase não rejeita — «não rejeitou» aí não é evidência de "
            "normalidade. Confira a forma de cada medida antes de ficar com ela."
        )
    rejeita = any(grupo.normal is not None and grupo.normal.rejeita for grupo in grupos)
    total_de_valores = validos * len(grupos)
    if rejeita and distintos <= POUCOS_DISTINTOS and distintos < total_de_valores:
        avisos.append(_aviso_de_discreta(nome, distintos, total_de_valores))
    for grupo in grupos:
        if grupo.normal is not None and grupo.normal.aviso and grupo.normal.aviso not in avisos:
            avisos.append(grupo.normal.aviso)
    return tuple(avisos)


# A regra


def regra(delineamento: str, normal: Normal | Sequence[Grupo]) -> Escolha:
    """
    A regra dos pressupostos: o teste que ela escolhe, e o motivo.

    O Shapiro-Wilk não rejeitou → o paramétrico do delineamento. Rejeitou, ou não
    pôde ser verificado → o que dispensa a normal. Se esse ainda não tem aritmética,
    a `Escolha` sai com `metodo` vazio e `da_regra` preenchido: a linha fica sem teste,
    e a nota diz qual faltou.

    Na uma amostra recebe o `Normal` da variável; entre grupos, os `Grupo`, cada um
    com o seu — e a normal se sustenta quando se sustenta **em todos**: um grupo que
    rejeita basta para o paramétrico não valer.

    Não olha o método escrito na ficha: quem o aplica é quem chama, por cima do que a
    regra devolveu — e é assim que a nota consegue dizer o que a regra teria
    escolhido.
    """
    parametrico, sem_normal = REGRA[delineamento]
    if isinstance(normal, Normal):
        if not normal.testada:
            return _pela_regra(
                delineamento,
                sem_normal,
                f"a normalidade não pôde ser verificada ({normal.impedimento})",
            )
        if normal.rejeita:
            return _pela_regra(
                delineamento,
                sem_normal,
                f"o Shapiro-Wilk rejeita a normal ({_p_na_frase(normal.p)})",
            )
        return _pela_regra(
            delineamento,
            parametrico,
            f"o Shapiro-Wilk não rejeita a normal ({_p_na_frase(normal.p)})",
        )

    grupos = tuple(normal)
    normais = [(grupo, grupo.normal or Normal(w=None, p=None)) for grupo in grupos]
    rejeitam = [(grupo, n) for grupo, n in normais if n.rejeita]
    if rejeitam:
        return _pela_regra(
            delineamento,
            sem_normal,
            "o Shapiro-Wilk rejeita a normal em "
            + _em_frase(f"{grupo.rotulo} ({_p_na_frase(n.p)})" for grupo, n in rejeitam),
        )
    sem_teste = [(grupo, n) for grupo, n in normais if not n.testada]
    if sem_teste:
        return _pela_regra(
            delineamento,
            sem_normal,
            "a normalidade não pôde ser verificada em "
            + _em_frase(f"{grupo.rotulo} ({n.impedimento})" for grupo, n in sem_teste),
        )
    return _pela_regra(
        delineamento,
        parametrico,
        f"o Shapiro-Wilk não rejeita a normal em {_nenhum(delineamento, len(grupos))} ("
        + "; ".join(f"{grupo.rotulo}: {_p_na_frase(n.p)}" for grupo, n in normais)
        + ")",
    )


def _pela_regra(delineamento: str, teste: str, motivo: str) -> Escolha:
    metodo = teste if _disponivel(delineamento, teste) else ""
    return Escolha(metodo=metodo, da_regra=teste, motivo=motivo)


def _disponivel(delineamento: str, teste: str) -> bool:
    return (delineamento, teste) in _CALCULO


# As tabelas


def _tabelas(variaveis: tuple[VariavelComparada, ...], total: int) -> tuple[Tabela, ...]:
    """
    Uma tabela por delineamento que apareceu na ficha, na ordem de `DELINEAMENTOS`, e
    os itens de cada uma na ordem da ficha.
    """
    montar = {
        UMA_AMOSTRA: _tabela_uma_amostra,
        DOIS_GRUPOS: _tabela_dois_grupos,
        K_GRUPOS: _tabela_k_grupos,
        REPETIDAS: _tabela_repetidas,
    }
    tabelas: list[Tabela] = []
    for delineamento in DELINEAMENTOS:
        itens = tuple(v for v in variaveis if v.delineamento == delineamento)
        if itens:
            tabelas.append(montar[delineamento](itens, total))
    return tuple(tabelas)


def linhas_da_tabela(variavel: VariavelComparada) -> tuple[tuple[str, ...], ...]:
    """
    As linhas de uma comparação na tabela do delineamento dela.

    Na uma amostra, uma linha. Entre grupos, um bloco: a linha da comparação — o
    rótulo da variável, o da variável de grupo, o n dos casos com as duas respostas, a
    diferença (entre dois grupos), o teste e o p — e uma linha por grupo, com o n, a
    média e o desvio. Nas medidas repetidas, uma linha por medida, com o teste e o p na
    primeira: não há variável de grupo para uma linha de cabeça.

    Pública porque o terminal desenha as mesmas linhas, item por item, com os
    destaques dele: as células saem daqui, e de mais lugar nenhum.

    O resumo de cada linha é o do teste dela — a média e o desvio, ou a mediana e os
    quartis —, e o intervalo só entra quando é o de 95% que o cabeçalho promete.
    """
    resultado = variavel.resultado
    p = valor_p(resultado.p if resultado else None)
    if variavel.repetidas:
        return tuple(
            (
                grupo.rotulo,
                str(variavel.validos),
                _resumo_da_linha(variavel, grupo.resumo),
                variavel.celula_do_teste if ordem == 0 else "",
                p if ordem == 0 else "",
            )
            for ordem, grupo in enumerate(variavel.grupos)
        )
    if not variavel.entre_grupos:
        return (
            (
                variavel.rotulo,
                str(variavel.validos),
                _resumo_da_linha(variavel, variavel.resumo),
                _intervalo(_ic_da_tabela(resultado), variavel.casas),
                _referencia_em_texto(variavel.referencia or 0.0),
                variavel.celula_do_teste,
                p,
            ),
        )
    grupos = tuple(
        (grupo.rotulo, str(grupo.n), _resumo_da_linha(variavel, grupo.resumo))
        for grupo in variavel.grupos
    )
    if variavel.delineamento == K_GRUPOS:
        return (
            (
                variavel.rotulo,
                variavel.rotulo_de_grupo,
                str(variavel.validos),
                "",
                variavel.celula_do_teste,
                p,
            ),
            *(("", rotulo, n, resumo, "", "") for rotulo, n, resumo in grupos),
        )
    cabeca = (
        variavel.rotulo,
        variavel.rotulo_de_grupo,
        str(variavel.validos),
        "",
        _diferenca(resultado, variavel.casas),
        variavel.celula_do_teste,
        p,
    )
    return (cabeca, *(("", rotulo, n, resumo, "", "", "") for rotulo, n, resumo in grupos))


def _teste_da_linha(variavel: VariavelComparada) -> str:
    """
    O teste que a linha mostra, ou que teria mostrado: o que rodou; o escolhido, quando
    uma barreira dele o impediu de rodar; o da regra, quando ela escolheu um que ainda
    não tem aritmética. Vazio quando nenhum teste chegou a ser escolhido.
    """
    escolha = variavel.escolha
    if escolha is None:
        return ""
    return escolha.metodo or escolha.da_regra


def _de_postos(variavel: VariavelComparada) -> bool:
    return _teste_da_linha(variavel) in TESTES_DE_POSTOS


def _resumo_da_linha(variavel: VariavelComparada, resumo: dict[str, float] | None) -> str:
    """
    O resumo de um grupo, de uma medida ou da variável, na medida que o teste da linha
    usa: a mediana e os quartis nos testes de postos, a média e o desvio nos outros — e
    quando não há teste nenhum, que é como a tabela sempre resumiu.
    """
    if _de_postos(variavel):
        return _mediana_e_quartis(resumo, variavel.casas)
    return _media_e_desvio(resumo, variavel.casas)


def _coluna_do_resumo(variaveis: Sequence[VariavelComparada]) -> str:
    """
    O cabeçalho da coluna do resumo, pelo que ela tem: as linhas sem resumo nenhum — o
    traço de quem não tem valor — não contam.
    """
    formas = {
        _de_postos(variavel)
        for variavel in variaveis
        if variavel.resumo or any(grupo.resumo for grupo in variavel.grupos)
    }
    if formas == {True}:
        return COLUNA_DA_MEDIANA
    if formas == {True, False}:
        return COLUNA_DAS_DUAS
    return COLUNA_DA_MEDIA


def _coluna_do_intervalo(variaveis: Sequence[VariavelComparada]) -> str:
    """
    O cabeçalho do intervalo da uma amostra, pelo teste de cada linha — o que rodou, ou
    o que a regra escolheu —, como o do resumo: o traço de um intervalo que não chega a
    95% fica debaixo do nome do intervalo que faltou, e não do da média. As linhas sem
    teste nenhum não contam, e uma tabela só delas fica com o da média, de sempre.
    """
    formas = {teste == WILCOXON for teste in map(_teste_da_linha, variaveis) if teste}
    if formas == {True}:
        return COLUNA_DO_IC_DA_PSEUDOMEDIANA
    if formas == {True, False}:
        return COLUNA_DO_IC
    return COLUNA_DO_IC_DA_MEDIA


def _coluna_da_diferenca(variaveis: Sequence[VariavelComparada]) -> str:
    """
    O cabeçalho da diferença entre dois grupos, pelo teste de cada linha, como o do
    intervalo da uma amostra: as linhas sem teste nenhum não contam, e uma tabela só do
    t — ou sem teste nenhum — fica com o de sempre.
    """
    formas = {teste == MANN_WHITNEY for teste in map(_teste_da_linha, variaveis) if teste}
    if formas == {True}:
        return COLUNA_DA_DIFERENCA_DE_LOCACAO
    if formas == {True, False}:
        return COLUNA_DAS_DUAS_DIFERENCAS
    return COLUNA_DA_DIFERENCA


def _ic_da_tabela(resultado: Resultado | None) -> tuple[float, float] | None:
    """
    O intervalo que vai para a tabela: o de 95%, e só ele. Quando o R não o alcança —
    poucos valores num teste de postos —, ele devolve um de nível menor, que fica no
    manifesto e no aviso, e não numa coluna que promete 95%.
    """
    if resultado is None or resultado.ic is None:
        return None
    if resultado.confianca_do_ic is not None and resultado.confianca_do_ic < CONFIANCA:
        return None
    return resultado.ic


def _tabela_uma_amostra(variaveis: tuple[VariavelComparada, ...], total: int) -> Tabela:
    """
    Uma linha por item, na ordem da ficha.

    As sete colunas — `variável`, `n`, o resumo, o intervalo, `referência`, `teste` e
    `p-valor` —, com o **rótulo** do dicionário na primeira. O resumo e o intervalo têm
    o cabeçalho do que levam: `média (DP)` e `IC 95% da média` quando todas as linhas
    são do t, e os do Wilcoxon quando ele aparece. O que decidiu cada teste — o p do
    Shapiro-Wilk, a estatística, os graus de liberdade, o caminho do p — vai para as
    notas do `.csv`, uma frase por linha, e para o manifesto.
    """
    corpo = tuple(linha for variavel in variaveis for linha in linhas_da_tabela(variavel))
    menor_p = numero(MENOR_P, 3)
    parametrico, de_postos = REGRA[UMA_AMOSTRA]
    notas = (
        "t de Student para uma amostra, bilateral, como o t.test do R: "
        "t = (média − referência) / (DP / √n), com n − 1 graus de liberdade; o IC 95% "
        "é o da média, com o quantil da mesma t.",
        "Wilcoxon para uma amostra — o teste do posto sinalizado —, bilateral, como o "
        "wilcox.test do R: V é a soma dos postos de |valor − referência| entre os valores "
        "acima da referência, e os valores iguais a ela saem do teste. O p é exato com "
        f"menos de {LIMITE_DO_EXATO} valores, sem empate e sem valor igual à referência; "
        "nos outros casos, a aproximação normal, com a correção para empates e a de "
        "continuidade. O IC 95% é o da pseudomediana de Hodges-Lehmann — a mediana das "
        "médias de cada par de valores —, como o wilcox.test com conf.int = TRUE.",
        f"teste escolhido pela regra dos pressupostos: o {parametrico} quando o "
        f"Shapiro-Wilk não rejeita a normal (p ≥ {numero(ALFA)}) sobre os valores "
        f"preenchidos da variável; o {de_postos} quando rejeita, ou quando a normalidade "
        f"não pode ser verificada. {_ainda_nao(UMA_AMOSTRA)}O método escrito na ficha tem "
        "precedência sobre a regra.",
        f"{COLUNA_DA_MEDIA} nas linhas do t e {COLUNA_DA_MEDIANA} nas do Wilcoxon, "
        "calculados como no resumo da descritiva; n: valores preenchidos, de "
        f"{total} linhas do banco — os faltantes são por variável.",
        "a referência é o valor escrito na ficha, na unidade da variável; o intervalo, da "
        "média ou da pseudomediana, se lê contra ela.",
        f"valor-p abaixo de {menor_p} sai como `< {menor_p}`; ele nunca é zero.",
        "cada linha é um teste; não há correção para comparações múltiplas.",
    ) + tuple(variavel.justificativa for variavel in variaveis)

    return Tabela(
        nome=ARQUIVO_TABELA,
        especie=UMA_AMOSTRA,
        # Vazia de propósito: esta tabela fala de várias variáveis.
        variavel="",
        titulo="Comparação com valor de referência",
        colunas=(
            "variável",
            "n",
            _coluna_do_resumo(variaveis),
            _coluna_do_intervalo(variaveis),
            "referência",
            "teste",
            "p-valor",
        ),
        linhas=corpo,
        notas=notas,
    )


def _tabela_dois_grupos(variaveis: tuple[VariavelComparada, ...], total: int) -> Tabela:
    """
    Um bloco por item, na ordem da ficha: a linha da comparação e uma linha por grupo.

    Sete colunas, como a da uma amostra — `variável`, `grupo`, `n`, o resumo, a
    diferença, `teste` e `p-valor`. A coluna `grupo` leva o rótulo da
    variável de grupo na linha da comparação e o de cada grupo nas seguintes, que é
    como uma tabela descritiva põe uma categórica: o nome, e as categorias embaixo.
    A diferença é a do teste da linha, com o intervalo dele — o do de Welch não é o do
    de Student, e a diferença de locação do Mann-Whitney não é nenhuma das duas —, e o
    cabeçalho dela diz qual: `diferença (IC 95%)` quando todas as linhas são do t, como
    sempre foi, `diferença de locação (IC 95%)` quando são do Mann-Whitney.
    """
    corpo = tuple(linha for variavel in variaveis for linha in linhas_da_tabela(variavel))
    menor_p = numero(MENOR_P, 3)
    parametrico, de_postos = REGRA[DOIS_GRUPOS]
    notas = (
        "uma comparação por bloco: a primeira linha traz a variável de grupo, o n dos "
        "casos que responderam as duas variáveis, a diferença, o teste e o p; as "
        "seguintes, cada grupo, na ordem do dicionário.",
        "diferença: no t, a média do primeiro grupo menos a do segundo; no Mann-Whitney, "
        "a diferença de locação de Hodges-Lehmann — a mediana das diferenças entre um "
        "valor do primeiro grupo e um do segundo, que não é a diferença das medianas —; "
        "as duas com o IC 95% do teste da linha.",
        "t de Welch para dois grupos independentes, bilateral, como o t.test do R: cada "
        "grupo com a sua variância, e os graus de liberdade de Welch-Satterthwaite, "
        "fracionários.",
        "t de Student para dois grupos independentes, bilateral, como o t.test do R com "
        "var.equal = TRUE: a variância dos dois grupos combinada, com n₁ + n₂ − 2 graus "
        "de liberdade.",
        "Mann-Whitney, bilateral, como o wilcox.test do R para duas amostras, que ele chama "
        "de soma de postos de Wilcoxon: W é o U do primeiro grupo — quantos pares têm o "
        "valor do primeiro grupo acima do valor do segundo, com meio ponto por empate. O p "
        f"é exato com menos de {LIMITE_DO_EXATO} valores em cada grupo e sem empate; nos "
        "outros casos, a aproximação normal, com a correção para empates e a de "
        "continuidade. O IC 95% é o do wilcox.test com conf.int = TRUE.",
        f"teste escolhido pela regra dos pressupostos: o {parametrico} — o padrão do "
        "t.test do R, que não supõe variâncias iguais — quando o Shapiro-Wilk não rejeita "
        f"a normal (p ≥ {numero(ALFA)}) em nenhum dos dois grupos; o {de_postos} quando "
        "rejeita em algum, ou quando a normalidade não pode ser verificada em algum. "
        f"{_ainda_nao(DOIS_GRUPOS)}O t de Student roda quando está escrito no item, e o "
        "método escrito na ficha tem precedência sobre a regra.",
        f"{COLUNA_DA_MEDIA} de cada grupo nas linhas do t e {COLUNA_DA_MEDIANA} nas do "
        "Mann-Whitney, calculados como no resumo da descritiva; n: casos com as duas "
        f"respostas, de {total} linhas do banco — os faltantes são por comparação.",
        f"valor-p abaixo de {menor_p} sai como `< {menor_p}`; ele nunca é zero.",
        "cada comparação é um teste; não há correção para comparações múltiplas.",
    ) + tuple(variavel.justificativa for variavel in variaveis)

    return Tabela(
        nome=ARQUIVO_DOIS_GRUPOS,
        especie=DOIS_GRUPOS,
        variavel="",
        titulo="Comparação entre dois grupos",
        colunas=(
            "variável",
            "grupo",
            "n",
            _coluna_do_resumo(variaveis),
            _coluna_da_diferenca(variaveis),
            "teste",
            "p-valor",
        ),
        linhas=corpo,
        notas=notas,
    )


def _tabela_k_grupos(variaveis: tuple[VariavelComparada, ...], total: int) -> Tabela:
    """
    Um bloco por item, como a dos dois grupos, sem a coluna da diferença: com três
    grupos ou mais não há uma diferença só. Seis colunas — `variável`, `grupo`, `n`, o
    resumo, `teste` e `p-valor` —; o F, o qui-quadrado e os graus de liberdade vão para
    as notas, com o resto do que decidiu cada teste.
    """
    corpo = tuple(linha for variavel in variaveis for linha in linhas_da_tabela(variavel))
    menor_p = numero(MENOR_P, 3)
    parametrico, de_postos = REGRA[K_GRUPOS]
    notas = (
        "uma comparação por bloco: a primeira linha traz a variável de grupo, o n dos "
        "casos que responderam as duas variáveis, o teste e o p; as seguintes, cada "
        "grupo, na ordem do dicionário.",
        "ANOVA de Welch, como o oneway.test do R — o padrão dele: cada grupo pesado pelo "
        "inverso da variância da sua média, e o F com k − 1 e os graus de liberdade de "
        "Welch no denominador, fracionários.",
        "ANOVA de um fator, como o oneway.test do R com var.equal = TRUE — o aov, quando "
        "cada grupo tem dois valores ou mais: a variância dentro dos grupos combinada, e "
        "o F com k − 1 e N − k graus de liberdade.",
        "Kruskal-Wallis, como o kruskal.test do R: os postos de todos os valores juntos, "
        "e o qui-quadrado com k − 1 graus de liberdade, com a correção para empates.",
        f"teste escolhido pela regra dos pressupostos: {_com_artigo(parametrico)} — o "
        "padrão do oneway.test do R, que não supõe variâncias iguais — quando o "
        f"Shapiro-Wilk não rejeita a normal (p ≥ {numero(ALFA)}) em nenhum dos grupos; "
        f"o {de_postos} quando rejeita em algum, ou quando a normalidade não pode ser "
        f"verificada em algum. {_ainda_nao(K_GRUPOS)}A ANOVA clássica roda quando está "
        "escrita no item, e o método escrito na ficha tem precedência sobre a regra.",
        "a ANOVA e o Kruskal-Wallis dizem se os grupos diferem, e não quais: a "
        "comparação dois a dois — o pós-teste — ainda não está no FlatCap.",
        f"{COLUNA_DA_MEDIA} de cada grupo nas linhas da ANOVA e {COLUNA_DA_MEDIANA} nas "
        "do Kruskal-Wallis, calculados como no resumo da descritiva; n: casos com as "
        f"duas respostas, de {total} linhas do banco — os faltantes são por comparação.",
        f"valor-p abaixo de {menor_p} sai como `< {menor_p}`; ele nunca é zero.",
        "cada comparação é um teste; não há correção para comparações múltiplas.",
    ) + tuple(variavel.justificativa for variavel in variaveis)

    return Tabela(
        nome=ARQUIVO_K_GRUPOS,
        especie=K_GRUPOS,
        variavel="",
        titulo="Comparação entre três grupos ou mais",
        colunas=(
            "variável",
            "grupo",
            "n",
            _coluna_do_resumo(variaveis),
            "teste",
            "p-valor",
        ),
        linhas=corpo,
        notas=notas,
    )


def _tabela_repetidas(variaveis: tuple[VariavelComparada, ...], total: int) -> Tabela:
    """
    Um bloco por item: uma linha por medida, na ordem da ficha, e o teste e o p na
    primeira. Cinco colunas — `medida`, `n`, o resumo, `teste` e `p-valor`.

    O n é o mesmo em todas as linhas do bloco — os casos com todas as medidas, que são
    os que entram no teste —, e o resumo de cada medida é o desses casos: com faltante
    em alguma medida, ele difere do `resumo` da descritiva, e a nota diz isso.
    """
    corpo = tuple(linha for variavel in variaveis for linha in linhas_da_tabela(variavel))
    menor_p = numero(MENOR_P, 3)
    parametrico, de_postos = REGRA[REPETIDAS]
    notas = (
        "uma comparação por bloco: uma linha por medida, na ordem da ficha, com o teste e "
        "o p na primeira.",
        "ANOVA de medidas repetidas de um fator, como o anova.mlm do R com test = "
        "\"Spherical\" — o F do aov com Error(caso / medida) —, sempre com a correção de "
        "Greenhouse-Geisser: ε (k − 1) e ε (n − 1)(k − 1) graus de liberdade, e o p da "
        "coluna G-G Pr. Sem o teste de Mauchly antes.",
        "Friedman, como o friedman.test do R: em cada caso, os postos das medidas, e o "
        "qui-quadrado com k − 1 graus de liberdade, com a correção para os empates de "
        "dentro dos casos.",
        f"teste escolhido pela regra dos pressupostos: {_com_artigo(parametrico)} quando o "
        f"Shapiro-Wilk não rejeita a normal (p ≥ {numero(ALFA)}) em nenhuma das medidas, "
        "sobre os casos completos; o "
        f"{de_postos} quando rejeita em alguma, ou quando a normalidade não pode ser "
        f"verificada em alguma. {_ainda_nao(REPETIDAS)}O método escrito no item — "
        f"{_ou([f'{CHAVE_METODO}: {chave}' for chave in _metodos_de((REPETIDAS,))])} — "
        "tem precedência sobre a regra.",
        "a ANOVA e o Friedman dizem se as medidas diferem, e não quais: a comparação dois "
        "a dois — o pós-teste — ainda não está no FlatCap.",
        "n: casos com todas as medidas do item, de "
        f"{total} linhas do banco — um caso com uma medida faltando sai do item inteiro. "
        f"O resumo de cada medida — {COLUNA_DA_MEDIA} nas linhas da ANOVA, "
        f"{COLUNA_DA_MEDIANA} nas do Friedman — é sobre esses casos, calculado como no "
        "resumo da descritiva, e diferente dele quando alguma medida tem faltante.",
        f"valor-p abaixo de {menor_p} sai como `< {menor_p}`; ele nunca é zero.",
        "cada comparação é um teste; não há correção para comparações múltiplas.",
    ) + tuple(variavel.justificativa for variavel in variaveis)

    return Tabela(
        nome=ARQUIVO_REPETIDAS,
        especie=REPETIDAS,
        variavel="",
        titulo="Comparação entre medidas repetidas",
        colunas=("medida", "n", _coluna_do_resumo(variaveis), "teste", "p-valor"),
        linhas=corpo,
        notas=notas,
    )


def _ainda_nao(delineamento: str) -> str:
    """
    A frase das notas sobre os testes da regra que ainda não têm aritmética — com o
    espaço do fim, para entrar entre duas frases —, ou vazio, que é o caso de todos os
    delineamentos desde a 1.14.0.
    """
    faltam = [teste for teste in REGRA[delineamento] if not _disponivel(delineamento, teste)]
    if not faltam:
        return ""
    if len(faltam) == 1:
        pronome = "a" if faltam[0].startswith("ANOVA") else "o"
        return (
            f"{_com_artigo(faltam[0], maiuscula=True)} ainda não está no FlatCap, e onde a "
            f"regra {pronome} escolhe a linha sai sem teste. "
        )
    return "Os dois ainda não estão no FlatCap, e a linha sai sem teste. "


# Os itens da ficha


def itens_da_ficha(raiz: Path) -> tuple[Pedido, ...]:
    """
    A lista `comparacao:` do `projeto.yaml`, conferida na forma e desdobrada.

    Quatro formas de item, e todas podem conviver:

        - [imc, 25]                # contra uma referência; a regra escolhe o método
        - [imc, sexo, student]     # entre os grupos de outra variável, com o método
        - sexo: [imc, idade]       # uma contra várias: cada uma entre os grupos de sexo
        - repetidas: [pas_0, pas_1, pas_2]   # a mesma medida, três vezes nos mesmos casos
          metodo: anova                      # o método, quando vier, na chave ao lado

    A terceira devolve um item por nome da lista, na ordem em que foram escritos. O
    método não se escreve nela: ficaria misturado aos nomes, como na correlação. Na
    quarta ele tem a chave dele, porque a lista das medidas não tem um terceiro lugar.

    Devolve vazio quando a chave não existe ou está vazia — quem recusa isso é o
    `comparar`, que tem o dicionário na mão para escrever quais variáveis existem.
    Formato errado recusa em vez de ignorar: um item que o comando pulasse em silêncio
    é o pior dos dois mundos — você escreveu, e não valeu.

    Lida pelo `ficha.bloco`, e não abrindo o YAML aqui: o `ficha.py` é o único módulo
    do pacote que abre o `projeto.yaml`.

    Raises:
        ItemInvalidoError
    """
    bruto = bloco(raiz, PASTA_COMPARACAO)
    if bruto is None:
        return ()
    if not isinstance(bruto, list):
        raise ItemInvalidoError(
            f"A chave `{PASTA_COMPARACAO}:` do {ARQUIVO_PROJETO} deveria ser uma lista, "
            f"e é {_descrever_valor(bruto)}.\n\n"
            f"Escreva assim, um item por linha:\n\n{EXEMPLO_DA_FICHA}"
        )

    pedidos: list[Pedido] = []
    problemas: list[str] = []
    for posicao, item in enumerate(bruto, start=1):
        lidos, problema = _ler_item(item)
        if problema:
            problemas.append(f"  {posicao}º item: {problema}")
        else:
            pedidos += lidos

    if problemas:
        raise ItemInvalidoError(
            f"A lista `{PASTA_COMPARACAO}:` do {ARQUIVO_PROJETO} tem "
            f"{len(problemas)} item(ns) fora do formato. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + f"\n\nEscreva assim, um item por linha:\n\n{EXEMPLO_DA_FICHA}\n\n"
            "O primeiro nome é a variável, como na coluna `variavel` do "
            f"{ARQUIVO_DICIONARIO}; o segundo é o valor de referência, com ponto "
            "decimal, ou a variável de grupo; o terceiro, quando vem, é o método — "
            f"{_ou(_metodos_de((UMA_AMOSTRA,)))} contra uma referência, "
            f"{_ou(_metodos_de(_DOS_GRUPOS))} entre grupos. Sem ele, a regra dos "
            f"pressupostos escolhe. Nas medidas repetidas, `{CHAVE_REPETIDAS}:` e a lista "
            f"das medidas, e o método, quando vier, na chave `{CHAVE_METODO}:` ao lado."
        )
    return tuple(pedidos)


def _ler_item(item: Any) -> tuple[tuple[Pedido, ...], str]:
    """
    Um item da lista: os `Pedido` que ele escreve, ou a frase do que está errado nele.
    """
    if isinstance(item, dict) and item:
        if any(_simplificado(str(chave)) == CHAVE_REPETIDAS for chave in item):
            return _ler_repetidas(item)
        return _ler_uma_contra_varias(item)
    if not isinstance(item, list):
        return (), (
            f"{_descrever_valor(item)} — um item se escreve entre colchetes, com a "
            "variável e o valor de referência, `[imc, 25]`, ou a variável e a de grupo, "
            "`[imc, sexo]`."
        )

    escrito = _descrever_valor(item)
    if not item:
        return (), (
            f"{escrito} — lista vazia; um item tem a variável e a referência, ou a "
            "variável e a de grupo."
        )

    nome = _nome(item[0])
    if not nome:
        if referencia_escrita(item[0]) is not None and len(item) >= 2 and _nome(item[1]):
            return (), (
                f"{escrito} — a variável vem primeiro e a referência depois: "
                f"`[{_nome(item[1])}, {_descrever_solto(item[0])}]`."
            )
        return (), f"{escrito} — o primeiro item é o nome da variável."

    if len(item) == 1:
        return (), (
            f"{escrito} — falta o valor de referência, `[{nome}, 25]`, ou a variável de "
            f"grupo, `[{nome}, sexo]`."
        )

    partido = _numero_partido(item)
    if partido is not None:
        com_ponto, sem_sinal = partido
        metodo = f", {_nome(item[3])}" if len(item) == 4 else ""
        sinal = (
            f" — ou `-{com_ponto}`, se ele era negativo: o sinal de um zero se perde na "
            "leitura"
            if sem_sinal
            else ""
        )
        return (), (
            f"{escrito} — a referência foi lida como dois itens, `{item[1]}` e "
            f"`{_digitos(item[2])}`: numa lista entre colchetes a vírgula separa os "
            f"itens, e a vírgula decimal partiu o número. Escreva `[{nome}, {com_ponto}"
            f'{metodo}]` ou `[{nome}, "{com_ponto.replace(".", ",")}"{metodo}]`{sinal}.'
        )

    referencia = referencia_escrita(item[1])
    if referencia is None:
        segundo = item[1]
        if isinstance(segundo, str) and _PARECE_NUMERO.match(segundo.strip()):
            return (), (
                f"{escrito} — `{_descrever_solto(segundo)}` não é um número que se leia "
                "sem ambiguidade. Escreva sem separador de milhar e com ponto decimal, "
                "como `1234.5`."
            )
        grupo = _nome(segundo)
        if not grupo:
            return (), (
                f"{escrito} — `{_descrever_solto(segundo)}` não é um número nem um nome: "
                f"o segundo item é o valor de referência, `[{nome}, 25]`, ou a variável "
                f"de grupo, `[{nome}, sexo]`."
            )
        return _ler_grupos(item, escrito, nome, grupo)

    if len(item) == 2:
        return (Pedido(nome, referencia),), ""

    if len(item) > 3:
        return (), (
            f"{escrito} — {len(item)} itens; um item tem a variável, a referência e, "
            "quando quiser escolher, o método."
        )

    terceiro = _nome(item[2]) or _descrever_solto(item[2])
    chave, problema = _metodo_na_ficha(escrito, terceiro, (UMA_AMOSTRA,))
    if problema:
        return (), problema
    return (Pedido(nome, referencia, chave),), ""


def _ler_grupos(
    item: list[Any], escrito: str, nome: str, grupo: str
) -> tuple[tuple[Pedido, ...], str]:
    """
    O item entre grupos: `[imc, sexo]`, ou `[imc, sexo, student]`.
    """
    if len(item) == 2:
        return (Pedido(nome, grupos=grupo),), ""
    if len(item) > 3:
        nomes = [_nome(valor) for valor in item[2:]]
        outras = ", ".join([nome, *(n for n in nomes if n and not _e_metodo(n))])
        return (), (
            f"{escrito} — {len(item)} itens; um item tem a variável, a de grupo e, "
            "quando quiser escolher, o método. Para comparar várias variáveis entre os "
            f"mesmos grupos, escreva `- {grupo}: [{outras}]`."
        )
    terceiro = _nome(item[2])
    if terceiro and not _e_metodo(terceiro):
        return (), (
            f"{escrito} — `{terceiro}` não é um método. O terceiro item, quando vem, é o "
            f"método: {_ou(_metodos_de(_DOS_GRUPOS))}. Para comparar várias variáveis "
            f"entre os grupos de `{grupo}`, escreva `- {grupo}: [{nome}, {terceiro}]`."
        )
    chave, problema = _metodo_na_ficha(
        escrito, terceiro or _descrever_solto(item[2]), _DOS_GRUPOS
    )
    if problema:
        return (), problema
    return (Pedido(nome, grupos=grupo, metodo=chave),), ""


def _ler_repetidas(item: dict[Any, Any]) -> tuple[tuple[Pedido, ...], str]:
    """
    O item de medidas repetidas — a marca `repetidas:` e a lista das medidas, na ordem
    em que foram feitas, e o método numa chave ao lado, quando vier:

        - repetidas: [pas_0, pas_1, pas_2]
          metodo: anova

    Três medidas ou mais: com duas, a pergunta é a do t pareado, que usa esta mesma
    forma e ainda não está no FlatCap — e a recusa diz isso, em vez de rodar uma ANOVA
    que é o t pareado ao quadrado.
    """
    chaves = {_simplificado(str(chave)): valor for chave, valor in item.items()}
    medidas = chaves.get(CHAVE_REPETIDAS)
    escrito = f"`{CHAVE_REPETIDAS}: {_descrever_solto(medidas)}`"
    outras = [str(chave) for chave in item if _simplificado(str(chave)) not in (
        CHAVE_REPETIDAS, CHAVE_METODO
    )]
    if outras:
        return (), (
            f"{escrito} — `{outras[0]}` não é uma chave do item de medidas repetidas; ao "
            f"lado de `{CHAVE_REPETIDAS}:` só vem `{CHAVE_METODO}:`."
        )
    lista = medidas if isinstance(medidas, list) else [medidas]
    nomes = [_nome(nome) for nome in lista]
    if not nomes or not all(nomes):
        return (), (
            f"{escrito} — depois de `{CHAVE_REPETIDAS}:` vem a lista das medidas, na ordem "
            f"em que foram feitas: `{CHAVE_REPETIDAS}: [pas_0, pas_1, pas_2]`."
        )
    repetidas = sorted({nome for nome in nomes if nomes.count(nome) > 1})
    if repetidas:
        return (), f"{escrito} — `{repetidas[0]}` duas vezes; cada medida entra uma vez."
    if len(nomes) < MINIMO_DE_MEDIDAS:
        if len(nomes) == 2:
            return (), (
                f"{escrito} — duas medidas: a comparação é o t pareado, que ainda não está "
                "no FlatCap. A ANOVA de medidas repetidas é para três medidas ou mais."
            )
        return (), f"{escrito} — uma medida só; a comparação é entre três medidas ou mais."

    chave = ""
    if CHAVE_METODO in chaves:
        texto = _nome(chaves[CHAVE_METODO]) or _descrever_solto(chaves[CHAVE_METODO])
        chave, problema = _metodo_na_ficha(escrito, texto, (REPETIDAS,))
        if problema:
            return (), problema
    return (Pedido(nomes[0], metodo=chave, medidas=tuple(nomes)),), ""


def _ler_uma_contra_varias(item: dict[Any, Any]) -> tuple[tuple[Pedido, ...], str]:
    """
    A forma com dois-pontos: `sexo: [imc, idade]` — cada variável da lista entre os
    grupos da que vem antes dos dois-pontos.
    """
    pedidos: list[Pedido] = []
    for chave, valor in item.items():
        solto = _descrever_solto(valor)
        if referencia_escrita(valor) is not None:
            return (), (
                f"`{chave}: {solto}` — o valor de referência vai dentro dos colchetes, "
                f"junto do nome: `[{chave}, {solto}]`."
            )
        grupo = _nome(chave)
        outras = valor if isinstance(valor, list) else [valor]
        nomes = [_nome(nome) for nome in outras]
        if not grupo or not nomes or not all(nomes):
            return (), (
                f"`{chave}: {solto}` — depois dos dois-pontos vem a lista das variáveis a "
                f"comparar entre os grupos de `{chave}`, com pelo menos um nome: "
                f"`- {grupo or 'sexo'}: [imc, idade]`."
            )
        metodos = [nome for nome in nomes if _e_metodo(nome)]
        if metodos:
            exemplo = next((nome for nome in nomes if not _e_metodo(nome)), "imc")
            return (), (
                f"`{chave}: {solto}` — `{metodos[0]}` é um método, e na forma uma contra "
                "várias o método não se escreve. Para escolhê-lo, escreva cada item: "
                f"`- [{exemplo}, {grupo}, {_chave(metodos[0])}]`."
            )
        pedidos += [Pedido(nome, grupos=grupo) for nome in nomes]
    return tuple(pedidos), ""


def _metodo_na_ficha(escrito: str, texto: str, familia: tuple[str, ...]) -> tuple[str, str]:
    """
    O método escrito no item, conferido contra a forma dele: devolve o nome na forma
    de `_chave`, ou a frase do que está errado.

    A forma diz a família de delineamentos — a uma amostra, ou os grupos —, e o
    método precisa querer dizer um teste que existe em algum deles. Entre grupos, se
    ele serve para o número de grupos que o banco tem só se sabe depois: ver
    `_problema_do_metodo`.
    """
    chave = _chave(texto)
    testes = METODOS.get(chave, {})
    da_familia = [(d, teste) for d, teste in testes.items() if d in familia]
    if any(_disponivel(d, teste) for d, teste in da_familia):
        return chave, ""

    disponiveis = _ou(_metodos_de(familia))
    if familia == (REPETIDAS,):
        if da_familia:
            return "", (
                f"{escrito} — {_com_artigo(da_familia[0][1])} ainda não está no FlatCap; "
                f"nas medidas repetidas, o método que se escreve é {disponiveis}."
            )
        return "", (
            f"{escrito} — `{texto}` não é um método das medidas repetidas; o método que "
            f"se escreve é {disponiveis}."
        )
    if familia == (UMA_AMOSTRA,):
        if da_familia:
            previsto = da_familia[0][1]
            return "", (
                f"{escrito} — o {previsto} ainda não está no FlatCap; nesta versão o método "
                f"que se escreve é {disponiveis}. Sem método, a regra escolhe — e, onde ela "
                f"escolheria o {previsto}, a linha sai sem teste, com o motivo."
            )
        if testes:
            return "", (
                f"{escrito} — `{texto}` não se aplica à comparação com um valor de "
                f"referência. O terceiro item, quando vem, é o método: {disponiveis}."
            )
        if chave in PREVISTOS:
            return "", (
                f"{escrito} — {_com_artigo(PREVISTOS[chave])} ainda não está no FlatCap, e "
                "não se aplica à comparação com um valor de referência. O terceiro item, "
                f"quando vem, é o método: {disponiveis}."
            )
        return "", (
            f"{escrito} — `{texto}` não é um método. O terceiro item, quando vem, é o "
            f"método: {disponiveis}."
        )

    if da_familia:
        previsto = da_familia[0][1]
        return "", (
            f"{escrito} — `{texto}` entre grupos é o {previsto}, que ainda não está no "
            f"FlatCap. Nesta versão, entre grupos, o método que se escreve é "
            f"{disponiveis}; sem método, a regra escolhe."
        )
    if testes:
        return "", (
            f"{escrito} — `{texto}` não se aplica à comparação entre grupos. O terceiro "
            f"item, quando vem, é o método: {disponiveis}."
        )
    if chave in PREVISTOS:
        return "", (
            f"{escrito} — {_com_artigo(PREVISTOS[chave])} ainda não está no FlatCap. "
            f"Nesta versão, entre grupos, o método que se escreve é {disponiveis}."
        )
    return "", (
        f"{escrito} — `{texto}` não é um método. O terceiro item, quando vem, é o "
        f"método: {disponiveis}."
    )


def _metodos_de(familia: Iterable[str]) -> list[str]:
    """Os nomes que se escrevem no item e têm teste com aritmética na família."""
    familia = tuple(familia)
    return [
        chave
        for chave, testes in METODOS.items()
        if any(d in familia and _disponivel(d, teste) for d, teste in testes.items())
    ]


def _e_metodo(texto: str) -> bool:
    chave = _chave(texto)
    return chave in METODOS or chave in PREVISTOS


def _teste_da_chave(chave: str, delineamento: str) -> str:
    return METODOS.get(chave, {}).get(delineamento, "")


def metodo_escrito(texto: str, delineamento: str = UMA_AMOSTRA) -> str:
    """
    O teste que o método escrito na ficha quer dizer no delineamento, como a tabela o
    escreve; vazio quando o texto não é um método dele, ou quando o teste ainda não
    está no FlatCap.

    Tolerante na leitura, como o da correlação: `T`, `t` e `Student` são o mesmo, e
    `mann-whitney` e `Mann Whitney` também. O delineamento muda o sentido: `t` é o de
    Student contra uma referência, e o de Welch entre dois grupos.
    """
    teste = _teste_da_chave(_chave(texto), delineamento)
    return teste if teste and _disponivel(delineamento, teste) else ""


def referencia_escrita(valor: Any) -> float | None:
    """
    O valor de referência, a partir de como a ficha o trouxe; `None` quando não é um
    número.

    Número do YAML entra como está. Texto entra quando é um número escrito — com
    vírgula ou ponto decimal, e sem separador de milhar: é o `"24,9"` entre aspas que
    a recusa da vírgula decimal ensina a escrever. Lógico não é número, embora o
    Python ache que `True` vale 1.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int | float):
        numero_ = float(valor)
        return numero_ if math.isfinite(numero_) else None
    if isinstance(valor, str):
        limpo = valor.strip()
        if _NUMERO_ESCRITO.match(limpo):
            return float(limpo.replace(",", "."))
    return None


def _numero_partido(item: list[Any]) -> tuple[str, bool] | None:
    """
    O `[imc, 24,9]` que o YAML leu como `[imc, 24, 9]`: o número de volta, com ponto
    — `24.9` —, e se o sinal dele se perdeu; `None` quando o item não tem essa forma.

    A forma é um inteiro depois do nome, e depois dele os algarismos da parte decimal
    — e o que vier depois, quando vier, sendo um método: `[imc, 24,9, t]` é o mesmo
    engano. A recusa sugere o número para copiar, e por isso ele precisa sair
    **exato**: com o zero à esquerda da parte decimal (ver `_digitos`), e com o aviso
    de que o sinal de `-0,5` não sobrevive à leitura — o YAML lê `-0` e `0` como o
    mesmo inteiro.
    """
    if len(item) not in (3, 4) or not _inteiro(item[1]):
        return None
    fracao = _digitos(item[2])
    if not fracao:
        return None
    if len(item) == 4 and not metodo_escrito(_nome(item[3])):
        return None
    inteiro = int(item[1])
    return f"{inteiro}.{fracao}", inteiro == 0


def _digitos(valor: Any) -> str:
    """
    Os algarismos de um inteiro sem sinal como foram digitados — `05`, e não `5` —, ou
    vazio quando o valor não é um.

    O zero à esquerda é o que separa `24,05` de `24,5` quando a vírgula decimal parte o
    número, e a recusa não pode sugerir o número errado para copiar. O `ruamel` guarda
    a largura de um inteiro escrito com zero à esquerda no `_width` do `ScalarInt`, que
    o `ficha.bloco` deixa passar; sem ela, os algarismos são os do próprio número — e
    é o caso de todo inteiro escrito sem zero à esquerda. Um texto só de algarismos
    também serve: é como outra biblioteca de YAML leria o `09`.
    """
    if isinstance(valor, bool):
        return ""
    if isinstance(valor, int):
        if valor < 0:
            return ""
        largura = getattr(valor, "_width", None)
        if isinstance(largura, int) and largura > 0:
            return f"{int(valor):0{largura}d}"
        return str(int(valor))
    if isinstance(valor, str) and valor.strip().isdigit():
        return valor.strip()
    return ""


def _inteiro(valor: Any) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _como_pedido(item: Pedido | tuple[Any, ...]) -> Pedido:
    if isinstance(item, Pedido):
        return item
    variavel, segundo, *resto = item
    if variavel == CHAVE_REPETIDAS and isinstance(segundo, list | tuple):
        chave = _chave(str(resto[0])) if resto else ""
        if resto and not _metodos_da_chave(chave, (REPETIDAS,)):
            raise ItemInvalidoError(f"`{resto[0]}` não é um método das medidas repetidas.")
        nomes = tuple(str(nome) for nome in segundo)
        return Pedido(nomes[0], metodo=chave, medidas=nomes)
    chave = _chave(str(resto[0])) if resto else ""
    numero_ = referencia_escrita(segundo)
    if numero_ is None:
        grupo = _nome(segundo)
        if not grupo:
            raise ItemInvalidoError(
                f"`{segundo}` não é um valor de referência nem uma variável de grupo."
            )
        if resto and not _metodos_da_chave(chave, _DOS_GRUPOS):
            raise ItemInvalidoError(f"`{resto[0]}` não é um método entre grupos.")
        return Pedido(str(variavel), None, chave, grupos=grupo)
    if resto and not metodo_escrito(chave, UMA_AMOSTRA):
        raise ItemInvalidoError(
            f"`{resto[0]}` não é um método contra uma referência: "
            f"{_ou(_metodos_de((UMA_AMOSTRA,)))}."
        )
    return Pedido(str(variavel), numero_, chave)


def _metodos_da_chave(chave: str, familia: tuple[str, ...]) -> bool:
    return any(
        d in familia and _disponivel(d, teste) for d, teste in METODOS.get(chave, {}).items()
    )


def _pedido_de(pergunta: Pergunta) -> Pedido:
    if pergunta.medidas:
        nomes = tuple(linha.variavel for linha in pergunta.medidas)
        return Pedido(nomes[0], metodo=pergunta.metodo, medidas=nomes)
    if pergunta.grupos is not None:
        return Pedido(
            pergunta.linha.variavel, None, pergunta.metodo, grupos=pergunta.grupos.variavel
        )
    return Pedido(pergunta.linha.variavel, pergunta.referencia, pergunta.metodo)


def _conferir_itens(pedidos: Sequence[Pedido], linhas: Sequence[Linha]) -> list[Pergunta]:
    """
    Confere cada item contra o dicionário, e recusa listando todos os problemas.

    Contra uma referência, quatro coisas: o nome não está no dicionário; a variável
    está marcada `ignorar` ou fora desta versão do banco; ela não é numérica — a média
    de um código não é uma média, e uma data tem média, mas a comparação dela com uma
    referência não quer dizer nada —; o item repete outro, mesmo com outro método, que
    seria fazer a mesma comparação duas vezes e ficar com o p que convier.

    Entre grupos, as mesmas para as duas variáveis, e os tipos precisam formar a
    comparação: a primeira numérica, a segunda categórica. Os outros arranjos são
    outras análises, e a recusa diz qual — duas categóricas são uma associação, duas
    numéricas são uma correlação —, ou diz que os dois nomes estão trocados.
    """
    por_nome = {linha.variavel: linha for linha in linhas}
    perguntas: list[Pergunta] = []
    problemas: list[str] = []
    vistos: dict[tuple[Any, ...], str] = {}

    for pedido in pedidos:
        if pedido.chave in vistos:
            problemas.append(
                f"  {pedido.escrito} — repete {vistos[pedido.chave]}; a mesma comparação "
                "se faz uma vez, por um teste"
            )
            continue
        vistos[pedido.chave] = pedido.escrito

        if pedido.medidas:
            motivo = _motivo_de_recusa_das_medidas(pedido.medidas, por_nome)
            if motivo:
                problemas.append(f"  {pedido.escrito} — {motivo}")
                continue
            linhas_das_medidas = tuple(por_nome[nome] for nome in pedido.medidas)
            perguntas.append(
                Pergunta(
                    linha=linhas_das_medidas[0],
                    metodo=pedido.metodo,
                    delineamento=REPETIDAS,
                    medidas=linhas_das_medidas,
                )
            )
            continue

        if pedido.grupos:
            motivo = _motivo_de_recusa_entre_grupos(pedido, por_nome)
            if motivo:
                problemas.append(f"  {pedido.escrito} — {motivo}")
                continue
            perguntas.append(
                Pergunta(
                    linha=por_nome[pedido.variavel],
                    metodo=pedido.metodo,
                    delineamento=GRUPOS,
                    grupos=por_nome[pedido.grupos],
                )
            )
            continue

        motivo = _motivo_de_recusa(pedido.variavel, por_nome.get(pedido.variavel))
        if motivo:
            problemas.append(f"  {pedido.escrito} — {motivo}")
            continue

        perguntas.append(
            Pergunta(
                linha=por_nome[pedido.variavel],
                referencia=pedido.referencia,
                metodo=pedido.metodo,
            )
        )

    if problemas:
        raise ItemInvalidoError(
            f"A lista `{PASTA_COMPARACAO}:` do {ARQUIVO_PROJETO} tem {len(problemas)} "
            "item(ns) que não podem ser comparados. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + "\n\nA comparação é sobre a média de uma variável marcada `numerica` no "
            f"{ARQUIVO_DICIONARIO} — contra um valor de referência, ou entre os grupos de "
            "uma variável marcada `categorica` —, ou entre medidas repetidas, todas "
            "`numerica`.\n\n"
            f"Corrija o nome na lista do {ARQUIVO_PROJETO} — ele é o da coluna "
            f"`variavel` do {ARQUIVO_DICIONARIO} —, ou o `tipo` no dicionário, e rode "
            "de novo."
        )
    return perguntas


def _motivo_de_recusa(nome: str, linha: Linha | None) -> str:
    presenca = _motivo_de_ausencia(nome, linha)
    if presenca or linha is None:
        return presenca
    if linha.tipo == CATEGORICA:
        return (
            f"`{nome}` está marcada `categorica` no {ARQUIVO_DICIONARIO} — a média de um "
            "código não é uma média"
        )
    if linha.tipo != NUMERICA:
        return f"`{nome}` está marcada `{linha.tipo}` no {ARQUIVO_DICIONARIO}"
    return ""


def _motivo_de_ausencia(nome: str, linha: Linha | None) -> str:
    if linha is None:
        return f"`{nome}` não está no {ARQUIVO_DICIONARIO}"
    if not linha.no_banco:
        return f"`{nome}` não está nesta versão do banco (`no_banco = nao`)"
    if linha.tipo == IGNORAR:
        return f"`{nome}` está marcada `ignorar` no {ARQUIVO_DICIONARIO}"
    return ""


def _motivo_de_recusa_das_medidas(nomes: Sequence[str], por_nome: dict[str, Linha]) -> str:
    """
    O que impede as medidas repetidas, pelo dicionário — ou vazio. As medidas com o
    mesmo problema saem numa frase só: três medidas marcadas `categorica` são uma
    decisão do dicionário, e não três.
    """
    fora = [nome for nome in nomes if nome not in por_nome]
    presentes = [por_nome[nome] for nome in nomes if nome in por_nome]
    sem_banco = [linha.variavel for linha in presentes if not linha.no_banco]
    ignoradas = [
        linha.variavel for linha in presentes if linha.no_banco and linha.tipo == IGNORAR
    ]
    categoricas = [
        linha.variavel for linha in presentes if linha.no_banco and linha.tipo == CATEGORICA
    ]
    outras = [
        linha
        for linha in presentes
        if linha.no_banco and linha.tipo not in (NUMERICA, CATEGORICA, IGNORAR)
    ]
    partes: list[str] = []
    if fora:
        partes.append(
            f"{_crases(fora)} {_verbo(fora, 'não está', 'não estão')} no {ARQUIVO_DICIONARIO}"
        )
    if sem_banco:
        partes.append(
            f"{_crases(sem_banco)} {_verbo(sem_banco, 'não está', 'não estão')} nesta versão "
            "do banco (`no_banco = nao`)"
        )
    if ignoradas:
        partes.append(
            f"{_crases(ignoradas)} {_verbo(ignoradas, 'está marcada', 'estão marcadas')} "
            f"`ignorar` no {ARQUIVO_DICIONARIO}"
        )
    if categoricas:
        partes.append(
            f"{_crases(categoricas)} {_verbo(categoricas, 'está marcada', 'estão marcadas')} "
            f"`categorica` no {ARQUIVO_DICIONARIO} — a média de um código não é uma média"
        )
    partes += [
        f"`{linha.variavel}` está marcada `{linha.tipo}` no {ARQUIVO_DICIONARIO}"
        for linha in outras
    ]
    return "; ".join(partes)


def _crases(nomes: Sequence[str]) -> str:
    return _em_frase(f"`{nome}`" for nome in nomes)


def _verbo(nomes: Sequence[str], singular: str, plural: str) -> str:
    return singular if len(nomes) == 1 else plural


def _motivo_de_recusa_entre_grupos(pedido: Pedido, por_nome: dict[str, Linha]) -> str:
    """
    O que impede o item entre grupos, pelo dicionário — ou vazio.
    """
    nome, grupo = pedido.variavel, pedido.grupos
    if nome == grupo:
        return f"`{nome}` duas vezes — a variável comparada e a de grupo são duas"
    ausencias = [
        motivo
        for motivo in (
            _motivo_de_ausencia(nome, por_nome.get(nome)),
            _motivo_de_ausencia(grupo, por_nome.get(grupo)),
        )
        if motivo
    ]
    if ausencias:
        return "; ".join(ausencias)

    tipo, tipo_do_grupo = por_nome[nome].tipo, por_nome[grupo].tipo
    if tipo == NUMERICA and tipo_do_grupo == CATEGORICA:
        return ""
    if tipo == CATEGORICA and tipo_do_grupo == NUMERICA:
        return (
            f"os dois estão trocados: `{grupo}` é a numérica, e a variável comparada vem "
            f"primeiro — `[{grupo}, {nome}]`, ou `- {nome}: [{grupo}]`"
        )
    if tipo == NUMERICA and tipo_do_grupo == NUMERICA:
        return (
            f"`{grupo}` está marcada `numerica` no {ARQUIVO_DICIONARIO}, e a variável de "
            "grupo é categórica. A relação entre duas numéricas é uma correlação — a "
            "lista `correlacao:` —; a mesma medida em três momentos ou mais é o item "
            f"`- {CHAVE_REPETIDAS}: [{nome}, {grupo}, ...]`, e em dois é um pareado, que "
            "ainda não está no FlatCap"
        )
    if tipo == CATEGORICA and tipo_do_grupo == CATEGORICA:
        return (
            f"`{nome}` está marcada `categorica` no {ARQUIVO_DICIONARIO} — a média de um "
            "código não é uma média. Duas categóricas são uma associação: a lista "
            "`associacao:`"
        )
    if tipo != NUMERICA:
        return (
            f"`{nome}` está marcada `{tipo}` no {ARQUIVO_DICIONARIO}, e a variável "
            "comparada é numérica"
        )
    return (
        f"`{grupo}` está marcada `{tipo_do_grupo}` no {ARQUIVO_DICIONARIO}, e a variável "
        "de grupo é categórica"
    )


# O manifesto


def montar_manifesto(comparacao: Comparacao, linhas: Sequence[Linha]) -> Manifesto:
    """
    Traduz a rodada para o índice que o relatório vai ler.

    **Um item só**, como na normalidade, na associação e na correlação: a seção do
    documento é uma seção de comparação, com uma tabela por delineamento. O `colunas`
    do item diz quais colunas do banco entraram — as de grupo também —, que é o que
    mantém as conferências do relatório certas para uma seção que não é de uma
    variável. O que decidiu cada teste vai em `detalhes`, sob o nome do delineamento.
    """
    banco = comparacao.banco
    leitura = banco.leitura
    ficha = comparacao.ficha

    detalhes: dict[str, Any] = {
        delineamento: [v.como_detalhe() for v in comparacao.do_delineamento(delineamento)]
        for delineamento in DELINEAMENTOS
        if comparacao.do_delineamento(delineamento)
    }
    detalhes.update(
        {
            "testadas": len(comparacao.testadas),
            "sem_teste": len(comparacao.sem_teste),
            "escritas_na_ficha": len(comparacao.pela_ficha),
        }
    )

    item = ItemDoManifesto(
        variavel="",
        slug=PASTA_COMPARACAO,
        rotulo="Comparação",
        tipo=ANALISE_COMPARACAO,
        n=banco.linhas,
        faltantes=0,
        colunas=comparacao.colunas_usadas,
        artefatos=tuple(
            Artefato(
                arquivo=tabela.nome,
                especie=tabela.especie,
                formato="csv",
                titulo=tabela.titulo,
            )
            for tabela in comparacao.tabelas
        ),
        detalhes=detalhes,
        avisos=tuple(aviso for variavel in comparacao.variaveis for aviso in variavel.avisos),
    )

    return Manifesto(
        analise=ANALISE_COMPARACAO,
        flatcap=__version__,
        gerado_em=comparacao.quando,
        projeto={
            "pasta": rotulo_do_projeto(ficha.raiz),
            "cliente": ficha.raiz.parent.name,
            "record_id": ficha.record_id,
            "matricula": ficha.matricula,
            "nome": ficha.nome,
            "tipo": ficha.tipo,
            "status": ficha.status,
        },
        banco={
            "arquivo": banco.versao.arquivo,
            "origem": banco.versao.origem,
            "sha256": banco.versao.sha256,
            "tamanho_bytes": banco.versao.tamanho_bytes,
            "linhas": banco.linhas,
            "colunas": banco.colunas,
            "planilha": leitura.aba,
            "separador": leitura.separador,
            "codificacao": leitura.codificacao,
            "virgula_decimal": list(leitura.virgula_decimal),
            "integridade": _integridade(banco.confere),
        },
        dicionario={
            "arquivo": ARQUIVO_DICIONARIO,
            "variaveis": len(linhas),
            "analisaveis": sum(1 for linha in linhas if linha.analisavel),
            "numericas": sum(
                1 for linha in linhas if linha.analisavel and linha.tipo == NUMERICA
            ),
        },
        ambiente=_ambiente(),
        regras=_regras(),
        itens=(item,),
        fora=tuple(
            {"variavel": f.variavel, "tipo": f.tipo, "motivo": f.motivo}
            for f in comparacao.fora
        ),
        avisos=comparacao.avisos,
    )


def _regras() -> dict[str, Any]:
    """
    As regras desta versão, escritas por extenso no manifesto — as mesmas das notas
    das tabelas, sem os números de uma rodada.
    """
    def escolha(delineamento: str, onde: str, depois: str) -> str:
        parametrico, de_postos = REGRA[delineamento]
        return (
            f"{parametrico} se o Shapiro-Wilk não rejeita a normal (p ≥ {ALFA:g}) {onde}; "
            f"senão {de_postos}. {_ainda_nao(delineamento)}{depois}"
        )

    return {
        "itens": f"os da lista `{PASTA_COMPARACAO}:` do {ARQUIVO_PROJETO}",
        "delineamentos": {
            UMA_AMOSTRA: "a média de uma numérica contra a referência escrita no item",
            DOIS_GRUPOS: (
                "a média de uma numérica entre os dois grupos de uma categórica, "
                "contados no banco"
            ),
            K_GRUPOS: (
                "a média de uma numérica entre os três grupos ou mais de uma categórica, "
                "contados no banco"
            ),
            REPETIDAS: (
                "a média de três medidas numéricas ou mais, feitas nos mesmos casos — o "
                f"item `{CHAVE_REPETIDAS}:` da lista"
            ),
        },
        "escolha_do_teste": {
            UMA_AMOSTRA: escolha(
                UMA_AMOSTRA,
                "sobre os valores preenchidos",
                "O método escrito na ficha tem precedência.",
            ),
            DOIS_GRUPOS: escolha(
                DOIS_GRUPOS,
                "em nenhum dos dois grupos",
                "O t de Student roda quando está escrito no item; o método escrito na "
                "ficha tem precedência.",
            ),
            K_GRUPOS: escolha(
                K_GRUPOS,
                "em nenhum dos grupos",
                "A ANOVA clássica roda quando está escrita no item; o método escrito na "
                "ficha tem precedência.",
            ),
            REPETIDAS: escolha(
                REPETIDAS,
                "em nenhuma das medidas, sobre os casos completos",
                f"O método escrito no item (`{CHAVE_METODO}:`) tem precedência.",
            ),
        },
        "t_de_student": (
            "t.test do R: bilateral; na uma amostra, t com n − 1 graus de liberdade e IC "
            f"{CONFIANCA:.0%} da média; entre dois grupos, var.equal = TRUE, t com "
            f"n₁ + n₂ − 2 graus de liberdade e IC {CONFIANCA:.0%} da diferença das médias"
        ),
        "t_de_welch": (
            "t.test do R, o padrão dele (var.equal = FALSE): bilateral, cada grupo com a "
            "sua variância, graus de liberdade de Welch-Satterthwaite e IC "
            f"{CONFIANCA:.0%} da diferença das médias"
        ),
        "anova": (
            "oneway.test do R com var.equal = TRUE: a variância dentro dos grupos "
            "combinada, F com k − 1 e N − k graus de liberdade; sem pós-teste"
        ),
        "anova_de_welch": (
            "oneway.test do R, o padrão dele (var.equal = FALSE): cada grupo pesado pelo "
            "inverso da variância da média, F com k − 1 e os gl de Welch; sem pós-teste"
        ),
        "anova_de_medidas_repetidas": (
            'anova.mlm do R com test = "Spherical" (o F do aov com Error), sempre com a '
            "correção de Greenhouse-Geisser — os gl multiplicados pelo ε, o p da coluna "
            "G-G Pr —, sem o teste de Mauchly; sem pós-teste"
        ),
        "wilcoxon": (
            "wilcox.test do R com conf.int = TRUE: bilateral; V, a soma dos postos de "
            "|valor − referência| dos valores acima da referência, sem os iguais a ela; p "
            f"exato com menos de {LIMITE_DO_EXATO} valores, sem empate e sem valor igual à "
            "referência, senão a aproximação normal com a correção para empates e a de "
            f"continuidade; IC {CONFIANCA:.0%} da pseudomediana de Hodges-Lehmann"
        ),
        "mann_whitney": (
            "wilcox.test do R para duas amostras, com conf.int = TRUE: bilateral; W, o U "
            f"do primeiro grupo; p exato com menos de {LIMITE_DO_EXATO} valores em cada "
            "grupo e sem empate, senão a aproximação normal com a correção para empates e "
            f"a de continuidade; IC {CONFIANCA:.0%} da diferença de locação de "
            "Hodges-Lehmann, que não é a diferença das medianas"
        ),
        "kruskal_wallis": (
            "kruskal.test do R: os postos de todos os valores juntos; qui-quadrado com "
            "k − 1 graus de liberdade, com a correção para empates; sem pós-teste"
        ),
        "friedman": (
            "friedman.test do R: os postos das medidas dentro de cada caso; qui-quadrado "
            "com k − 1 graus de liberdade, com a correção para empates; sem pós-teste"
        ),
        "resumo": (
            f"{COLUNA_DA_MEDIA} nas linhas do t e da ANOVA; {COLUNA_DA_MEDIANA} nas do "
            "Wilcoxon, do Mann-Whitney, do Kruskal-Wallis e do Friedman — o do teste que "
            "rodou, ou do que a regra escolheu quando ele não pôde rodar"
        ),
        "intervalo": (
            f"só o de {CONFIANCA:.0%} vai para a tabela; quando o teste de postos não o "
            "alcança, o de nível menor que o R devolve fica no manifesto"
        ),
        "normalidade": (
            "Shapiro-Wilk, pela mesma função da análise de normalidade — sobre os valores "
            "preenchidos na uma amostra, dentro de cada grupo entre grupos, e em cada "
            "medida, sobre os casos completos, nas medidas repetidas"
        ),
        "grupos": (
            "os rótulos do dicionário com resposta entre os casos que responderam as duas "
            "variáveis, na ordem do dicionário; a diferença é o primeiro menos o segundo"
        ),
        "alfa": ALFA,
        "minimo": {
            "t_uma_amostra": MINIMO_T,
            "t_de_welch": f"{MINIMO_T} em cada grupo",
            "t_de_student": MINIMO_STUDENT,
            "anova": f"{MINIMO_T} em cada grupo",
            "anova_de_welch": f"{MINIMO_T} em cada grupo",
            "anova_de_medidas_repetidas": (
                f"{MINIMO_DE_MEDIDAS} medidas e {MINIMO_T} casos com todas elas"
            ),
            "wilcoxon": MINIMO_T,
            "mann_whitney": "1 em cada grupo",
            "kruskal_wallis": "1 em cada grupo",
            "friedman": f"{MINIMO_DE_MEDIDAS} medidas e {MINIMO_T} casos com todas elas",
        },
        "faltantes": (
            "por variável na uma amostra; por comparação entre grupos; nas medidas "
            "repetidas, só os casos com todas as medidas do item"
        ),
        "hipotese": "bilateral",
        "comparacoes_multiplas": "nenhuma correção",
        "semente": SEMENTE,
    }


def _ambiente() -> dict[str, Any]:
    """
    As versões que produziram estes números.

    O `scipy` entra, porque o Shapiro-Wilk e a distribuição t são dele. O `matplotlib`
    e a `fonte` saem `None` — a rodada não desenha —, e as chaves continuam lá para o
    bloco ter a forma dos outros.
    """
    import openpyxl
    import scipy

    return {
        "python": ".".join(str(parte) for parte in sys.version_info[:3]),
        "flatcap": __version__,
        "pandas": pd.__version__,
        "openpyxl": openpyxl.__version__,
        "scipy": scipy.__version__,
        "matplotlib": None,
        "fonte": None,
    }


def _shapiro_no_manifesto(normal: Normal | None) -> dict[str, Any] | None:
    if normal is None:
        return None
    return {
        "w": _arredondar(normal.w),
        "p": _significativos(normal.p),
        "rejeita": normal.rejeita if normal.testada else None,
        "impedimento": normal.impedimento or None,
    }


# Mensagens


def _mensagem_sem_itens(linhas: Sequence[Linha]) -> str:
    numericas = [
        linha.variavel for linha in linhas if linha.analisavel and linha.tipo == NUMERICA
    ]
    categoricas = [
        linha.variavel for linha in linhas if linha.analisavel and linha.tipo == CATEGORICA
    ]
    if numericas:
        disponiveis = (
            f"As numéricas deste {ARQUIVO_DICIONARIO} são: "
            + ", ".join(numericas[:20])
            + (f" e mais {len(numericas) - 20}" if len(numericas) > 20 else "")
            + "."
        )
        if categoricas:
            disponiveis += (
                " As categóricas, que formam os grupos: "
                + ", ".join(categoricas[:20])
                + (f" e mais {len(categoricas) - 20}" if len(categoricas) > 20 else "")
                + "."
            )
    else:
        disponiveis = (
            f"Nenhuma variável deste {ARQUIVO_DICIONARIO} está marcada `numerica` ainda "
            "— reveja a coluna `tipo` antes."
        )
    return (
        f"O {ARQUIVO_PROJETO} deste projeto não diz o que comparar.\n\n"
        "Escreva a lista na ficha — a variável e o valor de referência entre colchetes, "
        "ou a variável e a de grupo, com o método como terceiro item quando quiser "
        f"escolhê-lo:\n\n{EXEMPLO_DA_FICHA}"
        f"\n\n{disponiveis}\n\n"
        "O que comparar, e contra qual valor, é decisão da reunião: a referência vem da "
        "literatura ou do protocolo, e o FlatCap não inventa uma."
    )


def _motivo_de_fora(linha: Linha) -> str:
    if not linha.no_banco:
        return "não está nesta versão do banco (`no_banco = nao`)"
    if linha.tipo == IGNORAR:
        return "marcada `ignorar` no dicionário"
    return f"não está em nenhum item da lista `{PASTA_COMPARACAO}:` do {ARQUIVO_PROJETO}"


def _acao_do_historico(plano: PlanoComparacao) -> str:
    comparacao = plano.comparacao
    metodos: list[str] = []
    for variavel in comparacao.variaveis:
        if variavel.metodo and variavel.metodo not in metodos:
            metodos.append(variavel.metodo)
    contagem = [(comparacao.quantos(metodo), f"com {_com_artigo(metodo)}") for metodo in metodos]
    contagem.append((len(comparacao.sem_teste), "sem teste"))
    resumo = ", ".join(f"{quantos} {nome}" for quantos, nome in contagem if quantos)
    partes = [
        f"`flatcap comparacao {comparacao.ficha.record_id}` — comparação de "
        f"`{comparacao.banco.versao.arquivo}`: {len(comparacao.variaveis)} item(ns) da "
        f"lista `{PASTA_COMPARACAO}:`"
        + (f" ({resumo})" if resumo else "")
        + f", em `{PASTA_ANALISES}/{PASTA_COMPARACAO}/`."
    ]
    if comparacao.pela_ficha:
        partes.append(f"{len(comparacao.pela_ficha)} com o método escrito na ficha.")
    if plano.arquivamento is not None:
        partes.append(
            f"A rodada anterior foi para `{PASTA_ANTIGAS}/{plano.arquivamento[1].name}/`."
        )
    return " ".join(partes)


# Leitura da série e formatação


def _coluna(quadro: pd.DataFrame, nome: str) -> pd.Series | None:
    """
    A coluna do banco pelo nome, ou `None` — pela posição, como nas outras análises:
    nome repetido devolveria um `DataFrame` no lugar de uma coluna.
    """
    for posicao, coluna in enumerate(quadro.columns):
        if str(coluna) == nome:
            return quadro.iloc[:, posicao]
    return None


def _rotulo(linha: Linha) -> str:
    return linha.rotulo or linha.variavel


def _nome(valor: Any) -> str:
    """
    Um nome, como a ficha o trouxe; vazio quando não é um nome.

    Número não é nome: é a referência escrita no lugar errado. Lista e bloco dentro
    da lista também não — é o `[[imc, 25]]` digitado com um colchete a mais.
    """
    if valor is None or isinstance(valor, list | dict | bool | int | float):
        return ""
    return str(valor).strip()


def _simplificado(texto: str) -> str:
    limpo = unicodedata.normalize("NFKD", str(texto or "")).lower().strip()
    return "".join(c for c in limpo if not unicodedata.combining(c))


def _chave(texto: str) -> str:
    """
    O método como ele se procura no `METODOS`: sem acento, minúsculo, e só letras e
    algarismos — `Mann-Whitney`, `mann whitney` e `MANN_WHITNEY` são o mesmo —, com as
    outras grafias do `_SINONIMOS` trocadas pela da casa.
    """
    limpo = "".join(c for c in _simplificado(texto) if c.isalnum())
    return _SINONIMOS.get(limpo, limpo)


def _concorda(teste: str, participio: str) -> str:
    """`t de Welch escrito`, `ANOVA escrita`: o participio no gênero do teste."""
    return participio[:-1] + "a" if teste.startswith("ANOVA") else participio


def _com_artigo(teste: str, maiuscula: bool = False) -> str:
    """`o t de Welch`, `a ANOVA` — e, no começo da frase, `O t de Welch`, `A ANOVA`."""
    artigo = "a" if teste.startswith("ANOVA") else "o"
    return f"{artigo.upper() if maiuscula else artigo} {teste}"


def _em_frase(itens: Iterable[str]) -> str:
    """`A`, `A e B`, `A, B e C`."""
    lista = list(itens)
    if len(lista) <= 1:
        return "".join(lista)
    return ", ".join(lista[:-1]) + " e " + lista[-1]


def _ou(nomes: Sequence[str]) -> str:
    """`` `t` ``, `` `t` ou `student` ``, com as crases."""
    escritos = [f"`{nome}`" for nome in nomes]
    if len(escritos) <= 1:
        return "".join(escritos)
    return ", ".join(escritos[:-1]) + " ou " + escritos[-1]


def _unidades(delineamento: str) -> tuple[str, str]:
    """O que se compara no delineamento, no singular e no plural."""
    return ("medida", "medidas") if delineamento == REPETIDAS else ("grupo", "grupos")


def _nenhum(delineamento: str, quantos: int) -> str:
    """`nenhum dos dois grupos`, `nenhum dos 3 grupos`, `nenhuma das 3 medidas`."""
    if delineamento == REPETIDAS:
        return f"nenhuma das {quantos} medidas"
    return "nenhum dos dois grupos" if quantos == 2 else f"nenhum dos {quantos} grupos"


def _p_na_frase(p: float | None) -> str:
    """
    O p dentro de uma frase: `p = 0,412`, ou `p < 0,001` — nunca `p = < 0,001`.
    """
    texto = valor_p(p)
    return f"p {texto}" if texto.startswith("<") else f"p = {texto}"


def _estatistica_em_texto(resultado: Resultado) -> str:
    """`t = 2,16; 56 gl`, `F = 6,39; 2 e 57 gl` — e, nas medidas repetidas, o ε de
    Greenhouse-Geisser que corrigiu os gl: `F = 35,44; 1,62 e 14,55 gl; ε = 0,808`. No
    Wilcoxon e no Mann-Whitney, o caminho do p, que muda com o n e com os empates:
    `V = 70; p exato`, `W = 25,5; p aproximado pela normal, …, porque há empates`."""
    texto = f"{resultado.nome_da_estatistica} = {numero(resultado.estatistica, 2)}"
    if resultado.gl:
        texto += "; " + " e ".join(numero(gl, 2) for gl in resultado.gl) + " gl"
    if resultado.epsilon is not None:
        texto += f"; ε = {numero(resultado.epsilon, 3)}"
    if resultado.exato is not None:
        texto += f"; p {resultado.calculo_do_p}"
    return texto


def _media_e_desvio(resumo: dict[str, float] | None, casas: int = CASAS_IC) -> str:
    """
    `26,41 (4,12)` — a média e o desvio como o `resumo_<variável>.csv` os escreve,
    pelo mesmo `numero()` e com as mesmas casas.
    """
    if not resumo:
        return _AUSENTE
    return f"{numero(resumo['media'], casas)} ({numero(resumo['desvio'], casas)})"


def _mediana_e_quartis(resumo: dict[str, float] | None, casas: int = CASAS_IC) -> str:
    """
    `25,9 [23,1 a 28,7]` — a mediana e os quartis como o `resumo_<variável>.csv` os
    escreve, pelo mesmo `numero()` e com as mesmas casas, com os quartis entre
    colchetes e o `a` do intervalo.
    """
    if not resumo:
        return _AUSENTE
    mediana, q1, q3 = (numero(resumo[chave], casas) for chave in ("mediana", "q1", "q3"))
    return f"{mediana} [{q1} a {q3}]"


def _intervalo(intervalo: tuple[float, float] | None, casas: int = CASAS_IC) -> str:
    if intervalo is None:
        return _AUSENTE
    baixo, alto = intervalo
    return f"{_fixo(baixo, casas)} a {_fixo(alto, casas)}"


def _diferenca(resultado: Resultado | None, casas: int = CASAS_IC) -> str:
    """
    `-1,52 (-3,21 a 0,17)` — a estimativa do teste e o intervalo dela, com as casas
    fixas do intervalo da uma amostra: a diferença das médias no t, a diferença de
    locação no Mann-Whitney. Sem o intervalo de 95%, o traço na célula inteira.
    """
    intervalo = _ic_da_tabela(resultado)
    if resultado is None or resultado.estimativa is None or intervalo is None:
        return _AUSENTE
    return f"{_fixo(resultado.estimativa, casas)} ({_intervalo(intervalo, casas)})"


def _fixo(valor: float, casas: int = CASAS_IC) -> str:
    """
    Casas fixas — as duas de sempre, ou as da variável quando a escala dela é pequena
    —, o hífen do teclado no negativo, e nunca `-0,00` — o formato do coeficiente da
    correlação: o Excel em português lê a célula como número, e um zero não tem
    direção.
    """
    texto = f"{valor:.{max(casas, CASAS_IC)}f}"
    if float(texto) == 0:
        texto = texto.lstrip("-")
    return texto.replace(".", ",")


def _referencia_em_texto(valor: float, ponto: bool = False) -> str:
    """
    A referência como foi escrita, sem os zeros do fim: `25`, `24,9`, `0,125`.

    Com `ponto`, a forma da ficha — `24.9` —, para as mensagens ensinarem a escrever
    o que funciona.
    """
    texto = numero(valor, CASAS_REFERENCIA)
    return texto.replace(",", ".") if ponto else texto


def _descrever_valor(valor: Any) -> str:
    if isinstance(valor, list):
        return "[" + ", ".join(_descrever_solto(item) for item in valor) + "]"
    if isinstance(valor, dict):
        return "um bloco `chave: valor`"
    if valor is None:
        return "vazio"
    if isinstance(valor, str):
        return f"`{valor}`"
    return f"`{valor}` ({type(valor).__name__})"


def _descrever_solto(valor: Any) -> str:
    """Um valor como ele apareceria dentro dos colchetes da ficha."""
    if isinstance(valor, list):
        return "[" + ", ".join(_descrever_solto(item) for item in valor) + "]"
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def _arredondar(valor: float | None) -> float | None:
    if valor is None:
        return None
    valor = float(valor)
    return round(valor, 6) if math.isfinite(valor) else None


def _significativos(valor: float | None) -> float | None:
    """
    O p no manifesto, com seis algarismos significativos, e não seis casas — o da
    correlação. Com seis casas, um p de 2,5e-08 seria gravado como `0.0`.
    """
    if valor is None:
        return None
    valor = float(valor)
    return float(f"{valor:.6g}") if math.isfinite(valor) else None


def _integridade(confere: bool | None) -> str:
    if confere is True:
        return "confere"
    if confere is False:
        return "ALTERADO"
    return "não conferida"


__all__ = [
    "ANOVA",
    "ANOVA_DE_WELCH",
    "ARQUIVOS",
    "ARQUIVO_DOIS_GRUPOS",
    "ARQUIVO_K_GRUPOS",
    "ARQUIVO_REPETIDAS",
    "ARQUIVO_TABELA",
    "ANOVA_DE_MEDIDAS_REPETIDAS",
    "CASAS_IC",
    "CASAS_REFERENCIA",
    "CHAVE_METODO",
    "CHAVE_REPETIDAS",
    "COLUNA_DAS_DUAS",
    "COLUNA_DAS_DUAS_DIFERENCAS",
    "COLUNA_DA_DIFERENCA",
    "COLUNA_DA_DIFERENCA_DE_LOCACAO",
    "COLUNA_DA_MEDIA",
    "COLUNA_DA_MEDIANA",
    "COLUNA_DO_IC",
    "COLUNA_DO_IC_DA_MEDIA",
    "COLUNA_DO_IC_DA_PSEUDOMEDIANA",
    "DELINEAMENTOS",
    "DOIS_GRUPOS",
    "EXEMPLO_DA_FICHA",
    "FRIEDMAN",
    "GRUPOS",
    "KRUSKAL_WALLIS",
    "K_GRUPOS",
    "MANN_WHITNEY",
    "METODOS",
    "MINIMO_DE_MEDIDAS",
    "PREVISTOS",
    "RAZAO_DE_DESVIOS",
    "REGRA",
    "REPETIDAS",
    "TESTES_DE_POSTOS",
    "T_DE_WELCH",
    "UMA_AMOSTRA",
    "WILCOXON",
    "Comparacao",
    "ComparacaoError",
    "DicionarioAusenteError",
    "DicionarioDesatualizadoError",
    "Escolha",
    "ForaDaComparacao",
    "Grupo",
    "ItemInvalidoError",
    "Normal",
    "Pedido",
    "Pergunta",
    "PlanoComparacao",
    "ResultadoComparacao",
    "SemItensError",
    "VariavelComparada",
    "VariavelIncompativelError",
    "comparar",
    "executar_comparacao",
    "itens_da_ficha",
    "linhas_da_tabela",
    "metodo_escrito",
    "montar_manifesto",
    "preparar_comparacao",
    "referencia_escrita",
    "regra",
]
