# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
A descritiva — o passo 2a do fluxo, o que se repete em todos os projetos.

Este módulo obedece ao `dicionario.csv` e a mais nada. É a decisão de arquitetura
nº 2 do roteiro levada até o fim: o que é categórica, o que é numérica, o que se
ignora, em que ordem as categorias aparecem e onde ficam os cortes das faixas foi
decidido por você, na reunião, com o cliente na frente — e está escrito em um
arquivo. Aqui a automação apenas cumpre.

A consequência prática é a que vale registrar: **não há nenhuma heurística neste
módulo.** Nenhum palpite de tipo, nenhuma inferência de categoria, nenhuma
adivinhação de formato. Tudo isso é da Fase 4, e ela existe justamente para que
esta fase não precise decidir nada. Quando a descritiva sai errada, o conserto é
uma célula do `dicionario.csv` — não uma condicional aqui dentro.

Segue o padrão das Fases 2, 3 e 4, decidir e escrever separados:

    plano = preparar_descritiva(raiz)   # abre o banco, lê o dicionário, calcula
    executar_descritiva(plano)          # só escreve

E, como as Fases 3 e 4, **não fala com o REDCap**. Recebe `Path`, não `Config`.

## As quatro decisões desta fase

**Faixas sem `faixas` preenchida: quartis.** Quatro faixas com aproximadamente um
quarto dos casos cada, cortadas em mínimo, Q1, mediana, Q3 e máximo. É a regra que
não inventa nada sobre a variável: ela descreve a distribuição que está lá, em vez
de impor cortes redondos que pareceriam decisão clínica sem terem sido. Quando o
cliente pedir cortes específicos, eles entram na coluna `faixas` e esta regra sai
de cena — e o `perfil.md` já traz os quartis de cada numérica exatamente para essa
conversa.

**Numérica que chegou como texto: recusa.** Se o dicionário diz `numerica` e a
coluna veio como texto — vírgula decimal, número entre aspas, `12 (repetido)` no
meio —, o comando não gera nada e diz quais são as colunas. A alternativa seria
converter em silêncio, e converter em silêncio é como uma média sai de 80% dos
casos sem que nada na tabela diga que os outros 20% não entraram. O caminho é o
que a Fase 3 já tem: o cliente corrige, você registra a versão nova com
`flatcap dados adicionar`, e a descritiva roda sobre ela.

    A exceção é a data, e a razão é do formato, não da regra. Em um `.csv` não
    existe tipo data: o `pandas` infere número a partir do texto e nunca infere
    data. Exigir que o cliente "conserte" isso seria exigir o impossível. Então a
    data escrita como texto é convertida — mas só quando **um único** formato
    explica a coluna quase inteira (a mesma função que a Fase 4 usa para
    denunciá-la), e o formato usado sai escrito no manifesto. Coluna com dois
    formatos misturados não é convertida: é recusada como as numéricas.

**Regerar arquiva a rodada anterior.** `3. Análises/descritiva/` inteira vai para
`2. Versões antigas/descritiva_AAAA-MM-DD_HHMM/` antes de a nova ser escrita. É a
mesma ideia da rotação de bancos da Fase 3, pelo mesmo motivo: um número que o
cliente já viu não pode sumir sem deixar rastro. Se ele perguntar "esse 37% não
era 41% no relatório passado?", a resposta está no disco.

**Data ganha resumo e distribuição no tempo.** O roteiro só fala de categóricas e
numéricas. Uma data descrita como categórica viraria uma tabela de frequência com
uma linha por dia; descrita como numérica, uma média de datas. As duas são inúteis.
O que serve é o período (de quando a quando) e como os casos se distribuem nele —
por mês quando o período é curto, por ano quando é longo.

## O que sai no disco

Uma pasta por rodada, com um arquivo por artefato e um `manifesto.json` que lista
todos eles. O manifesto é o que torna a Fase 6 simples: sem ele, o gerador de
relatório teria de adivinhar arquivos por nome; com ele, percorre uma lista
ordenada e sabe de qual variável cada arquivo saiu. É também o que registra as
versões de biblioteca — o que responde, no dia em que um gráfico sair diferente,
se mudaram os dados ou mudou o `matplotlib`.

Os `.csv` seguem a convenção do `dicionario.csv`: `;` entre campos, UTF-8 com BOM
e vírgula decimal, que é o que faz o arquivo abrir certo com dois cliques no Excel
em português. Sem separador de milhar, de propósito: `1.234,5` em uma célula é a
forma mais fácil de um número virar texto na volta.

## O que este módulo não faz

Não desenha — quem desenha é o `graficos.py`, que recebe as contagens já
calculadas e não recalcula nada. Não conhece o formato do manifesto — quem conhece
é o `manifesto.py`, que não importa nem o `pandas` nem o `matplotlib`. E não
escolhe qual arquivo é o banco: isso é do `banco.py` desde a Fase 4, e é o que
garante que a descritiva e o relatório falem da mesma versão.
"""

from __future__ import annotations

import math
import re
import sys
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__
from .banco import (
    Banco,
    abrir,
    casas_do_resumo,
    formato_de_data,
    serie_de_texto,
    texto_de_numero,
)
from .dicionario import (
    ARQUIVO_DICIONARIO,
    CATEGORICA,
    DATA,
    IGNORAR,
    NUMERICA,
    Linha,
    caminho_do_dicionario,
)
from .dicionario import ler as ler_dicionario
from .ficha import Ficha, escrever_atomico
from .ficha import ler as ler_ficha
from .manifesto import (
    ANALISE_DESCRITIVA,
    ARQUIVO_MANIFESTO,
    SEMENTE,
    Artefato,
    Grafico,
    ItemDoManifesto,
    Manifesto,
    Tabela,
    texto_do_manifesto,
)
from .nomes import rotulo_do_projeto
from .projeto import (
    PASTA_ANALISES,
    PASTA_ANTIGAS,
    PASTA_DESCRITIVA,
    anotar,
    pasta_da_analise,
)

# Nada nesta fase sorteia coisa nenhuma — uma descritiva é contagem, e contagem
# não tem aleatoriedade. A semente existe declarada e registrada no manifesto
# assim mesmo, por dois motivos: o roteiro pede, e a Fase 7 (bootstrap, testes de
# permutação, imputação) vai precisar de uma.
#
# Ela **desceu para o `manifesto.py`** na Fase 7 e é reexportada daqui, para que
# nenhum chamador mude. O motivo está na docstring dela: é um valor que todo
# manifesto registra, e uma segunda semente em um segundo módulo é como duas
# rodadas do mesmo projeto deixam de ser reproduzíveis uma contra a outra. Mesma
# manobra que `versao_vigente` e `formato_de_data` já fizeram.

# Regras de apresentação. Todas com nome, aqui em cima, pelo mesmo motivo da Fase
# 4: número solto no meio de uma função é decisão que ninguém consegue rever.
LIMITE_BARRAS = 15       # acima disso o gráfico junta a cauda em "Outras"
LIMITE_COLUNAS_TEMPO = 30  # acima disso a distribuição no tempo sai sem gráfico
MESES_PARA_MENSAL = 24   # período até 24 meses é contado por mês; acima, por ano
MINIMO_PARA_FAIXAS = 4   # abaixo disso, quartil não descreve nada
CASAS_RESUMO = 2         # casas das estatísticas; mais na escala pequena (casas_do_resumo)
CASAS_PERCENTUAL = 1

FAIXAS_QUARTIS = "quartis"
FAIXAS_DICIONARIO = "dicionario"

ROTULO_FALTANTE = "(sem informação)"
ROTULO_TOTAL = "Total"
ROTULO_OUTRAS = "Outras"
ROTULO_ABAIXO = "(abaixo da primeira faixa)"
ROTULO_ACIMA = "(acima da última faixa)"

_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")
_ESPACOS = re.compile(r"\s+")

_LIMITE_SLUG = 40


class DescritivaError(RuntimeError):
    """
    Falha ao gerar a descritiva, já traduzida para o usuário.

    Erro próprio pelo mesmo motivo de `ConfigError`, `RedcapError`, `ProjetoError`,
    `FichaError`, `DadosError`, `BancoError` e `DicionarioError`: a CLI captura
    esta classe e transforma em painel. Qualquer outra exceção é bug de verdade e
    deve subir com o traceback inteiro.

    A Fase 4 não declarou erro próprio porque o perfil não tinha como falhar
    sozinho — ele mede o que estiver lá. Esta fase tem: ela **recusa**, e as
    recusas abaixo são o conteúdo da decisão.
    """


class DicionarioAusenteError(DescritivaError):
    """
    O projeto não tem `dicionario.csv`. A descritiva não tem o que obedecer.
    """


class DicionarioDesatualizadoError(DescritivaError):
    """
    O banco tem colunas que o dicionário desconhece.

    Recusar é deliberado, e é a mesma escolha do `DicionarioInvalidoError` da Fase
    4: uma descritiva com metade das variáveis sai perfeitamente formatada, e nada
    nela denuncia a metade que ficou de fora.
    """


class VariavelIncompativelError(DescritivaError):
    """
    O dicionário promete um tipo que a coluna não tem.

    É a recusa da numérica que chegou como texto — a decisão central da fase.
    Lista **todas** as colunas de uma vez: descobrir a segunda depois de corrigir
    a primeira é o jeito mais lento possível de arrumar um banco.
    """


class NadaParaAnalisarError(DescritivaError):
    """
    Nenhuma variável do dicionário entra na descritiva.
    """


# O que sai no disco


# `Tabela` e `Grafico` moram no `manifesto.py` desde a Fase 7, e são reexportados
# daqui — `from .descritiva import Tabela` continua funcionando.
#
# Eles são o **contrato de saída de qualquer análise**, e não da descritiva: a
# normalidade escreve `.csv` e desenha `.png` com as mesmas duas classes. Deixá-los
# aqui obrigaria toda análise nova a importar o módulo da descritiva — acoplando
# duas análises que não têm nada a ver uma com a outra, e fazendo a segunda pagar
# meio segundo de `pandas` só para conhecer uma `dataclass` de texto. O
# `manifesto.py` já era dono do `Artefato`, não importa `pandas` nem `matplotlib`,
# e é o módulo que a Fase 6 lê para montar o documento: é o lugar.


@dataclass(frozen=True)
class VariavelDescrita:
    """
    Uma variável do dicionário, já descrita: as tabelas e os gráficos que ela gera.
    """

    variavel: str
    slug: str
    rotulo: str
    tipo: str
    n: int
    faltantes: int
    tabelas: tuple[Tabela, ...] = ()
    graficos: tuple[Grafico, ...] = ()
    detalhes: dict[str, Any] = field(default_factory=dict)
    avisos: tuple[str, ...] = ()

    @property
    def preenchidos(self) -> int:
        return self.n - self.faltantes


@dataclass(frozen=True)
class ForaDaDescritiva:
    """
    Uma variável do dicionário que não gerou artefato, e por quê.

    Ela aparece no manifesto de propósito. "Não está no relatório" e "ninguém
    reparou que ela existia" são coisas diferentes, e só a primeira é uma decisão.
    """

    variavel: str
    tipo: str
    motivo: str


@dataclass(frozen=True)
class Descritiva:
    """
    O banco inteiro descrito. É daqui que saem os arquivos e o terminal.
    """

    ficha: Ficha
    banco: Banco
    variaveis: tuple[VariavelDescrita, ...]
    fora: tuple[ForaDaDescritiva, ...]
    avisos: tuple[str, ...]
    quando: datetime

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def linhas(self) -> int:
        return self.banco.linhas

    @property
    def tabelas(self) -> tuple[Tabela, ...]:
        return tuple(t for v in self.variaveis for t in v.tabelas)

    @property
    def graficos(self) -> tuple[Grafico, ...]:
        return tuple(g for v in self.variaveis for g in v.graficos)

    def por_tipo(self, tipo: str) -> tuple[VariavelDescrita, ...]:
        return tuple(v for v in self.variaveis if v.tipo == tipo)


@dataclass(frozen=True)
class PlanoDescritiva:
    """
    Tudo o que o `descritiva` faria, decidido e ainda não escrito.
    """

    descritiva: Descritiva
    pasta: Path
    arquivamento: tuple[Path, Path] | None
    com_graficos: bool
    manifesto: Manifesto
    texto_manifesto: str

    @property
    def raiz(self) -> Path:
        return self.descritiva.raiz

    @property
    def tabelas(self) -> tuple[Tabela, ...]:
        return self.descritiva.tabelas

    @property
    def graficos(self) -> tuple[Grafico, ...]:
        return self.descritiva.graficos if self.com_graficos else ()

    @property
    def arquivos(self) -> tuple[str, ...]:
        nomes = [t.nome for t in self.tabelas] + [g.nome for g in self.graficos]
        return tuple(nomes + [ARQUIVO_MANIFESTO])


@dataclass(frozen=True)
class ResultadoDescritiva:
    """
    O que a execução de fato escreveu.
    """

    criados: tuple[Path, ...] = ()
    arquivado: tuple[Path, Path] | None = None
    avisos: tuple[str, ...] = ()


# Casos de uso


def preparar_descritiva(
    raiz: Path,
    aba: str | None = None,
    conferir: bool = True,
    com_graficos: bool = True,
    agora: datetime | None = None,
) -> PlanoDescritiva:
    """
    Abre o banco, lê o dicionário, calcula tudo e monta o plano. Não escreve nada.

    Args:
        raiz: a pasta do projeto (a que tem o `projeto.yaml`).
        aba: planilha do `.xlsx`, quando houver mais de uma.
        conferir: reler o `sha256` das versões e comparar com a ficha.
        com_graficos: desenhar os `.png`. Desligado, o `matplotlib` nem é importado.
        agora: relógio injetável — sem ele os testes não teriam como comparar o
            nome da pasta arquivada nem o manifesto, que carregam a data.

    Raises:
        FichaError, BancoError, DicionarioInvalidoError e as quatro recusas
        declaradas acima.
    """
    raiz = Path(raiz)
    quando = agora or datetime.now()

    banco = abrir(raiz, aba=aba, conferir=conferir)
    ficha = ler_ficha(raiz)
    linhas = _dicionario_do_projeto(raiz, banco)

    descritiva = descrever(banco, ficha, linhas, quando)

    # `pasta_da_analise` e não a concatenação à mão: a mesma pergunta é feita
    # pela normalidade e pelo relatório, e é o `projeto.py` que responde por
    # onde uma rodada mora. Duas formas de montar o mesmo caminho é como uma
    # delas deixa de acompanhar a próxima mudança no desenho da pasta.
    pasta = pasta_da_analise(raiz, PASTA_DESCRITIVA)
    manifesto = montar_manifesto(descritiva, linhas, com_graficos)

    return PlanoDescritiva(
        descritiva=descritiva,
        pasta=pasta,
        arquivamento=_arquivamento(raiz, pasta, quando),
        com_graficos=com_graficos,
        manifesto=manifesto,
        texto_manifesto=texto_do_manifesto(manifesto),
    )


def executar_descritiva(plano: PlanoDescritiva) -> ResultadoDescritiva:
    """
    Escreve o plano no disco. Não decide mais nada.

    A ordem é a da Fase 3, e pelo mesmo motivo: o recibo vem depois do que ele
    descreve. Arquiva a rodada anterior, cria a pasta, escreve as tabelas, desenha
    os gráficos, e só então o `manifesto.json` — que é o índice, e um índice que
    aponta para arquivo inexistente é pior do que índice nenhum.

    Cada etapa registra como voltar atrás. Uma falha no meio desfaz o que já foi
    feito, inclusive devolvendo a pasta arquivada ao lugar — senão a rodada
    anterior teria sumido em troca de nada.
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

        # `existia` antes do `mkdir`: a pasta só entra no desfazer quando foi
        # este comando que a criou. O `rmdir` é registrado **antes** dos
        # arquivos e o desfazer roda ao contrário, então os arquivos saem
        # primeiro e a pasta sai vazia, que é a única forma de ela sair.
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

        if plano.com_graficos and plano.graficos:
            # O `matplotlib` entra aqui dentro, e não no topo do arquivo: ele custa
            # perto de meio segundo para carregar, e `--sem-graficos` não deve
            # pagar por ele. É a mesma decisão que a Fase 4 tomou com o `pandas` na
            # CLI.
            from .graficos import desenhar

            for grafico in plano.graficos:
                caminho = plano.pasta / grafico.nome
                desenhar(grafico, caminho)
                criados.append(caminho)
                desfazer.append(lambda p=caminho: p.unlink(missing_ok=True))

        caminho = plano.pasta / ARQUIVO_MANIFESTO
        escrever_atomico(caminho, plano.texto_manifesto)
        criados.append(caminho)

        try:
            anotar(plano.raiz, _acao_do_historico(plano), plano.descritiva.quando)
        except OSError as erro:
            avisos.append(
                f"A descritiva foi escrita, mas não consegui escrever no "
                f"historico.md: {erro}"
            )

    except Exception:
        # Qualquer falha, e não só `OSError` e `DescritivaError`. O que roda
        # aqui dentro inclui o `matplotlib`, que estoura com exceções próprias
        # — e uma delas subindo sem passar por aqui deixava a rodada anterior
        # arquivada em troca de nada, que é exatamente o que o desfazer existe
        # para impedir. O erro continua subindo inteiro: o que muda é que o
        # disco volta ao estado de antes antes de ele subir.
        for passo in reversed(desfazer):
            try:
                passo()
            except OSError:
                avisos.append(
                    "Falhei ao desfazer uma etapa. Confira "
                    f"{PASTA_ANALISES}/{PASTA_DESCRITIVA} e {PASTA_ANTIGAS} antes "
                    "de rodar de novo."
                )
        raise

    return ResultadoDescritiva(
        criados=tuple(criados), arquivado=arquivado, avisos=tuple(avisos)
    )


def descrever(
    banco: Banco,
    ficha: Ficha,
    linhas_do_dicionario: Sequence[Linha],
    quando: datetime | None = None,
) -> Descritiva:
    """
    Descreve o banco obedecendo ao dicionário. Função pura.

    Separada de `preparar_descritiva` porque é o miolo testável, como o `perfilar`
    da Fase 4: dá para jogar um `DataFrame` montado à mão e uma lista de `Linha`
    aqui dentro e afirmar sobre as tabelas, sem pasta de projeto e sem disco.

    Raises:
        VariavelIncompativelError, NadaParaAnalisarError
    """
    quadro = banco.quadro
    total = int(quadro.shape[0])

    analisaveis = [linha for linha in linhas_do_dicionario if linha.analisavel]
    _recusar_incompativeis(quadro, analisaveis)

    fora: list[ForaDaDescritiva] = [
        ForaDaDescritiva(linha.variavel, linha.tipo, _motivo_de_fora(linha))
        for linha in linhas_do_dicionario
        if not linha.analisavel
    ]

    variaveis: list[VariavelDescrita] = []
    usados: set[str] = set()

    for linha in analisaveis:
        serie = _coluna(quadro, linha.variavel)
        if serie is None:  # pragma: no cover - `_recusar_incompativeis` já barrou
            continue

        slug = _slug(linha.variavel, usados)
        descrita = _descrever_variavel(linha, serie, slug, total)
        if descrita is None:
            fora.append(
                ForaDaDescritiva(
                    linha.variavel,
                    linha.tipo,
                    "coluna sem nenhum valor preenchido",
                )
            )
            continue
        variaveis.append(descrita)

    if not variaveis:
        raise NadaParaAnalisarError(_mensagem_nada_a_analisar(linhas_do_dicionario))

    avisos = list(banco.avisos)
    avisos += [aviso for v in variaveis for aviso in v.avisos]

    return Descritiva(
        ficha=ficha,
        banco=banco,
        variaveis=tuple(variaveis),
        fora=tuple(fora),
        avisos=tuple(avisos),
        quando=quando or datetime.now(),
    )


# Uma variável


def _descrever_variavel(
    linha: Linha, serie: pd.Series, slug: str, total: int
) -> VariavelDescrita | None:
    """
    Despacha para o tipo declarado no dicionário. Devolve `None` para coluna vazia.
    """
    faltantes = int(serie.isna().sum())
    if faltantes == total:
        return None

    if linha.tipo == CATEGORICA:
        return _descrever_categorica(linha, serie, slug, total, faltantes)
    if linha.tipo == NUMERICA:
        return _descrever_numerica(linha, serie, slug, total, faltantes)
    return _descrever_data(linha, serie, slug, total, faltantes)


def _descrever_categorica(
    linha: Linha, serie: pd.Series, slug: str, total: int, faltantes: int
) -> VariavelDescrita:
    """
    Frequência absoluta e relativa, com e sem faltantes, mais o gráfico de barras.

    A ordem das linhas é a do dicionário quando `categorias_ordem` está preenchida
    — é a decisão da reunião, e é o que faz duas tabelas do mesmo estudo
    apresentarem "Feminino" sempre antes de "Masculino". Sem ela, frequência
    decrescente com desempate alfabético, que é a ordem em que uma tabela nominal
    se lê e é determinística.

    Categoria declarada e ausente do banco sai com `n = 0`, em vez de sumir: a
    tabela do relatório precisa ser a mesma antes e depois de o cliente mandar a
    versão em que aquela categoria não apareceu. E valor que está no banco e não
    foi declarado entra no fim, com aviso — é assim que um `"Sim "` com espaço se
    denuncia sozinho.
    """
    textos = _serie_de_texto(serie)
    observadas = {
        str(valor): int(quantos) for valor, quantos in textos.value_counts().items()
    }
    preenchidos = total - faltantes

    declaradas = tuple(linha.categorias_ordem)
    avisos: list[str] = []

    if declaradas:
        ordem = list(declaradas)
        extras = sorted(
            (valor for valor in observadas if valor not in declaradas),
            key=lambda valor: (-observadas[valor], valor),
        )
        ordem += extras
        ausentes = [valor for valor in declaradas if valor not in observadas]
        if extras:
            avisos.append(
                f"`{linha.variavel}`: {len(extras)} valor(es) no banco fora da ordem "
                f"declarada no dicionário ({', '.join(repr(v) for v in extras[:5])}). "
                "Entraram no fim da tabela. Se for grafia diferente da declarada, "
                "acerte o dicionário ou peça a padronização ao cliente."
            )
        if ausentes:
            avisos.append(
                f"`{linha.variavel}`: {len(ausentes)} categoria(s) do dicionário sem "
                f"nenhum caso nesta versão do banco "
                f"({', '.join(linha.rotulo_de(v) for v in ausentes[:5])}). "
                "Ficaram na tabela com n = 0."
            )
    else:
        ordem = sorted(observadas, key=lambda valor: (-observadas[valor], valor))

    # O código conta, o rótulo imprime.
    #
    # `ordem` são os valores como eles estão na coluna do banco — é por eles que
    # `observadas` é consultada. O que vai para a tabela e para o gráfico é o
    # rótulo, que cai no próprio código quando não há um. Uma coluna de texto
    # atravessa isto sem nada acontecer: lá o valor **é** o rótulo.
    # Nome próprio, e não `contagem` de novo: o `value_counts` acima devolvia uma
    # `Series` indexada pelo valor do banco, e isto é um `dict` indexado pelo
    # rótulo. São duas coisas diferentes, e reaproveitar o nome fazia o miolo da
    # função mais importante do módulo depender de qual das duas era a da linha.
    por_rotulo: dict[str, int] = {}
    codigos_do_rotulo: dict[str, list[str]] = {}
    for codigo in ordem:
        nome_na_tabela = linha.rotulo_de(codigo)
        por_rotulo[nome_na_tabela] = (
            por_rotulo.get(nome_na_tabela, 0) + observadas.get(codigo, 0)
        )
        codigos_do_rotulo.setdefault(nome_na_tabela, []).append(codigo)

    # Dois códigos com o mesmo rótulo viram **uma linha só, somada**. Não é
    # tolerância a erro de digitação: é a promessa que o cabeçalho deste módulo
    # faz desde a Fase 4 — *"reagrupar categorias vira editar uma célula, não
    # caçar código"*. Escrever `1=Sim|2=Sim` é o jeito de dizer "some estes dois",
    # e duas linhas chamadas «Sim» na mesma tabela seriam a promessa quebrada.
    #
    # O aviso abaixo é o que impede o agrupamento acidental de passar: ele nomeia
    # quais códigos foram somados em qual rótulo, e aparece na tela e no manifesto.
    juntados = {r: c for r, c in codigos_do_rotulo.items() if len(c) > 1}
    if juntados:
        quais = "; ".join(
            f"{' + '.join(cs)} → «{r}»" for r, cs in list(juntados.items())[:5]
        )
        avisos.append(
            f"`{linha.variavel}`: {len(juntados)} rótulo(s) reúnem mais de um código e "
            f"foram somados em uma linha ({quais}). Se o agrupamento for o que você "
            "quis, está certo; se dois rótulos ficaram iguais sem querer, corrija o "
            f"`{ARQUIVO_DICIONARIO}`."
        )

    sem_rotulo = [codigo for codigo, rotulo in linha.rotulos_das_categorias if not rotulo]
    if sem_rotulo:
        avisos.append(
            f"`{linha.variavel}`: {len(sem_rotulo)} categoria(s) com `=` e nada depois "
            f"({', '.join(sem_rotulo[:5])}). Elas saíram na tabela com o próprio código. "
            "Escreva o rótulo depois do sinal, ou apague o sinal."
        )

    pares = list(por_rotulo.items())

    corpo = [
        (
            valor,
            str(quantos),
            _percentual(quantos, preenchidos),
            _percentual(quantos, total),
        )
        for valor, quantos in pares
    ]
    corpo.append(
        (ROTULO_FALTANTE, str(faltantes), "—", _percentual(faltantes, total))
    )
    corpo.append((ROTULO_TOTAL, str(total), _percentual(1, 1), _percentual(1, 1)))

    tabela = Tabela(
        nome=f"freq_{slug}.csv",
        especie="frequencia",
        variavel=linha.variavel,
        titulo=f"Frequência — {linha.rotulo or linha.variavel}",
        colunas=("categoria", "n", "% dos válidos", "% do total"),
        linhas=tuple(corpo),
        notas=(
            f"% dos válidos: denominador {preenchidos} (sem os faltantes).",
            f"% do total: denominador {total} (com os faltantes).",
            "ordem: "
            + ("do dicionário" if declaradas else "frequência decrescente"),
        )
        + (
            (
                "categorias rotuladas pelo dicionário: "
                + ", ".join(
                    f"{codigo} = {rotulo}"
                    for codigo, rotulo in linha.rotulos_das_categorias
                    if rotulo
                )
                + ".",
            )
            if linha.tem_rotulos
            else ()
        ),
    )

    graficos = ()
    if any(quantos for _, quantos in pares):
        graficos = (_grafico_de_barras(linha, slug, pares, preenchidos, faltantes),)

    return VariavelDescrita(
        variavel=linha.variavel,
        slug=slug,
        rotulo=linha.rotulo or linha.variavel,
        tipo=CATEGORICA,
        n=total,
        faltantes=faltantes,
        tabelas=(tabela,),
        graficos=graficos,
        detalhes={
            "categorias": len(pares),
            "ordem": "dicionario" if declaradas else "frequencia",
            "declaradas": list(declaradas),
            # O mapa vai para o manifesto de propósito: é ele que responde, seis
            # meses depois, de onde saiu a palavra «Feminino» em uma tabela cuja
            # coluna no banco só tem `1` e `2`.
            "rotulos": {
                codigo: rotulo for codigo, rotulo in linha.rotulos_das_categorias
            },
            "agrupadas": {rotulo: list(cs) for rotulo, cs in juntados.items()},
        },
        avisos=tuple(avisos),
    )


def _descrever_numerica(
    linha: Linha, serie: pd.Series, slug: str, total: int, faltantes: int
) -> VariavelDescrita:
    """
    Resumo, tabela por faixas e histograma.

    O resumo traz mais do que o mínimo e o máximo que o roteiro pede, e é
    deliberado: média, desvio, mediana e quartis são o que o relatório da Fase 6
    escreve sobre uma numérica, e tê-los aqui é o que impede a Fase 6 de reabrir o
    banco para recalcular — que é a porta pela qual o relatório passa a discordar
    da tabela.
    """
    valores = serie.dropna().astype("float64")
    preenchidos = int(valores.shape[0])
    avisos: list[str] = []

    resumo = _resumo_numerico(valores)
    # As casas da variável, e não as duas de sempre: numa concentração na casa de
    # 0,003, duas casas faziam o resumo inteiro sair `0`. Ver `banco.casas_do_resumo`.
    casas = casas_do_resumo(resumo)
    tabela_resumo = Tabela(
        nome=f"resumo_{slug}.csv",
        especie="resumo",
        variavel=linha.variavel,
        titulo=f"Resumo — {linha.rotulo or linha.variavel}",
        colunas=("estatistica", "valor"),
        linhas=(
            ("n válidos", str(preenchidos)),
            ("faltantes", str(faltantes)),
            ("mínimo", _numero(resumo["minimo"], casas)),
            ("q1", _numero(resumo["q1"], casas)),
            ("mediana", _numero(resumo["mediana"], casas)),
            ("q3", _numero(resumo["q3"], casas)),
            ("máximo", _numero(resumo["maximo"], casas)),
            ("média", _numero(resumo["media"], casas)),
            ("desvio padrão", _numero(resumo["desvio"], casas)),
        ),
        notas=(f"denominador: {preenchidos} válidos de {total} linhas.",),
    )

    tabelas = [tabela_resumo]
    detalhes: dict[str, Any] = {
        "preenchidos": preenchidos,
        "resumo": {chave: _arredondar(valor) for chave, valor in resumo.items()},
    }

    cortes, origem, motivo = _cortes_das_faixas(linha, valores)
    if cortes:
        # O corte escrito no dicionário sai como foi escrito: `0,00255` impresso com
        # as casas da variável seria um corte que ninguém pediu.
        casas_dos_cortes = (
            max(casas, _casas_escritas(linha.faixas))
            if origem == FAIXAS_DICIONARIO
            else casas
        )
        tabela_faixas, fora_das_faixas = _tabela_de_faixas(
            linha, slug, valores, cortes, origem, total, faltantes, casas_dos_cortes
        )
        tabelas.append(tabela_faixas)
        detalhes["faixas"] = {
            "origem": origem,
            # Os do dicionário vão inteiros: o relatório os compara com o dicionário
            # de hoje, e `0,00255` gravado como `0.0026` era um "dicionário mudou" falso.
            "cortes": [
                float(c) if origem == FAIXAS_DICIONARIO else _arredondar(c) for c in cortes
            ],
            "abaixo": fora_das_faixas[0],
            "acima": fora_das_faixas[1],
        }
        if sum(fora_das_faixas):
            avisos.append(
                f"`{linha.variavel}`: {sum(fora_das_faixas)} caso(s) fora das faixas "
                "declaradas no dicionário. Eles aparecem em linha própria na tabela "
                "— os cortes precisam cobrir o mínimo e o máximo da variável."
            )
    else:
        detalhes["faixas"] = {"origem": None, "motivo": motivo}
        avisos.append(f"`{linha.variavel}`: sem tabela por faixas — {motivo}.")

    graficos = ()
    bordas, contagens = _histograma(valores)
    if bordas:
        graficos = (
            Grafico(
                nome=f"hist_{slug}.png",
                especie="histograma",
                variavel=linha.variavel,
                titulo=linha.rotulo or linha.variavel,
                subtitulo=_subtitulo(preenchidos, faltantes),
                rotulo_categoria=linha.rotulo or linha.variavel,
                rotulo_valor="casos",
                bordas=bordas,
                contagens=contagens,
            ),
        )
        detalhes["histograma"] = {"classes": len(contagens)}

    return VariavelDescrita(
        variavel=linha.variavel,
        slug=slug,
        rotulo=linha.rotulo or linha.variavel,
        tipo=NUMERICA,
        n=total,
        faltantes=faltantes,
        tabelas=tuple(tabelas),
        graficos=graficos,
        detalhes=detalhes,
        avisos=tuple(avisos),
    )


def _descrever_data(
    linha: Linha, serie: pd.Series, slug: str, total: int, faltantes: int
) -> VariavelDescrita | None:
    """
    O período (de quando a quando) e como os casos se distribuem dentro dele.

    Devolve `None` quando não sobrou nenhuma data válida, como a coluna vazia:
    sem data não há período a descrever.
    """
    datas, formato, nao_convertidos = _como_data(serie)
    validas = datas.dropna()
    if validas.empty:
        # Sem nenhuma data válida não há período: `minimo` e `maximo` saem `NaT`
        # e `(maximo - minimo).days` estoura. Hoje é inalcançável — a recusa de
        # `recusar_incompativeis` exige um formato que explique 90% da coluna —,
        # e a guarda existe porque «inalcançável» é uma propriedade de outro
        # módulo, não desta função. `None` a manda para a lista `fora`, que é
        # onde as colunas sem valor já são registradas.
        return None

    preenchidos = int(validas.shape[0])
    avisos: list[str] = []
    de_onde = (
        "do próprio arquivo"
        if formato is None
        else f"a partir do texto, formato {formato}"
    )

    if nao_convertidos:
        avisos.append(
            f"`{linha.variavel}`: {nao_convertidos} valor(es) não são data no formato "
            f"`{formato}` e entraram como faltantes. O formato foi deduzido da própria "
            "coluna; confira no `perfil.md` se há mais de um formato misturado."
        )

    faltantes_efetivos = total - preenchidos

    minimo, maximo = validas.min(), validas.max()
    amplitude = int((maximo - minimo).days)

    tabela_data = Tabela(
        nome=f"data_{slug}.csv",
        especie="data",
        variavel=linha.variavel,
        titulo=f"Período — {linha.rotulo or linha.variavel}",
        colunas=("estatistica", "valor"),
        linhas=(
            ("n válidos", str(preenchidos)),
            ("faltantes", str(faltantes_efetivos)),
            ("primeira data", _data(minimo)),
            ("última data", _data(maximo)),
            ("amplitude (dias)", str(amplitude)),
        ),
        notas=(f"lida como data {de_onde}.",),
    )

    passo = "mes" if amplitude <= MESES_PARA_MENSAL * 31 else "ano"
    passo_legivel = "mês" if passo == "mes" else "ano"
    periodos = _contar_periodos(validas, passo)

    corpo = [
        (rotulo, str(quantos), _percentual(quantos, preenchidos))
        for rotulo, quantos in periodos
    ]
    corpo.append((ROTULO_TOTAL, str(preenchidos), _percentual(1, 1)))

    tabela_periodo = Tabela(
        nome=f"periodo_{slug}.csv",
        especie="periodo",
        variavel=linha.variavel,
        titulo=f"Distribuição no tempo — {linha.rotulo or linha.variavel}",
        colunas=("por " + passo_legivel, "n", "% dos válidos"),
        linhas=tuple(corpo),
        notas=(
            f"denominador: {preenchidos} válidos.",
            "períodos sem nenhum caso aparecem com n = 0, para que o vazio seja "
            "visível.",
        ),
    )

    graficos = ()
    if periodos and len(periodos) <= LIMITE_COLUNAS_TEMPO:
        graficos = (
            Grafico(
                nome=f"graf_periodo_{slug}.png",
                especie="colunas",
                variavel=linha.variavel,
                titulo=linha.rotulo or linha.variavel,
                subtitulo=_subtitulo(preenchidos, faltantes_efetivos),
                rotulo_categoria=passo_legivel,
                rotulo_valor="casos",
                categorias=tuple(rotulo for rotulo, _ in periodos),
                valores=tuple(float(quantos) for _, quantos in periodos),
                rotulos=tuple(str(quantos) for _, quantos in periodos),
            ),
        )
    elif periodos:
        avisos.append(
            f"`{linha.variavel}`: a distribuição tem {len(periodos)} períodos e saiu "
            f"sem gráfico (o limite é {LIMITE_COLUNAS_TEMPO} colunas). A tabela está "
            "completa. Se a variável for data de nascimento, ela costuma servir "
            "melhor como idade — uma coluna numérica."
        )

    return VariavelDescrita(
        variavel=linha.variavel,
        slug=slug,
        rotulo=linha.rotulo or linha.variavel,
        tipo=DATA,
        n=total,
        faltantes=faltantes_efetivos,
        tabelas=(tabela_data, tabela_periodo),
        graficos=graficos,
        detalhes={
            "formato": formato,
            "nao_convertidos": nao_convertidos,
            "primeira": _data(minimo),
            "ultima": _data(maximo),
            "amplitude_dias": amplitude,
            "passo": passo,
            "periodos": len(periodos),
        },
        avisos=tuple(avisos),
    )


# Faixas


def _cortes_das_faixas(
    linha: Linha, valores: pd.Series
) -> tuple[tuple[float, ...], str, str]:
    """
    Os cortes que valem para esta variável, e de onde eles vieram.

    A coluna `faixas` do dicionário manda. Ela já chegou conferida pela Fase 4 —
    números em ordem crescente —, então aqui não há o que validar de novo.

    Sem ela, os quartis: mínimo, Q1, mediana, Q3 e máximo, sem repetir. O que
    sobra depois de tirar os repetidos precisa ser **pelo menos três cortes** —
    isto é, duas faixas —, e não cinco: uma variável em que só a mediana coincide
    com Q1 ainda produz três faixas honestas, e recusá-la seria jogar fora uma
    tabela correta por causa de um empate.

    Abaixo de três, não sai tabela nenhuma e o motivo fica escrito no manifesto:
    com dois cortes sobraria uma faixa só, que é a variável inteira e não
    descreve nada. Uma variável assim é categórica disfarçada de número, e a
    decisão de tratá-la como tal é sua, no dicionário.
    """
    if linha.faixas:
        cortes = tuple(float(str(f).replace(",", ".")) for f in linha.faixas)
        return cortes, FAIXAS_DICIONARIO, ""

    preenchidos = int(valores.shape[0])
    if preenchidos < MINIMO_PARA_FAIXAS:
        return (), "", f"apenas {preenchidos} valor(es) válido(s)"

    quartis = [
        float(valores.min()),
        float(valores.quantile(0.25)),
        float(valores.median()),
        float(valores.quantile(0.75)),
        float(valores.max()),
    ]
    cortes = tuple(sorted(set(quartis)))
    if len(cortes) < 3:
        return (
            (),
            "",
            f"os quartis coincidem ({int(valores.nunique())} valor(es) distinto(s)) — "
            "é uma variável categórica disfarçada de número",
        )
    return cortes, FAIXAS_QUARTIS, ""


def _tabela_de_faixas(
    linha: Linha,
    slug: str,
    valores: pd.Series,
    cortes: tuple[float, ...],
    origem: str,
    total: int,
    faltantes: int,
    casas: int = CASAS_RESUMO,
) -> tuple[Tabela, tuple[int, int]]:
    """
    Conta os casos em cada faixa, com uma convenção só e escrita no arquivo.

    `[a a b)` inclui `a` e exclui `b`; a última faixa inclui os dois extremos. É a
    convenção das faixas etárias — `0|18|30` são "menor de 18", "de 18 a 29" —, e
    é a única que não deixa um caso em duas faixas nem fora de todas.

    A contagem é feita à mão, e não com `pd.cut`, por causa dessa última faixa: o
    `pd.cut` fecha todos os intervalos do mesmo lado, e o máximo da variável cairia
    fora do último. Um caso perdido em silêncio no extremo é exatamente o tipo de
    erro que ninguém confere.
    """
    preenchidos = int(valores.shape[0])
    corpo: list[tuple[str, ...]] = []

    for posicao in range(len(cortes) - 1):
        inferior, superior = cortes[posicao], cortes[posicao + 1]
        ultima = posicao == len(cortes) - 2
        de, ate = _numero(inferior, casas), _numero(superior, casas)
        if ultima:
            dentro = (valores >= inferior) & (valores <= superior)
            rotulo = f"[{de} a {ate}]"
        else:
            dentro = (valores >= inferior) & (valores < superior)
            rotulo = f"[{de} a {ate})"
        quantos = int(dentro.sum())
        corpo.append(
            (
                rotulo,
                de,
                ate,
                str(quantos),
                _percentual(quantos, preenchidos),
                _percentual(quantos, total),
            )
        )

    abaixo = int((valores < cortes[0]).sum())
    acima = int((valores > cortes[-1]).sum())
    for rotulo, quantos in ((ROTULO_ABAIXO, abaixo), (ROTULO_ACIMA, acima)):
        if quantos:
            corpo.append(
                (
                    rotulo,
                    "—",
                    "—",
                    str(quantos),
                    _percentual(quantos, preenchidos),
                    _percentual(quantos, total),
                )
            )

    corpo.append(
        (ROTULO_FALTANTE, "—", "—", str(faltantes), "—", _percentual(faltantes, total))
    )
    corpo.append(
        (ROTULO_TOTAL, "—", "—", str(total), _percentual(1, 1), _percentual(1, 1))
    )

    de_onde = (
        "cortes do dicionário"
        if origem == FAIXAS_DICIONARIO
        else "quartis da própria variável (regra padrão)"
    )
    tabela = Tabela(
        nome=f"faixas_{slug}.csv",
        especie="faixas",
        variavel=linha.variavel,
        titulo=f"Faixas — {linha.rotulo or linha.variavel}",
        colunas=(
            "faixa",
            "limite inferior",
            "limite superior",
            "n",
            "% dos válidos",
            "% do total",
        ),
        linhas=tuple(corpo),
        notas=(
            f"faixas: {de_onde}.",
            "[a a b) inclui a e exclui b; a última faixa inclui os dois extremos.",
            f"% dos válidos: denominador {preenchidos}. % do total: denominador {total}.",
        ),
    )
    return tabela, (abaixo, acima)


def _histograma(valores: pd.Series) -> tuple[tuple[float, ...], tuple[int, ...]]:
    """
    As classes do histograma, calculadas aqui e não no `graficos.py`.

    Quantas classes usar é decisão estatística, não de desenho: Freedman-Diaconis
    quando o intervalo interquartil existe (é robusto a valor extremo, que em banco
    de saúde é regra), Sturges quando ele é zero. O número de classes sai no
    manifesto, que é o que permite descobrir depois por que um histograma mudou de
    cara entre duas rodadas.

    Deliberadamente **não** são as faixas da tabela: a tabela responde "quantos em
    cada grupo que interessa"; o histograma mostra a forma da distribuição. Fazer
    os dois com os mesmos cortes é publicar a mesma informação duas vezes.
    """
    preenchidos = int(valores.shape[0])
    if preenchidos < 2:
        return (), ()

    minimo, maximo = float(valores.min()), float(valores.max())
    if not math.isfinite(minimo) or not math.isfinite(maximo) or minimo == maximo:
        return (), ()

    iiq = float(valores.quantile(0.75) - valores.quantile(0.25))
    if iiq > 0:
        largura = 2 * iiq / (preenchidos ** (1 / 3))
        classes = max(1, math.ceil((maximo - minimo) / largura)) if largura > 0 else 1
    else:
        classes = max(1, math.ceil(math.log2(preenchidos) + 1))

    classes = int(min(max(classes, 3), 50))
    largura = (maximo - minimo) / classes
    bordas = [minimo + largura * i for i in range(classes)] + [maximo]

    contagens: list[int] = []
    for posicao in range(classes):
        inferior, superior = bordas[posicao], bordas[posicao + 1]
        if posicao == classes - 1:
            dentro = (valores >= inferior) & (valores <= superior)
        else:
            dentro = (valores >= inferior) & (valores < superior)
        contagens.append(int(dentro.sum()))

    return tuple(bordas), tuple(contagens)


# Gráfico de barras


def _grafico_de_barras(
    linha: Linha,
    slug: str,
    pares: list[tuple[str, int]],
    preenchidos: int,
    faltantes: int,
) -> Grafico:
    """
    O gráfico da categórica: uma barra por categoria, na ordem da tabela.

    Acima de `LIMITE_BARRAS` categorias a cauda vira uma barra "Outras". Um gráfico
    de sessenta barras não é lido por ninguém, e a tabela ao lado continua com
    todas — o gráfico é a leitura rápida, a tabela é a fonte.

    Os faltantes não viram barra. O gráfico descreve a distribuição da variável
    entre quem respondeu; quantos não responderam é uma frase do subtítulo e uma
    linha da tabela.
    """
    visiveis = list(pares)
    juntadas = 0
    if len(visiveis) > LIMITE_BARRAS:
        cauda = visiveis[LIMITE_BARRAS:]
        juntadas = len(cauda)
        visiveis = visiveis[:LIMITE_BARRAS]
        visiveis.append((f"{ROTULO_OUTRAS} ({juntadas})", sum(q for _, q in cauda)))

    subtitulo = _subtitulo(preenchidos, faltantes)
    if juntadas:
        subtitulo += f" · {juntadas} categorias reunidas em {ROTULO_OUTRAS}"

    return Grafico(
        nome=f"graf_{slug}.png",
        especie="barras",
        variavel=linha.variavel,
        titulo=linha.rotulo or linha.variavel,
        subtitulo=subtitulo,
        rotulo_valor="casos",
        categorias=tuple(valor for valor, _ in visiveis),
        valores=tuple(float(quantos) for _, quantos in visiveis),
        rotulos=tuple(
            f"{quantos}  ({_percentual(quantos, preenchidos)}%)"
            for _, quantos in visiveis
        ),
    )


# O manifesto


def montar_manifesto(
    descritiva: Descritiva, linhas: Sequence[Linha], com_graficos: bool
) -> Manifesto:
    """
    Traduz a descritiva para o índice que a Fase 6 vai ler.
    """
    banco = descritiva.banco
    leitura = banco.leitura
    ficha = descritiva.ficha

    itens = tuple(
        ItemDoManifesto(
            variavel=v.variavel,
            slug=v.slug,
            rotulo=v.rotulo,
            tipo=v.tipo,
            n=v.n,
            faltantes=v.faltantes,
            artefatos=_artefatos(v, com_graficos),
            detalhes=dict(v.detalhes),
            avisos=v.avisos,
            # Uma seção da descritiva usa exatamente uma coluna, e é por isso que
            # o campo parecia redundante até existir a segunda análise. Ele é
            # escrito aqui porque a conferência do relatório passou a perguntar
            # "quais colunas esta rodada usou?" a **toda** rodada — e uma pergunta
            # que só algumas respondem é uma pergunta que não se pode fazer.
            colunas=(v.variavel,),
        )
        for v in descritiva.variaveis
    )

    return Manifesto(
        analise=ANALISE_DESCRITIVA,
        flatcap=__version__,
        gerado_em=descritiva.quando,
        projeto={
            # Cliente **e** projeto. Desde a 1.1.0 `raiz.name` é `Projeto 006`,
            # e o manifesto é o recibo da rodada: um recibo que não diz de quem
            # é o trabalho não serve para conferir coisa nenhuma depois.
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
            "integridade": _integridade(banco.confere),
        },
        dicionario={
            "arquivo": ARQUIVO_DICIONARIO,
            "variaveis": len(linhas),
            "analisaveis": sum(1 for linha in linhas if linha.analisavel),
            # Mesmo campo, mesmo esquema que o manifesto da normalidade. Dois
            # blocos `dicionario` com chaves diferentes obrigariam quem lê os
            # dois — o relatório, e você — a saber de qual análise é o arquivo
            # antes de saber o que perguntar a ele.
            "numericas": sum(
                1 for linha in linhas if linha.analisavel and linha.tipo == NUMERICA
            ),
        },
        ambiente=_ambiente(com_graficos),
        regras={
            "faixas_padrao": FAIXAS_QUARTIS,
            "fechamento_das_faixas": "[a a b) — a última faixa inclui os dois extremos",
            "graficos": com_graficos,
            "limite_de_barras": LIMITE_BARRAS,
            "semente": SEMENTE,
        },
        itens=itens,
        fora=tuple(
            {"variavel": f.variavel, "tipo": f.tipo, "motivo": f.motivo}
            for f in descritiva.fora
        ),
        avisos=descritiva.avisos,
    )


def _artefatos(variavel: VariavelDescrita, com_graficos: bool) -> tuple[Artefato, ...]:
    artefatos = [
        Artefato(
            arquivo=tabela.nome,
            especie=tabela.especie,
            formato="csv",
            titulo=tabela.titulo,
        )
        for tabela in variavel.tabelas
    ]
    if com_graficos:
        artefatos += [
            Artefato(
                arquivo=grafico.nome,
                especie=grafico.especie,
                formato="png",
                titulo=grafico.titulo,
            )
            for grafico in variavel.graficos
        ]
    return tuple(artefatos)


def _ambiente(com_graficos: bool) -> dict[str, Any]:
    """
    As versões que produziram estes números.

    O roteiro pede isso, e a justificativa dele é literal: no dia em que um gráfico
    sair diferente do que saía antes, é o que responde se mudaram os dados ou mudou
    a biblioteca. O `matplotlib` só é consultado quando há gráfico — perguntar a
    versão custaria importar a biblioteca que o `--sem-graficos` existe para evitar.

    A **fonte** entra junto, e ela não é uma versão: é a fonte que o matplotlib de
    fato resolveu, que pode não ser a que o `graficos.py` pediu. Sem o Arial
    instalado ele escreve um aviso em `stderr`, que ninguém lê, e desenha com o
    próximo nome da lista — o gráfico sai bonito, com a fonte errada, e a única
    forma de descobrir é pôr a figura ao lado do texto do documento e reparar.
    Escrita aqui, a pergunta «mudou a máquina ou mudou o código?» tem resposta.
    """
    import openpyxl

    ambiente: dict[str, Any] = {
        "python": ".".join(str(parte) for parte in sys.version_info[:3]),
        "flatcap": __version__,
        "pandas": pd.__version__,
        "openpyxl": openpyxl.__version__,
        "matplotlib": None,
        "fonte": None,
    }
    if com_graficos:
        from .graficos import fonte_dos_graficos, versao_do_matplotlib

        ambiente["matplotlib"] = versao_do_matplotlib()
        ambiente["fonte"] = fonte_dos_graficos()
    return ambiente


# Recusas


def conferir_dicionario(
    raiz: Path,
    banco: Banco,
    ausente: type[Exception] = DicionarioAusenteError,
    desatualizado: type[Exception] = DicionarioDesatualizadoError,
    analise: str = "a descritiva",
) -> tuple[Linha, ...]:
    """
    Lê o `dicionario.csv` e confere que ele descreve **este** banco.

    Pública desde a Fase 7, e com as duas classes de erro como parâmetro. A razão
    é que duas regras da casa se cruzam aqui:

    * **uma implementação só.** Toda análise obedece ao mesmo dicionário e
      pergunta a mesma coisa sobre o mesmo banco. Duas cópias desta conferência é
      como um comando aceita rodar sobre um dicionário que o outro recusou — e aí
      o relatório monta uma seção sobre variáveis que a outra seção não tem.
    * **um erro por módulo.** A CLI captura `DescritivaError` no comando
      `descritiva` e `NormalidadeError` no comando `normalidade`, e é isso que faz
      o painel sair com o título certo. Se esta função levantasse sempre
      `DescritivaError`, `flatcap normalidade` abriria um painel escrito
      "Descritiva" — sobre um comando que o usuário não rodou.

    Passar a classe resolve as duas sem escolher entre elas. O default é o da
    descritiva, então o chamador antigo não mudou.

    O `analise` entra só no texto, e entra porque a frase muda de dono: "a
    descritiva não tem o que obedecer" é a mesma informação que "a normalidade não
    tem o que obedecer", e nenhuma das duas deve dizer o nome da outra.
    """
    linhas = ler_dicionario(raiz)
    if not linhas:
        raise ausente(
            f"Este projeto não tem {ARQUIVO_DICIONARIO}, e {analise} não tem o que "
            "obedecer.\n"
            f"Esperado em: {caminho_do_dicionario(raiz)}\n\n"
            "O dicionário é escrito pelo `flatcap perfil` e preenchido por você na "
            "reunião — é onde está registrado o que é categórica, o que é numérica e "
            "o que fica de fora. Rode `flatcap perfil` e revise a coluna `tipo` antes "
            "de voltar aqui."
        )

    conhecidas = {linha.variavel for linha in linhas}
    novas = [str(nome) for nome in banco.quadro.columns if str(nome) not in conhecidas]
    if novas:
        # Entre aspas quando o nome tem espaço nas pontas ou quebra de linha: `Idade `
        # impresso solto é indistinguível de `Idade`, e a diferença é a recusa inteira.
        quais = "\n".join(
            f"  {nome!r}" if nome != nome.strip() or "\n" in nome else f"  {nome}"
            for nome in novas[:20]
        )
        resto = f"\n  ... e mais {len(novas) - 20}" if len(novas) > 20 else ""
        raise desatualizado(
            f"O banco tem {len(novas)} coluna(s) que o {ARQUIVO_DICIONARIO} "
            f"desconhece:\n{quais}{resto}\n\n"
            f"{analise.capitalize()} obedece ao dicionário e a mais nada — se ela "
            "rodasse assim, essas colunas ficariam fora do relatório sem que nada na "
            "saída dissesse que elas existem.\n"
            "Rode `flatcap perfil --sim`: a fusão acrescenta as variáveis novas e não "
            "toca em nenhuma linha que você já preencheu."
        )
    return linhas


# O nome privado que o resto deste módulo usa. Mesma manobra do
# `perfil._formato_de_data`: a função mudou de visibilidade, e nenhum chamador
# interno mudou de linha.
_dicionario_do_projeto = conferir_dicionario


def recusar_incompativeis(
    quadro: pd.DataFrame,
    analisaveis: Sequence[Linha],
    erro: type[Exception] = VariavelIncompativelError,
) -> None:
    """
    Recusa o comando inteiro quando o dicionário promete um tipo que a coluna não tem.

    É a decisão central da fase, e a razão dela é o denominador. Converter
    `"12,5"` em silêncio funciona nos valores que convertem e transforma os outros
    em faltantes — e uma média calculada sobre 80% dos casos sai com a mesma cara
    de uma calculada sobre 100%. O relatório não teria como denunciar isso, porque
    a conversão aconteceu antes de a contagem começar.

    Recusar devolve a decisão para onde ela pertence: o arquivo é do cliente, a
    correção é dele, e a Fase 3 tem o lugar certo para a versão corrigida entrar.
    Se a coluna não vai ser corrigida, o dicionário aceita `categorica` ou
    `ignorar` — as duas são decisões suas, escritas, e nenhuma delas é silenciosa.

    Pública desde a Fase 7, e com a classe de erro como parâmetro, pelo mesmo
    motivo do `conferir_dicionario` acima: a conferência precisa ser uma só e o
    painel precisa levar o nome do comando que o usuário rodou. Se a descritiva
    recusasse `peso` e a normalidade a aceitasse, o relatório sairia com um teste
    de normalidade sobre uma coluna que nenhuma tabela descreve.

    **Cada análise passa as variáveis que ela vai tocar**, e é por isso que a
    função recebe a lista em vez de ler o dicionário por conta própria. A
    normalidade só usa as `numerica`, então uma coluna `data` com dois formatos
    misturados — que recusa a descritiva — não bloqueia um teste que nunca a
    abriria. A regra é a mesma; o escopo é de quem chama.
    """
    problemas: list[tuple[str, str, list[str]]] = []

    for linha in analisaveis:
        serie = _coluna(quadro, linha.variavel)
        if serie is None:
            problemas.append(
                (linha.variavel, "não existe no banco (o dicionário a declara)", [])
            )
            continue

        preenchidos = serie.dropna()
        if preenchidos.empty:
            continue

        if linha.tipo == NUMERICA and not _e_numerica(serie):
            problemas.append(
                (
                    linha.variavel,
                    "está marcada `numerica` e chegou como texto",
                    _distintos(str(valor) for valor in preenchidos),
                )
            )
        elif linha.tipo == DATA and not _e_data(serie):
            textos = [str(valor) for valor in preenchidos]
            if formato_de_data(textos)[0] is None:
                problemas.append(
                    (
                        linha.variavel,
                        "está marcada `data` e não há um formato único que explique "
                        "a coluna",
                        _distintos(textos),
                    )
                )

    if problemas:
        raise erro(_mensagem_incompativel(problemas))


_recusar_incompativeis = recusar_incompativeis


def _mensagem_incompativel(problemas: list[tuple[str, str, list[str]]]) -> str:
    linhas = [
        f"{len(problemas)} variável(is) do dicionário não batem com a coluna do banco. "
        "Nada foi gerado.",
        "",
    ]
    for variavel, motivo, exemplos in problemas:
        linhas.append(f"  {variavel} — {motivo}")
        if exemplos:
            amostra = " · ".join(_encurtar(exemplo) for exemplo in exemplos)
            linhas.append(f"      valores: {amostra}")
    linhas += [
        "",
        "A descritiva não converte por conta própria: converter em silêncio é como "
        "uma média sai de 80% dos casos sem que nada na tabela diga que os outros "
        "20% não entraram.",
        "",
        "Três saídas, nesta ordem de preferência:",
        "  1. peça a correção ao cliente e registre a versão nova com "
        "`flatcap dados adicionar` — é o caminho que deixa rastro;",
        "  2. se a coluna é mesmo de texto, marque-a `categorica` no dicionário;",
        "  3. se ela não entra na descritiva, marque-a `ignorar`.",
        "",
        "O `perfil.md` deste projeto já lista essas colunas em 'Corrigir antes de "
        "começar', com exemplos para o cliente encontrar na planilha.",
    ]
    return "\n".join(linhas)


def _mensagem_nada_a_analisar(linhas: Sequence[Linha]) -> str:
    total = len(linhas)
    ignoradas = sum(1 for linha in linhas if linha.tipo == IGNORAR)
    fora_do_banco = sum(1 for linha in linhas if not linha.no_banco)
    return (
        f"Nenhuma das {total} variáveis do {ARQUIVO_DICIONARIO} entra na descritiva "
        f"({ignoradas} marcada(s) `ignorar`, {fora_do_banco} fora desta versão do "
        "banco, e o que sobrou está sem nenhum valor preenchido).\n\n"
        "Abra o dicionário e reveja a coluna `tipo`: `ignorar` é para identificador, "
        "texto livre e coluna auxiliar — não para tudo."
    )


def _motivo_de_fora(linha: Linha) -> str:
    if not linha.no_banco:
        return "não está nesta versão do banco (`no_banco = nao`)"
    return "marcada `ignorar` no dicionário"


# Arquivamento


def arquivamento(
    raiz: Path, pasta: Path, quando: datetime, analise: str = PASTA_DESCRITIVA
) -> tuple[Path, Path] | None:
    """
    Onde a rodada anterior vai parar, se houver uma.

    Arquivar a pasta inteira, e não sobrescrever arquivo por arquivo, é o que
    mantém cada rodada coerente consigo mesma: o `manifesto.json` de dentro
    descreve exatamente os arquivos que estão ao lado dele. Uma pasta sobrescrita
    pela metade teria a tabela nova de `sexo` ao lado do gráfico velho de `idade`,
    e nada diria qual é qual.

    O nome carrega data e hora porque duas rodadas no mesmo dia são o caso comum —
    você roda, olha, corrige o dicionário e roda de novo.

    Pública desde a Fase 7, com o nome da análise como parâmetro: a regra de
    arquivar é do desenho da pasta e vale para qualquer rodada, e o prefixo
    `descritiva_` era o único pedaço dela que sabia de qual análise se tratava.
    Com o parâmetro, `normalidade_2026-09-17_1500/` sai da mesma função — e a
    pasta `2. Versões antigas/` continua se lendo de cima para baixo, com o nome
    da análise na frente da data.
    """
    if not pasta.is_dir() or not any(pasta.iterdir()):
        return None

    base = raiz / PASTA_ANTIGAS / f"{analise}_{quando:%Y-%m-%d_%H%M}"
    destino = base
    sufixo = 2
    while destino.exists():
        destino = base.with_name(f"{base.name}_{sufixo}")
        sufixo += 1
    return pasta, destino


_arquivamento = arquivamento


def _acao_do_historico(plano: PlanoDescritiva) -> str:
    descritiva = plano.descritiva
    partes = [
        f"`flatcap descritiva {descritiva.ficha.record_id}` — descritiva de "
        f"`{descritiva.banco.versao.arquivo}`: {len(descritiva.variaveis)} variável(is), "
        f"{len(plano.tabelas)} tabela(s) e {len(plano.graficos)} gráfico(s) em "
        f"`{PASTA_ANALISES}/{PASTA_DESCRITIVA}/`."
    ]
    if plano.arquivamento is not None:
        partes.append(
            f"A rodada anterior foi para `{PASTA_ANTIGAS}/{plano.arquivamento[1].name}/`."
        )
    if not plano.com_graficos:
        partes.append("Rodado com `--sem-graficos`.")
    return " ".join(partes)


# Leitura da série


def _coluna(quadro: pd.DataFrame, nome: str) -> pd.Series | None:
    """
    A coluna do banco pelo nome, ou `None`.

    Pela posição, e não por `quadro[nome]`: nome repetido devolveria um `DataFrame`
    no lugar de uma coluna. A Fase 4 denuncia nome repetido como `cabecalho_repetido`
    e pede a correção; aqui a primeira ocorrência é usada, que é a que o dicionário
    descreve.
    """
    for posicao, coluna in enumerate(quadro.columns):
        if str(coluna) == nome:
            return quadro.iloc[:, posicao]
    return None


def _e_numerica(serie: pd.Series) -> bool:
    return bool(
        pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie)
    )


def _e_data(serie: pd.Series) -> bool:
    return bool(pd.api.types.is_datetime64_any_dtype(serie))


# A `serie_de_texto` desceu para o `banco.py` na 1.13.1, para o perfil propor as
# categorias com a mesma escrita das análises. Ela continua importável daqui —
# `from .descritiva import serie_de_texto` é como as outras análises a chamam —,
# e com o apelido privado que este módulo usa.
_serie_de_texto = serie_de_texto


def _como_data(serie: pd.Series) -> tuple[pd.Series, str | None, int]:
    """
    A coluna como data. Devolve a série, o formato usado e quantos não converteram.

    Já passou por `_recusar_incompativeis`, então ou a coluna é data no arquivo
    (`formato = None`), ou existe um formato único que explica quase toda ela.
    """
    if _e_data(serie):
        return serie, None, 0

    textos = [str(valor) for valor in serie.dropna()]
    formato, _ = formato_de_data(textos)
    convertidas = pd.to_datetime(serie, format=formato, errors="coerce")
    nao_convertidos = int(serie.notna().sum() - convertidas.notna().sum())
    return convertidas, formato, nao_convertidos


def resumo_numerico(valores: pd.Series) -> dict[str, float]:
    """
    Mínimo, quartis, mediana, máximo, média e desvio padrão de uma coluna já sem os
    faltantes.

    Pública desde a 1.7.0, com o apelido privado que este módulo usa. A comparação
    imprime a média e o desvio da mesma variável na tabela dela, e uma segunda conta
    é como a média do `resumo_imc.csv` diz `26,41` e a da comparação, na página
    seguinte, `26,4` — a manobra do `numero` e do `percentual`.
    """
    return {
        "minimo": float(valores.min()),
        "q1": float(valores.quantile(0.25)),
        "mediana": float(valores.median()),
        "q3": float(valores.quantile(0.75)),
        "maximo": float(valores.max()),
        "media": float(valores.mean()),
        "desvio": float(valores.std()) if int(valores.shape[0]) > 1 else 0.0,
    }


_resumo_numerico = resumo_numerico


def _contar_periodos(datas: pd.Series, passo: str) -> list[tuple[str, int]]:
    """
    Conta os casos por mês ou por ano, sem buracos.

    Período sem nenhum caso entra com zero de propósito: em um estudo, três meses
    sem recrutamento é informação — e uma tabela que simplesmente pula esses meses
    esconde justamente o que se queria ver.
    """
    if datas.empty:
        return []

    if passo == "mes":
        chaves = datas.dt.strftime("%Y-%m")
        inicio = datas.min().to_period("M")
        fim = datas.max().to_period("M")
        todos = [str(p) for p in pd.period_range(inicio, fim, freq="M")]
    else:
        chaves = datas.dt.strftime("%Y")
        todos = [str(ano) for ano in range(int(datas.min().year), int(datas.max().year) + 1)]

    contagem = chaves.value_counts()
    return [(rotulo, int(contagem.get(rotulo, 0))) for rotulo in todos]


# Formatação


def numero(valor: float | None, casas: int = CASAS_RESUMO) -> str:
    """
    Número no formato brasileiro, sem separador de milhar.

    Sem milhar de propósito: `1.234,5` numa célula é a forma mais fácil de um
    número virar texto na volta, e estes arquivos existem para serem lidos de volta
    — pela Fase 6 e por você, no Excel.

    Pública desde a Fase 7 pelo mesmo motivo do `tamanho_legivel` do `projeto.py`:
    dois formatadores diferentes para a mesma grandeza é como um relatório sai com
    `20,5` em uma tabela e `20.5` na seguinte, na mesma página. Pelo mesmo motivo,
    a conta mora no `banco.texto_de_numero` desde a 1.13.1: a `serie_de_texto`
    desceu para lá e escreve os números com ela.
    """
    return texto_de_numero(valor, casas)


_numero = numero


def percentual(parte: float, total: float) -> str:
    """
    Percentual com casas fixas: `5,0` e `100,0`, nunca `5` e `100`.

    Ao contrário das estatísticas, aqui o zero à direita não é ruído: uma coluna
    de percentuais em que uns valores têm casa decimal e outros não é uma coluna
    que não alinha, e desalinhada ela deixa de ser lida de cima para baixo — que é
    a única forma de ler uma tabela de frequência.

    Pública desde a 1.4.0, pelo mesmo motivo do `numero`: o cruzamento imprime
    `% dos válidos` ao lado das tabelas de frequência, e dois formatadores para o
    mesmo percentual é como um documento sai com `26,8` numa página e `26.8%` na
    seguinte.
    """
    if not total:
        return "—"
    valor = 100 * float(parte) / float(total)
    if not math.isfinite(valor):
        return "—"
    return f"{valor:.{CASAS_PERCENTUAL}f}".replace(".", ",")


_percentual = percentual


def _arredondar(valor: float | None) -> float | None:
    """
    O número do manifesto: quatro casas, ou quatro algarismos significativos quando
    ele é menor que 0,1 — com quatro casas, o desvio de 0,00062 era gravado `0.0006`.
    """
    if valor is None:
        return None
    valor = float(valor)
    if not math.isfinite(valor):
        return None
    if valor == 0:
        return 0.0
    return round(valor, max(4, 3 - math.floor(math.log10(abs(valor)))))


def _casas_escritas(textos: Sequence[str]) -> int:
    """
    As casas do corte mais preciso que o dicionário escreveu: `0,00255` tem cinco.
    """
    casas = 0
    for texto in textos:
        _, _, decimais = str(texto).strip().replace(",", ".").partition(".")
        casas = max(casas, len(decimais.rstrip("0")))
    return casas


def _data(valor: Any) -> str:
    try:
        return pd.Timestamp(valor).strftime("%d/%m/%Y")
    except (ValueError, TypeError):  # pragma: no cover - já validado antes
        return "—"


def _integridade(confere: bool | None) -> str:
    if confere is True:
        return "confere"
    if confere is False:
        return "ALTERADO"
    return "não conferida"


def _subtitulo(preenchidos: int, faltantes: int) -> str:
    partes = [f"n = {preenchidos}"]
    if faltantes:
        partes.append(f"{faltantes} sem informação")
    return " · ".join(partes)


def _distintos(valores: Any, quantos: int = 5) -> list[str]:
    """
    Alguns valores diferentes, na ordem em que aparecem.

    Diferentes, e não os primeiros: em uma coluna com dois formatos de data
    misturados, os cinco primeiros são cinco vezes o mesmo formato — e o exemplo
    existe justamente para mostrar a mistura.
    """
    vistos: list[str] = []
    for valor in valores:
        texto = str(valor)
        if texto not in vistos:
            vistos.append(texto)
        if len(vistos) >= quantos:
            break
    return vistos


def _encurtar(texto: str, limite: int = 40) -> str:
    limpo = _ESPACOS.sub(" ", str(texto)).strip()
    return limpo if len(limpo) <= limite else limpo[: limite - 1] + "…"


def slug(nome: str, usados: set[str]) -> str:
    """
    O pedaço do nome do arquivo que vem da variável.

    O nome da variável vem do banco do cliente: tem acento, espaço, parêntese,
    barra e às vezes cem caracteres. Nada disso monta nome de arquivo — é o mesmo
    cuidado que a `sanitizar` do `nomes.py` toma com a pasta, aplicado aqui porque
    a regra é outra: um nome de arquivo que precisa sobreviver a `.csv`, ao Windows
    e a um `%` de URL no dia em que o relatório virar HTML.

    Colisão (`Idade (anos)` e `idade_anos` dão o mesmo pedaço) resolve com sufixo
    numérico, na ordem das colunas do banco. É o `manifesto.json` que diz qual
    arquivo é de qual variável — e é por isso que ele existe.

    Pública desde a Fase 7: duas análises escrevendo `hist_idade.png` e
    `qq_idade_anos.png` para a mesma coluna, cada uma com a sua regra de limpeza,
    é como um `.png` deixa de ser encontrável pelo nome da variável que o gerou.
    O `usados` é por rodada — o desempate vale dentro de uma pasta, não entre elas.
    """
    limpo = unicodedata.normalize("NFKD", str(nome or "")).lower()
    limpo = "".join(c for c in limpo if not unicodedata.combining(c))
    limpo = _NAO_ALFANUMERICO.sub("_", limpo).strip("_")[:_LIMITE_SLUG].strip("_")
    base = limpo or "variavel"

    candidato = base
    sufixo = 2
    while candidato in usados:
        candidato = f"{base}_{sufixo}"
        sufixo += 1
    usados.add(candidato)
    return candidato


_slug = slug
