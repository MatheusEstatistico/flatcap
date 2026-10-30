# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Leitura e escrita do `projeto.yaml` — a ficha do atendimento.

Este é o primeiro módulo do FlatCap que **lê** o disco. Até a Fase 2 o disco era
só destino: o `novo` decidia tudo a partir do REDCap e escrevia. Da Fase 3 em
diante a pasta do projeto passa a ser uma fonte de informação — qual é a versão
vigente do banco, o que já foi registrado, o que o cliente combinou. É a mesma
ideia que a Fase 8 chama de "índice reconstruível": a fonte da verdade é sempre
o disco, e qualquer cache pode ser jogado fora e refeito.

Duas consequências de projeto vêm daí:

1. **O `dados adicionar` não fala com o REDCap.** A pasta já sabe de quem é.
   Pedir a rede para uma operação de arquivo local acrescentaria uma forma de
   falhar (token, VPN, servidor fora do ar) a um comando que não precisa dela.
   Por isso as funções daqui recebem `Path`, e não `Config`: a assinatura diz
   que este módulo não tem nada a ver com credenciais.

2. **A escrita é atômica.** O `projeto.yaml` é a memória do projeto. Um
   `write_text` que morre na metade — falta de espaço, unidade de rede que cai,
   OneDrive sincronizando — deixa o arquivo truncado e a ficha perdida. Aqui a
   gravação escreve um arquivo temporário ao lado e só então o troca de nome por
   cima do original, com `os.replace`, que é uma operação atômica no POSIX e no
   Windows: ou o arquivo antigo continua inteiro, ou o novo está inteiro. Nunca
   metade dos dois.

## Por que ruamel.yaml e não o PyYAML

Os dois convivem no projeto, e a divisão de trabalho é clara: o `projeto.py`
escreve a ficha do zero com o PyYAML, e este módulo a **altera** com o
`ruamel.yaml` em modo round-trip.

A diferença está em quem lê o arquivo de volta. O PyYAML descarta comentário no
parser — para ele, comentário não é dado —, então um `safe_load` seguido de
`dump` devolveria os mesmos valores e nenhuma das anotações que você escreveu
ao lado de `prazo` ou de `analises`. O ruamel em `typ="rt"` carrega os
comentários, a ordem das chaves e o estilo de aspas presos aos dados, e os
devolve na gravação. É o que sustenta literalmente a promessa do cabeçalho da
ficha: "edite à vontade, o FlatCap não sobrescreve o que você escreveu".

Toda a persistência do `projeto.yaml` está atrás das funções públicas abaixo —
`ler`, `bloco`, `acrescentar_versao`, `definir_status`, `localizar_projeto`,
`projetos_da_matricula`, `varrer`, `caminho_da_ficha`, `versao_vigente` e
`sequencia_do_nome`. Quem importa este módulo não sabe qual biblioteca de YAML está
em uso. Desde a 1.15.0, o `ler_yaml` estende o mesmo leitor aos outros YAML editados
à mão — o `desenho.yaml` da amostragem é o primeiro —, e o `numero_escrito` é a regra
de ler um número escrito num deles. Desde a 1.17.0, o `status_reconhecido` e o
`data_escrita` são as regras de ler o `status:` e o `prazo:` que você escreve.

Duas outras funções públicas, `escrever_atomico` e `temporario_ao_lado`, **não**
fazem parte desse contrato: são o utilitário de gravação que a Fase 4 passou a
compartilhar — o `dicionario.csv`, o `perfil.md`, as tabelas e os manifestos das
análises, e o `.docx` do relatório. Moram aqui porque foi aqui que a garantia
precisou existir primeiro, e porque duas implementações de escrita atômica no
mesmo pacote é como uma delas deixa de receber a próxima correção. Quem trocar
esta implementação de YAML por outra precisa levá-las junto.
"""

from __future__ import annotations

import math
import os
import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError

from .nomes import (
    PREFIXO_PROJETO,
    localizar_pasta,
    projetos_do_cliente,
    rotulo_do_projeto,
    sanitizar,
)
from .projeto import (
    ARQUIVO_PROJETO,
    STATUS,
    STATUS_EM_ANDAMENTO,
    STATUS_NAO_INICIADO,
    texto_da_migracao,
)

IMPLEMENTACAO = "ruamel.yaml (round-trip — preserva comentários e formatação)"

CHAVE_DADOS = "dados"
CHAVE_STATUS = "status"
CHAVE_PRAZO = "prazo"

# Ordem em que os campos de uma versão aparecem no arquivo. Fixa de propósito:
# o `projeto.yaml` é lido por humanos, e coluna que muda de lugar cansa.
CAMPOS_VERSAO = ("arquivo", "origem", "sha256", "tamanho_bytes", "data")


class FichaError(RuntimeError):
    """
    Falha ao lidar com o `projeto.yaml`, já traduzida para o usuário.

    Erro próprio pelo mesmo motivo de `ConfigError`, `RedcapError` e
    `ProjetoError`: a CLI captura esta classe e transforma em painel. Qualquer
    outra exceção é bug de verdade e deve subir com o traceback inteiro.
    """


class ProjetoNaoEncontradoError(FichaError):
    """
    Nenhuma pasta em `FLATCAP_ROOT` corresponde ao identificador pedido.
    """


class FichaAusenteError(FichaError):
    """
    A pasta existe, mas não tem `projeto.yaml`.

    Acontece com pasta criada à mão, antes do FlatCap existir. Não é erro do
    usuário: é um projeto que ainda não foi adotado pela ferramenta.
    """

    def __init__(self, mensagem: str, pasta: Path) -> None:
        super().__init__(mensagem)
        self.pasta = pasta


class ProjetoAmbiguoError(FichaError):
    """
    A matrícula pedida tem mais de um projeto, e nenhum deles é "o" projeto.

    **Não é erro de disco**, e a distinção importa: até a 1.0.0 dois achados
    para o mesmo identificador só podiam ser pasta duplicada, e a mensagem
    mandava resolver no disco. Desde a 1.1.0 é o caso normal de um cliente com
    dois trabalhos, e o que falta é o usuário dizer de qual deles ele está
    falando — por isso a lista dos projetos viaja no erro, em `.projetos`.

    `record_id` repetido continua sendo erro de disco, e sai por
    `ProjetoNaoEncontradoError` como antes: ele é único por construção do
    REDCap, e dois iguais querem dizer pasta copiada.
    """

    def __init__(self, mensagem: str, projetos: tuple[Path, ...]) -> None:
        super().__init__(mensagem)
        self.projetos = projetos


class LayoutAntigoError(FichaError):
    """
    A pasta do cliente ainda tem o `projeto.yaml` na raiz — o formato anterior
    à 1.1.0.

    Homônimo do erro de `projeto.py` de propósito: é o mesmo diagnóstico visto
    de dois lados (quem cria a pasta e quem a procura), e a regra da casa é um
    erro por módulo, para que a CLI capture a classe daquela camada. O texto é
    um só, e mora em `projeto.texto_da_migracao`.
    """

    def __init__(self, mensagem: str, pasta: Path) -> None:
        super().__init__(mensagem)
        self.pasta = pasta


class FichaInvalidaError(FichaError):
    """
    O `projeto.yaml` existe mas não é YAML válido, ou não tem o formato esperado.
    """

    def __init__(self, mensagem: str, caminho: Path) -> None:
        super().__init__(mensagem)
        self.caminho = caminho


@dataclass(frozen=True)
class Versao:
    """
    Uma versão do banco, do jeito que ela é registrada em `dados:`.

    Imutável como `Config`, `Cliente` e `Plano`. O `sha256` é o recibo: é o que
    responde "o arquivo que o cliente reenviou é diferente do anterior, ou ele
    mandou o mesmo de novo?" sem abrir planilha nenhuma.
    """

    arquivo: str
    origem: str
    sha256: str
    tamanho_bytes: int
    data: date | None = None

    @property
    def sequencia(self) -> int | None:
        """
        O número do prefixo (`00`, `01`, `02`...), ou `None` se o nome não seguir
        a convenção. É o índice da versão na história do projeto.
        """
        return sequencia_do_nome(self.arquivo)


@dataclass(frozen=True)
class Ficha:
    """
    O conteúdo do `projeto.yaml` que o FlatCap precisa conhecer.

    Deliberadamente **não** carrega tudo o que está no arquivo: os blocos de cada
    análise são seus, e quem precisa de um o lê pelo `bloco`. O que entra aqui é o
    mínimo para identificar o projeto e versionar o banco.

    A exceção são `finalidade` e `objetivos`, e ela tem uma regra por trás: entra
    aqui o que alguma camada de cima **imprime**. Os dois saem na primeira página
    de todo relatório, e o `relatorio.py` existe justamente para não abrir o banco
    nem falar com o REDCap — se ele não pudesse lê-los da ficha, não teria de onde.

    Os dois têm default vazio porque ficha criada antes deste campo existir
    continua abrindo. Vazio não é erro: é o que faz o documento sair com o
    marcador e o alerta `texto_ausente`, em vez de sair mais curto em silêncio.

    `analises` é a terceira exceção, e entrou na Fase 7 por uma razão de outra
    natureza: ela não é impressa, ela **dirige**. É a lista que o `flatcap novo`
    grava vazia e que o cabeçalho da ficha promete desde a Fase 2 — *"o que foi
    combinado na reunião. A Fase 7 lê esta lista para saber quais módulos rodar"*.
    Ela entra na `Ficha` porque é a única coisa da ficha que **toda** camada de
    cima consulta: é a ordem das seções do relatório quando há mais de uma rodada
    na pasta.

    `prazo` é a quarta, pela regra da primeira: o `flatcap status` o imprime, e lê
    todas as fichas do `FLATCAP_ROOT` de uma vez — pedir o prazo pelo `bloco`
    abriria cada arquivo duas vezes. Entra como está escrito (`2026-11-04`,
    `04/11/2026`, ou o que estiver lá), e quem o lê como data é o `data_escrita`: um
    prazo digitado errado não pode fazer a ficha inteira deixar de abrir. O `status`
    entra do mesmo jeito, como texto, e quem o reconhece é o `status_reconhecido`.

    Os parâmetros de cada análise — os pares da correlação, a lista de variáveis
    da normalidade — **não** entram aqui. Eles são de um módulo só, e um campo na
    `Ficha` por análise faria esta classe crescer a cada análise nova. Quem os lê é
    o `bloco(raiz, chave)`, mais abaixo.
    """

    raiz: Path
    record_id: str
    matricula: str
    nome: str
    tipo: str
    status: str
    dados: tuple[Versao, ...]
    finalidade: str = ""
    objetivos: str = ""
    analises: tuple[str, ...] = ()
    prazo: str = ""

    @property
    def versao_redcap(self) -> Versao | None:
        """
        A versão baixada do REDCap — a intocável. Identificada pela origem, e não
        pelo prefixo `00_`, porque a origem é o fato e o nome é convenção.
        """
        for versao in self.dados:
            if versao.origem == "redcap":
                return versao
        return None

    @property
    def ultima_versao(self) -> Versao | None:
        return self.dados[-1] if self.dados else None


def versao_vigente(ficha: Ficha) -> Versao | None:
    """
    A versão do banco que vale hoje: a de maior número de sequência.

    Não é `ficha.dados[-1]`. A ordem da lista é a ordem em que as versões foram
    registradas, e a ficha é editada à mão — uma entrada acrescentada fora de
    ordem faria a última da lista deixar de ser a mais nova. O número do prefixo,
    esse, é o índice da versão por construção da Fase 3.

    Empate (duas entradas sem prefixo reconhecível) resolve pela ordem da lista,
    que é a melhor informação que sobra — e o desempate é a **posição**, lida
    de um `enumerate`, não um `ficha.dados.index(versao)` dentro da chave do
    `max`: o `index` percorre a lista de novo a cada comparação (O(n²)) e, com
    duas `Versao` idênticas, devolve o mesmo índice para as duas — que é
    justamente o empate que ele deveria desfazer.

    Mora aqui desde a Fase 6, e não no `banco.py`, onde nasceu. A pergunta "qual
    versão vale?" se responde lendo a ficha: não precisa do `pandas`, não abre
    arquivo nenhum. Deixá-la no módulo que importa o `pandas` obrigava o
    `relatorio.py` — que existe justamente para **não** abrir o banco — a pagar
    meio segundo de partida para consultar uma lista que ele já tinha na mão. O
    `banco.py` reexporta o nome, então nenhum chamador mudou.
    """
    if not ficha.dados:
        return None
    posicao, _ = max(
        enumerate(ficha.dados),
        key=lambda par: (
            par[1].sequencia if par[1].sequencia is not None else -1,
            par[0],
        ),
    )
    return ficha.dados[posicao]


# Localização do projeto no disco


def caminho_da_ficha(raiz: Path) -> Path:
    return Path(raiz) / ARQUIVO_PROJETO


def localizar_projeto(root: Path, identificador: str) -> Path:
    """
    Encontra a pasta do projeto a partir de um `record_id` ou de uma matrícula.

    A busca é feita **no disco**, lendo o `record_id` e a `matricula` de cada
    `projeto.yaml`. Aceitar os dois identificadores não é conveniência gratuita:
    o `record_id` é o que aparece no `flatcap listar` e o que você tem em mãos
    logo depois de criar a pasta; a matrícula é o que está no nome da pasta e o
    que você tem em mãos seis meses depois, olhando para o disco.

    ## O que a 1.1.0 mudou aqui

    A varredura desceu um nível: era `FLATCAP_ROOT/*/projeto.yaml` e passou a
    ser `FLATCAP_ROOT/*/Projeto */projeto.yaml`.

    E os dois identificadores deixaram de ser equivalentes, porque um deles
    deixou de ser único. **O `record_id` identifica o projeto; a matrícula
    identifica a pessoa.** Daí a ordem de resolução:

    1. bate por `record_id` em um projeto → é esse, e ponto;
    2. bate por `record_id` em mais de um → pasta duplicada no disco, que é
       erro de verdade: o REDCap não emite dois registros com o mesmo número;
    3. bate por matrícula em um projeto → é esse (o caso comum, do cliente que
       só tem um trabalho — a busca por matrícula continua servindo para ele);
    4. bate por matrícula em vários → `ProjetoAmbiguoError`, com a lista. Não é
       falha: é o usuário tendo dado o nome da pessoa quando a pergunta era
       sobre o trabalho.

    O `record_id` vence a matrícula quando os dois batem porque ele é o mais
    específico dos dois — e porque a única forma de isso acontecer é uma
    matrícula que por acaso tem o mesmo número de um registro.

    Raises:
        ProjetoNaoEncontradoError: nada bateu, ou `record_id` duplicado.
        ProjetoAmbiguoError: a matrícula tem mais de um projeto.
        LayoutAntigoError: a pasta do cliente está no formato anterior à 1.1.0.
        FichaAusenteError: a pasta foi encontrada pelo nome, mas não tem ficha.
        FichaInvalidaError: há ficha que não abre, e pode ser justamente a pedida.
    """
    root = Path(root)
    procurado = sanitizar(str(identificador))
    if not procurado:
        raise ProjetoNaoEncontradoError(
            "Identificador vazio. Informe o `record_id` (como aparece no "
            "`flatcap listar`) ou a matrícula do cliente."
        )

    projetos, ilegiveis, antigas = _varrer(root)

    por_record = [
        pasta for pasta, ficha in projetos if _mesmo_record(ficha.record_id, procurado)
    ]
    if len(por_record) == 1:
        return por_record[0]
    if len(por_record) > 1:
        lista = "\n".join(f"  {p}" for p in por_record)
        raise ProjetoNaoEncontradoError(
            f"Mais de um projeto tem o record_id {identificador!r}:\n{lista}\n\n"
            "O REDCap não emite dois registros com o mesmo número, então isto é "
            "pasta duplicada — copiada de outro projeto e não editada, quase "
            "sempre. Resolva no disco antes de continuar: a ficha de cada pasta "
            "precisa dizer de qual registro ela é."
        )

    por_matricula = [
        pasta for pasta, ficha in projetos if ficha.matricula == procurado
    ]
    if len(por_matricula) == 1:
        return por_matricula[0]
    if len(por_matricula) > 1:
        raise ProjetoAmbiguoError(
            _mensagem_ambigua(identificador, projetos, por_matricula),
            tuple(por_matricula),
        )

    # Nada bateu. Antes de dizer "não existe", os três diagnósticos que dizem o
    # que fazer, em vez de mandar o usuário procurar erro de digitação.

    # 1. A pasta do cliente ficou no formato de antes da 1.1.0.
    for pasta_cliente, ficha_antiga in antigas:
        if ficha_antiga is None:
            continue
        if _mesmo_record(ficha_antiga.record_id, procurado) or (
            ficha_antiga.matricula == procurado
        ):
            raise LayoutAntigoError(
                texto_da_migracao(pasta_cliente, ficha_antiga.record_id), pasta_cliente
            )

    # 2. A pasta existe pelo nome, e não tem projeto dentro.
    pasta = localizar_pasta(root, procurado)
    if pasta is not None:
        for candidata, erro in ilegiveis:
            if candidata.parent == pasta:
                raise erro
        if (pasta / ARQUIVO_PROJETO).exists():
            raise LayoutAntigoError(texto_da_migracao(pasta), pasta)
        raise FichaAusenteError(
            f"Encontrei a pasta {pasta.name}, e ela não tem nenhum projeto dentro "
            f"com {ARQUIVO_PROJETO}.\n"
            "Pastas criadas à mão, antes do FlatCap, não têm ficha — e sem ficha "
            "não há onde registrar as versões do banco.\n"
            "Crie o projeto pelo `flatcap novo`, ou monte a subpasta "
            f"`{PREFIXO_PROJETO}NNN` à mão e copie para dentro dela um "
            f"`{ARQUIVO_PROJETO}` de outro projeto, ajustando os campos de "
            "identificação.",
            pasta,
        )

    # 3. Uma ficha ilegível não é uma nota de rodapé: enquanto houver uma, a
    # busca não pode afirmar que o projeto não existe — ele pode ser justamente
    # aquele que não deu para ler. Então o erro que sobe é o diagnóstico da ficha
    # quebrada, que diz o que fazer, e não um "não encontrei".
    if ilegiveis:
        pasta, erro = ilegiveis[0]
        raise FichaInvalidaError(
            f"Não consegui ler a ficha de {rotulo_do_projeto(pasta)}, então não dá "
            f"para afirmar se {identificador!r} é este projeto ou nenhum.\n\n{erro}"
            + (
                f"\n\nOutras {len(ilegiveis) - 1} ficha(s) também estão ilegíveis."
                if len(ilegiveis) > 1
                else ""
            ),
            erro.caminho,
        )

    raise ProjetoNaoEncontradoError(
        f"Nenhum projeto com record_id ou matrícula {identificador!r} em {root}.\n"
        "Confira o identificador no `flatcap listar`, ou a matrícula no nome da "
        "pasta do cliente e o número no nome da pasta do projeto."
    )


def projetos_da_matricula(root: Path, matricula: str) -> tuple[Path, ...]:
    """
    Todos os projetos de um cliente, em ordem, lendo as fichas.

    Pública porque é a pergunta que a `ProjetoAmbiguoError` responde. Lê as fichas,
    ao contrário do `nomes.projetos_do_cliente`, que só olha nomes: aqui a matrícula
    vem da ficha, então uma pasta renomeada à mão continua sendo encontrada. O painel
    de todos os projetos, que a Fase 8 previa aqui, é o `varrer`, logo abaixo.
    """
    procurado = sanitizar(str(matricula))
    if not procurado:
        return ()
    projetos, _, _ = _varrer(Path(root))
    return tuple(pasta for pasta, ficha in projetos if ficha.matricula == procurado)


@dataclass(frozen=True)
class Varredura:
    """
    O que há no `FLATCAP_ROOT`, lido ficha por ficha.

    As três listas do `_varrer`, cada item com o que já carrega: a `Ficha` sabe a
    pasta dela (`raiz`), e a `FichaInvalidaError`, o arquivo que não abriu
    (`caminho`).
    """

    projetos: tuple[Ficha, ...] = ()
    ilegiveis: tuple[FichaInvalidaError, ...] = ()
    antigas: tuple[Path, ...] = ()  # as pastas de cliente no formato anterior à 1.1.0


def varrer(root: Path) -> Varredura:
    """
    Todos os projetos do `FLATCAP_ROOT`, lendo as fichas: o painel do
    `flatcap status` parte daqui.

    É a varredura do `localizar_projeto` e do `projetos_da_matricula`, e não uma
    segunda: dois níveis, explícitos, para uma ficha esquecida em
    `2. Versões antigas/` não virar projeto. A ficha que não abre não interrompe a
    varredura — volta em `ilegiveis`, para quem pediu dizer o que fazer com ela, e o
    mesmo vale para a pasta no formato antigo.
    """
    projetos, ilegiveis, antigas = _varrer(Path(root))
    return Varredura(
        projetos=tuple(ficha for _, ficha in projetos),
        ilegiveis=tuple(erro for _, erro in ilegiveis),
        antigas=tuple(pasta for pasta, _ in antigas),
    )


def _varrer(
    root: Path,
) -> tuple[
    list[tuple[Path, Ficha]],
    list[tuple[Path, FichaInvalidaError]],
    list[tuple[Path, Ficha | None]],
]:
    """
    Percorre o `FLATCAP_ROOT` inteiro e devolve o que encontrou, em três listas:
    os projetos legíveis, as fichas que não abrem, e as pastas de cliente que
    ficaram no formato anterior à 1.1.0.

    Duas voltas, e não um `rglob`, para que a profundidade seja explícita: um
    `projeto.yaml` só conta como projeto no segundo nível. Isso é o que impede
    uma ficha esquecida dentro de `2. Versões antigas/` de ser confundida com um
    projeto — e é o que permite reconhecer o layout antigo em vez de ignorá-lo.
    """
    projetos: list[tuple[Path, Ficha]] = []
    ilegiveis: list[tuple[Path, FichaInvalidaError]] = []
    antigas: list[tuple[Path, Ficha | None]] = []

    if not root.is_dir():
        return projetos, ilegiveis, antigas

    for pasta_cliente in sorted(p for p in root.iterdir() if p.is_dir()):
        if caminho_da_ficha(pasta_cliente).exists():
            try:
                antigas.append((pasta_cliente, ler(pasta_cliente)))
            except FichaError:
                # A ficha antiga não abrir não impede o diagnóstico de layout;
                # só tira dele o número do projeto a criar.
                antigas.append((pasta_cliente, None))

        for pasta_projeto in projetos_do_cliente(pasta_cliente):
            if not caminho_da_ficha(pasta_projeto).exists():
                continue
            try:
                projetos.append((pasta_projeto, ler(pasta_projeto)))
            except FichaInvalidaError as erro:
                ilegiveis.append((pasta_projeto, erro))

    return projetos, ilegiveis, antigas


def _mesmo_record(da_ficha: str, procurado: str) -> bool:
    """
    O `record_id` da ficha é o que o usuário digitou?

    Igualdade de texto, e — quando os dois são número — igualdade de valor. O
    segundo caso existe porque a pasta se chama `Projeto 006` e o `listar`
    mostra `6`: digitar o que está na frente dos olhos tem de funcionar nos dois
    casos.

    A matrícula **não** recebe o mesmo tratamento, e a assimetria é deliberada:
    lá o zero à esquerda é parte do identificador. A matrícula `00742` não é a
    matrícula `742`, e tratá-las como iguais faria a busca entregar a pasta de
    outra pessoa.
    """
    if not da_ficha or not procurado:
        return False
    if da_ficha == procurado:
        return True
    if da_ficha.isdigit() and procurado.isdigit():
        return int(da_ficha) == int(procurado)
    return False


def _mensagem_ambigua(
    identificador: str,
    projetos: list[tuple[Path, Ficha]],
    achados: list[Path],
) -> str:
    """
    A lista de projetos do cliente, com o que distingue um do outro.

    Status e banco vigente, e não só o número: o que o usuário precisa para
    escolher é "qual deles é o que eu estava mexendo", e o número do registro
    sozinho não responde isso seis meses depois.
    """
    fichas = {pasta: ficha for pasta, ficha in projetos}
    nome = next((fichas[p].nome for p in achados if fichas[p].nome), "")

    linhas = []
    for pasta in achados:
        ficha = fichas[pasta]
        vigente = versao_vigente(ficha)
        banco = vigente.arquivo if vigente is not None else "(sem banco ainda)"
        linhas.append(
            f"  {pasta.name:<16} record_id {ficha.record_id or '?':<6} "
            f"status {ficha.status or '?':<12} {banco}"
        )

    de_quem = f" ({nome})" if nome else ""
    exemplo = fichas[achados[0]].record_id or "?"
    return (
        f"A matrícula {identificador}{de_quem} tem {len(achados)} projetos, e a "
        "matrícula não diz de qual deles você está falando.\n\n"
        + "\n".join(linhas)
        + "\n\nRode o comando de novo com o `record_id` em vez da matrícula:\n"
        f"  flatcap <comando> {exemplo}\n\n"
        "A matrícula continua funcionando para quem tem um projeto só — ela "
        "identifica a pessoa, e o `record_id` identifica o trabalho."
    )


# Leitura


def ler(raiz: Path) -> Ficha:
    """
    Lê o `projeto.yaml` de uma pasta de projeto.

    Raises:
        FichaAusenteError, FichaInvalidaError
    """
    raiz = Path(raiz)
    caminho = caminho_da_ficha(raiz)

    if not caminho.exists():
        raise FichaAusenteError(
            f"A pasta {raiz.name} não tem {ARQUIVO_PROJETO}.", raiz
        )

    documento = _carregar_documento(caminho)

    if not isinstance(documento, dict):
        raise FichaInvalidaError(
            f"{caminho} não contém um mapeamento de campos.\n"
            f"O arquivo deveria começar com `record_id:`, `tipo:`, `matricula:`... "
            f"e o que veio foi um {type(documento).__name__}.",
            caminho,
        )

    return Ficha(
        raiz=raiz,
        record_id=_texto(documento, "record_id"),
        matricula=_texto(documento, "matricula"),
        nome=_texto(documento, "nome"),
        tipo=_texto(documento, "tipo"),
        status=_texto(documento, CHAVE_STATUS),
        dados=_versoes(documento, caminho),
        finalidade=_texto(documento, "finalidade"),
        objetivos=_texto(documento, "objetivos"),
        analises=_analises(documento),
        prazo=_texto(documento, CHAVE_PRAZO),
    )


def bloco(raiz: Path, chave: str) -> Any:
    """
    O bloco cru de uma chave qualquer do `projeto.yaml`, ou `None`.

    Existe porque **este é o único módulo do pacote que abre o `projeto.yaml`**, e
    é bom que continue sendo. A Fase 7 pôs os parâmetros de cada análise na ficha —
    `normalidade:` com a lista de variáveis, `correlacao:` com os pares —, e sem
    esta função cada módulo de análise importaria o `ruamel` e viraria um segundo
    leitor de YAML. No dia em que a implementação de YAML mudar (a decisão está em
    aberto nas pendências do roteiro), quebrariam cinco lugares em vez de um.

    Devolve tipos comuns de Python, e não os objetos do `ruamel`: eles são
    subclasses de `dict` e `list` e funcionam do mesmo jeito, mas carregam junto os
    comentários e a formatação do arquivo — e um módulo de análise que recebesse
    isso poderia alterar a ficha sem querer, por uma linha que parece inofensiva.

    O valor **não é validado aqui**. O formato do bloco é assunto de quem o usa:
    o que é um par de variáveis para a correlação não é o que é uma lista de nomes
    para a normalidade, e este módulo não tem como saber qual é qual. A recusa por
    formato errado é de cada análise, com o nome dela no painel.

    Raises:
        FichaAusenteError, FichaInvalidaError
    """
    raiz = Path(raiz)
    caminho = caminho_da_ficha(raiz)
    if not caminho.exists():
        raise FichaAusenteError(
            f"A pasta {raiz.name} não tem {ARQUIVO_PROJETO}.", raiz
        )

    documento = _carregar_documento(caminho)
    if not isinstance(documento, dict):
        raise FichaInvalidaError(
            f"{caminho} não contém um mapeamento de campos.", caminho
        )
    return _simples(documento.get(chave))


def _simples(valor: Any) -> Any:
    """
    Converte o que o `ruamel` devolveu para `dict`, `list` e escalares comuns.
    """
    if isinstance(valor, dict):
        return {str(chave): _simples(item) for chave, item in valor.items()}
    if isinstance(valor, list):
        return [_simples(item) for item in valor]
    return valor


def _analises(documento) -> tuple[str, ...]:
    """
    A lista `analises:`, com o que não for texto descartado.

    Descarta em silêncio, e a escolha é deliberada. Esta lista é editada à mão, e
    o estrago de uma entrada malformada é pequeno e local: a seção correspondente
    não aparece na ordem pedida. Recusar a ficha inteira por causa dela travaria
    `flatcap dados listar` e `flatcap relatorio` — comandos que não têm nada a ver
    com a lista — por um erro de digitação em uma linha que nenhum deles lê.
    """
    bruto = documento.get("analises")
    if not isinstance(bruto, list):
        return ()
    return tuple(
        texto
        for texto in (str(item).strip() for item in bruto if item is not None)
        if texto
    )


def ler_yaml(caminho: Path) -> Any:
    """
    O conteúdo de outro YAML editado à mão, em tipos comuns de Python.

    O `desenho.yaml` da amostragem é o primeiro. Existe pelo motivo do `bloco`: este é
    o único módulo do pacote que abre YAML. E o `desenho.yaml` quebra pelos mesmos
    motivos da ficha — tabulação, dois-pontos dentro de um valor sem aspas —; lido por
    aqui, ele ganha o mesmo diagnóstico, em vez da mensagem crua do parser.

    O valor **não é validado aqui**, como no `bloco`: o que é um desenho válido é
    assunto de quem o usa.

    Raises:
        FichaAusenteError: o arquivo não existe.
        FichaInvalidaError: o arquivo não é um YAML válido.
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FichaAusenteError(
            f"A pasta {caminho.parent.name} não tem {caminho.name}.", caminho.parent
        )
    return _simples(_carregar_documento(caminho))


# Um número escrito como texto num YAML editado à mão: `"24,9"`, `"24.9"`, `" 25 "`.
# Sem separador de milhar — `1.234,5` é ambíguo, e ambiguidade numa ficha se recusa.
_NUMERO_ESCRITO = re.compile(r"^[+\-]?\d+(?:[.,]\d+)?$")


def numero_escrito(valor: Any) -> float | None:
    """
    Um número, a partir de como o YAML o trouxe; `None` quando não é um.

    Número do YAML entra como está. Texto entra quando é um número escrito — com
    vírgula ou ponto decimal, e sem separador de milhar: é o `margem: 2,5` do
    `desenho.yaml`, que o YAML lê como texto, e o `"24,9"` entre aspas que a recusa
    da comparação ensina a escrever. Lógico não é número, embora o Python ache que
    `True` vale 1.

    Morava na comparação, como `referencia_escrita`, e desceu para cá na 1.15.0: a
    amostragem lê o `desenho.yaml` com a mesma regra, e duas regras para o mesmo
    número escrito à mão é como uma ficha aceita `2,5` e a outra o recusa.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int | float):
        numero = float(valor)
        return numero if math.isfinite(numero) else None
    if isinstance(valor, str):
        limpo = valor.strip()
        if _NUMERO_ESCRITO.match(limpo):
            return float(limpo.replace(",", "."))
    return None


# As duas formas de escrever uma data à mão que a ficha aceita: a do YAML
# (`2026-11-04`, que ele já entrega como data) e a do Brasil (`04/11/2026`, que ele
# entrega como texto). Dia e mês com um algarismo só valem nas duas.
_DATA_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_DATA_BR = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def data_escrita(valor: Any) -> date | None:
    """
    Uma data, a partir de como o YAML a trouxe; `None` quando não é uma.

    É a regra do `prazo:`, que se escreve à mão depois da reunião. Sem aspas,
    `2026-11-04` chega do YAML como data, e entra como está; `04/11/2026` chega como
    texto, e é lido como dia, mês e ano — a ordem de quem escreve em português. O ano
    tem quatro algarismos nas duas formas: `04/11/26` é 2026 ou 1926, e ambiguidade
    numa ficha se recusa, como no `numero_escrito`. A data que não existe —
    `31/02/2026` — também não é data.
    """
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if not isinstance(valor, str):
        return None
    limpo = valor.strip()
    if achado := _DATA_ISO.match(limpo):
        ano, mes, dia = (int(parte) for parte in achado.groups())
    elif achado := _DATA_BR.match(limpo):
        dia, mes, ano = (int(parte) for parte in achado.groups())
    else:
        return None
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


# Os status que o cabeçalho de toda ficha anterior à 1.17.0 sugeria. O `novo` é o que
# o `flatcap novo` escrevia, e é o `não iniciado` de hoje; o `em_analise` é o
# `em andamento`. O terceiro, `entregue`, fica de fora de propósito: ele pode ser o
# `pronto` ou o `finalizado`, e adivinhar o segundo tiraria do painel um projeto que
# ainda não terminou.
_STATUS_DE_ANTES = {
    "novo": STATUS_NAO_INICIADO,
    "em analise": STATUS_EM_ANDAMENTO,
}


def _chave_do_status(texto: str) -> str:
    """
    O status reduzido ao que se compara: minúsculas, sem acento, `_` e `-` como
    espaço, e um espaço só entre as palavras.
    """
    decomposto = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(letra for letra in decomposto if not unicodedata.combining(letra))
    return " ".join(sem_acento.replace("_", " ").replace("-", " ").casefold().split())


_STATUS_POR_CHAVE = {
    **{_chave_do_status(status): status for status in STATUS},
    **_STATUS_DE_ANTES,
}


def status_reconhecido(escrito: str) -> str | None:
    """
    Qual dos status do `projeto.STATUS` está escrito na ficha; `None` quando não é
    nenhum deles.

    A leitura é tolerante e a escrita é estrita, como no `dicionario.csv`: o status se
    digita à mão, e `Em andamento`, `EM ANDAMENTO` e `nao iniciado` são os de sempre —
    o que volta é sempre a grafia do `projeto.STATUS`. Os dois que a ficha anterior à
    1.17.0 sugeria no cabeçalho, `novo` e `em_analise`, também são reconhecidos,
    porque toda ficha criada até ali diz `novo`.

    O que não é nenhum deles volta `None`, e não um palpite: quem mostra o status é
    quem decide o que fazer com um texto que não se reconhece — o painel o mostra como
    está, marcado.
    """
    return _STATUS_POR_CHAVE.get(_chave_do_status(escrito or ""))


# Escrita


def acrescentar_versao(raiz: Path, versao: Versao) -> None:
    """
    Acrescenta uma entrada ao fim da lista `dados:`, preservando o resto.

    Não é um "reescreve o arquivo com os campos que eu conheço". O `projeto.yaml`
    é editado à mão — o cabeçalho gerado pelo `novo` promete isso literalmente —
    e um comando que apagasse o `prazo` que você preencheu, ou a lista `analises`
    que você combinou na reunião, tornaria a promessa falsa.
    """
    caminho = caminho_da_ficha(Path(raiz))
    if not caminho.exists():
        raise FichaAusenteError(
            f"Não há {ARQUIVO_PROJETO} em {raiz}. Nada foi registrado.", Path(raiz)
        )

    documento = _carregar_documento(caminho)
    if not isinstance(documento, dict):
        raise FichaInvalidaError(
            f"{caminho} não contém um mapeamento de campos; não sei onde "
            "acrescentar a versão.",
            caminho,
        )

    lista = documento.get(CHAVE_DADOS)
    if not isinstance(lista, list):
        # Chave ausente, `dados:` vazio (que vira None) ou sobrescrito por engano.
        lista = CommentedSeq()
        documento[CHAVE_DADOS] = lista

    lista.append(_mapa_da_versao(versao))

    # Uma lista que veio do arquivo como `dados: []` mantém o estilo em linha, e
    # a entrada nova sairia toda espremida em uma linha só. Bloco é o formato em
    # que este arquivo é lido e editado.
    if hasattr(lista, "fa"):
        lista.fa.set_block_style()

    _gravar_documento(caminho, documento)


def definir_status(raiz: Path, status: str) -> None:
    """
    Escreve o `status:` da ficha, preservando o resto — os comentários, as aspas e a
    ordem das chaves, como o `acrescentar_versao`.

    É a exceção à promessa do cabeçalho — "o FlatCap não sobrescreve o que você
    escreveu" —, e o cabeçalho de toda ficha nova a diz: o `flatcap relatorio`,
    quando escreve o documento, passa o projeto para `pronto`. Por isso o valor é
    sempre um dos do `projeto.STATUS`, na grafia de lá: um texto qualquer aqui
    seria o FlatCap escrevendo na ficha um status que o painel não reconhece.

    O comentário escrito ao lado do `status:` fica onde está. A ficha sem a chave a
    ganha logo depois do `prazo`, que é onde o `flatcap novo` a escreve; sem `prazo`,
    no fim.

    Raises:
        FichaAusenteError, FichaInvalidaError
        ValueError: o status não é um do `projeto.STATUS` — defeito de quem chamou, e
            não do arquivo.
    """
    if status not in STATUS:
        raise ValueError(f"status desconhecido: {status!r}; os válidos são {STATUS}")

    caminho = caminho_da_ficha(Path(raiz))
    if not caminho.exists():
        raise FichaAusenteError(
            f"Não há {ARQUIVO_PROJETO} em {raiz}. O status não foi escrito.", Path(raiz)
        )

    documento = _carregar_documento(caminho)
    if not isinstance(documento, dict):
        raise FichaInvalidaError(
            f"{caminho} não contém um mapeamento de campos; não sei onde escrever o "
            "status.",
            caminho,
        )

    if CHAVE_STATUS in documento or CHAVE_PRAZO not in documento:
        documento[CHAVE_STATUS] = status
    else:
        documento.insert(list(documento).index(CHAVE_PRAZO) + 1, CHAVE_STATUS, status)

    _gravar_documento(caminho, documento)


# Backend: ruamel.yaml


# O `indent()` do ruamel vale para o documento inteiro — não há como preservar o
# recuo de cada lista separadamente. Então a escolha é entre impor um estilo e
# adotar o que o arquivo já usa. Impor era o que transformava um
# `  - descritiva` escrito à mão em `- descritiva`: YAML idêntico, e um diff
# gratuito num arquivo que o cabeçalho da ficha promete não mexer.
RECUO_PADRAO = 0  # o `-` na coluna da chave — o que o PyYAML do `projeto.py` escreve

# Uma chave que termina em `|` ou `>` abre um bloco literal. O `[-+]?\d*` cobre
# os indicadores (`|-`, `>+`, `|2`) e o `(#.*)?` o comentário na mesma linha.
_ABRE_BLOCO = re.compile(r"[|>][-+]?\d*\s*(#.*)?$")


def _recuo_das_listas(texto: str) -> int:
    """
    Em que coluna, em relação à chave que as contém, este arquivo escreve o `-`.

    Devolve `0` para o estilo que o `flatcap novo` grava::

        dados:
        - arquivo: 00_redcap_2026-09-01_banco.xlsx

    e `2` para o que se escreve à mão sem pensar::

        analises:
          - descritiva

    Vence a **primeira** lista do arquivo. Um arquivo que mistura os dois estilos
    não tem como manter os dois — o recuo do ruamel é do documento inteiro — e na
    ficha do FlatCap `analises:` vem antes de `dados:`, então quem vence é o bloco
    que você editou à mão. É o lado certo de errar: a lista `dados:` é escrita
    pela ferramenta e ninguém decora a coluna dela.

    Linha dentro de bloco literal (`objetivos: |`) é pulada: um `- ` ali é prosa
    do cliente, não item de lista.
    """
    pilha: list[int] = []
    bloco: int | None = None

    for linha in texto.splitlines():
        conteudo = linha.lstrip()
        coluna = len(linha) - len(conteudo)

        if bloco is not None:
            if not conteudo or coluna > bloco:
                continue
            bloco = None

        if not conteudo or conteudo.startswith("#"):
            continue

        if conteudo.startswith("- ") or conteudo == "-":
            pai = next((c for c in reversed(pilha) if c < coluna), 0)
            return coluna - pai

        while pilha and pilha[-1] >= coluna:
            pilha.pop()
        pilha.append(coluna)

        if _ABRE_BLOCO.search(conteudo):
            bloco = coluna

    return RECUO_PADRAO


def _construtor(recuo_da_lista: int = RECUO_PADRAO) -> YAML:
    """
    O leitor/escritor round-trip, configurado.

    `typ="rt"` é o modo que carrega comentários e formatação junto com os dados
    e os devolve na hora de gravar. `preserve_quotes` mantém `matricula: "00742"`
    entre aspas — sem isso a matrícula voltaria como o número 742 e a pasta
    deixaria de bater com o registro. E `width` alto impede que o ruamel quebre
    um nome de arquivo longo em duas linhas: é YAML válido, mas ilegível em um
    arquivo feito para ser aberto no editor.

    O `recuo_da_lista` é o único parâmetro porque é a única coisa aqui que não se
    decide no código: ela vem do arquivo que está sendo reescrito. Ver
    `_recuo_das_listas`.
    """
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=recuo_da_lista + 2, offset=recuo_da_lista)
    yaml.representer.add_representer(type(None), _representar_nulo)
    return yaml


def _representar_nulo(dumper, _dados):
    """
    Escreve o vazio como `null`, e não como uma linha terminada em dois-pontos.

    O ruamel, por padrão, grava `prazo:` — que o parser lê como nulo, mas que
    parece uma linha que alguém começou e não terminou. `prazo: null` diz que o
    campo está deliberadamente vazio. É também o que o PyYAML do `projeto.py`
    escreve quando cria a ficha, e os dois lados produzem o mesmo arquivo.
    """
    return dumper.represent_scalar("tag:yaml.org,2002:null", "null")


def _carregar_documento(caminho: Path):
    texto = _ler_texto(caminho)
    try:
        return _construtor().load(texto)
    except YAMLError as erro:
        raise FichaInvalidaError(_diagnostico(texto, caminho, erro), caminho) from erro


def _gravar_documento(caminho: Path, documento) -> None:
    import io

    # O recuo é lido do arquivo que está no disco, e não do documento carregado:
    # o ruamel prende os comentários aos dados, mas não a coluna em que as listas
    # foram escritas.
    recuo = _recuo_das_listas(_ler_texto(caminho)) if caminho.exists() else RECUO_PADRAO

    buffer = io.StringIO()
    _construtor(recuo).dump(documento, buffer)
    escrever_atomico(caminho, buffer.getvalue())


def _mapa_da_versao(versao: Versao) -> CommentedMap:
    """
    Converte a `Versao` no mapeamento que vai para o arquivo, na ordem fixa.
    """
    mapa = CommentedMap()
    mapa["arquivo"] = versao.arquivo
    mapa["origem"] = versao.origem
    mapa["sha256"] = versao.sha256
    mapa["tamanho_bytes"] = int(versao.tamanho_bytes)
    mapa["data"] = versao.data
    return mapa


# Auxiliares de leitura e gravação


def sequencia_do_nome(nome: str) -> int | None:
    """
    Extrai o prefixo numérico de `02_revisado_2026-03-14_banco.xlsx` → 2.

    Devolve `None` para nome que não segue a convenção — arquivo que o cliente
    largou na pasta à mão, por exemplo. `None` e `0` são coisas diferentes aqui,
    e é por isso que a função não devolve `-1` nem `0` como "não sei".
    """
    texto = str(nome or "")
    if len(texto) < 3 or texto[2] != "_" or not texto[:2].isdigit():
        return None
    return int(texto[:2])


def _ler_texto(caminho: Path) -> str:
    """
    Lê sempre em UTF-8, nunca na codificação do sistema.

    No Windows em português o padrão é cp1252, e o campo `nome` com acento
    voltaria diferente do que foi gravado — ou estouraria na leitura.
    """
    try:
        return caminho.read_text(encoding="utf-8")
    except UnicodeDecodeError as erro:
        raise FichaInvalidaError(
            f"{caminho} não está em UTF-8.\n"
            "O FlatCap sempre grava em UTF-8; um arquivo salvo por outro programa "
            "com codificação diferente precisa ser convertido antes.\n"
            f"Detalhe técnico: {erro}",
            caminho,
        ) from erro


def escrever_atomico(caminho: Path, texto: str) -> None:
    """
    Grava o arquivo inteiro ou não grava nada.

    Pública desde a Fase 4: o `dicionario.csv` guarda as decisões da reunião e o
    `perfil.md` é o documento que você leva para ela. Os dois merecem a mesma
    garantia que o `projeto.yaml`, e duas implementações de escrita atômica no
    mesmo pacote é como uma delas deixa de receber a próxima correção.

    O temporário é criado **na mesma pasta** do destino de propósito: `os.replace`
    só é atômico dentro do mesmo sistema de arquivos, e um temporário em `/tmp`
    poderia estar em outro disco — aí a troca vira cópia, que pode falhar pela
    metade. O `fsync` força o conteúdo para o disco antes da troca; sem ele, uma
    queda de energia logo depois pode deixar o nome novo apontando para um
    arquivo vazio.
    """
    caminho = Path(caminho)
    descritor, temporario = temporario_ao_lado(caminho)
    try:
        with open(descritor, "w", encoding="utf-8", newline="\n") as arquivo:
            arquivo.write(texto)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    except BaseException:
        temporario.unlink(missing_ok=True)
        raise


def temporario_ao_lado(destino: Path) -> tuple[int, Path]:
    """
    Cria um arquivo vazio, de nome único, na pasta do destino. Devolve o
    descritor aberto para escrita e o caminho.

    O modo pedido é `0o666`, e o sistema tira dele o `umask` do processo — o que
    acontece com qualquer arquivo que um programa cria. Até a 1.13.0 quem criava
    o temporário era o `tempfile.NamedTemporaryFile`, que usa `0o600` de propósito
    (um temporário não é para mais ninguém ler), e o `os.replace` levava esse modo
    para o destino: todo `projeto.yaml`, `dicionario.csv`, `perfil.md`, tabela,
    manifesto e `.docx` saía legível só pelo dono. Num `FLATCAP_ROOT` dividido pela
    equipe num servidor Linux ou num Mac, os colegas não abriam nada. No Windows
    quem decide é a permissão da pasta, e nada mudou por lá.

    Pública porque o `documento.py` grava o `.docx` atomicamente com o mesmo
    temporário — e duas formas de criá-lo é como uma delas fica com o defeito.
    """
    destino = Path(destino)
    # `O_BINARY` só existe no Windows: sem ele a biblioteca C trocaria cada `\n`
    # por `\r\n` na escrita, por baixo do `newline="\n"`.
    modo = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    for _ in range(100):
        temporario = destino.parent / f"{destino.name}.{secrets.token_hex(4)}.tmp"
        try:
            return os.open(temporario, modo, 0o666), temporario
        except FileExistsError:
            continue
    raise FileExistsError(f"Não consegui criar um temporário ao lado de {destino}.")


def _texto(documento, chave: str) -> str:
    valor = documento.get(chave)
    if valor is None:
        return ""
    return str(valor).strip()


def _versoes(documento, caminho: Path) -> tuple[Versao, ...]:
    """
    Traduz a lista `dados:` para objetos, recusando o que não dá para interpretar.
    """
    bruto = documento.get(CHAVE_DADOS)
    if bruto is None:
        return ()
    if not isinstance(bruto, list):
        raise FichaInvalidaError(
            f"A chave `{CHAVE_DADOS}` de {caminho} deveria ser uma lista de "
            f"versões e é um {type(bruto).__name__}.",
            caminho,
        )

    versoes: list[Versao] = []
    for posicao, item in enumerate(bruto, start=1):
        if not isinstance(item, dict):
            raise FichaInvalidaError(
                f"A {posicao}ª entrada de `{CHAVE_DADOS}` em {caminho} não é um "
                "conjunto de campos. Cada versão precisa de `arquivo:`, `origem:`, "
                "`sha256:`, `tamanho_bytes:` e `data:`.",
                caminho,
            )
        versoes.append(
            Versao(
                arquivo=_texto(item, "arquivo"),
                origem=_texto(item, "origem"),
                sha256=_texto(item, "sha256").lower(),
                tamanho_bytes=_inteiro(item.get("tamanho_bytes")),
                data=_data(item.get("data")),
            )
        )
    return tuple(versoes)


def _inteiro(valor) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def _data(valor) -> date | None:
    """
    O YAML já entrega `date` quando a data está sem aspas. Com aspas vem texto,
    e é isso que esta função resgata — o arquivo é editado à mão, e digitar
    `data: "2026-03-14"` é natural.
    """
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor).strip()[:10])
    except ValueError:
        return None


def _diagnostico(texto: str, caminho: Path, erro: Exception) -> str:
    """
    Traduz o estouro do parser, com um caso especial que vale ouro.

    Versões do `flatcap novo` anteriores à 0.4.0 escreviam uma barra solta na
    primeira linha do arquivo (uma continuação de linha `\\` digitada como `/`
    no cabeçalho). O YAML gerado é sintaticamente impossível, e a mensagem crua
    do parser fala de `<document start>` — que não diz nada a quem abrir o
    arquivo e vir um `/` inofensivo na primeira linha.

    O `reparar_fichas.py`, que consertava todas as pastas de uma vez, foi
    aposentado quando a migração da Fase 3 terminou. Este diagnóstico **não** vai
    junto: a ficha quebrada reaparece toda vez que alguém restaura uma pasta de um
    backup anterior à 0.4.0, e aí o conserto é manual — e precisa estar escrito
    aqui, porque não há mais script para indicar.
    """
    primeira = next((linha for linha in texto.splitlines() if linha.strip()), "")
    if primeira.strip() == "/":
        return (
            f"{caminho} começa com uma barra solta na primeira linha.\n\n"
            "É um defeito conhecido das versões do `flatcap novo` anteriores à "
            "0.4.0: o cabeçalho de comentários saía com um `/` antes do primeiro "
            "`#`, e isso torna o arquivo inteiro ilegível.\n\n"
            "Conserto: abra o arquivo em um editor de texto, apague a primeira "
            "linha — a que contém só `/` — e salve em UTF-8. A barra é a única "
            "coisa errada; o resto da ficha está intacto.\n\n"
            f"Detalhe técnico: {erro}"
        )
    return (
        f"{caminho} não é um YAML válido.\n\n"
        "Isso costuma ser edição à mão: indentação com tabulação em vez de "
        "espaços, dois-pontos dentro de um valor sem aspas (`nome: Fulano: o "
        "Segundo`) ou um alias `*id001` que ficou órfão.\n\n"
        f"Detalhe técnico: {erro}"
    )
