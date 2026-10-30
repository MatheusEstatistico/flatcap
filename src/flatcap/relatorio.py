# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
O relatório — o passo final do fluxo, e o que a Fase 6 automatiza.

Este módulo **monta o conteúdo** do documento e não escreve `.docx` nenhum. Quem
escreve é o `documento.py`, que recebe um `Relatorio` pronto e não decide mais
nada. É a mesma divisão da Fase 5 entre `descritiva.py` e `graficos.py`, pelo
mesmo motivo: se o gerador do documento recalculasse qualquer coisa, bastaria uma
diferença de arredondamento para o `.docx` dizer 37 e o `.csv` ao lado dizer 38 —
e ninguém confere documento contra planilha.

Aqui a regra é ainda mais forte, porque é o que sustenta a decisão de arquitetura
nº 3 do roteiro:

    **O relatório não abre o banco.** Nunca.

Ele lê o `manifesto.json` e os `.csv` que a Fase 5 escreveu, e é só isso. Não
importa o `pandas`, não importa o `matplotlib`, não recalcula uma média sequer.
Um número que aparece no documento é, byte a byte, o número que está no arquivo
que você pode abrir no Excel e conferir. Se o relatório recalculasse, existiriam
duas fontes para o mesmo 37% — e o dia em que elas discordassem seria o dia em que
o cliente perguntaria.

A consequência prática aparece no relógio: `flatcap relatorio` parte em ~0,1 s,
porque nenhuma das bibliotecas caras entra. Foi para manter isso que
`versao_vigente` desceu para o `ficha.py` e `PASTA_DESCRITIVA` para o
`projeto.py` — as duas moravam em módulos que importam o `pandas` e são, as duas,
perguntas que não precisam dele.

## O que este módulo decide

**De quais rodadas o documento fala.** De **todas** as que estiverem em
`3. Análises/*/` com um `manifesto.json` dentro. Não há nome de pasta fixo no
código: a descritiva, a normalidade e a análise que vier depois entram pelo
mesmo caminho, e o comando que a escreveu não precisa dizer nada a este módulo.
Uma rodada arquivada em `2. Versões antigas/` continua legível pelo
`manifesto.ler`, mas não é o que este comando monta: o relatório é o das
rodadas de agora.

Foi este o buraco que a Fase 7 abriu e que a 1.3.1 fecha. O `flatcap
normalidade` escrevia `normalidade.csv` e os `qq_*.png` no disco, o relatório
lia uma pasta de nome fixo, e nada disso chegava ao `.docx` — sem erro, sem
aviso, com o comando saindo com código 0 nas duas pontas.

**Em que ordem.** Na da lista `analises:` do `projeto.yaml`, que é o que foi
combinado na reunião — a ficha promete isso desde a Fase 2 e ninguém lia. O que
não estiver na lista entra depois, na `ORDEM_PADRAO_DAS_ANALISES` do
`manifesto.py`, e o que não estiver em nenhuma das duas entra no fim, em ordem
alfabética. Análise escrita na ficha e sem rodada no disco não é erro: vira um
aviso no terminal, porque quase sempre é a análise que você combinou e ainda
não rodou.

**Se elas ainda descrevem o que está na pasta.** Quatro conferências, e nenhuma
delas recusa o comando — a decisão da fase foi **gerar com o aviso dentro do
documento**:

    * a versão vigente do banco é outra desde a rodada;
    * o arquivo do banco foi alterado no disco depois de registrado;
    * o `dicionario.csv` mudou depois da rodada (variável nova, tipo trocado,
      rótulo reescrito, faixas diferentes);
    * um artefato listado em algum manifesto não está mais na pasta.

Cada uma vira um `Alerta`, e o `Alerta` viaja para dentro do `.docx`, logo abaixo
da identificação. Um aviso que fica só no terminal é um aviso que ninguém lê
depois de anexar o documento ao e-mail.

**Que o projeto fica pronto.** Escrito o documento, o `status:` da ficha passa para
`pronto` — é o que o `flatcap status` mostra, e o que tira dele o ATRASADO. É a
única linha da ficha que este módulo escreve, e a simulação diz que vai escrevê-la.
O documento vem primeiro: um status que não se escreve vira aviso, e não desfaz o
relatório.

**Como cada tabela vira tabela.** Os `.csv` da Fase 5 já trazem os números
formatados em português e um cabeçalho de comentário com o denominador. A leitura
aqui é fiel: separa os comentários das linhas de dados e não converte nada — o
texto que está na célula do `.csv` é o texto que vai para a célula do Word.

## O que sai na primeira página

Título, subtítulo com `matrícula - nome`, os alertas quando houver, a
**abertura** — três pedaços que `montar_abertura` junta, nesta ordem:

    1. o `TEXTO_PADRAO`, os parágrafos fixos que abrem todo relatório de todo
       projeto, definidos logo abaixo em um bloco só para serem reescritos sem
       se procurar código;
    2. a **finalidade** do estudo;
    3. os **objetivos**, geral e específicos —

e, fechando a página, a **metodologia**: o subtítulo "Metodologia Estatística
(texto padrão)" e um parágrafo para o cliente levar para o artigo.

Os dois do meio vêm da ficha, que os recebeu do formulário do REDCap (`fin` e
`obj1`) quando o `flatcap novo` criou a pasta — e que você pode corrigir à mão,
porque o `projeto.yaml` é seu.

A metodologia vem das rodadas, pelo `metodologia.py`: cada análise com rodada dá
uma frase que nomeia só os testes que rodaram, lidos do manifesto, e a versão do
Python fecha o parágrafo. Também não abre o banco — o que ela afirma é o que os
manifestos registraram. Viaja em dois campos próprios do `Relatorio`, e não no
`texto`, porque o subtítulo dela é um título, e o `documento.py` precisa saber
disso para escrevê-lo no estilo de subtítulo.

Campo da ficha em branco não encolhe a página em silêncio: vira um marcador
visível **e** um `Alerta` de código `texto_ausente`. Nada disso fere a regra da
casa: ler a ficha é ler YAML, não é abrir o banco.

## O que este módulo deliberadamente não faz

Não escreve prosa sobre os números. Não monta uma "Tabela 1" consolidada. Não
escreve apêndice técnico. As três foram decisões suas, e as três continuam a um
argumento de distância — o `Relatorio` já carrega tudo o que elas precisariam.

E não imprime mais a tabela de identificação nem os rodapés de denominador das
tabelas: as duas saíram na revisão de formatação, e o que elas diziam sobre a
procedência ficou nos metadados do arquivo (`documento._propriedades`) e no
`manifesto.json` da rodada.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .dados import linha_do_tempo
from .dicionario import ARQUIVO_DICIONARIO, linhas_de_comentario
from .dicionario import ler as ler_dicionario
from .ficha import (
    Ficha,
    FichaError,
    Versao,
    caminho_da_ficha,
    definir_status,
    escrever_atomico,
    status_reconhecido,
    versao_vigente,
)
from .ficha import ler as ler_ficha
from .manifesto import (
    ANALISE_DESCRITIVA,
    ARQUIVO_MANIFESTO,
    ORDEM_PADRAO_DAS_ANALISES,
    ItemDoManifesto,
    Manifesto,
)
from .manifesto import ler as ler_manifesto
from .metodologia import montar_metodologia
from .nomes import SEPARADOR, sanitizar
from .projeto import (
    ARQUIVO_PROJETO,
    ARQUIVO_TEMPLATE,
    PASTA_ANALISES,
    PASTA_ANTIGAS,
    STATUS_PRONTO,
    anotar,
    pastas_das_analises,
)

PREFIXO_RELATORIO = "Relatorio_"

TITULO_PADRAO = "Relatório Estatístico"

# `ARQUIVO_TEMPLATE` vem do `projeto.py`, e não mais escrito aqui uma segunda
# vez. A duplicação existia porque importar o `documento.py` no topo traria o
# `python-docx` junto, e a simulação deste comando não escreve documento nenhum;
# a constante desceu para o dono do desenho da pasta, que é o mesmo caminho que
# `versao_vigente` e `PASTA_DESCRITIVA` já tinham feito. O `documento.py`
# reexporta o nome, então quem o importava de lá não mudou.


# ─────────────────────────────────────────────────────────────────────────────
#  O TEXTO FIXO DA PRIMEIRA PÁGINA — é aqui que se escreve.
#
#  Uma linha da tupla, um parágrafo do documento, na ordem em que estão. É a
#  parte que não muda de cliente para cliente, e ela abre a página: a finalidade
#  e os objetivos, que são deste projeto, vêm logo depois.
#
#  `()` é o estado de hoje: ainda não escrito. A primeira página continua saindo
#  — com a finalidade e os objetivos —, só ainda não tem a parte institucional.
#  Escrever é acrescentar strings aqui, e nada mais: nada no código sabe o que
#  está escrito, e a estrutura do documento não muda quando o texto crescer,
#  encolher ou ganhar parágrafos.
#
#  O que **não** se faz é deixar um parágrafo de mentira guardando o lugar. Um
#  `xxxxx` ou um `[a definir]` esquecido aqui não é feio: é um defeito que
#  atravessa a conferência e chega impresso na mão de um professor de medicina.
# ─────────────────────────────────────────────────────────────────────────────

TEXTO_PADRAO: tuple[str, ...] = ()

# A nota de comentário que todo `.csv` da Fase 5 traz na segunda linha. Ela é
# descartada na leitura porque o título da seção já diz de qual variável se trata,
# e repetir "variável: escolaridade" embaixo de uma tabela chamada "Escolaridade"
# é ruído em um documento que vai para o cliente.
_NOTA_REDUNDANTE = re.compile(r"^vari[áa]vel:", re.IGNORECASE)

_SEPARADOR_CAMPO = ";"


class RelatorioError(RuntimeError):
    """
    Falha ao montar o relatório, já traduzida para o usuário.

    Erro próprio pelo mesmo motivo de `ConfigError`, `RedcapError`, `ProjetoError`,
    `FichaError`, `DadosError`, `BancoError`, `DicionarioError`, `DescritivaError`
    e `ManifestoError`: a CLI captura esta classe e transforma em painel. Qualquer
    outra exceção é bug de verdade e deve subir com o traceback inteiro.
    """


class AnaliseAusenteError(RelatorioError):
    """
    O projeto não tem nenhuma rodada de análise para relatar.

    É a única recusa desta fase, e ela não é uma escolha entre gerar e não gerar:
    sem manifesto nenhum não há o que montar. Todas as outras divergências viram
    aviso dentro do documento.

    Chamava-se `DescritivaAusenteError` quando a descritiva era a única análise
    que existia. O nome antigo continua apontando para esta classe, logo abaixo:
    ele está em `except` de quem chama, e um `raise` que nenhum `except` pega é
    um traceback na cara do usuário.
    """


DescritivaAusenteError = AnaliseAusenteError


class TabelaIlegivelError(RelatorioError):
    """
    Um `.csv` da rodada existe e não dá para interpretar.
    """


class ModeloAusenteError(RelatorioError):
    """
    O `template.docx` indicado em `--template` não existe.
    """


@dataclass(frozen=True)
class Alerta:
    """
    Uma divergência entre a rodada e o que está na pasta hoje.

    Vai para o terminal **e** para dentro do documento. A duplicação é o ponto:
    o terminal você vê agora, o documento é o que sobra depois de o arquivo ser
    anexado a um e-mail e aberto por outra pessoa em outro dia.
    """

    codigo: str
    titulo: str
    detalhe: str = ""


@dataclass(frozen=True)
class TabelaLida:
    """
    Um `.csv` da descritiva, separado em cabeçalho de comentário e dados.

    Os valores são texto e continuam texto. Converter `28,7` para `0.287` e
    formatar de novo na hora de escrever seria reintroduzir, no último passo do
    fluxo, exatamente o arredondamento que a Fase 5 já resolveu.
    """

    arquivo: str
    especie: str
    titulo: str
    notas: tuple[str, ...] = ()
    colunas: tuple[str, ...] = ()
    linhas: tuple[tuple[str, ...], ...] = ()

    @property
    def largura(self) -> int:
        return len(self.colunas)

    @property
    def total(self) -> int:
        return len(self.linhas)


@dataclass(frozen=True)
class Figura:
    """
    Um `.png` da descritiva, com o caminho já conferido.
    """

    arquivo: str
    caminho: Path
    especie: str
    titulo: str


@dataclass(frozen=True)
class Secao:
    """
    Uma variável no documento: o que ela mostra, na ordem em que mostra.

    A ordem das seções é a do manifesto, que é a do dicionário, que é a das
    colunas do banco. Reordenar o `dicionario.csv` reordena o documento, sem
    tocar em código — é a decisão da Fase 5 aparecendo aqui.
    """

    variavel: str
    rotulo: str
    tipo: str
    n: int
    faltantes: int
    tabelas: tuple[TabelaLida, ...] = ()
    figuras: tuple[Figura, ...] = ()

    @property
    def preenchidos(self) -> int:
        return self.n - self.faltantes


@dataclass(frozen=True)
class Rodada:
    """
    Uma rodada de análise encontrada em `3. Análises/`, já lida.

    O nome vem do campo `analise` do manifesto, e não do nome da pasta: nome de
    pasta é o que o usuário renomeia, e é ele que teria de bater com a lista
    `analises:` da ficha para a ordem do documento funcionar. A pasta entra só
    como o lugar onde os artefatos moram — e como o nome que sobra quando um
    manifesto antigo não declara a análise dele.
    """

    analise: str
    pasta: Path
    manifesto: Manifesto
    secoes: tuple[Secao, ...] = ()


@dataclass(frozen=True)
class ForaDoRelatorio:
    """
    Uma variável do dicionário que não gerou nada, e por quê.

    Não entra no `.docx` — é diagnóstico seu, não conteúdo do cliente —, mas
    aparece no terminal pelo mesmo motivo da Fase 5: "não está no relatório" e
    "ninguém reparou que ela existia" são coisas diferentes.
    """

    variavel: str
    tipo: str
    motivo: str


@dataclass(frozen=True)
class Relatorio:
    """
    O documento inteiro, decidido. É daqui que saem o `.docx` e o terminal.
    """

    ficha: Ficha
    # O manifesto que responde pelo documento quando a pergunta é uma só — a
    # data da rodada nas propriedades do `.docx`, o banco no cabeçalho do
    # terminal. É o da descritiva quando ela existe; ver `_manifesto_principal`.
    # As rodadas todas estão em `rodadas`.
    manifesto: Manifesto
    titulo: str
    secoes: tuple[Secao, ...]
    texto: tuple[str, ...] = ()
    # A metodologia da primeira página: os parágrafos e o subtítulo acima deles. Fora
    # do `texto` porque o subtítulo é um título, e não texto corrido; vazios, a
    # página fecha nos objetivos, como antes da 1.16.0.
    metodologia: tuple[str, ...] = ()
    titulo_da_metodologia: str = ""
    fora: tuple[ForaDoRelatorio, ...] = ()
    alertas: tuple[Alerta, ...] = ()
    avisos: tuple[str, ...] = ()
    # Sem `type: ignore`: o campo tem default e o default é `None`, então o tipo
    # é `datetime | None`. Declarar `datetime` e atribuir `None` era pedir ao
    # verificador para não olhar exatamente a linha em que ele estava certo.
    quando: datetime | None = None
    rodadas: tuple[Rodada, ...] = ()

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def analises(self) -> tuple[str, ...]:
        """
        As análises que entraram no documento, na ordem em que entraram.
        """
        return tuple(rodada.analise for rodada in self.rodadas)

    @property
    def subtitulo(self) -> str:
        """
        `00742 - José Antônio de Sá`, embaixo do título.

        Monta com o mesmo separador do `nomes.py`, e não com o nome da pasta,
        por dois motivos. O nome da pasta passou pela `sanitizar` — perdeu a
        barra, o dois-pontos, o que o Windows não aceita — e o documento não tem
        essa limitação; e a matrícula e o nome são campos da ficha, que é onde
        eles são a informação, enquanto na pasta são um caminho.

        Cliente sem nome (o cadastro incompleto que o `listar` marca em amarelo)
        sai só com a matrícula, em vez de sair com um separador solto no fim.
        """
        partes = [parte for parte in (self.ficha.matricula, self.ficha.nome) if parte]
        return SEPARADOR.join(partes)

    @property
    def tabelas(self) -> tuple[TabelaLida, ...]:
        return tuple(t for secao in self.secoes for t in secao.tabelas)

    @property
    def figuras(self) -> tuple[Figura, ...]:
        return tuple(f for secao in self.secoes for f in secao.figuras)


@dataclass(frozen=True)
class PlanoRelatorio:
    """
    Tudo o que o `relatorio` faria, decidido e ainda não escrito.

    Imutável como os planos das outras fases, e pela mesma razão: entre a
    simulação e a execução ninguém altera um caminho em trânsito. A árvore que
    aparece no terminal é lida deste objeto.
    """

    relatorio: Relatorio
    destino: Path
    arquivamentos: tuple[tuple[Path, Path], ...] = ()
    template: Path | None = None
    # A ficha passa para `pronto` depois do documento? Falso quando ela já está: um
    # arquivo que não muda não é reescrito.
    muda_o_status: bool = False

    @property
    def raiz(self) -> Path:
        return self.relatorio.raiz

    @property
    def secoes(self) -> tuple[Secao, ...]:
        return self.relatorio.secoes

    @property
    def total_tabelas(self) -> int:
        return len(self.relatorio.tabelas)

    @property
    def total_figuras(self) -> int:
        return len(self.relatorio.figuras)


@dataclass(frozen=True)
class ResultadoRelatorio:
    """
    O que a execução de fato escreveu.
    """

    caminho: Path
    arquivados: tuple[tuple[Path, Path], ...] = ()
    avisos: tuple[str, ...] = ()
    status_trocado: bool = False  # a ficha passou para `pronto` nesta execução


# Casos de uso


def preparar_relatorio(
    raiz: Path,
    template: Path | str | None = None,
    conferir: bool = True,
    agora: datetime | None = None,
    titulo: str = TITULO_PADRAO,
) -> PlanoRelatorio:
    """
    Lê as rodadas de análise da pasta e monta o documento inteiro. Não escreve nada.

    Args:
        raiz: a pasta do projeto (a que tem o `projeto.yaml`).
        template: um `.docx` para herdar estilos, cabeçalho e rodapé. Sem isso, o
            `template.docx` do `FLATCAP_ROOT`, e sem ele os estilos padrão.
        conferir: reler o `sha256` do banco e comparar com a ficha. É a única
            leitura cara deste comando, e `--rapido` a desliga.
        agora: relógio injetável — sem ele os testes não teriam como comparar o
            nome do arquivo, que carrega a data.

    Raises:
        FichaError: a ficha do projeto não abre.
        AnaliseAusenteError: não há rodada nenhuma para relatar.
        ManifestoInvalidoError: o `manifesto.json` não abre ou é de formato novo.
        DicionarioInvalidoError: o `dicionario.csv` que está lá não é interpretável.
        TabelaIlegivelError: um `.csv` da rodada não abre.
        ModeloAusenteError: o `--template` indicado não existe.
    """
    raiz = Path(raiz)
    quando = agora or datetime.now()

    ficha = ler_ficha(raiz)
    rodadas, ausentes, sem_rodada = _rodadas(raiz, ficha)

    alertas: list[Alerta] = []
    avisos: list[str] = []

    if ausentes:
        quais = ", ".join(f"`{nome}`" for nome in ausentes[:6])
        resto = f" e mais {len(ausentes) - 6}" if len(ausentes) > 6 else ""
        alertas.append(
            Alerta(
                codigo="artefato_ausente",
                titulo=f"{len(ausentes)} arquivo(s) das análises não estão na pasta",
                detalhe=(
                    f"O manifesto da rodada lista {quais}{resto}, e o arquivo não "
                    f"está em {PASTA_ANALISES}/. O documento saiu sem essa tabela ou "
                    "figura. Rode a análise de novo para refazer a rodada inteira."
                ),
            )
        )

    alertas += _conferir_banco(raiz, ficha, rodadas, conferir)
    alerta_dicionario, aviso_dicionario = _conferir_dicionario(raiz, rodadas)
    if alerta_dicionario is not None:
        alertas.append(alerta_dicionario)
    if aviso_dicionario:
        avisos.append(aviso_dicionario)

    # Análise combinada na reunião e ainda não rodada. Aviso de terminal, e não
    # `Alerta`: quem precisa saber é você, agora, antes de enviar — e o que está
    # escrito no documento continua verdadeiro sem ela. Pôr isto dentro do
    # `.docx` seria contar ao cliente uma combinação que é sua com ele.
    if sem_rodada:
        avisos.append(
            f"A lista `analises:` do {ARQUIVO_PROJETO} pede "
            f"{_analises_em_texto(sem_rodada)}, e não há rodada dessa(s) análise(s) "
            f"em {PASTA_ANALISES}/. O documento saiu sem essa(s) seção(ões) — rode a "
            "análise antes de gerar o relatório, ou tire o nome da lista."
        )

    # Por último de propósito: os quatro alertas acima falam da validade dos
    # números, e este fala do acabamento do documento. Um alerta de dado errado
    # não deve ficar abaixo de um alerta de texto por preencher.
    alerta_texto = conferir_texto(ficha)
    if alerta_texto is not None:
        alertas.append(alerta_texto)

    # A metodologia sai das rodadas, e não da ficha: o que ela afirma é o que os
    # manifestos registraram. Análise com rodada e sem frase é aviso de terminal —
    # o parágrafo sai sem ela, e quem precisa saber disso antes de enviar é você.
    metodologia = montar_metodologia(rodada.manifesto for rodada in rodadas)
    if metodologia.sem_frase:
        avisos.append(
            f"O parágrafo de metodologia da primeira página saiu sem "
            f"{_analises_em_texto(metodologia.sem_frase)}: o manifesto da rodada não "
            "diz quais testes rodaram. Rode a análise de novo com esta versão, ou "
            "complete o parágrafo no documento antes de enviar."
        )

    relatorio = Relatorio(
        ficha=ficha,
        manifesto=_manifesto_principal(rodadas),
        rodadas=rodadas,
        titulo=titulo,
        secoes=tuple(secao for rodada in rodadas for secao in rodada.secoes),
        # O texto entra no `Relatorio` como dado, e o `documento.py` não lê
        # constante nenhuma. É o que mantém a divisão da fase — e é o que fez
        # esta mudança caber em uma linha: o dia previsto na Fase 6, em que a
        # primeira página passaria a vir do `projeto.yaml`, é este. A
        # metodologia entra do mesmo jeito, como dado, em dois campos dela.
        texto=montar_abertura(ficha),
        metodologia=metodologia.paragrafos,
        titulo_da_metodologia=metodologia.titulo,
        fora=_variaveis_de_fora(rodadas),
        alertas=tuple(alertas),
        avisos=tuple(avisos),
        quando=quando,
    )

    return PlanoRelatorio(
        relatorio=relatorio,
        destino=raiz / nome_do_relatorio(ficha.matricula, quando.date()),
        arquivamentos=_arquivamentos(raiz),
        template=localizar_template(raiz, template),
        muda_o_status=status_reconhecido(ficha.status) != STATUS_PRONTO,
    )


def executar_relatorio(plano: PlanoRelatorio) -> ResultadoRelatorio:
    """
    Escreve o documento no disco. Não decide mais nada.

    A ordem é a das outras fases: arquiva o relatório anterior **antes** de
    escrever o novo, porque os dois têm o mesmo nome quando a rodada é do mesmo
    dia — e escrever primeiro seria escrever por cima do que se queria guardar.

    Uma falha no meio desfaz o que já foi feito, inclusive devolvendo o relatório
    arquivado ao lugar. Sem isso, a versão anterior teria sumido em troca de nada.
    É o mesmo cuidado do `executar_adicao` da Fase 3 e do `executar_descritiva`
    da Fase 5.

    Depois do documento, e antes do histórico, a ficha passa para `pronto` — e a
    linha do histórico diz isso só quando a troca aconteceu. O que se desfaz inclui a
    ficha: ela volta ao texto que tinha, letra por letra.

    O `documento.py` entra aqui dentro, e não no topo do arquivo, pelo mesmo
    motivo que o `matplotlib` entra dentro do `executar_descritiva`: a simulação
    não desenha documento nenhum e não deve pagar pelo `python-docx`.
    """
    from .documento import escrever

    arquivados: list[tuple[Path, Path]] = []
    avisos: list[str] = []
    desfazer: list[Any] = []
    status_trocado = False

    try:
        for de, para in plano.arquivamentos:
            para.parent.mkdir(parents=True, exist_ok=True)
            de.rename(para)
            arquivados.append((de, para))
            desfazer.append(lambda d=de, p=para: p.rename(d))

        escrever(plano.relatorio, plano.destino, plano.template)
        desfazer.append(lambda p=plano.destino: p.unlink(missing_ok=True))

        if plano.muda_o_status:
            status_trocado = _marcar_pronto(plano.raiz, avisos, desfazer)

        try:
            anotar(
                plano.raiz,
                _acao_do_historico(plano, status_trocado),
                plano.relatorio.quando,
            )
        except OSError as erro:
            avisos.append(
                f"O relatório foi escrito, mas não consegui escrever no "
                f"historico.md: {erro}"
            )

    # `Exception`, como no `executar_*` de cada análise, e não só `OSError` e
    # `RelatorioError`: até a 1.13.0 um `.png` ilegível estourava o `python-docx`
    # com uma exceção que não é nenhuma das duas, e o relatório anterior ficava em
    # `2. Versões antigas/` sem o novo no lugar dele. O erro sobe do mesmo jeito.
    except Exception:
        for passo in reversed(desfazer):
            try:
                passo()
            except OSError:
                avisos.append(
                    "Falhei ao desfazer uma etapa. Confira a pasta do projeto e "
                    f"{PASTA_ANTIGAS} antes de rodar de novo."
                )
        raise

    return ResultadoRelatorio(
        caminho=plano.destino,
        arquivados=tuple(arquivados),
        avisos=tuple(avisos),
        status_trocado=status_trocado,
    )


def _marcar_pronto(raiz: Path, avisos: list[str], desfazer: list[Any]) -> bool:
    """
    Passa a ficha para `pronto`, depois de o documento estar no disco. Devolve se
    passou.

    O documento é o produto e o status é o recibo dele: um `projeto.yaml` que não se
    deixa escrever — aberto noutro programa, a ficha que deixou de abrir entre a
    simulação e a execução — vira aviso, com o que escrever à mão, e o relatório fica.
    É a regra do somente-leitura do `flatcap novo`: perder a marca é aceitável,
    perder o produto por causa dela não.
    """
    caminho = caminho_da_ficha(raiz)
    try:
        # `newline=""` para o desfazer devolver o arquivo como estava, até o `\r\n` de
        # uma ficha editada no Windows.
        with caminho.open(encoding="utf-8", newline="") as arquivo:
            antes = arquivo.read()
        definir_status(raiz, STATUS_PRONTO)
    except (FichaError, OSError, UnicodeDecodeError) as erro:
        avisos.append(
            f"O relatório foi escrito, mas não consegui passar o projeto para "
            f"`{STATUS_PRONTO}` no {ARQUIVO_PROJETO}: {erro}\n"
            f"Escreva `status: {STATUS_PRONTO}` à mão."
        )
        return False
    desfazer.append(lambda: escrever_atomico(caminho, antes))
    return True


# Nome e lugar do arquivo


def nome_do_relatorio(matricula: str, quando: date) -> str:
    """
    Monta `Relatorio_00742_2026-09-20.docx`, como o roteiro pede.

    A matrícula vem da ficha e passa pela mesma limpeza dos nomes de pasta: ela
    é digitada por outra pessoa, em outro sistema, e o que vem de fora não monta
    caminho.
    """
    limpa = sanitizar(str(matricula)) or "sem_matricula"
    limpa = Path(limpa).name
    return f"{PREFIXO_RELATORIO}{limpa}_{quando:%Y-%m-%d}.docx"


def relatorios_na_pasta(raiz: Path) -> tuple[Path, ...]:
    """
    Os relatórios que já estão na raiz do projeto, em ordem.

    O `.docx` mora na raiz da pasta do projeto, e não em uma `4. Relatórios/`. É
    um desvio deliberado do apêndice A do roteiro, já registrado no `projeto.py`:
    o relatório é o produto que se entrega, e ele fica onde a mão alcança
    primeiro ao abrir a pasta.
    """
    raiz = Path(raiz)
    if not raiz.is_dir():
        return ()
    return tuple(
        sorted(
            arquivo
            for arquivo in raiz.iterdir()
            if arquivo.is_file()
            and arquivo.name.startswith(PREFIXO_RELATORIO)
            and arquivo.suffix.lower() == ".docx"
            and not arquivo.name.startswith("~$")  # o lixo que o Word deixa aberto
        )
    )


def _arquivamentos(raiz: Path) -> tuple[tuple[Path, Path], ...]:
    """
    O que sai da raiz e vai para `2. Versões antigas/`.

    **Todos** os relatórios anteriores, não só o de hoje. A raiz do projeto fica
    com um relatório só — o vigente —, que é a mesma regra que `1. Dados
    originais/` segue para o banco. Uma pasta com três `.docx` de datas
    diferentes é uma pasta em que alguém vai anexar o errado no e-mail.

    Duas rodadas no mesmo dia colidiriam no destino, porque o nome carrega a data
    e não a hora. O desempate é o sufixo numérico da Fase 5.

    Não recebe o destino, e é por isso que ele não aparece aqui: o relatório que
    está para ser escrito ou ainda não existe no disco, ou tem o nome de um dos
    anteriores — e aí já está na lista, achado pela varredura. A linha
    `_ = destino` que morava no fim desta função dizia isso e não fazia nada;
    dizer está na docstring, que é onde se diz.
    """
    pares: list[tuple[Path, Path]] = []
    ocupados: set[Path] = set()

    for anterior in relatorios_na_pasta(raiz):
        alvo = raiz / PASTA_ANTIGAS / anterior.name
        sufixo = 2
        while alvo.exists() or alvo in ocupados:
            alvo = alvo.with_name(f"{anterior.stem}_{sufixo}{anterior.suffix}")
            sufixo += 1
        ocupados.add(alvo)
        pares.append((anterior, alvo))

    return tuple(pares)


def localizar_template(raiz: Path, template: Path | str | None) -> Path | None:
    """
    Qual `.docx` empresta os estilos, e nesta ordem.

    1. o `--template` que você passou;
    2. o `template.docx` da **pasta do projeto**, para o trabalho que exige um
       modelo próprio;
    3. o `template.docx` da **pasta do cliente**, que vale para todos os
       projetos dele — o degrau novo da 1.1.0;
    4. o `template.docx` do `FLATCAP_ROOT`, que é onde o modelo institucional
       mora — fora do repositório, como todo o resto que não é código;
    5. nenhum: o documento sai com os estilos padrão do `documento.py`.

    **Esta função tinha um degrau a menos e teria quebrado em silêncio.** Até a
    1.0.0 `raiz.parent` era o `FLATCAP_ROOT`; com a pasta do projeto um nível
    abaixo, `raiz.parent` passou a ser a pasta do cliente, e o modelo
    institucional deixaria de ser encontrado — sem erro, sem aviso, só com todo
    relatório saindo de repente sem o logotipo. O degrau que se ganha no meio é
    a parte boa do acidente: um cliente com identidade visual própria agora tem
    onde guardar o modelo dele.

    O modelo mora fora do repositório de propósito. Ele carrega logotipo e
    identidade visual da instituição, muda sem pedir licença a ninguém, e é
    binário — três razões pelas quais ele não é código.

    Pública desde a 1.15.0, com o apelido privado de antes: o relatório da amostra
    procura o modelo pelos mesmos degraus, e dois caminhos de busca é como um dos
    dois relatórios sai sem o logotipo.
    """
    if template is not None:
        caminho = Path(template).expanduser()
        if not caminho.is_file():
            raise ModeloAusenteError(
                f"O modelo indicado em `--template` não existe:\n  {caminho}\n"
                "Confira o caminho. Se ele tiver espaço no nome, ponha entre aspas."
            )
        return caminho

    raiz = Path(raiz)
    candidatos = [raiz / ARQUIVO_TEMPLATE, raiz.parent / ARQUIVO_TEMPLATE]
    # O terceiro degrau só existe quando há um terceiro nível acima: numa raiz
    # de teste montada direto em `tmp_path`, `parent.parent` sairia da árvore.
    if raiz.parent.parent != raiz.parent:
        candidatos.append(raiz.parent.parent / ARQUIVO_TEMPLATE)

    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    return None


_localizar_template = localizar_template


# A rodada


def _rodadas(
    raiz: Path, ficha: Ficha
) -> tuple[tuple[Rodada, ...], list[str], list[str]]:
    """
    As rodadas de `3. Análises/`, na ordem do documento.

    Devolve as rodadas, os artefatos que os manifestos prometem e não estão no
    disco, e os nomes que a ficha pede e que não têm rodada nenhuma.

    **Varre, e não procura nome fixo.** É a diferença que faz a normalidade
    entrar no documento sem uma linha deste módulo saber que ela existe — e é o
    que a próxima análise vai encontrar pronto. Pasta sem `manifesto.json`
    dentro é ignorada em silêncio: `3. Análises/` é uma pasta do usuário, e uma
    subpasta de rascunho dele não é uma rodada mal formada.

    Raises:
        AnaliseAusenteError: não há rodada nenhuma.
        ManifestoInvalidoError: uma rodada tem manifesto e ele não abre.
    """
    achadas: list[Rodada] = []
    ausentes: list[str] = []

    for pasta in pastas_das_analises(raiz):
        if not (pasta / ARQUIVO_MANIFESTO).is_file():
            continue
        manifesto = ler_manifesto(pasta)
        secoes, faltando = _secoes(pasta, manifesto)
        ausentes += [f"{pasta.name}/{nome}" for nome in faltando]
        achadas.append(
            Rodada(
                analise=manifesto.analise or pasta.name,
                pasta=pasta,
                manifesto=manifesto,
                secoes=secoes,
            )
        )

    if not achadas:
        raise AnaliseAusenteError(_mensagem_sem_rodada(raiz))

    rodadas = _ordenar(achadas, ficha.analises)
    rodadas_no_disco = {rodada.analise for rodada in rodadas}
    sem_rodada = [
        nome for nome in ficha.analises if nome not in rodadas_no_disco
    ]
    return rodadas, ausentes, sem_rodada


def _ordenar(
    rodadas: list[Rodada], analises_da_ficha: tuple[str, ...]
) -> tuple[Rodada, ...]:
    """
    A ordem das seções do documento: a ficha primeiro, o padrão depois.

    É o que a lista `analises:` sempre prometeu e nunca dirigiu. O cabeçalho da
    ficha diz literalmente *«o que foi combinado na reunião»*, e o que foi
    combinado tem uma ordem — a descritiva antes dos pressupostos em um
    relatório, o contrário em outro, conforme o que o cliente vai ler primeiro.
    Sem isto a ordem era a do `sorted` do sistema de arquivos, que é alfabética
    por acidente.

    Três degraus, e o terceiro é o que torna a saída determinística: a posição
    na lista da ficha, a posição na `ORDEM_PADRAO_DAS_ANALISES`, e o nome. Nome
    escrito na ficha e sem rodada no disco não entra aqui — ele vira aviso, em
    `_rodadas`.
    """
    na_ficha = {nome: posicao for posicao, nome in enumerate(analises_da_ficha)}
    no_padrao = {
        nome: posicao for posicao, nome in enumerate(ORDEM_PADRAO_DAS_ANALISES)
    }
    return tuple(
        sorted(
            rodadas,
            key=lambda rodada: (
                na_ficha.get(rodada.analise, len(na_ficha)),
                no_padrao.get(rodada.analise, len(no_padrao)),
                rodada.analise,
            ),
        )
    )


def _manifesto_principal(rodadas: tuple[Rodada, ...]) -> Manifesto:
    """
    O manifesto que responde pelo documento quando a pergunta é uma só.

    As propriedades do `.docx` e o cabeçalho do terminal precisam de **um** banco
    e de **uma** data de rodada, e com mais de uma análise na pasta isso deixou
    de ser automático. A escolha é a descritiva: é ela que descreve o banco
    inteiro, e é a data dela que responde «de quando são estes números?» para
    quem abre o arquivo no Windows sem abri-lo no Word. Sem descritiva, a
    primeira rodada da ordem — que é a que o documento apresenta primeiro.
    """
    for rodada in rodadas:
        if rodada.analise == ANALISE_DESCRITIVA:
            return rodada.manifesto
    return rodadas[0].manifesto


def _variaveis_de_fora(rodadas: tuple[Rodada, ...]) -> tuple[ForaDoRelatorio, ...]:
    """
    As variáveis do dicionário que **nenhuma** rodada descreveu.

    A conta é entre rodadas, e precisa ser: a lista `fora` da normalidade tem
    toda categórica do banco — «a normalidade só se pergunta de numérica» —, e
    imprimir isso no terminal diria que `sexo` ficou fora do relatório logo
    acima da seção `Sexo` do próprio relatório. Fora do documento é quem não
    aparece em rodada nenhuma.
    """
    usadas = {
        coluna for rodada in rodadas for coluna in rodada.manifesto.colunas_usadas
    }
    vistas: dict[str, ForaDoRelatorio] = {}
    for rodada in rodadas:
        for entrada in rodada.manifesto.fora:
            nome = str(entrada.get("variavel", ""))
            if not nome or nome in usadas or nome in vistas:
                continue
            vistas[nome] = ForaDoRelatorio(
                variavel=nome,
                tipo=str(entrada.get("tipo", "")),
                motivo=str(entrada.get("motivo", "")),
            )
    return tuple(vistas.values())


def _mensagem_sem_rodada(raiz: Path) -> str:
    return (
        "Este projeto não tem nenhuma rodada de análise para relatar.\n"
        f"Esperado em: {Path(raiz) / PASTA_ANALISES}/<análise>/{ARQUIVO_MANIFESTO}\n\n"
        "O relatório monta os arquivos que as análises escreveram — ele não abre "
        "o banco e não recalcula nada, que é o que garante que o documento e as "
        "tabelas digam o mesmo número.\n"
        "Rode `flatcap descritiva <id> --sim` antes."
    )


def _analises_em_texto(analises: Sequence[str]) -> str:
    """
    `["descritiva", "normalidade"]` → «`descritiva` e `normalidade`».

    Sem artigo antes do nome de propósito: `a descritiva` e `a normalidade`
    funcionam, e `a teste t` não. O nome da análise vem do manifesto, e o
    manifesto é escrito por quem escreveu a análise.
    """
    nomes = [f"`{nome}`" for nome in analises]
    if len(nomes) <= 1:
        return nomes[0] if nomes else ""
    return ", ".join(nomes[:-1]) + f" e {nomes[-1]}"


def _secoes(pasta: Path, manifesto: Manifesto) -> tuple[tuple[Secao, ...], list[str]]:
    """
    Uma seção por variável do manifesto, na ordem dele.

    Artefato que sumiu da pasta não interrompe nada: ele é anotado e o documento
    sai sem aquela tabela ou figura, com o alerta dizendo qual. O contrário —
    recusar por causa de um `.png` apagado — seria transformar um acidente
    reversível em um comando que não roda.
    """
    secoes: list[Secao] = []
    ausentes: list[str] = []

    for item in manifesto.itens:
        tabelas: list[TabelaLida] = []
        figuras: list[Figura] = []

        for artefato in item.artefatos:
            caminho = pasta / artefato.arquivo
            if not caminho.is_file():
                ausentes.append(artefato.arquivo)
                continue
            if artefato.e_tabela:
                tabelas.append(ler_tabela(caminho, artefato.especie, artefato.titulo))
            elif artefato.e_figura:
                figuras.append(
                    Figura(
                        arquivo=artefato.arquivo,
                        caminho=caminho,
                        especie=artefato.especie,
                        titulo=artefato.titulo or item.rotulo or item.variavel,
                    )
                )

        secoes.append(
            Secao(
                variavel=item.variavel,
                rotulo=item.rotulo or item.variavel,
                tipo=item.tipo,
                n=item.n,
                faltantes=item.faltantes,
                tabelas=tuple(tabelas),
                figuras=tuple(figuras),
            )
        )

    return tuple(secoes), ausentes


def ler_tabela(caminho: Path, especie: str = "", titulo: str = "") -> TabelaLida:
    """
    Lê um `.csv` de uma análise sem o `pandas` e sem converter valor nenhum.

    O formato é o que a Fase 5 escreveu primeiro, e o `manifesto.Tabela` de toda
    análise escreve desde a Fase 7: BOM, algumas linhas de comentário com o
    título e os denominadores, e a tabela separada por `;`. As linhas de
    comentário viram `notas` — elas carregam os dois denominadores da tabela de
    frequência, que é a resposta do roteiro para "quando o cliente lê 45%, ele
    precisa saber se o denominador incluiu os casos sem resposta".

    Sem `pandas` de propósito. Não é economia de dependência — o `pandas` está
    instalado —, é economia de conversão: `pd.read_csv` leria `28,7` como texto
    ou como número dependendo do `decimal=`, e das duas uma sairia diferente do
    que está no arquivo. Aqui o texto atravessa intacto.
    """
    caminho = Path(caminho)
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            texto = caminho.read_text(encoding="cp1252")
        except (OSError, UnicodeDecodeError) as erro:
            raise TabelaIlegivelError(_mensagem_ilegivel(caminho, erro)) from erro
    except OSError as erro:
        raise TabelaIlegivelError(_mensagem_ilegivel(caminho, erro)) from erro

    return tabela_do_texto(texto, especie, titulo, caminho)


def tabela_do_texto(
    texto: str, especie: str = "", titulo: str = "", caminho: Path | str = "tabela.csv"
) -> TabelaLida:
    """
    O miolo do `ler_tabela`: o texto de um `.csv` de análise, já lido, virando tabela.

    Separado desde a 1.15.0, para a amostragem: ela monta o relatório da amostra a
    partir do texto do `tamanho.csv` **antes** de ele ir ao disco — o `preparar` decide
    o documento inteiro, e o `executar` só escreve. É o mesmo texto que vai para o
    arquivo, lido pela mesma função que o lê do disco, e por isso o documento e a
    tabela não têm como dizer números diferentes.

    O `caminho` só dá o nome ao arquivo e às mensagens; nada é lido dele. O BOM que o
    `manifesto.Tabela.texto` escreve é tirado aqui, como o `utf-8-sig` o tira na leitura.
    """
    caminho = Path(caminho)
    texto = texto.removeprefix("\ufeff")

    # Os comentários são só os do começo, como no `dicionario.csv`: depois do
    # cabeçalho das colunas, uma linha começada por `#` é uma categoria — o `#N/D`
    # que o Excel deixa numa célula com erro de fórmula. Até a 1.13.0 ela saía da
    # tabela do documento e virava nota, e o `Total` deixava de somar.
    todas = texto.splitlines()
    puladas = linhas_de_comentario(todas)
    comentarios = [
        linha.lstrip().lstrip("#").strip() for linha in todas[:puladas] if linha.strip()
    ]
    corpo = [linha for linha in todas[puladas:] if linha.strip()]

    if not corpo:
        raise TabelaIlegivelError(
            f"O arquivo `{caminho.name}`, da pasta `{caminho.parent.name}`, não tem "
            "nenhuma linha de dados — só o cabeçalho de comentário.\n"
            f"Rode `flatcap {caminho.parent.name} <id> --sim` para refazer a rodada."
        )

    leitor = csv.reader(io.StringIO("\n".join(corpo)), delimiter=_SEPARADOR_CAMPO)
    linhas = [tuple(campo.strip() for campo in registro) for registro in leitor]
    colunas, dados = linhas[0], linhas[1:]

    # O primeiro comentário é o título do arquivo; o título do manifesto é o
    # mesmo texto e tem precedência, para que o documento e o índice não possam
    # divergir. O resto vira nota, menos a linha `variável:`.
    notas = [
        nota
        for nota in comentarios[1:]
        if nota and not _NOTA_REDUNDANTE.match(nota)
    ]

    return TabelaLida(
        arquivo=caminho.name,
        especie=especie,
        titulo=titulo or (comentarios[0] if comentarios else caminho.stem),
        notas=tuple(notas),
        colunas=colunas,
        linhas=tuple(dados),
    )


# A primeira página


ROTULO_FINALIDADE = "Finalidade do estudo: "

# O que ocupa o lugar de um campo que veio em branco.
#
# Não é `[NULL]`, e a escolha tem três razões, em ordem de importância. O risco
# real não é o marcador ser feio: é ele **escapar** para a entrega, e aí ele
# precisa ser legível para quem abrir o documento sem nunca ter ouvido falar do
# FlatCap. `[NULL]` é vocabulário de banco de dados. E as aspas angulares fazem
# o que o colchete não faz: é impossível confundir isto com o texto do cliente.
#
# O marcador nunca vem sozinho — o `Alerta` de código `texto_ausente` sobe junto,
# e é ele a caixa amarela no alto da página. O marcador é para o seu olho na
# releitura; o alerta é o que sobrevive ao arquivo ser anexado a um e-mail.
_MARCADOR = "«a preencher: {}»"

_FINALIDADE_AUSENTE = _MARCADOR.format("a finalidade do estudo")
_OBJETIVOS_AUSENTES = _MARCADOR.format("o objetivo geral e os objetivos específicos")


def montar_abertura(
    ficha: Ficha, texto_padrao: tuple[str, ...] = TEXTO_PADRAO
) -> tuple[str, ...]:
    """
    Os parágrafos da primeira página: o texto fixo, a finalidade, os objetivos.

    A ordem é a da leitura. O parágrafo institucional enquadra, a finalidade diz
    para que o estudo serve, e os objetivos dizem o que se quer saber — do geral
    para o particular, que é como um cliente lê a própria primeira página.

    Campo em branco não some: vira marcador. Uma seção que simplesmente encolhe é
    uma falta em que ninguém repara, e é o mesmo argumento que a Fase 4 usou para
    imprimir a codificação no `perfil.md` — a única forma de descobrir que a
    escolha foi errada é vê-la escrita.

    Recebe a `Ficha`, e não a `Config`: montar a primeira página é ler YAML, não
    é falar com o REDCap. O teste em subprocesso que afirma que este módulo não
    carrega `pandas` nem `matplotlib` continua valendo, e o `texto_padrao`
    injetável existe para o teste poder afirmar a composição sem depender do que
    estiver escrito na constante hoje.
    """
    partes: list[str] = list(texto_padrao)

    if ficha.finalidade:
        partes.append(f"{ROTULO_FINALIDADE}{ficha.finalidade.rstrip(' .')}.")
    else:
        partes.append(f"{ROTULO_FINALIDADE}{_FINALIDADE_AUSENTE}")

    partes.extend(_paragrafos(ficha.objetivos) or (_OBJETIVOS_AUSENTES,))
    return tuple(partes)


def _paragrafos(texto: str) -> tuple[str, ...]:
    """
    Cada quebra de linha do campo `notes` vira um parágrafo do documento.

    Quebra de linha ali é intenção: numa caixa de texto do REDCap a linha quebra
    sozinha ao chegar na borda, e só existe um `\\n` onde a pessoa apertou Enter.
    Linha em branco entre dois parágrafos é descartada — parágrafo vazio no Word
    é um espaço que ninguém pediu e que reaparece na revisão como "sobrou uma
    linha aqui".
    """
    return tuple(parte.strip() for parte in re.split(r"\r?\n", texto or "") if parte.strip())


# As conferências


def conferir_texto(ficha: Ficha) -> Alerta | None:
    """
    Quais campos da primeira página vieram em branco.

    É a quinta conferência da fase, e a única que não fala de dados: as outras
    quatro perguntam se a rodada ainda descreve a pasta, esta pergunta se o
    documento está pronto para ser enviado. Ela não recusa nada, pelo mesmo
    motivo das outras — o documento sai, com o aviso dentro dele.

    Pública desde a 1.15.0, com o apelido privado de antes: o relatório da amostra
    abre com a mesma primeira página, e o campo em branco precisa do mesmo aviso lá.
    """
    faltando = [
        nome
        for nome, valor in (
            ("finalidade", ficha.finalidade),
            ("objetivos", ficha.objetivos),
        )
        if not valor
    ]
    if not faltando:
        return None

    quais = " e ".join(f"`{nome}`" for nome in faltando)
    return Alerta(
        codigo="texto_ausente",
        titulo="a primeira página está com campo por preencher",
        detalhe=(
            f"{quais} da ficha deste projeto está em branco, e o documento saiu com "
            "um marcador visível no lugar do texto.\n"
            "Esse texto vem do formulário do REDCap (`fin` e `obj1`) na hora em que "
            "a pasta é criada. Projeto criado antes disso, ou campo que o cliente "
            f"deixou em branco, se resolve escrevendo direto no `{ARQUIVO_PROJETO}` "
            "— o arquivo é seu, e o FlatCap não sobrescreve o que você escreveu."
        ),
    )


_conferir_texto = conferir_texto


def _conferir_banco(
    raiz: Path, ficha: Ficha, rodadas: tuple[Rodada, ...], conferir: bool
) -> list[Alerta]:
    """
    As rodadas ainda descrevem a versão vigente do banco?

    Duas perguntas diferentes, e vale separá-las porque o que fazer é diferente:

    * **outra versão** — o cliente mandou o banco revisado e a descritiva não foi
      refeita. O documento fala de uma versão que não é mais a de trabalho.
    * **arquivo alterado** — o mesmo arquivo foi aberto e salvo por cima depois
      de registrado. Aí nem a ficha descreve mais o que está no disco.

    A comparação é de `sha256`, e o da rodada está no próprio manifesto. Não há
    releitura do banco aqui: o `sha256` da versão vigente vem da ficha, e a
    conferência contra o disco é a mesma `linha_do_tempo` da Fase 3 — porque duas
    implementações da mesma conferência é como um comando diz "confere" enquanto
    o outro diz "ALTERADO" sobre o mesmo arquivo.

    Com mais de uma rodada na pasta, a conta é por **banco usado**, e não por
    rodada: duas análises da mesma versão são um alerta só, e duas análises de
    versões diferentes são dois — que é a informação que interessa, porque aí o
    documento está misturando números de dois bancos e as análises que ele nomeia
    são as que precisam ser refeitas.
    """
    alertas: list[Alerta] = []

    vigente: Versao | None = versao_vigente(ficha)
    if vigente is None:
        return alertas

    usados: dict[tuple[str, str], list[str]] = {}
    for rodada in rodadas:
        arquivo = str(rodada.manifesto.banco.get("arquivo") or "?")
        sha = str(rodada.manifesto.banco.get("sha256") or "").lower()
        usados.setdefault((arquivo, sha), []).append(rodada.analise)

    for (arquivo, sha), analises in usados.items():
        if not sha or not vigente.sha256 or sha == vigente.sha256.lower():
            continue
        uma = len(analises) == 1
        alertas.append(
            Alerta(
                codigo="banco_mudou",
                titulo=(
                    f"a rodada de {_analises_em_texto(analises)} foi feita "
                    "sobre outra versão do banco"
                    if uma
                    else f"as rodadas de {_analises_em_texto(analises)} foram "
                    "feitas sobre outra versão do banco"
                ),
                detalhe=(
                    f"Os números de {_analises_em_texto(analises)} saíram de "
                    f"`{arquivo}`, e a versão vigente do projeto hoje é "
                    f"`{vigente.arquivo}`. Para que o documento fale da versão "
                    f"atual, rode {_analises_em_texto(analises)} de novo e gere o "
                    "relatório em seguida."
                ),
            )
        )

    if not conferir:
        return alertas

    try:
        tempo = linha_do_tempo(raiz, conferir=True)
    except OSError:  # pragma: no cover - o disco já foi lido várias vezes até aqui
        return alertas

    arquivos = {arquivo for arquivo, _ in usados}
    for item in tempo.itens:
        arquivo_da_rodada = item.versao.arquivo
        if arquivo_da_rodada not in arquivos:
            continue
        if item.caminho is None:
            alertas.append(
                Alerta(
                    codigo="banco_ausente",
                    titulo="o banco descrito não está mais no disco",
                    detalhe=(
                        f"`{arquivo_da_rodada}` está registrado na ficha e não está na "
                        "pasta. As tabelas continuam válidas — elas foram escritas "
                        "quando o arquivo existia —, mas não há como conferi-las "
                        "contra a origem."
                    ),
                )
            )
        elif item.confere is False:
            alertas.append(
                Alerta(
                    codigo="banco_alterado",
                    titulo="o arquivo do banco foi alterado depois de registrado",
                    detalhe=(
                        f"`{arquivo_da_rodada}` está no disco com conteúdo diferente do "
                        "que foi registrado na ficha. Alguém o abriu e salvou por cima. "
                        "Trate o arquivo alterado como versão nova: rode "
                        "`flatcap dados adicionar` e refaça as análises."
                    ),
                )
            )

    return alertas


def _conferir_dicionario(
    raiz: Path, rodadas: tuple[Rodada, ...]
) -> tuple[Alerta | None, str]:
    """
    O `dicionario.csv` de hoje é o que dirigiu as rodadas?

    É a divergência mais fácil de acontecer e a mais difícil de perceber: você
    corrige um rótulo ou muda uma faixa depois de rodar a descritiva, gera o
    documento, e ele sai com os títulos antigos e os cortes antigos — bonito, e
    descrevendo uma decisão que você já revogou.

    Quatro diferenças são procuradas: variável que entrou, variável que saiu,
    tipo trocado e rótulo reescrito, mais as faixas, que o manifesto guarda em
    `detalhes`. Um dicionário ilegível **não** interrompe o relatório: ele já
    cumpriu o papel dele quando a rodada foi gerada, e recusar aqui seria travar
    o documento por causa de um arquivo que o documento não usa.

    ## `colunas_usadas`, e não `item.variavel`

    É a troca que faz esta conferência sobreviver à segunda análise. O campo
    `variavel` é singular e existe análise que não é de uma variável: a tabela de
    normalidade fala de todas de uma vez e sai do manifesto com `variavel=""`.
    Comparando por ele, o item da normalidade viraria a variável de nome vazio, e
    todo relatório sairia com «`` saiu da descritiva depois da rodada» — em todo
    projeto, para sempre. `colunas_usadas` responde a pergunta que se queria
    fazer, «quais colunas do banco esta rodada tocou?», e responde igual para uma
    seção de uma variável e para uma de doze.

    ## Quem responde por «entrou no dicionário depois»

    Só a descritiva, e a assimetria é deliberada. Ela é a análise que descreve
    **todas** as variáveis analisáveis; a normalidade só olha as numéricas.
    Perguntar a pergunta a todas as rodadas faria toda categórica do dicionário
    ser dada como «entrou depois» em um projeto que só rodou a normalidade —
    um alerta dentro do documento do cliente, sobre nada.
    """
    try:
        linhas = ler_dicionario(raiz)
    except Exception as erro:  # noqa: BLE001 - ver a justificativa acima
        return None, (
            f"Não consegui ler o {ARQUIVO_DICIONARIO} para conferir se ele mudou "
            f"depois da rodada: {erro}"
        )

    if not linhas:
        return (
            Alerta(
                codigo="dicionario_ausente",
                titulo=f"o {ARQUIVO_DICIONARIO} não está mais na pasta",
                detalhe=(
                    "As tabelas deste documento obedeceram a um dicionário que não "
                    "está mais lá. Não há como conferir se elas descrevem as decisões "
                    "que valem hoje."
                ),
            ),
            "",
        )

    analisaveis = {linha.variavel: linha for linha in linhas if linha.analisavel}

    # Quais colunas do banco cada rodada tocou, e qual rodada tocou primeiro.
    usadas: dict[str, str] = {}
    for rodada in rodadas:
        for coluna in rodada.manifesto.colunas_usadas:
            usadas.setdefault(coluna, rodada.analise)

    # Os itens que **são** uma variável. O tipo, o rótulo e as faixas só existem
    # para eles: uma seção que fala de doze colunas não tem um tipo do
    # dicionário para comparar, e a de normalidade se chama «Normalidade».
    conhecidas: dict[str, ItemDoManifesto] = {}
    for rodada in rodadas:
        for item in rodada.manifesto.itens:
            if item.variavel:
                conhecidas.setdefault(item.variavel, item)

    vazias = {
        str(entrada.get("variavel", ""))
        for rodada in rodadas
        for entrada in rodada.manifesto.fora
        if "sem nenhum valor" in str(entrada.get("motivo", ""))
    }

    mudancas: list[str] = []

    base = next(
        (rodada for rodada in rodadas if rodada.analise == ANALISE_DESCRITIVA),
        None,
    )
    if base is not None:
        descritas = set(base.manifesto.colunas_usadas)
        for nome in analisaveis:
            if nome not in descritas and nome not in vazias:
                mudancas.append(f"`{nome}` entrou no dicionário depois da rodada")

    for nome, analise in usadas.items():
        if nome and nome not in analisaveis:
            mudancas.append(
                f"`{nome}` deixou de ser analisável no dicionário depois da "
                f"rodada de `{analise}`"
            )

    for nome, linha in analisaveis.items():
        item = conhecidas.get(nome)
        if item is None:
            continue
        if linha.tipo != item.tipo:
            mudancas.append(
                f"`{nome}` era `{item.tipo}` na rodada e é `{linha.tipo}` hoje"
            )
        rotulo = linha.rotulo or linha.variavel
        if rotulo != item.rotulo:
            mudancas.append(
                f"`{nome}` mudou de rótulo: «{item.rotulo}» → «{rotulo}»"
            )
        diferenca = _faixas_mudaram(linha.faixas, item.detalhes)
        if diferenca:
            mudancas.append(f"`{nome}` {diferenca}")

    if not mudancas:
        return None, ""

    return (
        Alerta(
            codigo="dicionario_mudou",
            titulo=f"o {ARQUIVO_DICIONARIO} mudou depois das rodadas",
            detalhe=(
                "As tabelas deste documento obedecem ao dicionário de quando as "
                "análises foram geradas, e ele mudou desde então:\n"
                + "\n".join(f"— {mudanca}" for mudanca in mudancas[:8])
                + (
                    f"\n— e mais {len(mudancas) - 8} diferença(s)."
                    if len(mudancas) > 8
                    else ""
                )
                + "\nRode as análises de novo e gere o relatório em seguida."
            ),
        ),
        "",
    )


def _faixas_mudaram(faixas: tuple[str, ...], detalhes: dict[str, Any]) -> str:
    """
    Compara os cortes do dicionário com os que a rodada usou.

    O manifesto guarda `origem` (`dicionario` ou `quartis`) e os `cortes` já
    arredondados. As três formas de divergir são: faixas preenchidas depois de a
    rodada ter usado quartis, faixas apagadas, e cortes diferentes.
    """
    registradas = detalhes.get("faixas")
    if not isinstance(registradas, dict):
        return ""

    origem = registradas.get("origem")
    cortes = registradas.get("cortes") or []

    if faixas and origem != "dicionario":
        return "ganhou faixas no dicionário depois da rodada, que usou os quartis"
    if not faixas and origem == "dicionario":
        return "perdeu as faixas do dicionário; a rodada usou os cortes que estavam lá"
    if not faixas:
        return ""

    try:
        pedidos = [float(str(corte).replace(",", ".")) for corte in faixas]
    except ValueError:  # pragma: no cover - o dicionario.py já validou na leitura
        return ""

    usados = [float(corte) for corte in cortes if corte is not None]
    if len(pedidos) != len(usados) or any(
        abs(a - b) > 1e-9 for a, b in zip(pedidos, usados, strict=True)
    ):
        return "está com outros cortes de faixa do que os usados na rodada"
    return ""


# Mensagens


def _mensagem_ilegivel(caminho: Path, erro: Exception) -> str:
    return (
        f"Não consegui ler `{caminho.name}`, que a análise da pasta "
        f"`{caminho.parent.name}` escreveu.\n"
        "Os arquivos da rodada não são feitos para ser editados à mão — se você "
        f"precisou mexer em um, rode `flatcap {caminho.parent.name} <id> --sim` "
        "de novo.\n\n"
        f"Detalhe técnico: {type(erro).__name__}: {erro}"
    )


def _acao_do_historico(plano: PlanoRelatorio, status_trocado: bool = False) -> str:
    relatorio = plano.relatorio
    partes = [
        f"`flatcap relatorio {relatorio.ficha.record_id}` — `{plano.destino.name}` "
        f"escrito a partir de {_analises_em_texto(relatorio.analises)}, rodada(s) "
        f"até {relatorio.manifesto.gerado_em:%d/%m/%Y %H:%M}: "
        f"{len(relatorio.secoes)} seção(ões), {plano.total_tabelas} tabela(s) e "
        f"{plano.total_figuras} figura(s)."
    ]
    for _, para in plano.arquivamentos:
        partes.append(f"`{para.name}` foi para `{PASTA_ANTIGAS}/`.")
    if plano.template is not None:
        partes.append(f"Modelo: `{plano.template.name}`.")
    if relatorio.alertas:
        quais = ", ".join(alerta.codigo for alerta in relatorio.alertas)
        partes.append(f"Com aviso no documento: {quais}.")
    if status_trocado:
        anterior = relatorio.ficha.status
        de = f"de `{anterior}` " if anterior else ""
        partes.append(f"Status {de}para `{STATUS_PRONTO}`.")
    return " ".join(partes)


__all__ = [
    "Alerta",
    "AnaliseAusenteError",
    "Figura",
    "PlanoRelatorio",
    "Relatorio",
    "RelatorioError",
    "Rodada",
    "DescritivaAusenteError",
    "ModeloAusenteError",
    "ResultadoRelatorio",
    "Secao",
    "TabelaIlegivelError",
    "TabelaLida",
    "conferir_texto",
    "executar_relatorio",
    "ler_tabela",
    "localizar_template",
    "montar_abertura",
    "nome_do_relatorio",
    "preparar_relatorio",
    "relatorios_na_pasta",
    "tabela_do_texto",
]
