# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
O `projeto.yaml` — Fase 3.

Dois compromissos, e os dois têm teste com nome próprio:

**"Edite à vontade, o FlatCap não sobrescreve o que você escreveu."** É o que o
cabeçalho da ficha promete literalmente. Um comando que apagasse o `prazo` que
você preencheu, ou a lista `analises` combinada na reunião, tornaria a promessa
falsa. A exceção é uma, e o cabeçalho a diz: o `status`, que o relatório passa para
`pronto` — e mesmo ela não toca no comentário escrito ao lado.

**A escrita é atômica.** Um `write_text` que morre na metade — falta de espaço,
unidade de rede que cai, OneDrive sincronizando — deixaria a ficha perdida.
"""

from __future__ import annotations

import os
import stat
from datetime import date

import pytest

from conftest import MATRICULA, PASTA, PROJETO, RECORD_ID, escrever_ficha
from flatcap.ficha import (
    CAMPOS_VERSAO,
    IMPLEMENTACAO,
    FichaAusenteError,
    FichaInvalidaError,
    ProjetoNaoEncontradoError,
    Versao,
    acrescentar_versao,
    caminho_da_ficha,
    data_escrita,
    definir_status,
    escrever_atomico,
    ler,
    ler_yaml,
    localizar_projeto,
    numero_escrito,
    sequencia_do_nome,
    status_reconhecido,
    varrer,
    versao_vigente,
)
from flatcap.projeto import STATUS

UMA_VERSAO = Versao(
    "01_revisado_2026-09-04_banco.xlsx", "cliente_pos_reuniao", "b" * 64, 187904,
    date(2026, 9, 4),
)


# ── Leitura ─────────────────────────────────────────────────────────────────


class TestLeitura:
    def test_le_os_campos_de_identificacao(self, projeto_vazio):
        ficha = ler(projeto_vazio)
        assert (ficha.record_id, ficha.matricula) == (RECORD_ID, MATRICULA)
        assert ficha.raiz == projeto_vazio

    def test_a_matricula_com_zero_a_esquerda_sobrevive(self, projeto_vazio):
        """
        `00742` sem aspas voltaria como o número 742 e a pasta deixaria de bater
        com o registro.
        """
        assert ler(projeto_vazio).matricula == "00742"
        assert ler(projeto_vazio).matricula.startswith("0")

    def test_le_a_lista_de_versoes(self, projeto_com_banco):
        raiz = projeto_com_banco()
        (versao,) = ler(raiz).dados
        assert versao.origem == "redcap"
        assert len(versao.sha256) == 64
        assert versao.data == date(2026, 9, 1)

    def test_data_entre_aspas_tambem_e_lida(self, projeto_vazio):
        """
        O arquivo é editado à mão, e digitar `data: "2026-03-14"` é natural.
        """
        caminho = caminho_da_ficha(projeto_vazio)
        caminho.write_text(
            caminho.read_text(encoding="utf-8").replace("dados: []", "")
            + "dados:\n  - arquivo: b.xlsx\n    origem: redcap\n    sha256: abc\n"
            "    tamanho_bytes: 10\n    data: '2026-03-14'\n",
            encoding="utf-8",
            newline="\n",
        )
        assert ler(projeto_vazio).dados[0].data == date(2026, 3, 14)

    def test_o_sha_volta_em_minusculas(self, projeto_vazio):
        escrever_ficha(
            projeto_vazio,
            dados=[
                {
                    "arquivo": "b.xlsx", "origem": "redcap", "sha256": "ABCDEF",
                    "tamanho_bytes": 1, "data": "2026-09-01",
                }
            ],
        )
        assert ler(projeto_vazio).dados[0].sha256 == "abcdef"

    def test_pasta_sem_ficha(self, root):
        pasta = root / "00999 - Sem Ficha"
        pasta.mkdir()
        with pytest.raises(FichaAusenteError):
            ler(pasta)

    def test_yaml_invalido_diz_o_que_costuma_ser(self, projeto_vazio):
        caminho_da_ficha(projeto_vazio).write_text(
            "record_id: '42'\nnome: Fulano: o Segundo\n", encoding="utf-8", newline="\n"
        )
        with pytest.raises(FichaInvalidaError) as erro:
            ler(projeto_vazio)
        assert "edição à mão" in str(erro.value)

    def test_a_barra_solta_da_versao_antiga_tem_diagnostico_proprio(self, projeto_vazio):
        """
        Defeito conhecido das versões anteriores à 0.4.0: o cabeçalho saía com
        um `/` antes do primeiro `#`, e isso torna o arquivo inteiro ilegível. A
        mensagem crua do parser fala de `<document start>`, que não diz nada a
        quem abrir o arquivo e vir um `/` inofensivo na primeira linha.
        """
        caminho_da_ficha(projeto_vazio).write_text(
            "/\n# projeto.yaml\nrecord_id: '42'\n", encoding="utf-8", newline="\n"
        )
        with pytest.raises(FichaInvalidaError) as erro:
            ler(projeto_vazio)
        assert "barra solta" in str(erro.value)
        # O `reparar_fichas.py` foi aposentado com a migração da Fase 3, e o
        # diagnóstico ficou: quem restaura uma pasta de backup antigo precisa do
        # conserto escrito, porque não há mais script para indicar.
        assert "apague a primeira linha" in str(erro.value)

    def test_ficha_que_nao_e_mapeamento(self, projeto_vazio):
        caminho_da_ficha(projeto_vazio).write_text(
            "- um\n- dois\n", encoding="utf-8", newline="\n"
        )
        with pytest.raises(FichaInvalidaError) as erro:
            ler(projeto_vazio)
        assert "record_id:" in str(erro.value)

    def test_dados_que_nao_e_lista(self, projeto_vazio):
        caminho = caminho_da_ficha(projeto_vazio)
        caminho.write_text(
            caminho.read_text(encoding="utf-8").replace("dados: []", "dados: nenhum"),
            encoding="utf-8",
            newline="\n",
        )
        with pytest.raises(FichaInvalidaError) as erro:
            ler(projeto_vazio)
        assert "lista" in str(erro.value)

    def test_arquivo_que_nao_e_utf8(self, projeto_vazio):
        caminho_da_ficha(projeto_vazio).write_bytes(
            "record_id: '42'\nnome: José\n".encode("cp1252")
        )
        with pytest.raises(FichaInvalidaError) as erro:
            ler(projeto_vazio)
        assert "UTF-8" in str(erro.value)


# ── Escrita ─────────────────────────────────────────────────────────────────


class TestAcrescentarVersao:
    def test_a_entrada_entra_no_fim_com_os_cinco_campos(self, projeto_vazio):
        acrescentar_versao(projeto_vazio, UMA_VERSAO)
        texto = caminho_da_ficha(projeto_vazio).read_text(encoding="utf-8")
        for campo in CAMPOS_VERSAO:
            assert f"{campo}:" in texto
        assert ler(projeto_vazio).dados[-1] == UMA_VERSAO

    def test_o_comentario_escrito_a_mao_sobrevive(self, projeto_vazio):
        """
        A promessa literal do cabeçalho da ficha. O PyYAML descarta comentário
        no parser; é o `ruamel` em modo round-trip que os devolve na gravação.
        """
        caminho = caminho_da_ficha(projeto_vazio)
        caminho.write_text(
            "# a ficha deste atendimento\n"
            "record_id: '42'\n"
            "matricula: '00742'\n"
            "nome: José\n"
            "tipo: professor\n"
            "status: em_analise\n"
            "prazo: null      # combinar na reunião de terça\n"
            "analises:\n"
            "  - descritiva   # só a descritiva, combinado em 04/09\n"
            "dados: []\n",
            encoding="utf-8",
            newline="\n",
        )
        acrescentar_versao(projeto_vazio, UMA_VERSAO)
        texto = caminho.read_text(encoding="utf-8")
        assert "# a ficha deste atendimento" in texto
        assert "combinar na reunião de terça" in texto
        assert "combinado em 04/09" in texto

    def test_os_campos_que_voce_preencheu_ficam(self, projeto_vazio):
        caminho = caminho_da_ficha(projeto_vazio)
        caminho.write_text(
            caminho.read_text(encoding="utf-8")
            .replace("prazo: null", "prazo: 2026-09-20")
            .replace("analises: []", "analises:\n  - descritiva\n  - associacao"),
            encoding="utf-8",
            newline="\n",
        )
        acrescentar_versao(projeto_vazio, UMA_VERSAO)
        texto = caminho.read_text(encoding="utf-8")
        assert "2026-09-20" in texto
        assert "associacao" in texto

    def test_dados_vazio_em_linha_vira_bloco(self, projeto_vazio):
        """
        Uma lista que veio como `dados: []` manteria o estilo em linha, e a
        entrada nova sairia espremida numa linha só — que não é o formato em que
        este arquivo é lido e editado.
        """
        acrescentar_versao(projeto_vazio, UMA_VERSAO)
        texto = caminho_da_ficha(projeto_vazio).read_text(encoding="utf-8")
        assert "\n- arquivo:" in texto or "\n  - arquivo:" in texto

    def test_a_indentacao_da_lista_escrita_a_mao_nao_muda(self, projeto_vazio):
        """
        A ficha é editada à mão, e uma reindentação silenciosa produz diff em um
        arquivo que o usuário abre com frequência. Semanticamente idêntico não é
        o mesmo que igual.
        """
        caminho = caminho_da_ficha(projeto_vazio)
        caminho.write_text(
            "record_id: '42'\nmatricula: '00742'\nnome: José\ntipo: professor\n"
            "status: novo\nanalises:\n  - descritiva\ndados: []\n",
            encoding="utf-8",
            newline="\n",
        )
        acrescentar_versao(projeto_vazio, UMA_VERSAO)
        assert "  - descritiva" in caminho.read_text(encoding="utf-8")

    def test_o_nulo_sai_como_null_e_nao_como_linha_pela_metade(self, projeto_vazio):
        acrescentar_versao(projeto_vazio, UMA_VERSAO)
        texto = caminho_da_ficha(projeto_vazio).read_text(encoding="utf-8")
        assert "prazo: null" in texto

    def test_sem_ficha_recusa_sem_criar_nada(self, root):
        pasta = root / "00999 - Sem Ficha"
        pasta.mkdir()
        with pytest.raises(FichaAusenteError):
            acrescentar_versao(pasta, UMA_VERSAO)
        assert not caminho_da_ficha(pasta).exists()

    def test_duas_versoes_seguidas(self, projeto_vazio):
        acrescentar_versao(projeto_vazio, UMA_VERSAO)
        segunda = Versao("02_revisado_2026-09-06_b.xlsx", "cliente_pos_reuniao", "c" * 64, 10)
        acrescentar_versao(projeto_vazio, segunda)
        assert len(ler(projeto_vazio).dados) == 2


class TestEscritaAtomica:
    def test_grava_o_arquivo_inteiro(self, tmp_path):
        alvo = tmp_path / "a.txt"
        escrever_atomico(alvo, "conteúdo\ncom acento\n")
        assert alvo.read_text(encoding="utf-8") == "conteúdo\ncom acento\n"

    def test_sempre_utf8_e_sempre_lf(self, tmp_path):
        """
        Os padrões do Python dependem da máquina, e cp1252 estraga acento.
        """
        alvo = tmp_path / "a.txt"
        escrever_atomico(alvo, "linha 1\nlinha 2\n")
        assert alvo.read_bytes() == b"linha 1\nlinha 2\n"

    def test_o_temporario_nasce_na_mesma_pasta(self, tmp_path, monkeypatch):
        """
        `os.replace` só é atômico dentro do mesmo sistema de arquivos: um
        temporário em `/tmp` poderia estar em outro disco, e aí a troca vira
        cópia, que pode falhar pela metade.
        """
        import flatcap.ficha as modulo

        pastas: list = []
        original = modulo.temporario_ao_lado

        def espiar(destino):
            descritor, temporario = original(destino)
            pastas.append(temporario.parent)
            return descritor, temporario

        monkeypatch.setattr(modulo, "temporario_ao_lado", espiar)
        alvo = tmp_path / "sub" / "a.txt"
        alvo.parent.mkdir()
        escrever_atomico(alvo, "x")
        assert pastas == [alvo.parent]

    @pytest.mark.skipif(os.name != "posix", reason="no Windows, quem decide é a pasta")
    @pytest.mark.parametrize(
        ("umask", "esperado"), [(0o022, 0o644), (0o002, 0o664)], ids=["022", "002"]
    )
    def test_o_arquivo_sai_com_a_permissao_do_umask(self, tmp_path, umask, esperado):
        """
        REGRESSÃO da 1.13.0. O `tempfile.NamedTemporaryFile` cria o temporário
        com `0o600`, e o `os.replace` levava esse modo para o destino: num
        `FLATCAP_ROOT` dividido pela equipe, ninguém além do dono abria a ficha,
        o dicionário, as tabelas ou o relatório. A substituição de um arquivo que
        já existe também volta ao `umask` — é o que conserta os `0o600` antigos.
        """
        alvo = tmp_path / "a.txt"
        alvo.write_text("antigo", encoding="utf-8")
        alvo.chmod(0o600)

        anterior = os.umask(umask)
        try:
            escrever_atomico(alvo, "novo")
            escrever_atomico(tmp_path / "b.txt", "novo")
        finally:
            os.umask(anterior)

        assert stat.S_IMODE(alvo.stat().st_mode) == esperado
        assert stat.S_IMODE((tmp_path / "b.txt").stat().st_mode) == esperado

    def test_a_interrupcao_tambem_nao_deixa_lixo(self, tmp_path, monkeypatch):
        """
        O Ctrl+C não é `Exception`: a limpeza do temporário pega `BaseException`.
        """

        def interromper(*_a, **_k):
            raise KeyboardInterrupt

        monkeypatch.setattr("flatcap.ficha.os.replace", interromper)
        with pytest.raises(KeyboardInterrupt):
            escrever_atomico(tmp_path / "a.txt", "novo")
        assert not list(tmp_path.glob("*.tmp"))

    def test_falha_no_meio_nao_deixa_lixo(self, tmp_path, monkeypatch):
        alvo = tmp_path / "a.txt"
        alvo.write_text("antigo", encoding="utf-8")

        def falhar(*_a, **_k):
            raise OSError("disco cheio (simulado)")

        monkeypatch.setattr("flatcap.ficha.os.replace", falhar)
        with pytest.raises(OSError):
            escrever_atomico(alvo, "novo")
        assert alvo.read_text(encoding="utf-8") == "antigo"
        assert not list(tmp_path.glob("*.tmp"))


# ── Localizar o projeto ─────────────────────────────────────────────────────


class TestLocalizarProjeto:
    """
    Aceitar os dois identificadores não é conveniência gratuita: o `record_id` é
    o que você tem em mãos logo depois de criar a pasta; a matrícula é o que
    está no nome dela, e é o que você tem seis meses depois.
    """

    def test_pelo_record_id(self, projeto_vazio, root):
        assert localizar_projeto(root, RECORD_ID) == projeto_vazio

    def test_pela_matricula(self, projeto_vazio, root):
        assert localizar_projeto(root, MATRICULA) == projeto_vazio

    def test_identificador_vazio(self, root):
        with pytest.raises(ProjetoNaoEncontradoError) as erro:
            localizar_projeto(root, "")
        assert "flatcap listar" in str(erro.value)

    def test_nao_encontrado(self, projeto_vazio, root):
        with pytest.raises(ProjetoNaoEncontradoError) as erro:
            localizar_projeto(root, "99999")
        assert "Confira o identificador" in str(erro.value)

    def test_duas_pastas_com_o_mesmo_identificador(self, projeto_vazio, root):
        gemea = root / "00743 - Outro" / PROJETO
        gemea.mkdir(parents=True)
        escrever_ficha(gemea, matricula="00743")
        with pytest.raises(ProjetoNaoEncontradoError) as erro:
            localizar_projeto(root, RECORD_ID)
        assert "pasta duplicada" in str(erro.value)

    def test_pasta_criada_a_mao_sem_ficha_e_encontrada_pelo_nome(self, root):
        pasta = root / "00999 - Feita a Mao"
        pasta.mkdir()
        with pytest.raises(FichaAusenteError) as erro:
            localizar_projeto(root, "00999")
        assert "flatcap novo" in str(erro.value)

    def test_ficha_ilegivel_nao_vira_nota_de_rodape(self, root):
        """
        Enquanto houver uma ficha ilegível, a busca não pode afirmar que o
        projeto não existe — ele pode ser justamente aquele que não deu para
        ler. O erro que sobe é o diagnóstico da ficha quebrada.
        """
        # No segundo nível, onde mora uma ficha de projeto desde a 1.1.0. No
        # primeiro, ela é layout antigo — outro diagnóstico, outro teste.
        quebrada = root / "00999 - Quebrada" / "Projeto 999"
        quebrada.mkdir(parents=True)
        caminho_da_ficha(quebrada).write_text("/\nrecord_id: x\n", encoding="utf-8")
        with pytest.raises(FichaInvalidaError) as erro:
            localizar_projeto(root, "12345")
        assert "não dá para afirmar" in str(erro.value)


class TestSequenciaDoNome:
    @pytest.mark.parametrize(
        ("nome", "esperado"),
        [
            ("00_redcap_2026-09-01_b.xlsx", 0),
            ("01_revisado_2026-09-04_b.xlsx", 1),
            ("12_revisado_b.csv", 12),
            ("banco.xlsx", None),
            ("1_revisado.csv", None),
            ("", None),
            ("ab_revisado.csv", None),
        ],
    )
    def test_extrai_o_prefixo(self, nome, esperado):
        """
        `None` e `0` são coisas diferentes aqui — por isso a função não devolve
        `-1` nem `0` como "não sei".
        """
        assert sequencia_do_nome(nome) == esperado


def test_a_implementacao_carregada_e_informavel():
    """
    O `doctor` diz qual está em uso. Trocar de implementação de YAML é
    substituir um arquivo, e o comando precisa dizer qual está lá.
    """
    assert IMPLEMENTACAO
    assert "yaml" in IMPLEMENTACAO.lower()


def test_a_pasta_do_projeto_e_a_do_fixture(projeto_vazio):
    assert projeto_vazio.name == PROJETO
    assert projeto_vazio.parent.name == PASTA
    assert versao_vigente(ler(projeto_vazio)) is None


# ── Os outros YAML editados à mão ───────────────────────────────────────────


class TestLerYaml:
    def test_devolve_tipos_comuns(self, tmp_path):
        caminho = tmp_path / "desenho.yaml"
        caminho.write_text(
            "# comentário de quem preencheu\n"
            "desenho: aas\npopulacao: 1200\nmargem: 2,5\nlista: [1, 2]\n",
            encoding="utf-8",
        )
        conteudo = ler_yaml(caminho)
        assert conteudo == {
            "desenho": "aas", "populacao": 1200, "margem": "2,5", "lista": [1, 2]
        }
        assert type(conteudo) is dict
        assert type(conteudo["lista"]) is list

    def test_yaml_quebrado_tem_o_diagnostico_da_ficha(self, tmp_path):
        """A tabulação, o engano mais comum de quem edita à mão, vira frase, e não traceback."""
        caminho = tmp_path / "desenho.yaml"
        caminho.write_text("desenho: aas\n\tpopulacao: 1200\n", encoding="utf-8")
        with pytest.raises(FichaInvalidaError, match="não é um YAML válido"):
            ler_yaml(caminho)

    def test_arquivo_ausente(self, tmp_path):
        with pytest.raises(FichaAusenteError, match="desenho.yaml"):
            ler_yaml(tmp_path / "desenho.yaml")

    def test_arquivo_vazio_e_none(self, tmp_path):
        caminho = tmp_path / "desenho.yaml"
        caminho.write_text("# só comentário\n", encoding="utf-8")
        assert ler_yaml(caminho) is None


class TestNumeroEscrito:
    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [(25, 25.0), (24.9, 24.9), ("24,9", 24.9), (" 25 ", 25.0), ("-1,5", -1.5), ("2,5", 2.5)],
    )
    def test_numero(self, valor, esperado):
        assert numero_escrito(valor) == esperado

    @pytest.mark.parametrize(
        "valor", [True, False, "2.500,00", float("nan"), float("inf"), None, "", "cinco", [5]]
    )
    def test_o_que_nao_e_numero(self, valor):
        assert numero_escrito(valor) is None

    def test_e_a_regra_da_referencia_da_comparacao(self):
        """
        A regra desceu da comparação para cá: as duas fichas leem o número escrito do
        mesmo jeito.
        """
        from flatcap.comparacao import referencia_escrita

        for valor in (25, 24.9, "24,9", " 25 ", True, "2.500,00", None, float("nan")):
            assert referencia_escrita(valor) == numero_escrito(valor)


# ── O status e o prazo ──────────────────────────────────────────────────────


class TestStatusReconhecido:
    @pytest.mark.parametrize("status", STATUS)
    def test_cada_um_como_esta_na_lista(self, status):
        assert status_reconhecido(status) == status

    @pytest.mark.parametrize(
        ("escrito", "esperado"),
        [
            ("Em andamento", "em andamento"),
            ("EM ANDAMENTO", "em andamento"),
            ("em_andamento", "em andamento"),
            ("  em   andamento ", "em andamento"),
            ("nao iniciado", "não iniciado"),
            ("Não Iniciado", "não iniciado"),
            ("aguardando-banco-de-dados", "aguardando banco de dados"),
            ("calculo amostral", "cálculo amostral"),
            ("Cálculo Amostral", "cálculo amostral"),
            ("calculo_amostral", "cálculo amostral"),
            ("Finalizado", "finalizado"),
            ("PRONTO", "pronto"),
        ],
    )
    def test_sem_maiuscula_nem_acento_nem_sublinhado(self, escrito, esperado):
        """
        A leitura é tolerante e a escrita é estrita, como no `dicionario.csv`: o
        status se digita à mão, e o que volta é a grafia da lista.
        """
        assert status_reconhecido(escrito) == esperado

    @pytest.mark.parametrize(
        ("escrito", "esperado"), [("novo", "não iniciado"), ("em_analise", "em andamento")]
    )
    def test_os_dois_do_cabecalho_de_antes(self, escrito, esperado):
        """
        Toda ficha criada antes da 1.17.0 diz `status: novo`, e o cabeçalho delas
        sugeria `em_analise`.
        """
        assert status_reconhecido(escrito) == esperado

    @pytest.mark.parametrize(
        "escrito",
        [
            "entregue",
            "",
            "aguardando banco",
            "pronta",
            "em análise do cliente",
            "cálculo",
            "amostragem",
        ],
    )
    def test_o_que_nao_e_nenhum_deles(self, escrito):
        """
        `entregue`, o terceiro do cabeçalho de antes, pode ser o `pronto` ou o
        `finalizado` — e adivinhar não é ler. Pelo mesmo motivo, `amostragem`, o nome
        do comando, não é o `cálculo amostral`.
        """
        assert status_reconhecido(escrito) is None


class TestDataEscrita:
    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [
            (date(2026, 11, 4), date(2026, 11, 4)),
            ("2026-11-04", date(2026, 11, 4)),
            ("2026-11-4", date(2026, 11, 4)),
            ("04/11/2026", date(2026, 11, 4)),
            ("4/11/2026", date(2026, 11, 4)),
            (" 04/11/2026 ", date(2026, 11, 4)),
        ],
    )
    def test_as_duas_formas(self, valor, esperado):
        assert data_escrita(valor) == esperado

    @pytest.mark.parametrize(
        "valor",
        ["04/11/26", "31/02/2026", "11/2026", "semana que vem", "2026/11/04", "", None, 20261104],
    )
    def test_o_que_nao_e_data(self, valor):
        """
        `04/11/26` é 2026 ou 1926; a data que não existe também não é data.
        """
        assert data_escrita(valor) is None


class TestPrazoEStatusNaLeitura:
    def test_o_prazo_entra_como_esta_escrito(self, projeto_vazio):
        escrever_ficha(projeto_vazio, prazo="04/11/2026")
        assert ler(projeto_vazio).prazo == "04/11/2026"

    def test_o_prazo_sem_aspas_e_a_data_em_texto(self, projeto_vazio):
        escrever_ficha(projeto_vazio, prazo="2026-11-04")
        ficha = ler(projeto_vazio)
        assert ficha.prazo == "2026-11-04"
        assert data_escrita(ficha.prazo) == date(2026, 11, 4)

    def test_prazo_nulo_e_vazio(self, projeto_vazio):
        assert ler(projeto_vazio).prazo == ""

    def test_prazo_que_nao_e_data_nao_impede_a_ficha_de_abrir(self, projeto_vazio):
        escrever_ficha(projeto_vazio, prazo="semana que vem")
        assert ler(projeto_vazio).prazo == "semana que vem"

    def test_o_status_entra_como_esta_escrito(self, projeto_vazio):
        escrever_ficha(projeto_vazio, status="Em Andamento")
        assert ler(projeto_vazio).status == "Em Andamento"


class TestDefinirStatus:
    def test_escreve_o_status(self, projeto_vazio):
        definir_status(projeto_vazio, "pronto")
        assert ler(projeto_vazio).status == "pronto"

    def test_o_resto_da_ficha_fica(self, projeto_vazio):
        """
        A exceção à promessa do cabeçalho é a linha do status, e só ela: o comentário
        escrito ao lado dela, o prazo, a lista e as aspas da matrícula ficam.
        """
        caminho = caminho_da_ficha(projeto_vazio)
        caminho.write_text(
            "# a ficha deste atendimento\n"
            "record_id: '42'\n"
            "matricula: '00742'\n"
            "nome: José\n"
            "prazo: 04/11/2026     # combinado na reunião de terça\n"
            "status: em andamento  # mexi à mão\n"
            "analises:\n"
            "  - descritiva\n"
            "dados: []\n",
            encoding="utf-8",
            newline="\n",
        )
        definir_status(projeto_vazio, "pronto")
        texto = caminho.read_text(encoding="utf-8")
        assert "# a ficha deste atendimento" in texto
        assert "prazo: 04/11/2026     # combinado na reunião de terça" in texto
        assert "status: pronto" in texto and "# mexi à mão" in texto
        assert "matricula: '00742'" in texto
        assert "  - descritiva" in texto
        assert texto.count("status:") == 1

    def test_a_ficha_sem_status_o_ganha_depois_do_prazo(self, projeto_vazio):
        caminho = caminho_da_ficha(projeto_vazio)
        caminho.write_text(
            "record_id: '42'\nprazo: null\nanalises: []\ndados: []\n",
            encoding="utf-8",
            newline="\n",
        )
        definir_status(projeto_vazio, "pronto")
        linhas = caminho.read_text(encoding="utf-8").splitlines()
        assert linhas[linhas.index("prazo: null") + 1] == "status: pronto"

    def test_o_status_fora_da_lista_e_defeito_de_quem_chama(self, projeto_vazio):
        """
        O FlatCap escreve na ficha só um dos status da lista, na grafia de lá: um
        texto qualquer seria um status que o painel não reconhece.
        """
        antes = caminho_da_ficha(projeto_vazio).read_bytes()
        for errado in ("Pronto", "entregue", ""):
            with pytest.raises(ValueError):
                definir_status(projeto_vazio, errado)
        assert caminho_da_ficha(projeto_vazio).read_bytes() == antes

    def test_sem_ficha_recusa_sem_criar_nada(self, root):
        pasta = root / "00999 - Sem Ficha"
        pasta.mkdir()
        with pytest.raises(FichaAusenteError):
            definir_status(pasta, "pronto")
        assert not caminho_da_ficha(pasta).exists()


class TestVarrer:
    def test_os_projetos_as_fichas_quebradas_e_as_pastas_antigas(self, projeto_vazio, root):
        quebrada = root / "00999 - Quebrada" / "Projeto 999"
        quebrada.mkdir(parents=True)
        caminho_da_ficha(quebrada).write_text("nome: Fulano: o Segundo\n", encoding="utf-8")
        antiga = root / "00888 - Antiga"
        antiga.mkdir()
        escrever_ficha(antiga, record_id="88", matricula="00888")

        varredura = varrer(root)
        assert [ficha.raiz for ficha in varredura.projetos] == [projeto_vazio]
        assert [erro.caminho.parent for erro in varredura.ilegiveis] == [quebrada]
        assert varredura.antigas == (antiga,)

    def test_a_ficha_esquecida_nas_versoes_antigas_nao_e_projeto(self, projeto_vazio, root):
        """
        Dois níveis, explícitos — a regra do `localizar_projeto`.
        """
        esquecida = projeto_vazio / "2. Versões antigas" / "Projeto 041"
        esquecida.mkdir(parents=True)
        escrever_ficha(esquecida, record_id="41")
        assert [ficha.record_id for ficha in varrer(root).projetos] == [RECORD_ID]

    def test_root_que_nao_existe(self, tmp_path):
        varredura = varrer(tmp_path / "nao-existe")
        assert (varredura.projetos, varredura.ilegiveis, varredura.antigas) == ((), (), ())
