# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
O que mais de um arquivo de teste usa.

Três regras que valem para a pasta inteira, e cada uma existe por um motivo que
já custou caro neste projeto:

**Um módulo em `src/flatcap/` pede um `test_` de mesmo nome.** Um teste novo tem
exatamente um lugar possível, e ninguém precisa lembrar de disciplina nenhuma
para acertar. A desordem que os ajustes pós-Fase 3 arrumaram nasceu de cada fase
recriar os próprios ajudantes.

**Nada aqui toca a rede.** A suíte offline roda com `REDCAP_TOKEN` inválido de
propósito: os comandos das Fases 3 a 6 não podem falhar por token expirado, e a
única forma de garantir isso é nunca dar a eles um token que funcione.

**O relógio é injetado, nunca lido.** Todo `preparar*` aceita `agora=`. Um teste
que compara nome de arquivo com data é um teste que quebra à meia-noite.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from flatcap import projeto
from flatcap.ficha import ARQUIVO_PROJETO, Ficha, Versao

if TYPE_CHECKING:  # o `pandas` só entra quando um teste monta um banco
    import pandas as pd

    from flatcap.banco import Banco

# O relógio de toda a suíte. Fixo, e com hora que não é meia-noite, para que um
# `%H%M` errado apareça em vez de sair `0000` por acidente.
AGORA = datetime(2026, 9, 9, 14, 30, 0)
HOJE = AGORA.date()

MATRICULA = "00742"
RECORD_ID = "42"
NOME = "José Antônio de Sá"
PASTA = f"{MATRICULA} - {NOME}"  # a pasta do CLIENTE

# A pasta do PROJETO, um nível abaixo da do cliente — o layout da 1.1.0.
#
# Escrita à mão, e não com `nomes.nome_do_projeto(RECORD_ID)`, pelo mesmo motivo
# do `escrever_ficha`: um fixture que usa a regra do pacote só prova que o pacote
# concorda consigo mesmo. Se o nome da pasta mudar de formato, é aqui que o teste
# precisa quebrar.
PROJETO = "Projeto 042"

# A primeira página do relatório, como o `flatcap novo` a traz do formulário.
# Preenchidas por padrão: uma ficha sem as duas faz todo relatório da suíte sair
# com o alerta `texto_ausente`, e aí o teste de "rodada atual não gera alerta"
# mede a ficha do fixture em vez da rodada. Quem quer a ficha sem elas passa
# `None` — é o que `test_relatorio.py` faz para conferir o próprio alerta.
FINALIDADE = "Artigo científico"
OBJETIVOS = "Objetivo geral: descrever o perfil dos pacientes atendidos."


# ── Ambiente ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch, tmp_path):
    """
    Nenhum teste enxerga o `.env` da máquina nem o `FLATCAP_ROOT` de verdade.

    `autouse` de propósito: a variável de ambiente é estado global, e um teste
    que esquece de limpá-la contamina os seguintes de um jeito que depende da
    ordem de execução — o defeito mais caro de diagnosticar numa suíte.
    """
    for chave in ("REDCAP_API_URL", "REDCAP_TOKEN", "FLATCAP_ROOT"):
        monkeypatch.delenv(chave, raising=False)
    # `find_dotenv` sobe a árvore a partir do diretório atual: se a suíte rodar
    # da raiz do repositório, ela acharia o `.env` de verdade.
    monkeypatch.chdir(tmp_path)
    # E o `.env` da sua conta é o terceiro degrau da procura desde a 1.13.1: sem
    # isto, a suíte leria o que você criou com `flatcap doctor --criar-env`.
    monkeypatch.setattr(
        "flatcap.config.pasta_de_configuracao", lambda: tmp_path / "configuracao-da-conta"
    )
    return tmp_path


@pytest.fixture
def root(tmp_path) -> Path:
    """
    Um `FLATCAP_ROOT` vazio.
    """
    caminho = tmp_path / "FlatCapRoot"
    caminho.mkdir()
    return caminho


@pytest.fixture
def env_valido(monkeypatch, root) -> Path:
    """
    As três chaves preenchidas, com um token que **não funciona**.

    O token inválido é o ponto: os comandos das Fases 3 a 6 não falam com o
    REDCap, e um teste que lhes dá credencial boa não prova nada.
    """
    monkeypatch.setenv("REDCAP_API_URL", "https://exemplo.invalido/redcap/api/")
    monkeypatch.setenv("REDCAP_TOKEN", "0" * 32)
    monkeypatch.setenv("FLATCAP_ROOT", str(root))
    return root


# ── Uma pasta de projeto pronta ─────────────────────────────────────────────


def escrever_ficha(
    raiz: Path,
    *,
    record_id: str = RECORD_ID,
    matricula: str = MATRICULA,
    nome: str = NOME,
    tipo: str = "professor",
    status: str = "em andamento",
    prazo: str = "null",
    finalidade: str | None = FINALIDADE,
    objetivos: str | None = OBJETIVOS,
    dados: list[dict] | None = None,
    cabecalho: str = "# projeto.yaml — a ficha deste atendimento.\n",
) -> Path:
    """
    Escreve um `projeto.yaml` à mão, sem passar pelo `projeto.py`.

    À mão de propósito: um teste do leitor que usa o escritor do próprio pacote
    só prova que os dois concordam entre si. O formato que precisa ser lido é o
    que está no disco de um projeto de verdade — inclusive o editado por você.

    `status` e `prazo` entram como se digitam no editor, sem aspas: `prazo` é o
    texto da linha, e `2026-11-04` e `04/11/2026` chegam ao leitor como o YAML os
    entrega — uma data e um texto.
    """
    linhas = [
        cabecalho,
        f"record_id: '{record_id}'",
        f"tipo: {tipo}",
        f"matricula: '{matricula}'",
        f"nome: {nome}",
        f"criado_em: {HOJE.isoformat()}",
        f"prazo: {prazo}",
        f"status: {status}",
        f"finalidade: {_texto_yaml(finalidade)}",
        f"objetivos: {_texto_yaml(objetivos)}",
        "analises: []",
    ]
    if dados:
        linhas.append("dados:")
        for versao in dados:
            linhas.append(f"  - arquivo: {versao['arquivo']}")
            linhas.append(f"    origem: {versao['origem']}")
            linhas.append(f"    sha256: {versao['sha256']}")
            linhas.append(f"    tamanho_bytes: {versao['tamanho_bytes']}")
            linhas.append(f"    data: {versao['data']}")
    else:
        linhas.append("dados: []")

    caminho = raiz / ARQUIVO_PROJETO
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8", newline="\n")
    return caminho


def _texto_yaml(valor: str | None) -> str:
    """
    `null` para o campo vazio; entre aspas simples para o resto.

    Aspas porque a finalidade e os objetivos são prosa do cliente, e prosa tem
    `:` no meio — `Objetivo geral: descrever` sem aspas é um YAML que não abre.
    """
    if valor is None:
        return "null"
    return "'" + valor.replace("'", "''") + "'"


def sha_e_tamanho(caminho: Path) -> tuple[str, int]:
    bruto = Path(caminho).read_bytes()
    return hashlib.sha256(bruto).hexdigest(), len(bruto)


@pytest.fixture
def projeto_vazio(root) -> Path:
    """
    A pasta do projeto com as três subpastas, a ficha e o histórico — sem banco.

    É o estado em que o `flatcap novo` deixa um registro cujo REDCap não trouxe
    anexo, e é o ponto de partida do `dados adicionar`.

    Dois níveis, desde a 1.1.0: `root/<cliente>/<projeto>/projeto.yaml`. Até a
    revisão 1.3.1 este fixture montava a ficha na pasta do cliente, que é o
    layout que o `ficha.localizar_projeto` passou a recusar com
    `LayoutAntigoError` — e era a origem isolada de trinta falhas da suíte.
    """
    raiz = root / PASTA / PROJETO
    raiz.mkdir(parents=True)
    for subpasta in projeto.SUBPASTAS:
        (raiz / subpasta).mkdir()
    escrever_ficha(raiz)
    (raiz / projeto.ARQUIVO_HISTORICO).write_text(
        f"# Histórico — {PASTA} · {PROJETO}\n\n"
        "Uma linha por ação do FlatCap nesta pasta.\n\n",
        encoding="utf-8",
        newline="\n",
    )
    return raiz


@pytest.fixture
def projeto_com_banco(projeto_vazio, bancos):
    """
    A pasta com o `00_redcap_*` já registrado na ficha, como o `novo` a deixa.

    Devolve uma função: cada teste escolhe qual banco quer lá dentro sem que a
    suíte precise de uma fixture por formato.
    """

    def montar(quadro=None, nome: str = "00_redcap_2026-09-01_banco.csv") -> Path:
        quadro = bancos.completo() if quadro is None else quadro
        destino = projeto_vazio / projeto.PASTA_DADOS / nome
        if nome.endswith(".xlsx"):
            quadro.to_excel(destino, index=False)
        else:
            quadro.to_csv(destino, sep=";", index=False, encoding="utf-8")
        sha, tamanho = sha_e_tamanho(destino)
        escrever_ficha(
            projeto_vazio,
            dados=[
                {
                    "arquivo": nome,
                    "origem": "redcap",
                    "sha256": sha,
                    "tamanho_bytes": tamanho,
                    "data": "2026-09-01",
                }
            ],
        )
        return projeto_vazio

    return montar


@pytest.fixture
def bancos():
    """
    Os bancos de mentira, como módulo, para não repetir o import em cada arquivo.
    """
    import bancos as modulo

    return modulo


# ── O que as funções puras recebem ──────────────────────────────────────────


def banco_em_memoria(quadro: pd.DataFrame) -> Banco:
    """
    Um `Banco` montado em volta de um `DataFrame`, sem arquivo nenhum.

    É o que o miolo de cada análise recebe — `descrever`, `avaliar`, `cruzar` — e
    o que permite afirmar sobre uma tabela sem pasta de projeto e sem disco. Até a
    1.4.0 havia uma cópia em `test_descritiva.py` e outra em `test_normalidade.py`,
    com um aviso no topo do segundo para trocá-la pela daqui; a terceira análise
    era a hora de ele ter um lugar só.
    """
    from flatcap.banco import Banco, Leitura

    caminho = Path(projeto.PASTA_DADOS) / "00_redcap_2026-09-01_banco.csv"
    return Banco(
        quadro=quadro,
        versao=Versao(
            arquivo=caminho.name, origem="redcap", sha256="a" * 64, tamanho_bytes=1024
        ),
        leitura=Leitura(caminho=caminho, separador=";", codificacao="utf-8"),
        confere=True,
    )


def ficha_em_memoria(raiz: Path | None = None) -> Ficha:
    """
    A `Ficha` que acompanha o `banco_em_memoria`.

    A raiz padrão é a do `projeto_vazio`, em dois níveis, e nunca é criada: nada
    que recebe esta ficha escreve no disco. Ela aparece só no manifesto — `pasta`
    e `cliente` —, e é por isso que ela tem a forma da pasta de verdade.
    """
    return Ficha(
        raiz=raiz or Path("FlatCapRoot") / PASTA / PROJETO,
        record_id=RECORD_ID,
        matricula=MATRICULA,
        nome=NOME,
        tipo="professor",
        status="em andamento",
        dados=(),
    )


def acrescentar_a_ficha(raiz: Path, texto: str) -> Path:
    """
    Acrescenta YAML ao fim do `projeto.yaml`, do jeito que você faria no editor.

    Texto, e não uma lista que o teste monta: a lista `cruzamento:` e a
    `normalidade:` são escritas à mão na reunião, e o que precisa ser testado é o
    que se digita — `- [sexo, escolaridade]`, com o recuo que a pessoa escolher.
    """
    caminho = Path(raiz) / ARQUIVO_PROJETO
    atual = caminho.read_text(encoding="utf-8")
    caminho.write_text(
        atual.rstrip("\n") + "\n" + texto.strip("\n") + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return caminho


def marcar_numericas(raiz: Path, *nomes: str) -> Path:
    """
    Marca as variáveis `numerica` no `dicionario.csv`, como se faz na reunião.

    O `perfil` propõe `categorica` para inteiros pequenos que se repetem — a dor de 0
    a 4 tem a cara de um código —, e é a pessoa quem diz que ela é uma escala: troca
    o `tipo` e apaga a `categorias_ordem`, que numérica não tem.
    """
    caminho = Path(raiz) / "dicionario.csv"
    linhas = caminho.read_text(encoding="utf-8-sig").splitlines()
    faltam = set(nomes)
    for i, linha in enumerate(linhas):
        campos = linha.split(";")
        if campos[0] in faltam:
            campos[2], campos[3] = "numerica", ""
            linhas[i] = ";".join(campos)
            faltam.discard(campos[0])
    assert not faltam, f"o dicionário não tem {sorted(faltam)}"
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8-sig", newline="\n")
    return caminho


def escrever_analises(raiz: Path, texto: str) -> Path:
    """
    Troca a linha `analises: []` da ficha pelo que você escreveria na reunião.

    Troca, e não acrescenta como o `acrescentar_a_ficha`: a ficha do `flatcap novo`
    e a do `escrever_ficha` já trazem a chave vazia, e o YAML recusa a mesma chave
    duas vezes. `texto` é a linha inteira, como se digita — `analises: [descritiva,
    normalidade]`, ou a chave com um nome por linha.
    """
    caminho = Path(raiz) / ARQUIVO_PROJETO
    atual = caminho.read_text(encoding="utf-8")
    assert "\nanalises: []\n" in atual, "a ficha não tem a linha `analises: []` para trocar"
    caminho.write_text(
        atual.replace("\nanalises: []\n", "\n" + texto.strip("\n") + "\n", 1),
        encoding="utf-8",
        newline="\n",
    )
    return caminho


# ── Uma rodada de descritiva pronta ─────────────────────────────────────────


@pytest.fixture
def projeto_com_rodada(projeto_com_banco):
    """
    Projeto com `dicionario.csv`, `perfil.md` e uma rodada de descritiva escrita.

    É o insumo do `relatorio`, e montá-lo rodando as Fases 4 e 5 de verdade é
    deliberado: um manifesto escrito à mão testaria o leitor contra a ideia que
    o teste faz do formato, e não contra o formato que a Fase 5 escreve.
    """

    def montar(quadro=None, agora: datetime = AGORA) -> Path:
        from flatcap.descritiva import executar_descritiva, preparar_descritiva
        from flatcap.perfil import executar_perfil, preparar_perfil

        raiz = projeto_com_banco(quadro)
        executar_perfil(preparar_perfil(raiz, agora=agora))
        executar_descritiva(preparar_descritiva(raiz, agora=agora))
        return raiz

    return montar


@pytest.fixture
def pasta_da_rodada():
    def caminho(raiz: Path) -> Path:
        return raiz / projeto.PASTA_ANALISES / projeto.PASTA_DESCRITIVA

    return caminho


# ── Registros do REDCap ─────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def registros() -> list[dict]:
    """
    Os registros anonimizados, lidos do fixture.

    Anonimizados de verdade — matrículas e nomes fictícios —, mas com as
    esquisitices reais preservadas: acento, nome composto, `intro` em branco,
    anexo ausente, espaço sobrando. São elas que quebram o código.
    """
    caminho = Path(__file__).parent / "fixtures" / "registros.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


# ── Auxiliares que valem para vários arquivos ───────────────────────────────


@pytest.fixture
def sem_modulo(monkeypatch):
    """
    Esconde uma biblioteca instalada, para testar o caminho de "falta isso aqui".

    O `doctor` só falhou em produção porque a máquina que roda os testes é a
    única em que o `matplotlib` nunca falta. Esta fixture é o conserto disso.
    """
    import builtins

    original = builtins.__import__

    def esconder(*nomes: str) -> None:
        alvos = set(nomes)

        def falso_import(nome, *args, **kwargs):
            if nome in alvos or nome.split(".")[0] in alvos:
                raise ImportError(f"No module named {nome!r} (escondido pelo teste)")
            return original(nome, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", falso_import)
        for nome in list(alvos):
            monkeypatch.delitem(__import__("sys").modules, nome, raising=False)

    return esconder


@pytest.fixture
def congelar_relogio(monkeypatch):
    """
    Para os poucos lugares que ainda chamam `datetime.now()` sem `agora=`.

    Se um teste precisar desta fixture para um `preparar*`, é sinal de que
    aquele `preparar*` esqueceu o parâmetro — e isso é um achado, não um
    contorno.
    """

    def congelar(quando: datetime = AGORA):
        class Relogio(datetime):
            @classmethod
            def now(cls, tz=None):  # noqa: ARG003
                return quando

        for modulo in (
            "amostragem", "analises", "associacao", "comparacao", "correlacao",
            "cruzamento", "dados", "descritiva", "normalidade", "painel", "perfil",
            "projeto", "relatorio",
        ):
            alvo = __import__(f"flatcap.{modulo}", fromlist=["datetime"])
            if hasattr(alvo, "datetime"):
                monkeypatch.setattr(alvo, "datetime", Relogio)
        return quando

    return congelar


def linhas_do_historico(raiz: Path) -> list[str]:
    """
    As linhas de log do `historico.md`, sem o cabeçalho.

    Todo comando que escreve acrescenta uma; é a tarefa da Fase 8 que já vale
    para os seis, e o jeito de não deixá-la apodrecer é conferi-la em cada
    `test_cli`.
    """
    texto = (raiz / projeto.ARQUIVO_HISTORICO).read_text(encoding="utf-8")
    return [linha for linha in texto.splitlines() if linha.startswith("- **")]


def bytes_iguais(a: Path, b: Path) -> bool:
    return Path(a).read_bytes() == Path(b).read_bytes()


__all__ = [
    "AGORA",
    "FINALIDADE",
    "HOJE",
    "MATRICULA",
    "NOME",
    "OBJETIVOS",
    "PASTA",
    "PROJETO",
    "RECORD_ID",
    "acrescentar_a_ficha",
    "banco_em_memoria",
    "bytes_iguais",
    "escrever_analises",
    "escrever_ficha",
    "ficha_em_memoria",
    "linhas_do_historico",
    "sha_e_tamanho",
]
