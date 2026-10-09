# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
O cruzamento — uma tabela por par de variáveis categóricas.

Responde ao passo 2b do fluxo, e é a análise mais simples da Fase 7: duas
categóricas lado a lado, cada combinação de categorias com quantos casos e o
percentual. Sem teste e sem gráfico. É o `cruz()` que se fazia à mão, dentro do
FlatCap:

    Sexo              Escolaridade   n  % dos válidos
    Feminino          Superior      15           26,8
    Feminino          Médio         12           21,4
    ...
    (sem informação)                 4              —
    Total                           60          100,0

Segue o padrão das Fases 2 a 6, decidir e escrever separados:

    plano = preparar_cruzamento(raiz)   # abre o banco, conta, não toca no disco
    executar_cruzamento(plano)          # só escreve

E, como elas, **não fala com o REDCap**. Recebe `Path`, não `Config`.

## Quais pares

Os que estiverem escritos na ficha, e só eles:

    cruzamento:
      - [sexo, escolaridade]
      - [grupo, desfecho]

Sem a lista, o comando recusa. É a assimetria com a normalidade, e é deliberada:
lá "todas as numéricas" é um padrão que não produz achado nenhum; aqui não existe
padrão razoável. Trinta categóricas dão 435 pares, e cruzar todas é trocar a
pergunta do estudo por um laço aninhado. Quais pares cruzar é decisão da reunião,
e mora onde as decisões da reunião moram.

A variável numérica de poucos valores — escala de 0 a 5, código 1/2 — entra
marcada `categorica` no dicionário. O `flatcap perfil` já propõe isso para
"inteiros pequenos que se repetem", e este módulo não precisa saber que a coluna
era número: ele obedece ao `tipo`, como a descritiva.

## A decisão central: o denominador do par

Uma tabela de cruzamento é sobre quem respondeu **as duas** perguntas. Quem
respondeu uma só não tem combinação — e, se saísse da tabela inteira, como o
`pd.crosstab` faz em silêncio, o `Total` do cruzamento ficaria menor do que o das
duas tabelas de frequência que estão duas páginas antes, no mesmo documento. Quem
somasse acharia que faltou gente.

Então:

* **o percentual é sobre quem respondeu as duas.** Os números das combinações são
  os do `cruz()`, e a coluna se chama `% dos válidos` — o mesmo nome e o mesmo
  cálculo da primeira coluna de percentual da descritiva;
* **quem não respondeu uma delas vira a linha `(sem informação)`**, e o `Total` é
  o do banco, igual ao das tabelas de frequência;
* **os faltantes são por par**, e não por lista completa do banco: o cruzamento de
  `sexo` com `escolaridade` não depende de quem respondeu `renda`.

## O que ele reaproveita, e por quê

A categoria sai escrita **igual** à da tabela de frequência da mesma variável. O
código `1` vira `Feminino` pelo rótulo do dicionário (`Linha.rotulo_de`), e uma
coluna de código que o Excel leu como decimal não sai `1.0`. As duas coisas passam
pelas mesmas funções da descritiva — `serie_de_texto` e `percentual` —, porque duas
tabelas do mesmo documento escrevendo a mesma categoria de dois jeitos é o defeito
que ninguém confere. Pelo mesmo motivo, dois códigos com o mesmo rótulo
(`1=Sim|2=Sim`) viram uma combinação só: o agrupamento que a descritiva faz é o
que o cruzamento faz.

As recusas de dicionário e de tipo também são as da descritiva, com a classe de
erro deste módulo. Se as duas discordassem, `flatcap descritiva` recusaria uma
coluna que `flatcap cruzamento` aceitaria.

## O que ele deliberadamente não faz

**Não testa independência.** Qui-quadrado e Fisher são outra análise, a
`associacao`, com os pressupostos dela — frequência esperada, tamanho da tabela —
e as recusas dela.

**Não desenha.** O `graficos.py` tem uma cor de série só, e de propósito. Um
gráfico de duas variáveis precisa de uma paleta, e essa é uma decisão de desenho
que vale para toda figura futura com mais de uma série — merece a conversa dela.

**Não põe a tabela em grade.** O formato é a lista de combinações, da mais
frequente para a menos, que é como o `cruz()` a entrega e como ela se lê: "quais
combinações são as mais comuns?".
"""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__
from .banco import Banco, abrir
from .descritiva import (
    ROTULO_FALTANTE,
    ROTULO_TOTAL,
    conferir_dicionario,
    percentual,
    recusar_incompativeis,
    serie_de_texto,
)
from .descritiva import arquivamento as arquivamento_da_rodada
from .descritiva import slug as slug_do_nome
from .dicionario import ARQUIVO_DICIONARIO, CATEGORICA, IGNORAR, NUMERICA, Linha
from .ficha import Ficha, bloco, escrever_atomico
from .ficha import ler as ler_ficha
from .manifesto import (
    ANALISE_CRUZAMENTO,
    ARQUIVO_MANIFESTO,
    SEMENTE,
    Artefato,
    ItemDoManifesto,
    Manifesto,
    Tabela,
    texto_do_manifesto,
)
from .nomes import rotulo_do_projeto
from .projeto import (
    ARQUIVO_PROJETO,
    PASTA_ANALISES,
    PASTA_ANTIGAS,
    PASTA_CRUZAMENTO,
    anotar,
    pasta_da_analise,
)

PREFIXO_TABELA = "cruz_"

# O sinal entre os dois rótulos, no título da seção e da tabela. É o "vezes" de
# "sexo × escolaridade", que é como se fala de um cruzamento em voz alta.
SINAL = " × "

# Acima disto a tabela sai inteira, e com aviso. Duas variáveis de dez categorias
# cada dão até cem combinações, e uma lista desse tamanho atravessa páginas e se
# lê mal — é o `LIMITE_BARRAS` da descritiva aplicado a outra forma. O conserto
# não é cortar a tabela: é agrupar categorias no dicionário, que é decisão sua.
LIMITE_COMBINACOES = 30

_AUSENTE = "—"

# O exemplo que as mensagens escrevem. Um lugar só, para a recusa e o `--help`
# nunca ensinarem duas formas diferentes de escrever a mesma lista.
EXEMPLO_DA_FICHA = f"""  {PASTA_CRUZAMENTO}:
    - [sexo, escolaridade]
    - [grupo, desfecho]"""


class CruzamentoError(RuntimeError):
    """
    Falha ao gerar o cruzamento, já traduzida para o usuário.

    Erro próprio pela regra da casa: a CLI captura esta classe e transforma em
    painel com o nome do comando que o usuário rodou. Qualquer outra exceção é bug
    de verdade e deve subir com o traceback inteiro.

    As recusas de dicionário e de tipo são as da descritiva — uma implementação
    só —, e chegam aqui como subclasses desta porque as duas funções de lá recebem
    a classe de erro como parâmetro. Ver `descritiva.conferir_dicionario`.
    """


class DicionarioAusenteError(CruzamentoError):
    """
    O projeto não tem `dicionario.csv`. Não há o que obedecer.
    """


class DicionarioDesatualizadoError(CruzamentoError):
    """
    O banco tem colunas que o dicionário desconhece.
    """


class VariavelIncompativelError(CruzamentoError):
    """
    O dicionário declara uma variável que o banco não tem.

    A mesma recusa da Fase 5, pela mesma função. Para uma categórica ela só tem uma
    forma de disparar — a coluna não existe —, porque texto, número, data e lógico
    viram categoria do mesmo jeito que viram na tabela de frequência.
    """


class SemParesError(CruzamentoError):
    """
    A ficha não diz quais pares cruzar.

    Recusa, e não uma rodada com todos os pares possíveis: ver o topo do módulo.
    """


class ParInvalidoError(CruzamentoError):
    """
    A lista `cruzamento:` da ficha tem par que não serve.

    Formato errado, nome que não está no dicionário, variável que não é
    `categorica`, a mesma variável duas vezes ou o mesmo par duas vezes. A
    mensagem lista **todos** de uma vez: descobrir o segundo depois de corrigir o
    primeiro é o jeito mais lento de arrumar uma lista — a regra que a Fase 5
    escreveu para as colunas incompatíveis.
    """


# O que sai no disco


@dataclass(frozen=True)
class Par:
    """
    Um par pedido na ficha, já conferido contra o dicionário.

    `linha` é a primeira coluna da tabela, `coluna` a segunda — a ordem em que os
    dois nomes foram escritos na ficha.
    """

    linha: Linha
    coluna: Linha


@dataclass(frozen=True)
class ParCruzado:
    """
    Um par, contado. É uma seção do relatório.

    `combinacoes` são os rótulos das duas categorias e o número de casos, na ordem
    da tabela. `validos` é quem respondeu as duas, e é o denominador do percentual;
    `total` é o banco inteiro, e é o `Total` da tabela.
    """

    variavel_linha: str
    variavel_coluna: str
    rotulo_linha: str
    rotulo_coluna: str
    slug: str
    total: int
    validos: int
    combinacoes: tuple[tuple[str, str, int], ...]
    tabela: Tabela
    avisos: tuple[str, ...] = ()

    @property
    def faltantes(self) -> int:
        return self.total - self.validos

    @property
    def rotulo(self) -> str:
        return f"{self.rotulo_linha}{SINAL}{self.rotulo_coluna}"

    @property
    def colunas(self) -> tuple[str, str]:
        return (self.variavel_linha, self.variavel_coluna)


@dataclass(frozen=True)
class ForaDoCruzamento:
    """
    Uma variável do dicionário que não está em par nenhum, e por quê.

    Vai para o manifesto pelo mesmo motivo da Fase 5 — "não está no relatório" e
    "ninguém reparou que ela existia" são coisas diferentes. O `relatorio.py` só a
    anuncia quando **nenhuma** rodada a descreve, então a lista pode ser longa sem
    virar ruído no terminal de quem rodou a descritiva.
    """

    variavel: str
    tipo: str
    motivo: str


@dataclass(frozen=True)
class Cruzamento:
    """
    A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.
    """

    ficha: Ficha
    banco: Banco
    pares: tuple[ParCruzado, ...]
    fora: tuple[ForaDoCruzamento, ...]
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
        return tuple(par.tabela for par in self.pares)

    @property
    def colunas_usadas(self) -> tuple[str, ...]:
        vistas: list[str] = []
        for par in self.pares:
            for coluna in par.colunas:
                if coluna not in vistas:
                    vistas.append(coluna)
        return tuple(vistas)


@dataclass(frozen=True)
class PlanoCruzamento:
    """
    Tudo o que o `cruzamento` faria, decidido e ainda não escrito.

    Imutável como os planos das outras fases, e pela mesma razão: entre a simulação
    e a execução ninguém altera um caminho em trânsito. A árvore que aparece no
    terminal é lida deste objeto.
    """

    cruzamento: Cruzamento
    pasta: Path
    arquivamento: tuple[Path, Path] | None
    manifesto: Manifesto
    texto_manifesto: str

    @property
    def raiz(self) -> Path:
        return self.cruzamento.raiz

    @property
    def tabelas(self) -> tuple[Tabela, ...]:
        return self.cruzamento.tabelas

    @property
    def arquivos(self) -> tuple[str, ...]:
        return tuple([tabela.nome for tabela in self.tabelas] + [ARQUIVO_MANIFESTO])


@dataclass(frozen=True)
class ResultadoCruzamento:
    """
    O que a execução de fato escreveu.
    """

    criados: tuple[Path, ...] = ()
    arquivado: tuple[Path, Path] | None = None
    avisos: tuple[str, ...] = ()


# Casos de uso


def preparar_cruzamento(
    raiz: Path,
    aba: str | None = None,
    conferir: bool = True,
    agora: datetime | None = None,
) -> PlanoCruzamento:
    """
    Lê os pares da ficha, abre o banco, conta cada par e monta o plano. Não
    escreve nada.

    A lista da ficha é conferida **antes** de abrir o banco: um par escrito fora do
    formato é o engano mais provável deste comando, e descobri-lo não deve custar a
    releitura do `sha256` de um banco grande.

    Args:
        raiz: a pasta do projeto (a que tem o `projeto.yaml`).
        aba: planilha do `.xlsx`, quando houver mais de uma.
        conferir: reler o `sha256` das versões e comparar com a ficha.
        agora: relógio injetável — sem ele os testes não teriam como comparar o
            nome da pasta arquivada nem o manifesto, que carregam a data.

    Raises:
        FichaError, BancoError, DicionarioInvalidoError e as recusas declaradas
        acima.
    """
    raiz = Path(raiz)
    quando = agora or datetime.now()

    pedidos = pares_da_ficha(raiz)

    banco = abrir(raiz, aba=aba, conferir=conferir)
    ficha = ler_ficha(raiz)
    linhas = conferir_dicionario(
        raiz,
        banco,
        ausente=DicionarioAusenteError,
        desatualizado=DicionarioDesatualizadoError,
        analise="o cruzamento",
    )
    cruzamento = cruzar(banco, ficha, linhas, pedidos, quando)

    pasta = pasta_da_analise(raiz, PASTA_CRUZAMENTO)
    manifesto = montar_manifesto(cruzamento, linhas)

    return PlanoCruzamento(
        cruzamento=cruzamento,
        pasta=pasta,
        arquivamento=arquivamento_da_rodada(raiz, pasta, quando, PASTA_CRUZAMENTO),
        manifesto=manifesto,
        texto_manifesto=texto_do_manifesto(manifesto),
    )


def executar_cruzamento(plano: PlanoCruzamento) -> ResultadoCruzamento:
    """
    Escreve o plano no disco. Não decide mais nada.

    A ordem é a da Fase 5, e pelo mesmo motivo: o recibo vem depois do que ele
    descreve. Arquiva a rodada anterior, cria a pasta, escreve as tabelas, e só
    então o `manifesto.json` — que é o índice, e um índice que aponta para arquivo
    inexistente é pior do que índice nenhum.

    Cada etapa registra como voltar atrás. Uma falha no meio desfaz o que já foi
    feito, inclusive devolvendo a pasta arquivada ao lugar — senão a rodada
    anterior teria sumido em troca de nada. O desfazer roda para **qualquer**
    exceção, como na descritiva e na normalidade desde a revisão 1.3.1, e a exceção
    continua subindo inteira.
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
        # comando que a criou. O `rmdir` é registrado **antes** dos arquivos e o
        # desfazer roda ao contrário, então os arquivos saem primeiro e a pasta
        # sai vazia, que é a única forma de ela sair.
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
            anotar(plano.raiz, _acao_do_historico(plano), plano.cruzamento.quando)
        except OSError as erro:
            avisos.append(
                "O cruzamento foi escrito, mas não consegui escrever no "
                f"historico.md: {erro}"
            )

    except Exception:
        for passo in reversed(desfazer):
            try:
                passo()
            except OSError:
                avisos.append(
                    "Falhei ao desfazer uma etapa. Confira "
                    f"{PASTA_ANALISES}/{PASTA_CRUZAMENTO} e {PASTA_ANTIGAS} antes "
                    "de rodar de novo."
                )
        raise

    return ResultadoCruzamento(
        criados=tuple(criados), arquivado=arquivado, avisos=tuple(avisos)
    )


def cruzar(
    banco: Banco,
    ficha: Ficha,
    linhas_do_dicionario: Sequence[Linha],
    pedidos: Sequence[tuple[str, str]],
    quando: datetime | None = None,
) -> Cruzamento:
    """
    Conta cada par pedido, obedecendo ao dicionário. Função pura.

    Separada de `preparar_cruzamento` porque é o miolo testável, como o `descrever`
    da Fase 5 e o `avaliar` da normalidade: um `DataFrame` montado à mão, uma lista
    de `Linha` e os pares entram, e as afirmações são sobre as tabelas — sem pasta
    de projeto e sem disco.

    Args:
        pedidos: os pares como a ficha os escreve — `(linha, coluna)`, pelos nomes
            das colunas do banco. É o que `pares_da_ficha` devolve.

    Raises:
        SemParesError, ParInvalidoError, VariavelIncompativelError
    """
    quadro = banco.quadro
    total = int(quadro.shape[0])

    if not pedidos:
        raise SemParesError(_mensagem_sem_pares(linhas_do_dicionario))

    pares = _conferir_pares(pedidos, linhas_do_dicionario)

    # Só as variáveis dos pares vão para a recusa, e não o dicionário inteiro. A
    # conferência é a da Fase 5; o escopo é deste comando — a docstring de
    # `recusar_incompativeis` diz isso com todas as letras.
    envolvidas: list[Linha] = []
    for par in pares:
        for linha in (par.linha, par.coluna):
            if linha not in envolvidas:
                envolvidas.append(linha)
    recusar_incompativeis(quadro, envolvidas, erro=VariavelIncompativelError)

    usados: set[str] = set()
    cruzados = tuple(
        _cruzar_par(
            quadro,
            par,
            slug_do_nome(f"{par.linha.variavel} x {par.coluna.variavel}", usados),
            total,
        )
        for par in pares
    )

    nos_pares = {coluna for par in cruzados for coluna in par.colunas}
    fora = tuple(
        ForaDoCruzamento(linha.variavel, linha.tipo, _motivo_de_fora(linha))
        for linha in linhas_do_dicionario
        if linha.variavel not in nos_pares
    )

    avisos = list(banco.avisos)
    avisos += [aviso for par in cruzados for aviso in par.avisos]

    return Cruzamento(
        ficha=ficha,
        banco=banco,
        pares=cruzados,
        fora=fora,
        avisos=tuple(avisos),
        quando=quando or datetime.now(),
    )


# Um par


def _cruzar_par(quadro: pd.DataFrame, par: Par, slug: str, total: int) -> ParCruzado:
    """
    Conta as combinações de um par e monta a tabela dele.

    **O código conta, o rótulo imprime** — a regra do `_descrever_categorica`. Os
    valores do banco passam pela `serie_de_texto` da descritiva, que é o que faz um
    código lido como `1.0` virar `1`, e o `1` vira `Feminino` pelo `rotulo_de` do
    dicionário. A contagem é feita **sobre os rótulos**, e é isso que junta numa
    combinação só os códigos que o dicionário agrupou.

    As duas séries são filtradas pela mesma máscara e depois lidas por posição: um
    índice de banco com rótulo repetido não tem como parear a linha errada.
    """
    serie_linha = _coluna(quadro, par.linha.variavel)
    serie_coluna = _coluna(quadro, par.coluna.variavel)
    if serie_linha is None or serie_coluna is None:  # pragma: no cover - a recusa já barrou
        raise VariavelIncompativelError(
            f"`{par.linha.variavel}` ou `{par.coluna.variavel}` não existe no banco."
        )

    respondeu_as_duas = serie_linha.notna() & serie_coluna.notna()
    validos = int(respondeu_as_duas.sum())

    rotulos_linha = [
        par.linha.rotulo_de(valor) for valor in serie_de_texto(serie_linha[respondeu_as_duas])
    ]
    rotulos_coluna = [
        par.coluna.rotulo_de(valor)
        for valor in serie_de_texto(serie_coluna[respondeu_as_duas])
    ]
    contagem = Counter(zip(rotulos_linha, rotulos_coluna, strict=True))

    ordem_linha = _ordem_dos_rotulos(par.linha)
    ordem_coluna = _ordem_dos_rotulos(par.coluna)
    combinacoes = tuple(
        sorted(
            ((a, b, int(n)) for (a, b), n in contagem.items() if n > 0),
            key=lambda c: (
                -c[2],
                _posicao(ordem_linha, c[0]),
                c[0],
                _posicao(ordem_coluna, c[1]),
                c[1],
            ),
        )
    )

    rotulo_linha = par.linha.rotulo or par.linha.variavel
    rotulo_coluna = par.coluna.rotulo or par.coluna.variavel
    faltantes = total - validos

    avisos: list[str] = []
    nome_do_par = f"`{par.linha.variavel}`{SINAL}`{par.coluna.variavel}`"
    if not validos:
        avisos.append(
            f"{nome_do_par}: nenhum caso tem resposta nas duas variáveis. A tabela saiu "
            f"só com `{ROTULO_FALTANTE}` e o `{ROTULO_TOTAL}`."
        )
    if len(combinacoes) > LIMITE_COMBINACOES:
        avisos.append(
            f"{nome_do_par}: {len(combinacoes)} combinações. A tabela saiu inteira, e uma "
            "lista desse tamanho atravessa páginas e se lê mal. Agrupar categorias no "
            f"{ARQUIVO_DICIONARIO} — dois códigos com o mesmo rótulo, `1=Sim|2=Sim` — "
            "encurta a tabela aqui e na descritiva ao mesmo tempo."
        )

    corpo = [(a, b, str(n), percentual(n, validos)) for a, b, n in combinacoes]
    corpo.append((ROTULO_FALTANTE, "", str(faltantes), _AUSENTE))
    corpo.append((ROTULO_TOTAL, "", str(total), percentual(1, 1) if validos else _AUSENTE))

    tabela = Tabela(
        nome=f"{PREFIXO_TABELA}{slug}.csv",
        especie="cruzamento",
        # Vazia de propósito: esta tabela não é de uma variável, e a linha
        # `# variável:` do cabeçalho do `.csv` mentiria com qualquer uma das duas.
        variavel="",
        titulo=f"Cruzamento — {rotulo_linha}{SINAL}{rotulo_coluna}",
        colunas=(rotulo_linha, rotulo_coluna, "n", "% dos válidos"),
        linhas=tuple(corpo),
        notas=_notas(par, validos, faltantes, total),
    )

    return ParCruzado(
        variavel_linha=par.linha.variavel,
        variavel_coluna=par.coluna.variavel,
        rotulo_linha=rotulo_linha,
        rotulo_coluna=rotulo_coluna,
        slug=slug,
        total=total,
        validos=validos,
        combinacoes=combinacoes,
        tabela=tabela,
        avisos=tuple(avisos),
    )


def _notas(par: Par, validos: int, faltantes: int, total: int) -> tuple[str, ...]:
    """
    O cabeçalho de comentário do `.csv`: de onde sai cada número da tabela.

    As notas não vão para o `.docx` desde a revisão de formatação da Fase 6; elas
    são para quem abre o arquivo sozinho, fora do documento, e precisa saber qual é
    o denominador do percentual sem reabrir o banco.
    """
    notas = [
        f"% dos válidos: denominador {validos} (os casos com resposta nas duas "
        "variáveis).",
        f"{ROTULO_FALTANTE}: {faltantes} caso(s) sem resposta em pelo menos uma das "
        f"duas; o {ROTULO_TOTAL} é o do banco, {total} linha(s).",
        "combinações sem nenhum caso não aparecem.",
        "ordem: frequência decrescente; empate pela ordem das categorias no "
        "dicionário.",
    ]
    for linha in (par.linha, par.coluna):
        if linha.tem_rotulos:
            quais = ", ".join(
                f"{codigo} = {rotulo}"
                for codigo, rotulo in linha.rotulos_das_categorias
                if rotulo
            )
            notas.append(f"{linha.variavel} rotulada pelo dicionário: {quais}.")
    return tuple(notas)


def _ordem_dos_rotulos(linha: Linha) -> list[str]:
    """
    Os rótulos na ordem declarada no dicionário — o desempate da tabela.

    Frequência decrescente sozinha não é determinística: duas combinações com o
    mesmo `n` sairiam na ordem em que o `Counter` as viu, que é a ordem das linhas
    do banco. Desempatar pela ordem do dicionário é o que faz duas rodadas sobre o
    mesmo banco darem o mesmo arquivo, e é também a ordem que a tabela de
    frequência da variável usa.
    """
    return [linha.rotulo_de(codigo) for codigo in linha.categorias_ordem]


def _posicao(ordem: list[str], rotulo: str) -> int:
    """
    Onde o rótulo está na ordem do dicionário; o que não foi declarado vai depois.
    """
    return ordem.index(rotulo) if rotulo in ordem else len(ordem)


# Os pares da ficha


def pares_da_ficha(raiz: Path) -> tuple[tuple[str, str], ...]:
    """
    A lista `cruzamento:` do `projeto.yaml`, conferida na forma.

    Devolve vazio quando a chave não existe ou está vazia — quem recusa isso é o
    `cruzar`, que tem o dicionário na mão para escrever na mensagem quais
    categóricas existem. Aqui a recusa é só de formato: uma lista que não é de
    pares, ou um par que não tem dois nomes.

    Lida pelo `ficha.bloco`, e não abrindo o YAML aqui: o `ficha.py` é o único
    módulo do pacote que abre o `projeto.yaml`, e é bom que continue sendo.

    Formato errado recusa em vez de ignorar, como a lista `normalidade:`. Um par
    que o comando pulasse em silêncio é o pior dos dois mundos: você escreveu, e
    não valeu.

    Raises:
        ParInvalidoError
    """
    bruto = bloco(raiz, PASTA_CRUZAMENTO)
    if bruto is None:
        return ()
    if not isinstance(bruto, list):
        raise ParInvalidoError(
            f"A chave `{PASTA_CRUZAMENTO}:` do {ARQUIVO_PROJETO} deveria ser uma lista "
            f"de pares, e é {_descrever_valor(bruto)}.\n\n"
            f"Escreva assim, um par por linha:\n\n{EXEMPLO_DA_FICHA}"
        )

    pares: list[tuple[str, str]] = []
    problemas: list[str] = []
    for posicao, item in enumerate(bruto, start=1):
        if not isinstance(item, list):
            problemas.append(
                f"  {posicao}º item: {_descrever_valor(item)} — um par se escreve entre "
                "colchetes, com vírgula: [sexo, escolaridade]"
            )
            continue
        nomes = [str(nome).strip() for nome in item if nome is not None and str(nome).strip()]
        if len(nomes) != 2 or len(item) != 2:
            problemas.append(
                f"  {posicao}º item: {_descrever_valor(item)} — "
                + (
                    f"{len(item)} nomes; um par tem dois. Para cruzar três variáveis, "
                    "escreva os pares."
                    if len(item) > 2
                    else "um par tem dois nomes, e os dois preenchidos."
                )
            )
            continue
        pares.append((nomes[0], nomes[1]))

    if problemas:
        raise ParInvalidoError(
            f"A lista `{PASTA_CRUZAMENTO}:` do {ARQUIVO_PROJETO} tem "
            f"{len(problemas)} item(ns) fora do formato de pares. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + f"\n\nEscreva assim, um par por linha:\n\n{EXEMPLO_DA_FICHA}"
        )
    return tuple(pares)


def _conferir_pares(
    pedidos: Sequence[tuple[str, str]], linhas: Sequence[Linha]
) -> list[Par]:
    """
    Confere cada par contra o dicionário, e recusa listando todos os problemas.

    Cinco coisas podem estar erradas, e cada uma tem um conserto diferente — é por
    isso que a mensagem diz qual, par a par: o nome não está no dicionário
    (digitação, ou coluna que sumiu do banco); a variável está marcada `ignorar` ou
    fora desta versão do banco; ela não é `categorica`; é a mesma variável duas
    vezes; ou o par já foi pedido — inclusive na ordem inversa, que muda só qual
    coluna vem primeiro e daria duas seções com os mesmos números no documento.
    """
    por_nome = {linha.variavel: linha for linha in linhas}
    pares: list[Par] = []
    problemas: list[str] = []
    vistos: dict[frozenset[str], int] = {}

    for posicao, (nome_linha, nome_coluna) in enumerate(pedidos, start=1):
        escrito = f"[{nome_linha}, {nome_coluna}]"

        if nome_linha == nome_coluna:
            problemas.append(f"  {escrito} — a mesma variável duas vezes")
            continue

        chave = frozenset((nome_linha, nome_coluna))
        if chave in vistos:
            problemas.append(
                f"  {escrito} — o mesmo par do {vistos[chave]}º item; a ordem só troca "
                "qual coluna vem primeiro, e os números seriam os mesmos"
            )
            continue
        vistos[chave] = posicao

        motivos = [
            motivo
            for motivo in (
                _motivo_de_recusa(nome, por_nome.get(nome))
                for nome in (nome_linha, nome_coluna)
            )
            if motivo
        ]
        if motivos:
            problemas.append(f"  {escrito} — " + "; ".join(motivos))
            continue

        pares.append(Par(linha=por_nome[nome_linha], coluna=por_nome[nome_coluna]))

    if problemas:
        raise ParInvalidoError(
            f"A lista `{PASTA_CRUZAMENTO}:` do {ARQUIVO_PROJETO} tem {len(problemas)} "
            "par(es) que não podem ser cruzados. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + "\n\nO cruzamento é entre duas categóricas. Uma numérica de poucos valores "
            "— código 0/1, escala de 1 a 5 — entra se estiver marcada `categorica` no "
            f"{ARQUIVO_DICIONARIO}, que é o que o `flatcap perfil` propõe para ela.\n\n"
            f"Corrija o nome na lista do {ARQUIVO_PROJETO} — ele é o da coluna "
            f"`variavel` do {ARQUIVO_DICIONARIO} —, ou o `tipo` no dicionário, e rode "
            "de novo."
        )
    return pares


def _motivo_de_recusa(nome: str, linha: Linha | None) -> str:
    if linha is None:
        return f"`{nome}` não está no {ARQUIVO_DICIONARIO}"
    if not linha.no_banco:
        return f"`{nome}` não está nesta versão do banco (`no_banco = nao`)"
    if linha.tipo == IGNORAR:
        return f"`{nome}` está marcada `ignorar` no {ARQUIVO_DICIONARIO}"
    if linha.tipo != CATEGORICA:
        return f"`{nome}` está marcada `{linha.tipo}` no {ARQUIVO_DICIONARIO}"
    return ""


def _descrever_valor(valor: Any) -> str:
    """
    O que estava escrito, do jeito que o YAML entregou, para a mensagem mostrar.
    """
    if isinstance(valor, list):
        return "[" + ", ".join(str(item) for item in valor) + "]"
    if isinstance(valor, dict):
        return "um bloco `chave: valor`"
    if isinstance(valor, str):
        return f"`{valor}`"
    return f"`{valor}` ({type(valor).__name__})"


# O manifesto


def montar_manifesto(cruzamento: Cruzamento, linhas: Sequence[Linha]) -> Manifesto:
    """
    Traduz a rodada para o índice que o relatório vai ler.

    **Um item por par**, e é a terceira forma de item do manifesto: na descritiva um
    item é uma variável, na normalidade é a análise inteira, e aqui é um par. O
    campo `colunas`, que a Fase 7 criou esperando exatamente este caso, diz quais
    duas colunas do banco o item usou — e é ele que mantém as conferências do
    relatório certas para uma seção que não é de uma variável.

    `n` é o banco inteiro e `faltantes` é quem não respondeu uma das duas, que é o
    que a linha `(sem informação)` da tabela mostra.
    """
    banco = cruzamento.banco
    leitura = banco.leitura
    ficha = cruzamento.ficha

    itens = tuple(
        ItemDoManifesto(
            variavel="",
            slug=par.slug,
            rotulo=par.rotulo,
            tipo=ANALISE_CRUZAMENTO,
            n=par.total,
            faltantes=par.faltantes,
            colunas=par.colunas,
            artefatos=(
                Artefato(
                    arquivo=par.tabela.nome,
                    especie=par.tabela.especie,
                    formato="csv",
                    titulo=par.tabela.titulo,
                ),
            ),
            detalhes={
                "linha": par.variavel_linha,
                "coluna": par.variavel_coluna,
                "validos": par.validos,
                "combinacoes": len(par.combinacoes),
            },
            avisos=par.avisos,
        )
        for par in cruzamento.pares
    )

    return Manifesto(
        analise=ANALISE_CRUZAMENTO,
        flatcap=__version__,
        gerado_em=cruzamento.quando,
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
            "integridade": _integridade(banco.confere),
        },
        dicionario={
            "arquivo": ARQUIVO_DICIONARIO,
            "variaveis": len(linhas),
            "analisaveis": sum(1 for linha in linhas if linha.analisavel),
            # Mesmo esquema do bloco da descritiva e da normalidade: três rodadas
            # com três blocos `dicionario` diferentes obrigariam quem lê a saber de
            # qual análise é o arquivo antes de saber o que perguntar a ele.
            "numericas": sum(
                1 for linha in linhas if linha.analisavel and linha.tipo == NUMERICA
            ),
        },
        ambiente=_ambiente(),
        regras={
            "pares": f"os da lista `{PASTA_CRUZAMENTO}:` do {ARQUIVO_PROJETO}",
            "percentual": "dos válidos — os casos com resposta nas duas variáveis",
            "faltantes": f"por par; vão para a linha {ROTULO_FALTANTE}",
            "combinacoes_vazias": "omitidas",
            "ordem": "frequência decrescente; empate pela ordem do dicionário",
            "limite_de_combinacoes": LIMITE_COMBINACOES,
            "semente": SEMENTE,
        },
        itens=itens,
        fora=tuple(
            {"variavel": f.variavel, "tipo": f.tipo, "motivo": f.motivo}
            for f in cruzamento.fora
        ),
        avisos=cruzamento.avisos,
    )


def _ambiente() -> dict[str, Any]:
    """
    As versões que produziram estes números.

    Cada rodada declara o que ela usou. Esta não desenha e não testa nada, então
    o `matplotlib` e a `fonte` saem `None` — as chaves continuam lá para o bloco
    ter a mesma forma do da descritiva rodada com `--sem-graficos` —, e o `scipy`
    não aparece: anunciar uma versão dele seria dizer que um destes números passou
    por ele.
    """
    import openpyxl

    return {
        "python": ".".join(str(parte) for parte in sys.version_info[:3]),
        "flatcap": __version__,
        "pandas": pd.__version__,
        "openpyxl": openpyxl.__version__,
        "matplotlib": None,
        "fonte": None,
    }


# Mensagens


def _mensagem_sem_pares(linhas: Sequence[Linha]) -> str:
    categoricas = [
        linha.variavel for linha in linhas if linha.analisavel and linha.tipo == CATEGORICA
    ]
    if categoricas:
        disponiveis = (
            f"As categóricas deste {ARQUIVO_DICIONARIO} são: "
            + ", ".join(categoricas[:20])
            + (f" e mais {len(categoricas) - 20}" if len(categoricas) > 20 else "")
            + "."
        )
    else:
        disponiveis = (
            f"Nenhuma variável deste {ARQUIVO_DICIONARIO} está marcada `categorica` "
            "ainda — reveja a coluna `tipo` antes."
        )
    return (
        f"O {ARQUIVO_PROJETO} deste projeto não diz quais pares cruzar.\n\n"
        "Escreva a lista na ficha, um par por linha — o primeiro nome vai na primeira "
        f"coluna da tabela:\n\n{EXEMPLO_DA_FICHA}\n\n"
        f"{disponiveis} Uma numérica de poucos valores, como uma escala de 0 a 5, "
        "entra se estiver marcada `categorica`.\n\n"
        "Quais pares cruzar é decisão da reunião: o FlatCap não cruza tudo com tudo, "
        "porque trinta variáveis dariam 435 tabelas."
    )


def _motivo_de_fora(linha: Linha) -> str:
    if not linha.no_banco:
        return "não está nesta versão do banco (`no_banco = nao`)"
    if linha.tipo == IGNORAR:
        return "marcada `ignorar` no dicionário"
    return f"não está em nenhum par da lista `{PASTA_CRUZAMENTO}:` do {ARQUIVO_PROJETO}"


def _acao_do_historico(plano: PlanoCruzamento) -> str:
    cruzamento = plano.cruzamento
    quantos = len(cruzamento.pares)
    partes = [
        f"`flatcap cruzamento {cruzamento.ficha.record_id}` — cruzamento de "
        f"`{cruzamento.banco.versao.arquivo}`: {quantos} par(es) da lista "
        f"`{PASTA_CRUZAMENTO}:`, em `{PASTA_ANALISES}/{PASTA_CRUZAMENTO}/`."
    ]
    if plano.arquivamento is not None:
        partes.append(
            f"A rodada anterior foi para `{PASTA_ANTIGAS}/{plano.arquivamento[1].name}/`."
        )
    return " ".join(partes)


# Leitura da série


def _coluna(quadro: pd.DataFrame, nome: str) -> pd.Series | None:
    """
    A coluna do banco pelo nome, ou `None`.

    Pela posição, e não por `quadro[nome]`, pela mesma razão da Fase 5: nome
    repetido devolveria um `DataFrame` no lugar de uma coluna. É a terceira cópia
    destas cinco linhas — a descritiva e a normalidade têm a delas —, e ficou assim
    de propósito: é uma busca, não uma decisão de apresentação, e não tem como duas
    cópias discordarem sobre um número.
    """
    for posicao, coluna in enumerate(quadro.columns):
        if str(coluna) == nome:
            return quadro.iloc[:, posicao]
    return None


def _integridade(confere: bool | None) -> str:
    if confere is True:
        return "confere"
    if confere is False:
        return "ALTERADO"
    return "não conferida"


__all__ = [
    "EXEMPLO_DA_FICHA",
    "LIMITE_COMBINACOES",
    "PREFIXO_TABELA",
    "SINAL",
    "Cruzamento",
    "CruzamentoError",
    "DicionarioAusenteError",
    "DicionarioDesatualizadoError",
    "ForaDoCruzamento",
    "Par",
    "ParCruzado",
    "ParInvalidoError",
    "PlanoCruzamento",
    "ResultadoCruzamento",
    "SemParesError",
    "VariavelIncompativelError",
    "cruzar",
    "executar_cruzamento",
    "montar_manifesto",
    "pares_da_ficha",
    "preparar_cruzamento",
]
