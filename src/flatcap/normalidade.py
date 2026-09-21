"""
A normalidade — a primeira análise da Fase 7.

Responde ao passo 2b do fluxo: as análises que variam de projeto para projeto.
Esta é a que vem primeiro, e não por acaso. Ela é **pressuposto**, não resultado:
Pearson ou Spearman, teste t ou Mann-Whitney, a média ou a mediana no texto — as
três perguntas seguintes começam aqui. Uma correlação implementada antes desta
seria uma correlação escolhida no escuro.

Segue o padrão das Fases 2 a 6, decidir e escrever separados:

    plano = preparar_normalidade(raiz)   # abre o banco, calcula, não toca no disco
    executar_normalidade(plano)          # só escreve

E, como elas, **não fala com o REDCap**. Recebe `Path`, não `Config`.

## A decisão central: o valor-p sozinho não responde à pergunta

É o risco real desta análise, e ele não é técnico. O valor-p do Shapiro-Wilk é
função do tamanho da amostra: com n = 30 quase nada é rejeitado, porque o teste
não tem poder para rejeitar; com n = 3000 quase tudo é, porque qualquer desvio
irrelevante vira significante. Um módulo que imprimisse `p = 0,003 → não normal`
automatizaria má prática dentro de um documento assinado que vai para um professor
de medicina.

Então cada variável sai com quatro coisas, e nenhuma delas sozinha:

    n                     em coluna própria, porque é ele que calibra o resto
    assimetria e curtose  medem o **tamanho** do desvio, e não dependem do n
    W e o valor-p         o teste, com os limites dele escritos no arquivo
    o Q-Q                 onde a distribuição se afasta, que é o que o p não diz

Mais uma leitura em palavras, na última coluna, como o `motivo` do `perfil.md` da
Fase 4. Ela descreve a **forma** da distribuição — "assimétrica à direita",
"caudas pesadas" — e nunca escolhe um teste para você. Escolher o teste depende da
comparação que se vai fazer, e este módulo não sabe qual é: ele olha uma coluna,
não um delineamento.

## O que ele deliberadamente não faz

**Não imprime média nem desvio padrão.** Eles são o `resumo_<variável>.csv` da
descritiva. Duas fontes para o mesmo número é o que este projeto gasta energia
impedindo desde a Fase 5, e a média impressa em duas tabelas da mesma página
discordando na segunda casa é exatamente o defeito que ninguém confere.

**Não testa resíduo nem subgrupo.** O que este módulo mede é a distribuição da
coluna como ela está. Para um teste t o que importa é a normalidade **dentro de
cada grupo**, e para uma regressão é a dos **resíduos** — as duas são outra
análise, e nenhuma das duas se deduz desta. Está escrito na nota do `.csv`, porque
é o engano mais fácil de cometer lendo a tabela.

**Não converte nada.** Numérica que chegou como texto é recusada, com a mesma
função e a mesma mensagem da descritiva — se as duas discordassem, o relatório
sairia com um teste de normalidade sobre uma coluna que nenhuma tabela descreve.

## Quais variáveis entram

Todas as `numerica` analisáveis do dicionário, e a lista `normalidade:` da ficha
restringe quando você quiser.

A assimetria com a correlação é deliberada e vale registrar. Um par de variáveis é
uma **hipótese**, e um dicionário de 30 variáveis dá 435 pares: rodar todos e
imprimir os valores-p é *p-hacking* feito por máquina, e é por isso que os pares da
correlação virão escritos na ficha, um a um. Uma varredura de normalidade é outra
coisa — é diagnóstico sobre variáveis que já têm seção própria no relatório, e não
produz achado nenhum. Com uma condição, que é a razão de a tabela se chamar
*Pressupostos* no documento: ela não é resultado, e não deve ser lida como um.

## O `scipy`

É a dependência nova da fase, e a primeira desde a Fase 6. O `pandas` calcula
assimetria e curtose; o que ele não tem é a distribuição do W de Shapiro-Wilk.

Implementá-la à mão seria transcrever o AS R94 (Royston, 1992) — aproximações
polinomiais das estatísticas de ordem esperadas da normal, coeficientes tabelados,
e uma transformação normalizadora com ramos diferentes para n ≤ 11 e n ≥ 12 —, e a
única forma de conferir a transcrição seria comparar com o `scipy`, que é a
biblioteca que se estaria evitando importar. Além disso, "de onde saiu esse p?"
precisa ter como resposta uma **versão**: `scipy 1.17.1`, escrita no `ambiente` do
manifesto desta rodada. Uma função escrita à mão não tem versão.

Ele é importado **dentro** da função que calcula, como o `matplotlib` no
`graficos.py` e o `python-docx` no `documento.py`, e pelo mesmo motivo: nenhum
comando que não faz teste de normalidade deve pagar o import.
"""

from __future__ import annotations

import math
import sys
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__
from .banco import Banco, abrir
from .descritiva import arquivamento as arquivamento_da_rodada
from .descritiva import conferir_dicionario, numero, recusar_incompativeis
from .descritiva import slug as slug_do_nome
from .dicionario import ARQUIVO_DICIONARIO, NUMERICA, Linha
from .ficha import Ficha, bloco, escrever_atomico
from .ficha import ler as ler_ficha
from .manifesto import (
    ANALISE_NORMALIDADE,
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
    ARQUIVO_PROJETO,
    PASTA_ANALISES,
    PASTA_ANTIGAS,
    PASTA_NORMALIDADE,
    anotar,
    pasta_da_analise,
)

ARQUIVO_TABELA = "normalidade.csv"

# Os limites do teste. Todos com nome, aqui em cima, pelo mesmo motivo das Fases 4
# e 5: número solto no meio de uma função é decisão que ninguém consegue rever.

# O Shapiro-Wilk não existe abaixo de três observações: com duas, quaisquer dois
# pontos estão perfeitamente sobre uma reta.
MINIMO_SHAPIRO = 3

# Abaixo disto o teste roda e quase não rejeita. Não é recusa — é aviso, porque o
# resultado continua sendo verdadeiro sobre o que ele mede; o que muda é o que ele
# permite concluir. "Não rejeitou" com n = 8 não é evidência de normalidade, é
# ausência de evidência de qualquer coisa, e é o engano mais comum com este teste.
MINIMO_CONFIAVEL = 20

# Acima disto o próprio `scipy` avisa que o valor-p deixa de ser exato. O aviso
# dele vai para `stderr`, onde ninguém lê; aqui ele é capturado e vira aviso do
# FlatCap, que viaja para o manifesto e para o terminal — mesma manobra do
# `ParserWarning` do `banco.py`.
MAXIMO_CONFIAVEL = 5000

ALFA = 0.05

# O menor valor-p que se imprime como número. Abaixo dele sai `< 0,001`, e nunca
# `0,000`: um valor-p é sempre maior que zero, e imprimi-lo como zero é escrever no
# relatório um número que não existe.
MENOR_P = 0.001

CASAS_P = 3
CASAS_W = 3
CASAS_FORMA = 2  # assimetria e curtose

# Os cortes da leitura em palavras. São convenções de leitura, não fronteiras da
# natureza — daí estarem nomeadas aqui, onde se discute se mudam.
ASSIMETRIA_LEVE = 0.5
ASSIMETRIA_FORTE = 1.0
CURTOSE_NOTAVEL = 1.0

# Até este número de valores distintos, a variável é avisada como discreta.
#
# O Shapiro-Wilk supõe uma variável **contínua**, e uma escala de 0 a 5 respondida
# por 180 pessoas não é uma. Ele rejeita a normal nesse caso quase sempre, e o
# motivo não é a forma da distribuição estar errada — é ela ser discreta. Sem o
# aviso, a linha sai igual à de uma variável contínua assimétrica, e as duas pedem
# decisões opostas.
#
# O limite é o mesmo `LIMITE_UNICOS_CODIGO` que o `perfil.py` usa para propor
# `categorica` a uma coluna de inteiros pequenos: é a mesma pergunta, feita duas
# fases depois, e dois limites diferentes para ela é como o perfil sugere uma coisa
# e a análise aponta outra sobre a mesma coluna.
POUCOS_DISTINTOS = 10

_AUSENTE = "—"


class NormalidadeError(RuntimeError):
    """
    Falha ao gerar a análise de normalidade, já traduzida para o usuário.

    Erro próprio pela regra da casa: a CLI captura esta classe e transforma em
    painel com o nome do comando que o usuário rodou. Qualquer outra exceção é bug
    de verdade e deve subir com o traceback inteiro.

    As recusas de dicionário e de tipo são compartilhadas com o `descritiva.py` —
    uma implementação só —, e mesmo assim chegam aqui como subclasses destas: as
    duas funções de lá recebem a classe de erro como parâmetro exatamente para
    isso. Ver `descritiva.conferir_dicionario`.
    """


class DicionarioAusenteError(NormalidadeError):
    """
    O projeto não tem `dicionario.csv`. Não há o que obedecer.
    """


class DicionarioDesatualizadoError(NormalidadeError):
    """
    O banco tem colunas que o dicionário desconhece.
    """


class VariavelIncompativelError(NormalidadeError):
    """
    O dicionário promete `numerica` e a coluna chegou como texto.

    A mesma recusa da Fase 5, com a mesma mensagem e pela mesma função. Se as duas
    discordassem, `flatcap descritiva` recusaria `peso` e `flatcap normalidade`
    calcularia um W sobre ela — e o relatório sairia com um teste sobre uma coluna
    que nenhuma tabela do documento descreve.
    """


class NadaParaAnalisarError(NormalidadeError):
    """
    Nenhuma variável do dicionário é `numerica`.

    Recusa, e não uma pasta com uma tabela vazia dentro: uma rodada que não mede
    nada mas existe no disco é uma rodada que o relatório vai encontrar, montar uma
    seção para, e imprimir vazia no documento do cliente.
    """


class VariavelPedidaInexistenteError(NormalidadeError):
    """
    A lista `normalidade:` da ficha nomeia uma variável que não serve.

    Recusa em vez de ignorar, e é a mesma escolha que a Fase 5 fez com o dicionário
    desatualizado: rodar sem ela produziria uma tabela com uma linha a menos, e
    nada na saída diria que a variável que você escreveu na ficha não entrou.
    """


# O que sai no disco


@dataclass(frozen=True)
class VariavelTestada:
    """
    Uma variável numérica, medida. É a linha da tabela.

    `w` e `p` são `None` quando o teste não pôde rodar — n abaixo de três, ou
    coluna constante. A linha **sai assim mesmo**, com o motivo escrito em
    `leitura`. Uma variável que simplesmente não aparecesse na tabela seria uma
    variável que ninguém repara que faltou, e essa distinção é a mesma que a lista
    `fora` da Fase 5 existe para marcar.
    """

    variavel: str
    slug: str
    rotulo: str
    n: int
    distintos: int
    faltantes: int
    assimetria: float | None
    curtose: float | None
    w: float | None
    p: float | None
    leitura: str
    avisos: tuple[str, ...] = ()
    pontos_x: tuple[float, ...] = ()
    pontos_y: tuple[float, ...] = ()
    reta: tuple[float, float] | None = None

    @property
    def testada(self) -> bool:
        return self.w is not None and self.p is not None

    @property
    def rejeita(self) -> bool:
        """
        O teste rejeitou a normal neste nível?

        `False` quando não houve teste — "não rejeitou" e "não foi testada" são
        coisas diferentes, e quem precisa distinguir olha `testada`.
        """
        return self.p is not None and self.p < ALFA

    def como_detalhe(self) -> dict[str, Any]:
        """
        Os números desta variável, para o manifesto.
        """
        return {
            "n": self.n,
            "distintos": self.distintos,
            "faltantes": self.faltantes,
            "assimetria": _arredondar(self.assimetria),
            "curtose": _arredondar(self.curtose),
            "w": _arredondar(self.w),
            "p": _arredondar(self.p),
            "rejeita": self.rejeita if self.testada else None,
            "leitura": self.leitura,
        }


@dataclass(frozen=True)
class ForaDaNormalidade:
    """
    Uma variável do dicionário que não entra, e por quê.

    Aqui é quase toda a tabela do dicionário: categórica, data e `ignorar` não têm
    normalidade para testar. Elas aparecem no manifesto pelo mesmo motivo da Fase
    5 — "não está no relatório" e "ninguém reparou que ela existia" são coisas
    diferentes, e só a primeira é uma decisão.
    """

    variavel: str
    tipo: str
    motivo: str


@dataclass(frozen=True)
class Normalidade:
    """
    A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.
    """

    ficha: Ficha
    banco: Banco
    variaveis: tuple[VariavelTestada, ...]
    fora: tuple[ForaDaNormalidade, ...]
    avisos: tuple[str, ...]
    quando: datetime
    tabela: Tabela
    graficos: tuple[Grafico, ...] = ()
    pedidas: tuple[str, ...] = ()  # a lista da ficha, quando houver

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def linhas(self) -> int:
        return self.banco.linhas

    @property
    def colunas_usadas(self) -> tuple[str, ...]:
        return tuple(v.variavel for v in self.variaveis)

    @property
    def rejeitadas(self) -> tuple[VariavelTestada, ...]:
        return tuple(v for v in self.variaveis if v.rejeita)

    @property
    def nao_testadas(self) -> tuple[VariavelTestada, ...]:
        return tuple(v for v in self.variaveis if not v.testada)


@dataclass(frozen=True)
class PlanoNormalidade:
    """
    Tudo o que o `normalidade` faria, decidido e ainda não escrito.

    Imutável como os planos das outras fases, e pela mesma razão: entre a simulação
    e a execução ninguém altera um caminho em trânsito. A árvore que aparece no
    terminal é lida deste objeto.
    """

    normalidade: Normalidade
    pasta: Path
    arquivamento: tuple[Path, Path] | None
    com_graficos: bool
    manifesto: Manifesto
    texto_manifesto: str

    @property
    def raiz(self) -> Path:
        return self.normalidade.raiz

    @property
    def tabela(self) -> Tabela:
        return self.normalidade.tabela

    @property
    def graficos(self) -> tuple[Grafico, ...]:
        return self.normalidade.graficos if self.com_graficos else ()

    @property
    def arquivos(self) -> tuple[str, ...]:
        nomes = [self.tabela.nome] + [g.nome for g in self.graficos]
        return tuple(nomes + [ARQUIVO_MANIFESTO])


@dataclass(frozen=True)
class ResultadoNormalidade:
    """
    O que a execução de fato escreveu.
    """

    criados: tuple[Path, ...] = ()
    arquivado: tuple[Path, Path] | None = None
    avisos: tuple[str, ...] = ()


# Casos de uso


def preparar_normalidade(
    raiz: Path,
    aba: str | None = None,
    conferir: bool = True,
    com_graficos: bool = True,
    agora: datetime | None = None,
) -> PlanoNormalidade:
    """
    Abre o banco, testa cada numérica e monta o plano. Não escreve nada.

    Args:
        raiz: a pasta do projeto (a que tem o `projeto.yaml`).
        aba: planilha do `.xlsx`, quando houver mais de uma.
        conferir: reler o `sha256` das versões e comparar com a ficha.
        com_graficos: desenhar os Q-Q. Desligado, o `matplotlib` nem é importado.
        agora: relógio injetável — sem ele os testes não teriam como comparar o
            nome da pasta arquivada nem o manifesto, que carregam a data.

    Raises:
        FichaError, BancoError, DicionarioInvalidoError e as cinco recusas
        declaradas acima.
    """
    raiz = Path(raiz)
    quando = agora or datetime.now()

    banco = abrir(raiz, aba=aba, conferir=conferir)
    ficha = ler_ficha(raiz)

    linhas = conferir_dicionario(
        raiz,
        banco,
        ausente=DicionarioAusenteError,
        desatualizado=DicionarioDesatualizadoError,
        analise="a normalidade",
    )
    pedidas = _variaveis_pedidas(raiz)
    normalidade = avaliar(banco, ficha, linhas, pedidas, quando, com_graficos)

    pasta = pasta_da_analise(raiz, PASTA_NORMALIDADE)
    manifesto = montar_manifesto(normalidade, linhas, com_graficos)

    return PlanoNormalidade(
        normalidade=normalidade,
        pasta=pasta,
        arquivamento=arquivamento_da_rodada(raiz, pasta, quando, PASTA_NORMALIDADE),
        com_graficos=com_graficos,
        manifesto=manifesto,
        texto_manifesto=texto_do_manifesto(manifesto),
    )


def executar_normalidade(plano: PlanoNormalidade) -> ResultadoNormalidade:
    """
    Escreve o plano no disco. Não decide mais nada.

    A ordem é a da Fase 5, e pelo mesmo motivo: o recibo vem depois do que ele
    descreve. Arquiva a rodada anterior, cria a pasta, escreve a tabela, desenha os
    Q-Q, e só então o `manifesto.json` — que é o índice, e um índice que aponta
    para arquivo inexistente é pior do que índice nenhum.

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

        caminho = plano.pasta / plano.tabela.nome
        escrever_atomico(caminho, plano.tabela.texto())
        criados.append(caminho)
        desfazer.append(lambda p=caminho: p.unlink(missing_ok=True))

        if plano.com_graficos and plano.graficos:
            # O `matplotlib` entra aqui dentro, e não no topo do arquivo, pela
            # mesma razão que na Fase 5: `--sem-graficos` não deve pagar por uma
            # biblioteca que ele existe para não usar.
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
            anotar(plano.raiz, _acao_do_historico(plano), plano.normalidade.quando)
        except OSError as erro:
            avisos.append(
                "A normalidade foi escrita, mas não consegui escrever no "
                f"historico.md: {erro}"
            )

    except Exception:
        # Qualquer falha, e não só `OSError` e `NormalidadeError`. O que roda
        # aqui dentro inclui o `matplotlib`, que estoura com exceções próprias —
        # e uma delas subindo sem passar por aqui deixava a rodada anterior
        # arquivada em troca de nada, que é exatamente o que o desfazer existe
        # para impedir. O erro continua subindo inteiro: o que muda é que o
        # disco volta ao estado de antes antes de ele subir.
        for passo in reversed(desfazer):
            try:
                passo()
            except OSError:
                avisos.append(
                    "Falhei ao desfazer uma etapa. Confira "
                    f"{PASTA_ANALISES}/{PASTA_NORMALIDADE} e {PASTA_ANTIGAS} antes "
                    "de rodar de novo."
                )
        raise

    return ResultadoNormalidade(
        criados=tuple(criados), arquivado=arquivado, avisos=tuple(avisos)
    )


def avaliar(
    banco: Banco,
    ficha: Ficha,
    linhas_do_dicionario: Sequence[Linha],
    pedidas: tuple[str, ...] = (),
    quando: datetime | None = None,
    com_graficos: bool = True,
) -> Normalidade:
    """
    Avalia a normalidade das numéricas do dicionário. Função pura.

    Separada de `preparar_normalidade` porque é o miolo testável, como o `perfilar`
    da Fase 4 e o `descrever` da Fase 5: dá para jogar um `DataFrame` montado à mão
    e uma lista de `Linha` aqui dentro e afirmar sobre a tabela, sem pasta de
    projeto e sem disco.

    `com_graficos` chega até aqui porque os pontos do Q-Q são calculados por
    variável e descartados inteiros quando não há figura: com `--sem-graficos`,
    `_pontos_do_qq` ordenava a coluna, chamava o `scipy` uma vez por variável e
    guardava N pontos que o `PlanoNormalidade.graficos` jogava fora. É o mesmo
    argumento do import do `matplotlib` lá embaixo — quem desligou o gráfico não
    deve pagar por ele.

    **Chama-se `avaliar` e não `testar`, e o motivo é prático.** O `pytest` coleta
    como teste qualquer objeto chamado `test*` no espaço de nomes de um arquivo de
    teste — inclusive um que tenha sido importado de outro módulo. Com o nome
    `testar`, o `from flatcap.normalidade import testar` do `test_normalidade.py`
    fazia o `pytest` tentar rodar a função como se ela fosse um caso de teste, e a
    suíte saía com um `ERROR` de fixture não encontrada que não tem nada a ver com
    o código. Foi encontrado rodando, e não lendo.

    Raises:
        VariavelIncompativelError, NadaParaAnalisarError,
        VariavelPedidaInexistenteError
    """
    quadro = banco.quadro
    total = int(quadro.shape[0])

    analisaveis = [linha for linha in linhas_do_dicionario if linha.analisavel]
    numericas = [linha for linha in analisaveis if linha.tipo == NUMERICA]

    # Só as numéricas vão para a recusa, e não `analisaveis` inteiro. A conferência
    # é a mesma da Fase 5; o escopo é desta análise. Uma coluna `data` com dois
    # formatos misturados recusa a descritiva e não tem por que bloquear um teste
    # que nunca a abriria. Ver `descritiva.recusar_incompativeis`.
    recusar_incompativeis(quadro, numericas, erro=VariavelIncompativelError)

    # Por nome, e não `if linha not in numericas`: a comparação de `Linha` é por
    # valor e a busca é linear, o que dava O(n²) — e, com duas linhas idênticas,
    # a segunda seria dada como numérica sem ser. A variável é a chave do
    # dicionário, e o `ler_arquivo` já recusa duas linhas com o mesmo nome.
    nomes_numericos = {linha.variavel for linha in numericas}
    fora: list[ForaDaNormalidade] = [
        ForaDaNormalidade(linha.variavel, linha.tipo, _motivo_de_fora(linha))
        for linha in linhas_do_dicionario
        if linha.variavel not in nomes_numericos
    ]

    if pedidas:
        _conferir_pedidas(pedidas, numericas, linhas_do_dicionario)
        escolhidas = [linha for linha in numericas if linha.variavel in pedidas]
        fora += [
            ForaDaNormalidade(
                linha.variavel,
                linha.tipo,
                f"numérica, e fora da lista `{PASTA_NORMALIDADE}:` do "
                f"{ARQUIVO_PROJETO}",
            )
            for linha in numericas
            if linha.variavel not in pedidas
        ]
    else:
        escolhidas = list(numericas)

    if not escolhidas:
        raise NadaParaAnalisarError(_mensagem_nada_a_analisar(linhas_do_dicionario))

    variaveis: list[VariavelTestada] = []
    usados: set[str] = set()
    for linha in escolhidas:
        serie = _coluna(quadro, linha.variavel)
        if serie is None:  # pragma: no cover - `recusar_incompativeis` já barrou
            continue
        variaveis.append(
            _testar_variavel(
                linha,
                serie,
                slug_do_nome(linha.variavel, usados),
                total,
                com_graficos,
            )
        )

    avisos = list(banco.avisos)
    avisos += [aviso for v in variaveis for aviso in v.avisos]

    return Normalidade(
        ficha=ficha,
        banco=banco,
        variaveis=tuple(variaveis),
        fora=tuple(fora),
        avisos=tuple(avisos),
        quando=quando or datetime.now(),
        tabela=_tabela(tuple(variaveis), total),
        graficos=tuple(
            _grafico(v) for v in variaveis if v.pontos_x and v.reta is not None
        ),
        pedidas=pedidas,
    )


# Uma variável


def _testar_variavel(
    linha: Linha,
    serie: pd.Series,
    slug: str,
    total: int,
    com_graficos: bool = True,
) -> VariavelTestada:
    """
    Mede uma coluna: forma, teste, e os pontos do Q-Q.

    Os faltantes são tratados **por variável**: cada uma é testada sobre os
    próprios valores preenchidos, e por isso o `n` muda de linha para linha da
    tabela. É o oposto do descarte por lista completa, que jogaria fora a linha
    inteira do banco por causa de uma célula vazia em uma coluna — e faria o teste
    de `idade` depender de quem respondeu `imc`. A coluna `n` está na tabela
    justamente porque ele varia; escondê-la seria deixar o leitor supor que é o
    mesmo denominador em todas.
    """
    valores = serie.dropna().astype("float64")
    preenchidos = int(valores.shape[0])
    faltantes = total - preenchidos
    distintos = int(valores.nunique())
    avisos: list[str] = []

    # `nunique() >= 2` antes de pedir a forma, e não é precaução: em uma coluna
    # constante a assimetria é 0/0, e o `pandas` devolve **0,0** para ela em vez de
    # `nan`. Impresso na tabela, esse zero se lê como "perfeitamente simétrica"
    # sobre uma coluna que não tem forma nenhuma — e é indistinguível do zero de
    # uma variável que é mesmo simétrica. O traço é a resposta certa.
    tem_forma = distintos >= 2
    assimetria = _finito(valores.skew()) if tem_forma and preenchidos >= 3 else None
    curtose = _finito(valores.kurt()) if tem_forma and preenchidos >= 4 else None

    w, p, impedimento, aviso_do_teste = _shapiro(linha.variavel, valores, preenchidos)
    if aviso_do_teste:
        avisos.append(aviso_do_teste)

    if impedimento:
        leitura = impedimento
    else:
        leitura = _leitura(assimetria, curtose, p)

    if w is not None and 2 <= distintos <= POUCOS_DISTINTOS:
        avisos.append(
            f"`{linha.variavel}`: {distintos} valor(es) distinto(s) em {preenchidos} "
            "casos. O Shapiro-Wilk supõe variável contínua, e sobre uma coluna "
            "discreta ele rejeita a normal quase sempre — o que a rejeição diz aí é "
            "«esta variável é discreta», não «a forma dela está errada». Vale conferir "
            f"no {ARQUIVO_DICIONARIO} se ela não é `categorica`: é o que o "
            "`flatcap perfil` propõe para código e para escala de poucos pontos."
        )

    if w is not None and MINIMO_SHAPIRO <= preenchidos < MINIMO_CONFIAVEL:
        avisos.append(
            f"`{linha.variavel}`: o teste rodou sobre {preenchidos} valor(es). Abaixo "
            f"de {MINIMO_CONFIAVEL} o Shapiro-Wilk quase não rejeita — «não rejeitou» "
            "aí não é evidência de normalidade, é ausência de evidência de qualquer "
            "coisa. A assimetria, a curtose e o Q-Q valem mais do que o valor-p neste "
            "tamanho."
        )

    # Sem figura, sem pontos. Eles só existem para o Q-Q, e calculá-los custa
    # ordenar a coluna e uma chamada ao `scipy` por variável — para guardar N
    # pontos que o `PlanoNormalidade.graficos` descarta em seguida.
    if com_graficos:
        pontos_x, pontos_y, reta = _pontos_do_qq(valores, preenchidos)
    else:
        pontos_x, pontos_y, reta = (), (), None

    return VariavelTestada(
        variavel=linha.variavel,
        slug=slug,
        rotulo=linha.rotulo or linha.variavel,
        n=preenchidos,
        distintos=distintos,
        faltantes=faltantes,
        assimetria=assimetria,
        curtose=curtose,
        w=w,
        p=p,
        leitura=leitura,
        avisos=tuple(avisos),
        pontos_x=pontos_x,
        pontos_y=pontos_y,
        reta=reta,
    )


def _shapiro(
    variavel: str, valores: pd.Series, preenchidos: int
) -> tuple[float | None, float | None, str, str]:
    """
    O Shapiro-Wilk, com os dois casos em que ele não existe barrados antes.

    Devolve `(W, p, impedimento, aviso)`. `impedimento` é a frase que vai para a
    coluna `leitura` quando não houve teste — ela ocupa o lugar do resultado, e não
    some junto com ele.

    Duas barreiras antes da chamada, e as duas são condições do teste e não
    precaução: abaixo de três observações o W não é definido, e uma coluna com um
    valor só tem variância zero, onde a estatística é uma divisão por zero. O
    `scipy` sinaliza os dois, mas cada versão dele sinaliza de um jeito — em umas
    levanta `ValueError`, em outras devolve `nan` com um aviso —, e um módulo que
    dependesse de qual é o comportamento de hoje é um módulo que muda de resposta
    quando o `pip` resolve outra versão.

    O aviso do próprio `scipy` para n grande é capturado, e não deixado ir para o
    `stderr`: um aviso impresso no meio da saída de um comando é um recado que o
    usuário aprende a ignorar. Capturado aqui, ele vira aviso do FlatCap e viaja
    até o manifesto junto do resto — mesma manobra que o `banco.py` faz com o
    `ParserWarning` do `pandas`, **inclusive no filtro por categoria**, que é o
    que faltava: um `simplefilter("always")` sem categoria recolhe qualquer aviso
    que qualquer biblioteca emita dentro do bloco, e o `or capturados` que estava
    aqui transformava um deles na frase «o teste rodou sobre N valores, acima de
    5000» dentro do manifesto — sobre uma amostra de trinta. Uma frase falsa no
    recibo da rodada é pior do que aviso nenhum.

    Quando o `scipy` avisa de outra coisa, o texto dele vai junto, como ele
    escreveu. O FlatCap repassa o recado; ele não inventa o motivo.
    """
    if preenchidos < MINIMO_SHAPIRO:
        return (
            None,
            None,
            f"{preenchidos} valor(es) — o teste precisa de pelo menos "
            f"{MINIMO_SHAPIRO}",
            "",
        )

    if int(valores.nunique()) < 2:
        return (
            None,
            None,
            "um único valor em todas as linhas — não há distribuição a testar",
            f"`{variavel}`: a coluna tem um valor só e não foi testada. Uma variável "
            "que não varia costuma ser critério de inclusão do estudo — vale citar "
            "no texto e deixar fora das tabelas.",
        )

    from scipy import stats

    aviso = ""
    try:
        with warnings.catch_warnings(record=True) as capturados:
            warnings.simplefilter("always", UserWarning)
            resultado = stats.shapiro(valores.to_numpy())
    except (ValueError, TypeError) as erro:  # pragma: no cover - as duas barreiras acima
        return None, None, "o teste não pôde ser calculado", (
            f"`{variavel}`: o Shapiro-Wilk não pôde ser calculado ({erro})."
        )

    do_scipy = [c for c in capturados if issubclass(c.category, UserWarning)]
    if preenchidos > MAXIMO_CONFIAVEL:
        aviso = (
            f"`{variavel}`: o teste rodou sobre {preenchidos} valor(es), acima de "
            f"{MAXIMO_CONFIAVEL}. O `scipy` avisa que o valor-p deixa de ser exato "
            "nesse tamanho — e, mais importante, com n grande qualquer desvio "
            "irrelevante sai significante. Leia a assimetria, a curtose e o Q-Q."
        )
    elif do_scipy:
        quais = "; ".join(
            dict.fromkeys(str(c.message).strip() for c in do_scipy)
        )
        aviso = (
            f"`{variavel}`: o `scipy` avisou ao calcular o Shapiro-Wilk sobre "
            f"{preenchidos} valor(es) — {quais}"
        )

    w = _finito(float(resultado.statistic))
    p = _finito(float(resultado.pvalue))
    if w is None or p is None:
        return None, None, "o teste não pôde ser calculado", aviso
    return w, p, "", aviso


def _pontos_do_qq(
    valores: pd.Series, preenchidos: int
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, float] | None]:
    """
    Os pontos do Q-Q e a reta de referência, calculados aqui e não no `graficos.py`.

    É a mesma divisão que a Fase 5 fez com as classes do histograma, pela mesma
    razão: qual quantil teórico corresponde à i-ésima observação é decisão
    estatística, não de desenho. A posição usada é a de Blom, `(i − 3/8) / (n + 1/4)`
    — a mesma do `scipy.stats.probplot`, para que a figura do FlatCap e a que
    alguém desenhar por fora do FlatCap tenham os mesmos pontos.

    **A reta passa pelos quartis**, e não é um ajuste por mínimos quadrados. É a
    `qqline` do R, e a diferença aparece justamente no caso em que se consulta a
    figura: um valor extremo inclina a reta dos mínimos quadrados o bastante para o
    resto dos pontos parecer curvo — e o que se queria ver era o valor extremo.

    Devolve vazio quando não há reta possível: menos de três valores, ou Q1 igual a
    Q3, que é a variável discreta com duas ou três categorias disfarçada de número.
    Sem reta a figura não sai, e o motivo vai para o manifesto — mesma decisão que
    a Fase 5 tomou com os quartis que coincidem.
    """
    if preenchidos < MINIMO_SHAPIRO:
        return (), (), None

    from scipy import stats

    ordenados = valores.sort_values().to_numpy()
    posicoes = [(i + 1 - 0.375) / (preenchidos + 0.25) for i in range(preenchidos)]
    teoricos = [float(q) for q in stats.norm.ppf(posicoes)]

    q1, q3 = float(valores.quantile(0.25)), float(valores.quantile(0.75))
    x1, x3 = float(stats.norm.ppf(0.25)), float(stats.norm.ppf(0.75))
    if q3 == q1:
        return (), (), None

    inclinacao = (q3 - q1) / (x3 - x1)
    intercepto = q1 - inclinacao * x1
    if not (math.isfinite(inclinacao) and math.isfinite(intercepto)):
        return (), (), None

    return (
        tuple(teoricos),
        tuple(float(valor) for valor in ordenados),
        (intercepto, inclinacao),
    )


def _grafico(variavel: VariavelTestada) -> Grafico:
    """
    O Q-Q de uma variável.

    O subtítulo é `n = 180 · 12 sem informação`, o mesmo das figuras da Fase 5, e
    **não** traz o W nem o valor-p. Os dois estão na tabela, que fica na mesma
    seção do documento, duas linhas acima: repeti-los na figura seria publicar o
    mesmo número duas vezes na mesma página — que é o argumento pelo qual a
    categórica saiu sem eixo de valores.
    """
    return Grafico(
        nome=f"qq_{variavel.slug}.png",
        especie="qq",
        variavel=variavel.variavel,
        titulo=f"Q-Q — {variavel.rotulo}",
        subtitulo=_subtitulo(variavel.n, variavel.faltantes),
        rotulo_categoria="quantis esperados da normal",
        rotulo_valor=variavel.rotulo,
        pontos_x=variavel.pontos_x,
        pontos_y=variavel.pontos_y,
        reta=variavel.reta,
    )


# A leitura em palavras


def _leitura(
    assimetria: float | None, curtose: float | None, p: float | None
) -> str:
    """
    O que os números dizem, em português, na última coluna da tabela.

    Descreve a **forma** e o que o teste concluiu, e nunca escolhe um teste para
    você. "Use Mann-Whitney" depende da comparação que se vai fazer — de quantos
    grupos, pareados ou não, de que tamanho —, e este módulo olha uma coluna, não
    um delineamento. Sugerir dali seria a mesma ultrapassagem que a Fase 5 recusou
    quando decidiu não escrever prosa sobre os números.

    A ordem das partes é a da leitura: primeiro a forma, que vale em qualquer n,
    depois o veredito do teste, que não vale.
    """
    partes: list[str] = []

    if assimetria is not None:
        direcao = "à direita" if assimetria > 0 else "à esquerda"
        if abs(assimetria) < ASSIMETRIA_LEVE:
            partes.append("simétrica")
        elif abs(assimetria) < ASSIMETRIA_FORTE:
            partes.append(f"levemente assimétrica {direcao}")
        else:
            partes.append(f"assimétrica {direcao}")

    if curtose is not None:
        if curtose >= CURTOSE_NOTAVEL:
            partes.append("caudas pesadas")
        elif curtose <= -CURTOSE_NOTAVEL:
            partes.append("achatada")

    if p is not None:
        partes.append(
            "o teste rejeita a normal" if p < ALFA else "compatível com a normal"
        )

    return "; ".join(partes) if partes else _AUSENTE


# A tabela


def _tabela(variaveis: tuple[VariavelTestada, ...], total: int) -> Tabela:
    """
    Uma tabela só, com uma linha por variável.

    É a diferença de forma em relação à descritiva, e ela tem razão: uma tabela de
    normalidade é lida **atravessando** as variáveis — "quais destas eu posso
    tratar como normais?" —, e uma linha por arquivo daria doze arquivos de uma
    linha e doze cabeçalhos repetidos no documento. A descritiva escreve um arquivo
    por variável porque lá cada um é uma tabela de verdade.

    A consequência no manifesto é a que o `colunas` da Fase 7 resolve: esta rodada
    tem **um item** com muitas colunas, em vez de um item por coluna.

    A primeira coluna é o **rótulo**, e não o nome da coluna do banco: é o que o
    cliente lê, e é o mesmo texto que encabeça a seção da variável na descritiva.
    O nome técnico está no manifesto, que é quem liga arquivo a variável.
    """
    corpo = tuple(
        (
            v.rotulo,
            str(v.n),
            str(v.faltantes),
            _forma(v.assimetria),
            _forma(v.curtose),
            _estatistica(v.w),
            _valor_p(v.p),
            v.leitura,
        )
        for v in variaveis
    )

    return Tabela(
        nome=ARQUIVO_TABELA,
        especie="normalidade",
        # Vazia de propósito: esta tabela não é de uma variável. É o campo que a
        # linha `# variável:` do cabeçalho do `.csv` usa, e escrever ali a primeira
        # das doze seria uma legenda mentindo.
        variavel="",
        titulo="Pressupostos — normalidade",
        colunas=(
            "variável",
            "n",
            "faltantes",
            "assimetria",
            "curtose",
            "W",
            "valor-p",
            "leitura",
        ),
        linhas=corpo,
        notas=(
            f"teste de Shapiro-Wilk, nível de {numero(ALFA)}.",
            "assimetria e curtose são as amostrais, com correção de viés (G1 e G2); "
            "a curtose é a em excesso — na normal as duas valem 0.",
            f"valor-p abaixo de {numero(MENOR_P, 3)} sai como `< {numero(MENOR_P, 3)}`; "
            "ele nunca é zero.",
            "faltantes por variável: cada uma é testada sobre os próprios valores "
            f"preenchidos, de {total} linhas do banco — por isso o n muda de linha.",
            "o valor-p depende do n: com poucos casos o teste quase não rejeita, e "
            "com muitos rejeita desvios irrelevantes. Leia junto com a assimetria, a "
            "curtose e o Q-Q.",
            "isto descreve a variável como ela está. Normalidade dentro de cada grupo "
            "(para um teste t) e normalidade dos resíduos (para uma regressão) são "
            "outras perguntas, e não se deduzem desta.",
        ),
    )


# O manifesto


def montar_manifesto(
    normalidade: Normalidade, linhas: Sequence[Linha], com_graficos: bool
) -> Manifesto:
    """
    Traduz a rodada para o índice que o relatório vai ler.

    **Um item só**, e é a novidade de forma da Fase 7. Na descritiva um item é uma
    variável, porque lá cada variável é uma seção do documento com a tabela dela.
    Aqui a seção é uma: uma tabela que fala de todas e um Q-Q por variável abaixo
    dela. O item declara em `colunas` quais colunas do banco entraram — é o campo
    que faz as conferências do relatório continuarem funcionando quando a pasta tem
    mais de uma rodada.

    `n` é o número de linhas do banco e `faltantes` é zero, porque a rodada cobre o
    banco inteiro; o `n` que varia é o de cada variável, e ele está na tabela e nos
    `detalhes`, que é onde ele quer dizer alguma coisa.
    """
    banco = normalidade.banco
    leitura = banco.leitura
    ficha = normalidade.ficha

    item = ItemDoManifesto(
        variavel="",
        slug=PASTA_NORMALIDADE,
        rotulo="Normalidade",
        tipo=ANALISE_NORMALIDADE,
        n=banco.linhas,
        faltantes=0,
        colunas=normalidade.colunas_usadas,
        artefatos=_artefatos(normalidade, com_graficos),
        detalhes={
            "variaveis": {v.variavel: v.como_detalhe() for v in normalidade.variaveis},
            "testadas": sum(1 for v in normalidade.variaveis if v.testada),
            "rejeitadas": len(normalidade.rejeitadas),
            "pedidas_na_ficha": list(normalidade.pedidas),
        },
        avisos=tuple(aviso for v in normalidade.variaveis for aviso in v.avisos),
    )

    return Manifesto(
        analise=ANALISE_NORMALIDADE,
        flatcap=__version__,
        gerado_em=normalidade.quando,
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
            "numericas": sum(
                1 for linha in linhas if linha.analisavel and linha.tipo == NUMERICA
            ),
        },
        ambiente=_ambiente(com_graficos),
        regras={
            "teste": "shapiro-wilk",
            "alfa": ALFA,
            "minimo": MINIMO_SHAPIRO,
            "minimo_confiavel": MINIMO_CONFIAVEL,
            "maximo_confiavel": MAXIMO_CONFIAVEL,
            "assimetria": "amostral (G1, com correção de viés) — normal = 0",
            "curtose": "em excesso, amostral (G2, com correção de viés) — normal = 0",
            "faltantes": "por variável",
            "posicao_do_qq": "Blom, (i - 3/8) / (n + 1/4)",
            "reta_do_qq": "pelos quartis (qqline), não por mínimos quadrados",
            "graficos": com_graficos,
            "semente": SEMENTE,
        },
        itens=(item,),
        fora=tuple(
            {"variavel": f.variavel, "tipo": f.tipo, "motivo": f.motivo}
            for f in normalidade.fora
        ),
        avisos=normalidade.avisos,
    )


def _artefatos(normalidade: Normalidade, com_graficos: bool) -> tuple[Artefato, ...]:
    artefatos = [
        Artefato(
            arquivo=normalidade.tabela.nome,
            especie=normalidade.tabela.especie,
            formato="csv",
            titulo=normalidade.tabela.titulo,
        )
    ]
    if com_graficos:
        artefatos += [
            Artefato(
                arquivo=grafico.nome,
                especie=grafico.especie,
                formato="png",
                titulo=grafico.titulo,
            )
            for grafico in normalidade.graficos
        ]
    return tuple(artefatos)


def _ambiente(com_graficos: bool) -> dict[str, Any]:
    """
    As versões que produziram estes números.

    O `scipy` entra aqui e **não** entra no `ambiente` da descritiva, e a assimetria
    é deliberada: cada rodada declara o que ela usou. Uma descritiva que anunciasse
    uma versão de `scipy` estaria dizendo que um daqueles números passou por ele, e
    nenhum passou — e o `ambiente` existe justamente para responder "mudaram os
    dados ou mudou a biblioteca?" sobre os números **daquele** arquivo.

    O `matplotlib` só é consultado quando há gráfico, como na Fase 5: perguntar a
    versão custaria importar a biblioteca que o `--sem-graficos` existe para evitar.
    A `fonte` entra junto e pela mesma razão que na descritiva: ela é a que o
    matplotlib resolveu, que pode não ser a que o `graficos.py` pediu.
    """
    import openpyxl
    import scipy

    ambiente: dict[str, Any] = {
        "python": ".".join(str(parte) for parte in sys.version_info[:3]),
        "flatcap": __version__,
        "pandas": pd.__version__,
        "openpyxl": openpyxl.__version__,
        "scipy": scipy.__version__,
        "matplotlib": None,
        "fonte": None,
    }
    if com_graficos:
        from .graficos import fonte_dos_graficos, versao_do_matplotlib

        ambiente["matplotlib"] = versao_do_matplotlib()
        ambiente["fonte"] = fonte_dos_graficos()
    return ambiente


# A lista da ficha


def _variaveis_pedidas(raiz: Path) -> tuple[str, ...]:
    """
    A lista `normalidade:` do `projeto.yaml`, quando ela existir.

    Ausente ou vazia quer dizer "todas as numéricas", que é o padrão e o caso
    comum: a normalidade é diagnóstico, e o diagnóstico é sobre o banco inteiro.
    A lista existe para o projeto em que só algumas variáveis vão para o teste —
    porque só elas entram em uma comparação depois.

    Lida pelo `ficha.bloco`, e não abrindo o YAML aqui: o `ficha.py` é o único
    módulo do pacote que abre o `projeto.yaml`, e é bom que continue sendo.

    Formato errado recusa em vez de ignorar. Um `normalidade: idade` (um texto, não
    uma lista) é engano fácil de cometer, e ignorá-lo rodaria a análise inteira
    como se a linha não estivesse lá — que é o pior dos dois mundos: você escreveu,
    e não valeu.
    """
    bruto = bloco(raiz, PASTA_NORMALIDADE)
    if bruto is None:
        return ()
    if not isinstance(bruto, list):
        raise VariavelPedidaInexistenteError(
            f"A chave `{PASTA_NORMALIDADE}:` do {ARQUIVO_PROJETO} deveria ser uma "
            f"lista de variáveis e é um {type(bruto).__name__}.\n\n"
            "Escreva assim:\n\n"
            f"  {PASTA_NORMALIDADE}:\n"
            "    - idade\n"
            "    - imc\n\n"
            "Ou apague a chave: sem ela, todas as numéricas do dicionário entram."
        )
    return tuple(
        texto
        for texto in (str(item).strip() for item in bruto if item is not None)
        if texto
    )


def _conferir_pedidas(
    pedidas: tuple[str, ...],
    numericas: Sequence[Linha],
    linhas: Sequence[Linha],
) -> None:
    """
    Recusa a rodada quando a lista da ficha nomeia algo que não serve.

    Duas situações, e a mensagem separa as duas porque o conserto é diferente: a
    variável não existe no dicionário (erro de digitação, ou coluna que sumiu do
    banco) ou existe e não é `numerica` (o tipo está errado em um dos dois lugares).
    """
    disponiveis = {linha.variavel for linha in numericas}
    conhecidas = {linha.variavel: linha for linha in linhas}

    desconhecidas = [nome for nome in pedidas if nome not in conhecidas]
    nao_numericas = [
        (nome, conhecidas[nome].tipo)
        for nome in pedidas
        if nome in conhecidas and nome not in disponiveis
    ]

    if not desconhecidas and not nao_numericas:
        return

    partes = [
        f"A lista `{PASTA_NORMALIDADE}:` do {ARQUIVO_PROJETO} nomeia "
        f"{len(desconhecidas) + len(nao_numericas)} variável(is) que não entram na "
        "análise. Nada foi gerado.",
        "",
    ]
    for nome in desconhecidas:
        partes.append(f"  {nome} — não está no {ARQUIVO_DICIONARIO}")
    for nome, tipo in nao_numericas:
        partes.append(f"  {nome} — está marcada `{tipo}` no {ARQUIVO_DICIONARIO}")
    partes += [
        "",
        "Normalidade é uma pergunta sobre variável numérica: uma categórica não tem "
        "distribuição contínua para comparar com a normal, e uma data tem, mas a "
        "resposta não quer dizer nada.",
        "",
        "Duas saídas:",
        f"  1. corrija o nome na lista do {ARQUIVO_PROJETO} — ele é o nome da coluna "
        f"no banco, como aparece na primeira coluna do {ARQUIVO_DICIONARIO};",
        f"  2. se a variável é mesmo numérica, corrija o `tipo` dela no "
        f"{ARQUIVO_DICIONARIO} e rode `flatcap descritiva` de novo antes.",
    ]
    raise VariavelPedidaInexistenteError("\n".join(partes))


# Mensagens


def _motivo_de_fora(linha: Linha) -> str:
    if not linha.no_banco:
        return "não está nesta versão do banco (`no_banco = nao`)"
    if not linha.analisavel:
        return "marcada `ignorar` no dicionário"
    return f"marcada `{linha.tipo}` — a normalidade só se pergunta de numérica"


def _mensagem_nada_a_analisar(linhas: Sequence[Linha]) -> str:
    total = len(linhas)
    numericas = sum(
        1 for linha in linhas if linha.analisavel and linha.tipo == NUMERICA
    )
    if numericas:
        return (
            f"As {numericas} variável(is) numérica(s) do {ARQUIVO_DICIONARIO} ficaram "
            f"todas fora da lista `{PASTA_NORMALIDADE}:` do {ARQUIVO_PROJETO}.\n\n"
            "Ou acrescente pelo menos uma à lista, ou apague a chave — sem ela, todas "
            "as numéricas entram."
        )
    return (
        f"Nenhuma das {total} variáveis do {ARQUIVO_DICIONARIO} é `numerica`, e "
        "normalidade só se pergunta de variável numérica.\n\n"
        "Abra o dicionário e reveja a coluna `tipo`. Se uma coluna de números ficou "
        "marcada `categorica` — o que a Fase 4 sugere para código de 0/1 e para "
        "escala de 1 a 5, e costuma estar certo —, ela continua não tendo "
        "normalidade a testar: o teste é sobre variável contínua."
    )


def _acao_do_historico(plano: PlanoNormalidade) -> str:
    normalidade = plano.normalidade
    rejeitadas = len(normalidade.rejeitadas)
    partes = [
        f"`flatcap normalidade {normalidade.ficha.record_id}` — normalidade de "
        f"`{normalidade.banco.versao.arquivo}`: {len(normalidade.variaveis)} "
        f"variável(is) testada(s), {rejeitadas} com a normal rejeitada "
        f"(Shapiro-Wilk, {numero(ALFA)}), em "
        f"`{PASTA_ANALISES}/{PASTA_NORMALIDADE}/`."
    ]
    if plano.arquivamento is not None:
        partes.append(
            f"A rodada anterior foi para `{PASTA_ANTIGAS}/{plano.arquivamento[1].name}/`."
        )
    if normalidade.pedidas:
        partes.append(
            f"Restrita à lista `{PASTA_NORMALIDADE}:` do {ARQUIVO_PROJETO}."
        )
    if not plano.com_graficos:
        partes.append("Rodado com `--sem-graficos`.")
    return " ".join(partes)


# Leitura da série e formatação


def _coluna(quadro: pd.DataFrame, nome: str) -> pd.Series | None:
    """
    A coluna do banco pelo nome, ou `None`.

    Pela posição, e não por `quadro[nome]`, pela mesma razão da Fase 5: nome
    repetido devolveria um `DataFrame` no lugar de uma coluna.
    """
    for posicao, coluna in enumerate(quadro.columns):
        if str(coluna) == nome:
            return quadro.iloc[:, posicao]
    return None


def _finito(valor: Any) -> float | None:
    """
    O número, ou `None` quando ele não é um número.

    O `pandas` devolve `nan` para assimetria com menos de três valores e para
    curtose com menos de quatro, e `nan` impresso em uma tabela é a palavra `nan`
    dentro de uma célula do Word.
    """
    try:
        numero_ = float(valor)
    except (TypeError, ValueError):
        return None
    return numero_ if math.isfinite(numero_) else None


def _arredondar(valor: float | None) -> float | None:
    if valor is None:
        return None
    return round(float(valor), 6) if math.isfinite(float(valor)) else None


def _forma(valor: float | None) -> str:
    """
    Assimetria e curtose com sinal, sempre com as mesmas casas.

    Com as casas fixas de propósito, ao contrário das estatísticas da descritiva:
    esta coluna é lida **de cima para baixo**, comparando variáveis entre si, e uma
    coluna em que uns valores têm casa decimal e outros não é uma coluna que não
    alinha. É o mesmo argumento dos percentuais da Fase 5.
    """
    if valor is None:
        return _AUSENTE
    return f"{valor:+.{CASAS_FORMA}f}".replace(".", ",")


def _estatistica(valor: float | None) -> str:
    if valor is None:
        return _AUSENTE
    return f"{valor:.{CASAS_W}f}".replace(".", ",")


def valor_p(valor: float | None) -> str:
    """
    O valor-p, com três casas e nunca como zero.

    `< 0,001` em vez de `0,000` não é preciosismo de formatação: um valor-p é
    estritamente maior que zero, e `p = 0,000` impresso em um relatório assinado é
    um número que não existe. É a convenção de qualquer revista da área, e é a
    única regra de formatação deste módulo que alguém vai conferir.

    Pública desde a 1.5.0, com o apelido privado que este módulo usa: a associação
    imprime p-valor na mesma página, e dois formatadores para o mesmo p é como um
    documento sai com `< 0,001` numa tabela e `0,000` na seguinte.
    """
    if valor is None:
        return _AUSENTE
    if valor < MENOR_P:
        return f"< {numero(MENOR_P, CASAS_P)}"
    return f"{valor:.{CASAS_P}f}".replace(".", ",")


_valor_p = valor_p


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


__all__ = [
    "ALFA",
    "ARQUIVO_TABELA",
    "MAXIMO_CONFIAVEL",
    "MINIMO_CONFIAVEL",
    "MINIMO_SHAPIRO",
    "DicionarioAusenteError",
    "DicionarioDesatualizadoError",
    "ForaDaNormalidade",
    "NadaParaAnalisarError",
    "Normalidade",
    "NormalidadeError",
    "PlanoNormalidade",
    "ResultadoNormalidade",
    "VariavelIncompativelError",
    "VariavelPedidaInexistenteError",
    "VariavelTestada",
    "avaliar",
    "executar_normalidade",
    "montar_manifesto",
    "preparar_normalidade",
    "valor_p",
]
