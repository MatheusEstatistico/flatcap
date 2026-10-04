"""
Os testes do `analises.py` — o lote.

O critério de pronto do módulo é o primeiro teste deste arquivo: **o lote escreve,
byte a byte, o que os comandos escreveriam um por um.** Duas cópias da mesma pasta,
uma rodada pelo lote e a outra pelo `preparar_*` e pelo `executar_*` de cada análise,
e `3. Análises/` sai igual nas duas. Enquanto ele passar, o lote não tem uma segunda
forma de descrever, testar ou arquivar — e o dia em que uma análise mudar, ele muda
junto.

O resto é o que o lote acrescenta à soma: a lista conferida antes de tudo, as recusas
de todas de uma vez, o aviso do que ficou de fora, a linha do lote no histórico e a
frase de onde ele parou quando uma escrita falha no meio.

O banco é o `bancos.completo()` do `conftest`, com o dicionário que o `perfil`
escreve para ele: `sexo` e `escolaridade` categóricas, `idade` e `imc` numéricas.
"""

from __future__ import annotations

import inspect
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import (
    AGORA,
    PASTA,
    PROJETO,
    RECORD_ID,
    acrescentar_a_ficha,
    escrever_analises,
    linhas_do_historico,
)
from flatcap import projeto
from flatcap.analises import (
    REGISTRO,
    AnaliseDesconhecidaError,
    AnaliseRepetidaError,
    AnalisesRecusadasError,
    DicionarioDoLoteError,
    ListaMalEscritaError,
    ListaVaziaError,
    executar_analises,
    lista_da_ficha,
    preparar_analises,
)
from flatcap.ficha import ARQUIVO_PROJETO
from flatcap.ficha import ler as ler_ficha
from flatcap.manifesto import ARQUIVO_MANIFESTO, ORDEM_PADRAO_DAS_ANALISES
from flatcap.projeto import PASTA_ANALISES, PASTA_ANTIGAS

TODAS = "analises: [descritiva, normalidade, cruzamento, associacao, correlacao, comparacao]"

# Um bloco por análise que tem bloco, com o que o banco do `conftest` aceita.
BLOCOS = (
    "cruzamento:\n  - [sexo, escolaridade]\n"
    "associacao:\n  - [sexo, escolaridade]\n"
    "correlacao:\n  - [idade, imc]\n"
    "comparacao:\n  - [imc, 25]\n  - [imc, sexo]\n"
)

DEPOIS = AGORA.replace(hour=16)


@pytest.fixture
def projeto_para_o_lote(projeto_com_banco):
    """
    Projeto com banco, dicionário, a lista `analises:` e os blocos — e nenhuma rodada.

    Sem rodada de propósito: o critério do módulo compara o que o lote escreve com o
    que os comandos escreveriam, e as duas cópias precisam partir do mesmo lugar.
    """

    def montar(lista: str | None = TODAS, blocos: str = BLOCOS) -> Path:
        from flatcap.perfil import executar_perfil, preparar_perfil

        raiz = projeto_com_banco()
        executar_perfil(preparar_perfil(raiz, agora=AGORA))
        if lista is not None:
            escrever_analises(raiz, lista)
        if blocos:
            acrescentar_a_ficha(raiz, blocos)
        return raiz

    return montar


def _arquivos(raiz: Path) -> dict[str, bytes]:
    """Tudo o que está em `3. Análises/`, pelo caminho relativo, com os bytes."""
    pasta = raiz / PASTA_ANALISES
    return {
        str(caminho.relative_to(pasta)): caminho.read_bytes()
        for caminho in sorted(pasta.rglob("*"))
        if caminho.is_file()
    }


def _copia(raiz: Path, destino: Path) -> Path:
    """
    A mesma pasta de projeto em outro `FLATCAP_ROOT`, com os mesmos nomes.

    Os mesmos nomes porque o manifesto registra o cliente e o projeto pela pasta — é
    o recibo da rodada —, e duas pastas de nomes diferentes dariam manifestos
    diferentes por isso, e não pelo que se quer comparar.
    """
    copia = destino / PASTA / PROJETO
    shutil.copytree(raiz, copia)
    return copia


def _um_por_um(raiz: Path, nomes: tuple[str, ...], com_graficos: bool) -> None:
    """
    Cada análise pelo `preparar_*` e pelo `executar_*` dela, como o comando dela os
    chama — pelas funções do módulo, e não pelo registro do lote, que é justamente o
    que se quer conferir.
    """
    import importlib

    for nome in nomes:
        modulo = importlib.import_module(f"flatcap.{nome}")
        preparar = getattr(modulo, f"preparar_{nome}")
        executar = getattr(modulo, f"executar_{nome}")
        extras = (
            {"com_graficos": com_graficos}
            if "com_graficos" in inspect.signature(preparar).parameters
            else {}
        )
        executar(preparar(raiz, agora=AGORA, **extras))


# ── A soma dos comandos ─────────────────────────────────────────────────────


class TestASomaDosComandos:
    def test_o_lote_escreve_o_que_os_comandos_escreveriam(
        self, projeto_para_o_lote, tmp_path
    ):
        """
        O critério de pronto do módulo: as seis análises, e `3. Análises/` igual byte a
        byte — as tabelas, as notas dos `.csv` e os manifestos, com a hora deles.
        """
        lote = projeto_para_o_lote()
        um_por_um = _copia(lote, tmp_path / "um_por_um")

        executar_analises(preparar_analises(lote, com_graficos=False, agora=AGORA))
        _um_por_um(um_por_um, tuple(ORDEM_PADRAO_DAS_ANALISES), com_graficos=False)

        arquivos = _arquivos(lote)
        assert {caminho.split("/")[0] for caminho in arquivos} == set(
            ORDEM_PADRAO_DAS_ANALISES
        )
        assert arquivos == _arquivos(um_por_um)

    def test_com_os_graficos_tambem(self, projeto_para_o_lote, tmp_path):
        """
        Os `.png` também saem iguais byte a byte: o `matplotlib` não carimba data na
        figura. Só as duas análises de figura pequena — a 600 DPI, a descritiva
        inteira custaria segundos que a suíte já não tem.
        """
        lote = projeto_para_o_lote("analises: [normalidade, correlacao]")
        um_por_um = _copia(lote, tmp_path / "um_por_um")

        executar_analises(preparar_analises(lote, agora=AGORA))
        _um_por_um(um_por_um, ("normalidade", "correlacao"), com_graficos=True)

        arquivos = _arquivos(lote)
        assert any(caminho.endswith(".png") for caminho in arquivos)
        assert arquivos == _arquivos(um_por_um)

    def test_o_historico_e_a_soma_mais_a_linha_do_lote(self, projeto_para_o_lote, tmp_path):
        """
        Cada análise escreve a linha que o comando dela escreveria, e o lote acrescenta
        uma, por último, dizendo que foram uma execução só.
        """
        lote = projeto_para_o_lote()
        um_por_um = _copia(lote, tmp_path / "um_por_um")

        executar_analises(preparar_analises(lote, com_graficos=False, agora=AGORA))
        _um_por_um(
            um_por_um,
            ("descritiva", "normalidade", "cruzamento", "associacao", "correlacao", "comparacao"),
            com_graficos=False,
        )

        linhas = linhas_do_historico(lote)
        assert linhas[:-1] == linhas_do_historico(um_por_um)
        assert f"`flatcap analisar {RECORD_ID}`" in linhas[-1]
        assert (
            "6 análises da lista `analises:`, na ordem dela: `descritiva`, `normalidade`, "
            "`cruzamento`, `associacao`, `correlacao` e `comparacao`" in linhas[-1]
        )
        assert "Rodado com `--sem-graficos`." in linhas[-1]


# ── O registro ──────────────────────────────────────────────────────────────


class TestORegistro:
    def test_e_a_ordem_padrao_do_relatorio(self):
        """
        Uma análise nova que entre num registro e não no outro roda sem lugar no
        documento, ou tem lugar no documento e não roda.
        """
        assert tuple(registro.nome for registro in REGISTRO) == ORDEM_PADRAO_DAS_ANALISES

    @pytest.mark.parametrize("registro", REGISTRO, ids=lambda r: r.nome)
    def test_cada_analise_segue_a_convencao(self, registro):
        """
        O nome é o da pasta, e dele saem o módulo, as duas funções e a classe de erro —
        com as duas recusas do dicionário como filhas dela.
        """
        assert getattr(projeto, f"PASTA_{registro.nome.upper()}") == registro.nome
        modulo = registro.modulo
        assert callable(getattr(modulo, f"preparar_{registro.nome}"))
        assert callable(getattr(modulo, f"executar_{registro.nome}"))
        assert issubclass(registro.erro, RuntimeError)
        for erro in registro.erros_do_projeto:
            assert issubclass(erro, registro.erro)

    @pytest.mark.parametrize("registro", REGISTRO, ids=lambda r: r.nome)
    def test_desenha_e_o_que_a_assinatura_diz(self, registro):
        """
        O `com_graficos` só vai para quem o aceita, e a marca no registro é conferida
        contra a assinatura — um argumento a mais seria um `TypeError` no meio do lote.
        """
        preparar = getattr(registro.modulo, f"preparar_{registro.nome}")
        assert registro.desenha == ("com_graficos" in inspect.signature(preparar).parameters)

    def test_importar_o_modulo_nao_traz_o_pandas(self):
        """
        O import preguiçoso da terceira regra, conferido em processo limpo: quem traz o
        `pandas`, o `scipy` e o `matplotlib` é cada análise, e só quando roda.
        """
        codigo = (
            "import sys, flatcap.analises; "
            "print(sorted(m for m in ('pandas', 'scipy', 'matplotlib') if m in sys.modules))"
        )
        saida = subprocess.run(
            [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
        )
        assert saida.stdout.strip() == "[]"


# ── A lista ─────────────────────────────────────────────────────────────────


class TestALista:
    def test_le_os_nomes_na_ordem_escrita(self, projeto_vazio):
        escrever_analises(projeto_vazio, "analises:\n  - normalidade\n  - descritiva")
        assert lista_da_ficha(projeto_vazio) == ("normalidade", "descritiva")

    def test_a_forma_de_uma_linha(self, projeto_vazio):
        escrever_analises(projeto_vazio, "analises: [descritiva, cruzamento]")
        assert lista_da_ficha(projeto_vazio) == ("descritiva", "cruzamento")

    def test_item_vazio_e_espaco_sobrando_nao_contam(self, projeto_vazio):
        escrever_analises(projeto_vazio, "analises:\n  -\n  - ' descritiva '")
        assert lista_da_ficha(projeto_vazio) == ("descritiva",)

    def test_e_a_mesma_lista_que_o_relatorio_le(self, projeto_vazio):
        """
        O lote e o relatório leem a mesma chave por caminhos diferentes — o bloco cru e
        a `Ficha`. Para uma lista válida, precisam concordar: é ela que ordena as
        seções do documento.
        """
        escrever_analises(projeto_vazio, "analises:\n  - comparacao\n  - descritiva")
        assert lista_da_ficha(projeto_vazio) == ler_ficha(projeto_vazio).analises


class TestAListaVazia:
    def test_recusa_e_escreve_a_linha_pelos_blocos(self, projeto_vazio):
        acrescentar_a_ficha(
            projeto_vazio, "cruzamento:\n  - [sexo, escolaridade]\ncomparacao:\n  - [imc, 25]\n"
        )
        with pytest.raises(ListaVaziaError) as erro:
            lista_da_ficha(projeto_vazio)
        mensagem = str(erro.value)
        assert "analises: [descritiva, cruzamento, comparacao]" in mensagem
        assert "não escolhe análise nenhuma por conta própria" in mensagem
        assert "A `normalidade` não precisa de bloco" in mensagem

    def test_com_o_bloco_da_normalidade_ela_entra_na_linha(self, projeto_vazio):
        acrescentar_a_ficha(
            projeto_vazio, "normalidade: [idade]\ncorrelacao:\n  - [idade, imc]\n"
        )
        with pytest.raises(ListaVaziaError) as erro:
            lista_da_ficha(projeto_vazio)
        assert "analises: [descritiva, normalidade, correlacao]" in str(erro.value)
        assert "não precisa de bloco" not in str(erro.value)

    def test_sem_bloco_nenhum_a_linha_minima(self, projeto_vazio):
        with pytest.raises(ListaVaziaError) as erro:
            lista_da_ficha(projeto_vazio)
        assert "analises: [descritiva]" in str(erro.value)
        assert "não tem bloco de análise nenhum" in str(erro.value)

    def test_bloco_vazio_nao_conta_como_escrito(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "cruzamento: []\n")
        with pytest.raises(ListaVaziaError) as erro:
            lista_da_ficha(projeto_vazio)
        assert "analises: [descritiva]\n" in str(erro.value)

    @pytest.mark.parametrize(
        "linha", ["analises:", "analises: null", "analises: ''", "analises:\n  -"]
    )
    def test_as_formas_de_vazia(self, projeto_vazio, linha):
        escrever_analises(projeto_vazio, linha)
        with pytest.raises(ListaVaziaError):
            lista_da_ficha(projeto_vazio)

    def test_sem_a_chave(self, projeto_vazio):
        ficha = projeto_vazio / ARQUIVO_PROJETO
        ficha.write_text(
            ficha.read_text(encoding="utf-8").replace("analises: []\n", ""), encoding="utf-8"
        )
        with pytest.raises(ListaVaziaError):
            lista_da_ficha(projeto_vazio)


class TestAListaMalEscrita:
    """
    Recusa em vez de ignorar: a `Ficha` perdoa o que não reconhece, porque para o
    relatório a lista só ordena seções; aqui ela dirige, e uma entrada que some em
    silêncio é uma análise combinada que não roda.
    """

    def test_texto_no_lugar_da_lista(self, projeto_vazio):
        escrever_analises(projeto_vazio, "analises: descritiva, normalidade")
        with pytest.raises(ListaMalEscritaError) as erro:
            lista_da_ficha(projeto_vazio)
        mensagem = str(erro.value)
        assert "tem um texto, e não uma lista: `descritiva, normalidade`" in mensagem
        assert "analises: [descritiva, normalidade]" in mensagem
        assert "      - normalidade" in mensagem

    def test_texto_separado_por_espaco(self, projeto_vazio):
        escrever_analises(projeto_vazio, "analises: descritiva normalidade")
        with pytest.raises(ListaMalEscritaError) as erro:
            lista_da_ficha(projeto_vazio)
        assert "analises: [descritiva, normalidade]" in str(erro.value)

    def test_lista_dentro_da_lista(self, projeto_vazio):
        escrever_analises(projeto_vazio, "analises:\n  - [descritiva, normalidade]")
        with pytest.raises(ListaMalEscritaError) as erro:
            lista_da_ficha(projeto_vazio)
        assert "uma lista dentro da lista" in str(erro.value)

    def test_o_bloco_escrito_dentro_da_lista(self, projeto_vazio):
        """
        O engano provável: os pares debaixo do nome, dentro da lista. A recusa mostra
        o mesmo conteúdo no lugar dele.
        """
        escrever_analises(
            projeto_vazio,
            "analises:\n  - descritiva\n  - correlacao:\n    - [idade, imc]\n    - [idade, pas]",
        )
        with pytest.raises(ListaMalEscritaError) as erro:
            lista_da_ficha(projeto_vazio)
        mensagem = str(erro.value)
        assert "`correlacao:`, com o que seria o bloco dela dentro" in mensagem
        assert "    correlacao:\n      - [idade, imc]\n      - [idade, pas]" in mensagem

    def test_um_mapa_no_lugar_da_lista(self, projeto_vazio):
        escrever_analises(projeto_vazio, "analises:\n  descritiva: sim")
        with pytest.raises(ListaMalEscritaError) as erro:
            lista_da_ficha(projeto_vazio)
        assert "deveria ser uma lista de nomes" in str(erro.value)

    def test_numero_na_lista(self, projeto_vazio):
        escrever_analises(projeto_vazio, "analises: [descritiva, 3]")
        with pytest.raises(ListaMalEscritaError) as erro:
            lista_da_ficha(projeto_vazio)
        assert "`3`" in str(erro.value)


class TestNomes:
    @pytest.mark.parametrize(
        ("escrito", "conserto"),
        [
            ("Descritiva", "escreva `descritiva`, em minúsculas"),
            ("associação", "escreva `associacao`, sem acento"),
            ("Comparação", "escreva `comparacao`, sem acento"),
            ("corelacao", "você quis dizer `correlacao`?"),
            ("normal", "você quis dizer `normalidade`?"),
            ("anova", "é um teste, e ele roda dentro da `comparacao`"),
            ("Qui-quadrado", "é um teste, e ele roda dentro da `associacao`"),
            ("spearman", "é um teste, e ele roda dentro da `correlacao`"),
            ("regressao", "não é uma análise do FlatCap"),
        ],
    )
    def test_o_nome_desconhecido_recusa_com_o_conserto(self, projeto_vazio, escrito, conserto):
        escrever_analises(projeto_vazio, f"analises: [descritiva, {escrito}]")
        with pytest.raises(AnaliseDesconhecidaError) as erro:
            lista_da_ficha(projeto_vazio)
        assert f"  {escrito} — {conserto}" in str(erro.value)
        assert "Nada foi preparado." in str(erro.value)

    def test_todos_os_desconhecidos_de_uma_vez(self, projeto_vazio):
        escrever_analises(projeto_vazio, "analises: [descritivo, descritiva, associação]")
        with pytest.raises(AnaliseDesconhecidaError) as erro:
            lista_da_ficha(projeto_vazio)
        mensagem = str(erro.value)
        assert "2 nomes que o FlatCap não conhece" in mensagem
        assert "descritivo —" in mensagem and "associação —" in mensagem

    def test_repetido_recusa(self, projeto_vazio):
        """
        A posição na lista é a posição da seção no relatório, e uma análise não tem
        duas.
        """
        escrever_analises(projeto_vazio, "analises: [descritiva, normalidade, descritiva]")
        with pytest.raises(AnaliseRepetidaError) as erro:
            lista_da_ficha(projeto_vazio)
        assert "repete `descritiva`" in str(erro.value)


# ── Preparar ────────────────────────────────────────────────────────────────


class TestPreparar:
    def test_prepara_na_ordem_da_lista(self, projeto_para_o_lote):
        raiz = projeto_para_o_lote("analises: [comparacao, descritiva, cruzamento]")
        plano = preparar_analises(raiz, com_graficos=False, agora=AGORA)
        assert plano.nomes == ("comparacao", "descritiva", "cruzamento")
        assert [type(etapa.plano).__name__ for etapa in plano.etapas] == [
            "PlanoComparacao",
            "PlanoDescritiva",
            "PlanoCruzamento",
        ]

    def test_nao_toca_no_disco(self, projeto_para_o_lote):
        raiz = projeto_para_o_lote()
        antes = linhas_do_historico(raiz)
        preparar_analises(raiz, com_graficos=False, agora=AGORA)
        assert not any((raiz / PASTA_ANALISES).iterdir())
        assert linhas_do_historico(raiz) == antes

    def test_o_relogio_e_um_so_para_todas(self, projeto_para_o_lote):
        """
        O mesmo carimbo no manifesto e no nome da pasta arquivada de todas: é assim
        que se reconhece em `2. Versões antigas/` o que foi arquivado junto.
        """
        raiz = projeto_para_o_lote()
        executar_analises(preparar_analises(raiz, com_graficos=False, agora=AGORA))
        plano = preparar_analises(raiz, com_graficos=False, agora=DEPOIS)
        assert {etapa.plano.manifesto.gerado_em for etapa in plano.etapas} == {DEPOIS}
        assert {etapa.arquivamento[1].name for etapa in plano.etapas} == {
            f"{nome}_2026-09-09_1630" for nome in plano.nomes
        }

    def test_os_graficos_so_vao_para_quem_desenha(self, projeto_para_o_lote):
        raiz = projeto_para_o_lote()
        plano = preparar_analises(raiz, com_graficos=False, agora=AGORA)
        desenham = {etapa.nome for etapa in plano.etapas if etapa.analise.desenha}
        assert desenham == {"descritiva", "normalidade", "correlacao"}
        for etapa in plano.etapas:
            if etapa.analise.desenha:
                assert etapa.plano.com_graficos is False

    def test_a_aba_e_a_conferencia_chegam_a_todas(self, projeto_para_o_lote, monkeypatch):
        """
        O que o comando de cada uma receberia: a mesma aba e a mesma conferência do
        `sha256` para as seis. O espião registra e abre o `.csv` do projeto sem aba.
        """
        raiz = projeto_para_o_lote()
        pedidos = {}
        for registro in REGISTRO:
            original = registro.modulo.abrir

            def espiao(raiz_, aba=None, conferir=True, _nome=registro.nome, _abrir=original):
                pedidos[_nome] = (aba, conferir)
                return _abrir(raiz_, conferir=conferir)

            monkeypatch.setattr(registro.modulo, "abrir", espiao)

        preparar_analises(raiz, aba="Dados", conferir=False, com_graficos=False, agora=AGORA)
        assert pedidos == {registro.nome: ("Dados", False) for registro in REGISTRO}


class TestRecusas:
    def test_as_recusas_saem_todas_de_uma_vez(self, projeto_para_o_lote):
        """
        A segunda regra: nada é escrito enquanto uma recusar — e as recusas saem juntas,
        cada uma com o erro da análise dela.
        """
        from flatcap.comparacao import ComparacaoError
        from flatcap.correlacao import CorrelacaoError

        raiz = projeto_para_o_lote(
            "analises: [descritiva, correlacao, cruzamento, comparacao]",
            "correlacao:\n  - [idade, peso]\n"
            "cruzamento:\n  - [sexo, escolaridade]\n"
            "comparacao:\n  - [sexo, 25]\n",
        )
        antes = linhas_do_historico(raiz)

        with pytest.raises(AnalisesRecusadasError) as erro:
            preparar_analises(raiz, com_graficos=False, agora=AGORA)

        recusas = erro.value.recusas
        assert [recusa.nome for recusa in recusas] == ["correlacao", "comparacao"]
        assert [recusa.titulo for recusa in recusas] == ["Correlação", "Comparação"]
        assert isinstance(recusas[0].erro, CorrelacaoError)
        assert isinstance(recusas[1].erro, ComparacaoError)
        assert erro.value.prontas == ("descritiva", "cruzamento")
        assert "`peso` não está no dicionario.csv" in recusas[0].mensagem
        assert not any((raiz / PASTA_ANALISES).iterdir())
        assert linhas_do_historico(raiz) == antes

    @pytest.mark.parametrize(
        ("recusadas", "prontas", "frase"),
        [
            (1, 0, "A única análise da lista recusou. Nada foi escrito nem arquivado."),
            (2, 0, "As 2 análises da lista recusaram. Nada foi escrito nem arquivado."),
            (1, 1, "A outra (`descritiva`) está pronta — rode o lote de novo depois de "
                   "resolver a recusa, ou o comando dela, à parte."),
            (2, 2, "As outras (`descritiva` e `cruzamento`) estão prontas — rode o lote de "
                   "novo depois de resolver as recusas, ou o comando de cada uma, à parte."),
        ],
    )
    def test_o_fecho_concorda_com_o_numero(self, recusadas, prontas, frase):
        from flatcap.analises import Recusa

        recusas = [Recusa(registro, RuntimeError("não")) for registro in REGISTRO[-recusadas:]]
        erro = AnalisesRecusadasError(recusas, prontas=["descritiva", "cruzamento"][:prontas])
        assert frase in erro.resumo
        assert erro.resumo in str(erro)

    def test_o_dicionario_ausente_para_na_primeira(self, projeto_para_o_lote, monkeypatch):
        """
        O que vale para todas para na primeira: seis painéis dizendo que o dicionário
        não existe não ensinam nada que o primeiro não tenha ensinado.
        """
        from flatcap.descritiva import DicionarioAusenteError

        raiz = projeto_para_o_lote("analises: [descritiva, normalidade]")
        (raiz / "dicionario.csv").unlink()

        def nao_chegue_aqui(*_a, **_k):
            raise AssertionError("a normalidade foi preparada depois da recusa do dicionário")

        monkeypatch.setattr("flatcap.normalidade.preparar_normalidade", nao_chegue_aqui)
        with pytest.raises(DicionarioDoLoteError) as erro:
            preparar_analises(raiz, agora=AGORA)
        assert isinstance(erro.value.__cause__, DicionarioAusenteError)
        assert "Vale para todas as análises da lista" in str(erro.value)

    def test_o_banco_ausente_sobe_como_o_erro_do_banco(self, projeto_para_o_lote):
        from flatcap.banco import BancoError

        raiz = projeto_para_o_lote()
        for arquivo in (raiz / projeto.PASTA_DADOS).iterdir():
            arquivo.unlink()
        with pytest.raises(BancoError):
            preparar_analises(raiz, agora=AGORA)


class TestForaDaLista:
    def test_o_bloco_fora_da_lista_vira_aviso_e_entra_no_historico(self, projeto_para_o_lote):
        raiz = projeto_para_o_lote("analises: [descritiva]", "correlacao:\n  - [idade, imc]\n")
        plano = preparar_analises(raiz, com_graficos=False, agora=AGORA)

        assert plano.fora_da_lista == ("correlacao",)
        assert plano.avisos == (
            "`correlacao` não está na lista `analises:`, e o bloco `correlacao:` está "
            "escrito na ficha — ela não roda neste lote. Acrescente o nome à lista, ou "
            "rode `flatcap correlacao <id>` à parte.",
        )
        executar_analises(plano)
        assert (
            "Fora da lista, e sem rodar: `correlacao`, que tem bloco escrito na ficha."
            in linhas_do_historico(raiz)[-1]
        )

    def test_a_rodada_fora_da_lista_vira_aviso(self, projeto_para_o_lote):
        """
        A rodada antiga pesa mais do que parece: o relatório a inclui depois das
        seções da lista, com os números de quando ela rodou.
        """
        raiz = projeto_para_o_lote("analises: [descritiva]", "")
        antiga = raiz / PASTA_ANALISES / "associacao"
        antiga.mkdir()
        (antiga / ARQUIVO_MANIFESTO).write_text("{}", encoding="utf-8")
        (raiz / PASTA_ANALISES / "rascunho").mkdir()  # pasta sua: não é rodada

        avisos = preparar_analises(raiz, com_graficos=False, agora=AGORA).avisos
        assert len(avisos) == 1
        assert "há uma rodada dela em `3. Análises/associacao/`" in avisos[0]
        assert "o relatório a inclui depois das seções da lista" in avisos[0]

    def test_bloco_e_rodada_fora_da_lista_viram_um_aviso_so(self, projeto_para_o_lote):
        raiz = projeto_para_o_lote(
            "analises: [descritiva]", "associacao:\n  - [sexo, escolaridade]\n"
        )
        antiga = raiz / PASTA_ANALISES / "associacao"
        antiga.mkdir()
        (antiga / ARQUIVO_MANIFESTO).write_text("{}", encoding="utf-8")

        avisos = preparar_analises(raiz, com_graficos=False, agora=AGORA).avisos
        assert len(avisos) == 1
        assert "o bloco `associacao:` está escrito na ficha e há uma rodada dela" in avisos[0]


# ── Executar ────────────────────────────────────────────────────────────────


class TestExecutar:
    def test_ao_escrever_e_chamado_depois_de_cada_uma_na_ordem(self, projeto_para_o_lote):
        raiz = projeto_para_o_lote("analises: [cruzamento, descritiva]")
        vistas: list[tuple[str, bool]] = []

        def ao_escrever(feita):
            manifesto = raiz / PASTA_ANALISES / feita.nome / ARQUIVO_MANIFESTO
            vistas.append((feita.nome, manifesto.is_file()))

        resultado = executar_analises(
            preparar_analises(raiz, com_graficos=False, agora=AGORA), ao_escrever=ao_escrever
        )
        assert vistas == [("cruzamento", True), ("descritiva", True)]
        assert [feita.nome for feita in resultado.feitas] == ["cruzamento", "descritiva"]

    def test_rodar_de_novo_arquiva_todas_com_a_mesma_hora(self, projeto_para_o_lote):
        raiz = projeto_para_o_lote()
        executar_analises(preparar_analises(raiz, com_graficos=False, agora=AGORA))
        resultado = executar_analises(preparar_analises(raiz, com_graficos=False, agora=DEPOIS))

        arquivadas = sorted(p.name for p in (raiz / PASTA_ANTIGAS).iterdir())
        assert arquivadas == sorted(f"{nome}_2026-09-09_1630" for nome in ORDEM_PADRAO_DAS_ANALISES)
        assert all(feita.arquivado is not None for feita in resultado.feitas)

    def test_a_unica_analise_da_lista(self, projeto_para_o_lote):
        raiz = projeto_para_o_lote("analises: [descritiva]", "")
        executar_analises(preparar_analises(raiz, com_graficos=False, agora=AGORA))
        assert linhas_do_historico(raiz)[-1].endswith(
            f"`flatcap analisar {RECORD_ID}` — a única análise da lista `analises:`, "
            "`descritiva`; a linha dela está acima. Rodado com `--sem-graficos`."
        )


class TestParada:
    """
    Uma falha no meio para o lote. A análise que falhou se desfaz sozinha, como no
    comando dela; as anteriores ficam; as seguintes não rodam — e a mesma frase vai
    para o histórico e presa ao erro.
    """

    LISTA = "analises: [descritiva, cruzamento, comparacao]"

    def test_a_falha_de_escrita_desfaz_so_a_que_falhou(self, projeto_para_o_lote, monkeypatch):
        import flatcap.cruzamento as modulo

        raiz = projeto_para_o_lote(self.LISTA)
        executar_analises(preparar_analises(raiz, com_graficos=False, agora=AGORA))
        cruzamento = raiz / PASTA_ANALISES / "cruzamento"
        comparacao = raiz / PASTA_ANALISES / "comparacao"
        antes = {p: {a.name: a.read_bytes() for a in p.iterdir()} for p in (cruzamento, comparacao)}

        original = modulo.escrever_atomico

        def falha_no_manifesto(caminho, texto):
            if caminho.name == ARQUIVO_MANIFESTO:
                raise OSError("disco cheio")
            original(caminho, texto)

        monkeypatch.setattr(modulo, "escrever_atomico", falha_no_manifesto)
        plano = preparar_analises(raiz, com_graficos=False, agora=DEPOIS)
        with pytest.raises(OSError, match="disco cheio") as erro:
            executar_analises(plano)

        situacao = (
            "Parou na análise `cruzamento`, que falhou ao escrever em disco e foi desfeita, "
            "com a rodada anterior de volta ao lugar. Antes dela, a análise `descritiva` "
            "foi escrita. A análise `comparacao` não rodou."
        )
        assert erro.value.__notes__ == [situacao]
        assert linhas_do_historico(raiz)[-1].endswith(
            f"`flatcap analisar {RECORD_ID}` — parou na análise `cruzamento`, que falhou "
            "ao escrever em disco e foi desfeita, com a rodada anterior de volta ao lugar. "
            "Antes dela, a análise `descritiva` foi escrita. A análise `comparacao` não rodou."
        )
        # A que falhou voltou inteira; a seguinte nem foi tocada; a anterior ficou.
        assert {p: {a.name: a.read_bytes() for a in p.iterdir()} for p in antes} == antes
        assert sorted(p.name for p in (raiz / PASTA_ANTIGAS).iterdir()) == [
            "descritiva_2026-09-09_1630"
        ]

    def test_o_ctrl_c_nao_promete_o_desfazer(self, projeto_para_o_lote, monkeypatch):
        """
        O `executar_*` de cada análise desfaz em `Exception`, e o Ctrl+C não é uma. A
        frase diz que a pasta pode ter ficado pela metade em vez de prometer o que
        não aconteceu.
        """

        def interrompe(_plano):
            raise KeyboardInterrupt

        raiz = projeto_para_o_lote(self.LISTA)
        monkeypatch.setattr("flatcap.cruzamento.executar_cruzamento", interrompe)
        with pytest.raises(KeyboardInterrupt) as erro:
            executar_analises(preparar_analises(raiz, com_graficos=False, agora=AGORA))

        nota = erro.value.__notes__[0]
        assert nota.startswith("Interrompido durante a análise `cruzamento`, que pode ter")
        assert "confira `3. Análises/cruzamento/` e `2. Versões antigas/`" in nota
        assert "interrompido durante a análise `cruzamento`" in linhas_do_historico(raiz)[-1]

    def test_o_erro_inesperado_sobe_como_veio(self, projeto_para_o_lote, monkeypatch):
        """
        Bug é bug: sobe com o tipo e o traceback dele — e com a nota de onde o lote
        parou, que o Python imprime junto.
        """

        def quebra(_plano):
            raise ValueError("bug")

        raiz = projeto_para_o_lote(self.LISTA)
        monkeypatch.setattr("flatcap.comparacao.executar_comparacao", quebra)
        with pytest.raises(ValueError, match="bug") as erro:
            executar_analises(preparar_analises(raiz, com_graficos=False, agora=AGORA))
        assert erro.value.__notes__ == [
            "Parou na análise `comparacao`, que falhou com um erro inesperado (ValueError) "
            "e foi desfeita. Antes dela, as análises `descritiva` e `cruzamento` foram "
            "escritas."
        ]

    def test_interrompido_entre_duas_analises(self, projeto_para_o_lote):
        raiz = projeto_para_o_lote(self.LISTA)

        def interrompe(_feita):
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt) as erro:
            executar_analises(
                preparar_analises(raiz, com_graficos=False, agora=AGORA), ao_escrever=interrompe
            )
        assert erro.value.__notes__ == [
            "Interrompido entre uma análise e a seguinte; nenhuma ficou pela metade. A "
            "análise `descritiva` foi escrita. As análises `cruzamento` e `comparacao` não "
            "rodaram."
        ]
