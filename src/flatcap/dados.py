"""
Versionamento dos bancos de dados de um projeto.

Responde ao passo 3c do fluxo: conviver com a versão que veio do REDCap e a
versão revisada que o cliente manda depois da reunião, sem nunca perder o rastro
de qual é qual.

Segue o mesmo padrão da Fase 2 — decidir e escrever são funções separadas:

    plano = preparar_adicao(root, identificador, caminho)  # só lê
    executar_adicao(plano)                                 # só escreve

E a diferença que vale registrar em relação à Fase 2: **nada aqui fala com o
REDCap**. A pasta do projeto já sabe de quem ela é, e a resposta está no
`projeto.yaml`. Por isso as funções recebem `root: Path` e não `Config`: um
comando que só mexe em arquivo local não deve poder falhar por token expirado.

## As três regras que sustentam a cronologia

1. **O `00_redcap_*` nunca se move e nunca se apaga.** Há uma verificação
   explícita antes de qualquer rotação, e um teste com o nome disso.

2. **O número do prefixo é o índice da versão e nunca se repete.** A primeira
   revisão é `01_`, a segunda `02_`, a terceira `03_`. `1. Dados originais/`
   fica sempre com o `00_redcap_*` e a versão vigente; `2. Versões antigas/`
   acumula as anteriores em ordem. É um desvio deliberado do texto do roteiro,
   que escreve `01_revisado_` sempre: com o número fixo, duas versões diferentes
   levariam o mesmo prefixo e a ordem passaria a depender só da data no nome —
   que empata quando o cliente reenvia duas vezes no mesmo dia.

3. **Reenvio idêntico não vira versão.** O `sha256` do arquivo é comparado com o
   de todas as versões já registradas antes de qualquer escrita. É exatamente a
   pergunta que o roteiro levanta: "o arquivo que o cliente reenviou é realmente
   diferente do anterior, ou ele mandou o mesmo de novo?".
"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .ficha import (
    Ficha,
    FichaError,
    Versao,
    acrescentar_versao,
    ler,
    localizar_projeto,
    sequencia_do_nome,
)
from .nomes import sanitizar
from .projeto import (
    EXTENSOES_DE_BANCO,
    PASTA_ANTIGAS,
    PASTA_DADOS,
    anotar,
    tamanho_legivel,
)

ORIGEM_REDCAP = "redcap"
ORIGEM_PADRAO = "cliente_pos_reuniao"

ROTULO_REVISADO = "revisado"

SEQUENCIA_REDCAP = 0
SEQUENCIA_MAXIMA = 99  # o prefixo tem dois dígitos

_BLOCO = 1024 * 1024  # 1 MiB por leitura ao calcular o hash


class DadosError(RuntimeError):
    """
    Falha ao versionar um banco, já traduzida para o usuário.
    """


class ArquivoOrigemError(DadosError):
    """
    O arquivo que você mandou registrar não serve — não existe, é uma pasta,
    está vazio ou já está dentro do próprio projeto.
    """


class VersaoDuplicadaError(DadosError):
    """
    O arquivo é byte a byte idêntico a uma versão já registrada.

    Não é erro: é a resposta certa para "ele reenviou o mesmo arquivo". Sai com
    código 0, como a pasta já existente da Fase 2, para não quebrar script.
    """

    def __init__(self, mensagem: str, versao: Versao) -> None:
        super().__init__(mensagem)
        self.versao = versao


class DestinoOcupadoError(DadosError):
    """
    O nome calculado para a versão nova já existe no disco.
    """


@dataclass(frozen=True)
class PlanoDados:
    """
    Tudo o que o `dados adicionar` faria, decidido e ainda não escrito.

    Imutável, como o `Plano` da Fase 2, e pela mesma razão: entre a simulação e a
    execução ninguém altera um caminho em trânsito. A árvore que aparece no
    terminal é lida deste objeto, não de uma lista escrita à parte — é isso que
    faz a simulação valer alguma coisa.
    """

    ficha: Ficha
    origem: Path
    destino: Path
    sequencia: int
    sha256: str
    tamanho: int
    rotacoes: tuple[tuple[Path, Path], ...]
    versao: Versao
    quando: datetime

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def tamanho_legivel(self) -> str:
        return tamanho_legivel(self.tamanho)


@dataclass(frozen=True)
class ResultadoDados:
    """
    O que a execução de fato fez.
    """

    criados: tuple[Path, ...] = ()
    movidos: tuple[tuple[Path, Path], ...] = ()
    avisos: tuple[str, ...] = ()


@dataclass(frozen=True)
class ItemDaLinha:
    """
    Uma versão registrada, confrontada com o que está de fato no disco.
    """

    versao: Versao
    caminho: Path | None
    local: str
    confere: bool | None  # None = não conferido, ou arquivo ausente

    @property
    def presente(self) -> bool:
        return self.caminho is not None


@dataclass(frozen=True)
class LinhaDoTempo:
    """
    A cronologia das versões, mais as divergências entre a ficha e o disco.
    """

    ficha: Ficha
    itens: tuple[ItemDaLinha, ...]
    nao_registrados: tuple[Path, ...]
    conferido: bool

    @property
    def ausentes(self) -> tuple[ItemDaLinha, ...]:
        return tuple(item for item in self.itens if not item.presente)

    @property
    def alterados(self) -> tuple[ItemDaLinha, ...]:
        return tuple(item for item in self.itens if item.confere is False)

    @property
    def integra(self) -> bool:
        return not (self.ausentes or self.alterados or self.nao_registrados)


# Caso de uso: adicionar uma versão


def preparar_adicao(
    root: Path,
    identificador: str,
    caminho: Path | str,
    agora: datetime | None = None,
    origem_rotulo: str = ORIGEM_PADRAO,
) -> PlanoDados:
    """
    Decide tudo o que a adição faria. Não escreve nada, não move nada.

    Args:
        root: o `FLATCAP_ROOT`.
        identificador: `record_id` ou matrícula.
        caminho: o arquivo revisado, onde quer que ele esteja.
        agora: relógio injetável — sem ele os testes não teriam como comparar o
            nome do arquivo, que carrega a data.

    Raises:
        ProjetoNaoEncontradoError, FichaAusenteError, FichaInvalidaError,
        ArquivoOrigemError, VersaoDuplicadaError, DestinoOcupadoError
    """
    quando = agora or datetime.now()
    raiz = localizar_projeto(Path(root), identificador)
    ficha = ler(raiz)

    origem = _conferir_origem(caminho, raiz)
    sha256, tamanho = _hash_e_tamanho(origem)

    _recusar_duplicata(ficha, sha256)

    sequencia = _proxima_sequencia(ficha, raiz)
    destino = raiz / PASTA_DADOS / _nome_da_versao(sequencia, origem.name, quando.date())

    if destino.exists():
        raise DestinoOcupadoError(
            f"Já existe um arquivo com o nome calculado para esta versão:\n"
            f"  {destino}\n"
            "Nada foi alterado. Isso quer dizer que o disco tem um arquivo que a "
            "ficha não conhece — rode `flatcap dados listar` para ver a divergência."
        )

    return PlanoDados(
        ficha=ficha,
        origem=origem,
        destino=destino,
        sequencia=sequencia,
        sha256=sha256,
        tamanho=tamanho,
        rotacoes=_rotacoes(raiz),
        versao=Versao(
            arquivo=destino.name,
            origem=origem_rotulo,
            sha256=sha256,
            tamanho_bytes=tamanho,
            data=quando.date(),
        ),
        quando=quando,
    )


def executar_adicao(plano: PlanoDados) -> ResultadoDados:
    """
    Escreve o plano no disco. Não decide mais nada.

    A ordem das operações não é arbitrária. A cópia do arquivo novo vem primeiro
    porque é a etapa lenta e a que mais tem como falhar (espaço em disco, unidade
    de rede, nuvem sincronizando). Se o processo morrer entre a cópia e a
    rotação, o estado que fica no disco é "as duas versões estão em
    `1. Dados originais/`" — nada foi perdido, e o `dados listar` mostra
    exatamente isso. A ordem inversa deixaria a versão de trabalho já arquivada e
    a nova ainda não escrita, que assusta muito mais ao abrir a pasta.

    Quando dá para desfazer, desfaz: cada etapa registra como voltar atrás, e uma
    falha no meio reverte o que já foi feito antes de propagar o erro.
    """
    criados: list[Path] = []
    movidos: list[tuple[Path, Path]] = []
    avisos: list[str] = []
    desfazer: list[Callable[[], None]] = []

    try:
        pasta_antigas = plano.raiz / PASTA_ANTIGAS
        if not pasta_antigas.exists():
            pasta_antigas.mkdir(parents=True)
            criados.append(pasta_antigas)
            desfazer.append(lambda p=pasta_antigas: p.rmdir())

        # 1. A versão nova, copiada (nunca movida: o arquivo do cliente continua
        #    onde ele estava, na sua pasta de downloads ou no anexo do e-mail).
        shutil.copy2(plano.origem, plano.destino)
        criados.append(plano.destino)
        desfazer.append(lambda p=plano.destino: p.unlink(missing_ok=True))

        # 2. Conferência do que foi escrito. Um `sha256` gravado na ficha sobre
        #    uma cópia truncada seria um recibo falso — pior do que recibo nenhum.
        gravado, _ = _hash_e_tamanho(plano.destino)
        if gravado != plano.sha256:
            raise DadosError(
                "A cópia saiu diferente do original.\n"
                f"  esperado: {plano.sha256}\n"
                f"  no disco: {gravado}\n"
                "Nada foi registrado e o arquivo copiado foi removido. Isso costuma "
                "ser o arquivo de origem sendo alterado durante a cópia (planilha "
                "aberta no Excel) ou disco cheio."
            )

        # 3. Rotação da versão anterior. Renomear dentro da mesma pasta de projeto
        #    é operação de sistema de arquivos, instantânea e sem cópia.
        for de, para in plano.rotacoes:
            de.rename(para)
            movidos.append((de, para))
            desfazer.append(lambda d=de, p=para: p.rename(d))

        # 4. A ficha. Escrita atômica, dentro de `ficha.py`.
        acrescentar_versao(plano.raiz, plano.versao)

        # 5. O histórico. Última porque é a única etapa que, se falhar, não
        #    invalida nada: o registro está na ficha, e a linha do histórico é
        #    conveniência de leitura.
        try:
            anotar(plano.raiz, _acao_do_historico(plano), plano.quando)
        except OSError as erro:
            avisos.append(
                f"A versão foi registrada, mas não consegui escrever no "
                f"historico.md: {erro}"
            )

    except (OSError, DadosError, FichaError):
        for passo in reversed(desfazer):
            try:
                passo()
            except OSError:
                avisos.append(
                    "Falhei ao desfazer uma etapa. Confira a pasta do projeto "
                    "antes de rodar de novo."
                )
        raise

    return ResultadoDados(
        criados=tuple(criados), movidos=tuple(movidos), avisos=tuple(avisos)
    )


# Caso de uso: a linha do tempo


def linha_do_tempo(raiz: Path, conferir: bool = True) -> LinhaDoTempo:
    """
    Confronta a lista `dados:` da ficha com o que está de fato no disco.

    Não basta imprimir a ficha. A ficha diz o que foi registrado; a pergunta do
    critério de pronto — "dá para reconstruir a cronologia sem depender da minha
    memória?" — só tem resposta se o que está registrado for confrontado com o
    que existe. Três divergências aparecem aqui:

    * **ausente**: a ficha registra um arquivo que não está mais no disco;
    * **alterado**: o arquivo está lá, mas o `sha256` não é mais o registrado —
      alguém abriu e salvou por cima;
    * **não registrado**: há arquivo na pasta que a ficha desconhece **e que
      poderia ser um banco** — ver `e_candidato_a_banco`.

    A conferência de `sha256` é o padrão porque, nesta configuração, só o
    `00_redcap_*` é somente-leitura: as versões revisadas continuam editáveis, e
    a releitura do hash é o que transforma "editei sem querer" em algo visível.
    Use `conferir=False` quando os bancos forem grandes e você só quiser a lista.
    """
    ficha = ler(Path(raiz))
    pastas = (Path(raiz) / PASTA_DADOS, Path(raiz) / PASTA_ANTIGAS)

    presentes: dict[str, Path] = {}
    for pasta in pastas:
        if not pasta.is_dir():
            continue
        for arquivo in sorted(pasta.iterdir()):
            if arquivo.is_file() and not arquivo.name.startswith("."):
                presentes.setdefault(arquivo.name, arquivo)

    itens: list[ItemDaLinha] = []
    for versao in ficha.dados:
        caminho = presentes.pop(versao.arquivo, None)
        if caminho is None:
            itens.append(ItemDaLinha(versao, None, "ausente", None))
            continue
        confere: bool | None = None
        if conferir:
            atual, _ = _hash_e_tamanho(caminho)
            confere = atual == versao.sha256
        itens.append(ItemDaLinha(versao, caminho, caminho.parent.name, confere))

    # O que sobrou de `presentes` é o que a ficha não conhece — e nem tudo o que
    # a ficha não conhece é banco. As duas pastas guardam outras coisas: o
    # `Relatorio_*.docx` que o `flatcap relatorio` arquiva, um `.txt` de
    # anotações. O filtro fica **aqui**, e não na varredura acima, porque a
    # varredura também serve para encontrar as versões registradas: uma versão
    # com nome fora da convenção precisa continuar sendo achada no disco, em vez
    # de virar `ausente` por causa de um filtro.
    return LinhaDoTempo(
        ficha=ficha,
        itens=tuple(itens),
        nao_registrados=tuple(
            sorted(
                caminho
                for caminho in presentes.values()
                if e_candidato_a_banco(caminho)
            )
        ),
        conferido=conferir,
    )


def e_candidato_a_banco(caminho: Path) -> bool:
    """
    Este arquivo, achado na pasta de dados, poderia ser uma versão do banco?

    A pergunta existe porque `2. Versões antigas/` deixou de guardar só banco: a
    Fase 5 passou a arquivar lá a rodada anterior da descritiva e a Fase 6 o
    relatório anterior. Sem este filtro, o `Relatorio_00742_2026-09-20.docx` que
    o `flatcap relatorio` acabou de arquivar aparece no `flatcap dados listar`
    como «arquivo que a ficha não conhece» — um alarme que o FlatCap dispara
    contra si mesmo, e que ensina o usuário a ignorar a lista inteira.

    Duas formas de responder que sim, e basta uma:

    * **o nome segue a convenção** (`NN_`), que é como toda versão escrita pelo
      FlatCap se chama — inclusive uma que tenha perdido a extensão;
    * **a extensão é a de um banco**, que é o caso da planilha que você largou
      na pasta à mão e ainda não registrou. É justamente o que a mensagem de
      `banco._mensagem_sem_versao` existe para apontar, e por isso ela não pode
      ser filtrada aqui.
    """
    return (
        sequencia_do_nome(caminho.name) is not None
        or caminho.suffix.lower() in EXTENSOES_DE_BANCO
    )


# Backend


def _conferir_origem(caminho: Path | str, raiz: Path) -> Path:
    """
    Recusa, com o motivo, tudo o que não pode virar versão.
    """
    origem = Path(caminho).expanduser()

    if not origem.exists():
        raise ArquivoOrigemError(
            f"O arquivo não existe: {origem}\n"
            "Confira o caminho. Se ele tiver espaço no nome, ponha entre aspas."
        )
    if origem.is_dir():
        raise ArquivoOrigemError(
            f"{origem} é uma pasta. O `dados adicionar` registra um arquivo por vez."
        )
    if not origem.is_file():
        raise ArquivoOrigemError(f"{origem} não é um arquivo comum.")
    if origem.stat().st_size == 0:
        raise ArquivoOrigemError(
            f"O arquivo está vazio (0 bytes): {origem}\n"
            "Isso quase sempre é download interrompido ou anexo que não abriu. "
            "Nada foi registrado."
        )

    resolvido = origem.resolve()
    if resolvido == raiz.resolve() or raiz.resolve() in resolvido.parents:
        raise ArquivoOrigemError(
            f"Esse arquivo já está dentro da pasta do projeto:\n  {resolvido}\n"
            "O `dados adicionar` traz um arquivo de fora — do e-mail, da pasta de "
            "downloads, do pen drive. Registrar um arquivo que já está lá dentro "
            "criaria uma cópia dele com outro nome e duas entradas para a mesma "
            "versão.\n"
            "Se a intenção é registrar um arquivo que você largou na pasta à mão, "
            "mova-o para fora primeiro."
        )
    return origem


def _hash_e_tamanho(caminho: Path) -> tuple[str, int]:
    """
    Calcula o `sha256` lendo o arquivo em blocos, e devolve o tamanho junto.

    Ler em blocos e não de uma vez importa aqui e não importava na Fase 2: lá os
    bytes já vinham inteiros da rede; aqui a origem é um arquivo em disco que
    pode ter centenas de megabytes, e `read_bytes()` carregaria tudo na memória
    de uma vez só para calcular um hash de 32 bytes.
    """
    digestor = hashlib.sha256()
    tamanho = 0
    with open(caminho, "rb") as arquivo:
        while bloco := arquivo.read(_BLOCO):
            digestor.update(bloco)
            tamanho += len(bloco)
    return digestor.hexdigest(), tamanho


def _recusar_duplicata(ficha: Ficha, sha256: str) -> None:
    for versao in ficha.dados:
        if versao.sha256 and versao.sha256 == sha256:
            quando = f" ({versao.data:%d/%m/%Y})" if versao.data else ""
            raise VersaoDuplicadaError(
                f"Este arquivo é byte a byte idêntico a uma versão já "
                f"registrada:\n  {versao.arquivo}{quando}\n\n"
                "Nada foi alterado. O cliente reenviou o mesmo arquivo — o que é "
                "comum quando ele responde ao e-mail antigo em vez de mandar a "
                "planilha corrigida.",
                versao,
            )


def _proxima_sequencia(ficha: Ficha, raiz: Path) -> int:
    """
    O próximo número de versão: um a mais que o maior já usado.

    O maior é procurado na ficha **e** no disco. Só na ficha seria suficiente se
    nada além do FlatCap tocasse na pasta — e a premissa do projeto é a
    contrária, a de que a pasta é sua e você mexe nela. Um arquivo `03_` que
    exista no disco sem estar registrado precisa impedir que um novo `03_` seja
    criado, senão dois arquivos diferentes carregariam o mesmo índice.
    """
    usados = {
        versao.sequencia for versao in ficha.dados if versao.sequencia is not None
    }
    for pasta in (raiz / PASTA_DADOS, raiz / PASTA_ANTIGAS):
        if not pasta.is_dir():
            continue
        for arquivo in pasta.iterdir():
            numero = sequencia_do_nome(arquivo.name)
            if numero is not None:
                usados.add(numero)

    proxima = (max(usados) + 1) if usados else 1
    if proxima > SEQUENCIA_MAXIMA:
        raise DadosError(
            f"Este projeto chegou a {SEQUENCIA_MAXIMA} versões do banco, que é o "
            "limite do prefixo de dois dígitos. Antes de continuar, vale entender "
            "por que houve tantas revisões."
        )
    return proxima


def _rotacoes(raiz: Path) -> tuple[tuple[Path, Path], ...]:
    """
    Decide o que sai de `1. Dados originais/` e vai para `2. Versões antigas/`.

    Só entram arquivos que seguem a convenção de nome (`NN_`) e cujo número não
    é zero. As duas condições são deliberadas: o `00_redcap_*` é intocável por
    regra, e um arquivo com nome fora da convenção — um `notas.txt`, um
    `dicionario.csv` que você deixou ali — não é versão de banco e não deve ser
    movido por um comando que o usuário chamou para outra coisa.
    """
    pasta = raiz / PASTA_DADOS
    destino = raiz / PASTA_ANTIGAS
    if not pasta.is_dir():
        return ()

    pares: list[tuple[Path, Path]] = []
    for arquivo in sorted(pasta.iterdir()):
        if not arquivo.is_file():
            continue
        numero = sequencia_do_nome(arquivo.name)
        if numero is None or numero == SEQUENCIA_REDCAP:
            continue
        alvo = destino / arquivo.name
        if alvo.exists():
            raise DestinoOcupadoError(
                f"Já existe {arquivo.name} em {PASTA_ANTIGAS}.\n"
                "Como o número da versão nunca se repete, isso indica dois "
                "arquivos distintos com o mesmo índice. Nada foi alterado — "
                "resolva no disco antes de continuar."
            )
        pares.append((arquivo, alvo))
    return tuple(pares)


def _nome_da_versao(sequencia: int, nome_original: str, quando: date) -> str:
    """
    Monta `01_revisado_AAAA-MM-DD_<nome original>`.

    O nome original é preservado e passa pela mesma `sanitizar` das pastas — ele
    vem de fora, e o que vem de fora não monta caminho.
    """
    base = sanitizar(nome_original) or "banco"
    base = Path(base).name  # segunda barreira contra `../` no nome
    return f"{sequencia:02d}_{ROTULO_REVISADO}_{quando:%Y-%m-%d}_{base}"


def _acao_do_historico(plano: PlanoDados) -> str:
    partes = [
        f"`flatcap dados adicionar {plano.ficha.record_id}` — versão "
        f"`{plano.destino.name}` ({plano.tamanho_legivel}) registrada a partir de "
        f"`{plano.origem.name}`."
    ]
    for de, _ in plano.rotacoes:
        partes.append(f"`{de.name}` foi para `{PASTA_ANTIGAS}/`.")
    return " ".join(partes)
