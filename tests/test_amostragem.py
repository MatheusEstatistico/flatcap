# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Os testes do `amostragem.py` — a pasta, a ficha, a conta e o relatório da amostra.

A aritmética é do `test_amostral.py`; aqui o que se testa é o que a amostragem decide em
volta dela: o modelo do `desenho.yaml` na primeira rodada e nunca por cima dele, cada
recusa da ficha, a tabela que sai, o manifesto, o relatório da amostra, as versões antigas
dentro da pasta dela, e o desfazer.

O projeto de partida é o `projeto_vazio`: a pasta como o `flatcap novo` a deixa quando o
REDCap não trouxe anexo — que é o caso do pedido de amostragem.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from docx import Document

from conftest import AGORA, escrever_ficha, linhas_do_historico
from flatcap.amostragem import (
    ARQUIVO_TAMANHO,
    DESENHO_AAS,
    DESENHOS,
    MODELO_DO_DESENHO,
    PREVISTOS,
    ROTULO_DO_TAMANHO,
    TITULO_DA_AMOSTRA,
    AmostragemError,
    DesenhoExistenteError,
    DesenhoInvalidoError,
    executar_amostragem,
    ler_desenho,
    nome_do_relatorio_da_amostra,
    preparar_amostragem,
    resumo_do_tamanho,
)
from flatcap.ficha import ler_yaml
from flatcap.manifesto import ARQUIVO_MANIFESTO
from flatcap.projeto import (
    ARQUIVO_DESENHO,
    PASTA_AMOSTRAGEM,
    PASTA_ANTIGAS_DA_AMOSTRAGEM,
    SUBPASTAS,
)

DEPOIS = AGORA.replace(hour=16)

# O caso de todo dia: o cliente informou só a população.
COM_POPULACAO = "desenho: aas\npopulacao: 1200\nconfianca: 95\nmargem: 5\nproporcao: 50\n"


def escrever_desenho(raiz: Path, texto: str) -> Path:
    """O `desenho.yaml` à mão, como você o preenche — sem passar pelo modelo."""
    pasta = raiz / PASTA_AMOSTRAGEM
    pasta.mkdir(exist_ok=True)
    caminho = pasta / ARQUIVO_DESENHO
    caminho.write_text(texto, encoding="utf-8", newline="\n")
    return caminho


def rodar(raiz: Path, agora=AGORA, **argumentos):
    plano = preparar_amostragem(raiz, agora=agora, **argumentos)
    return plano, executar_amostragem(plano)


def recusa(raiz: Path, texto: str) -> str:
    escrever_desenho(raiz, texto)
    with pytest.raises(DesenhoInvalidoError) as erro:
        preparar_amostragem(raiz, agora=AGORA)
    return " ".join(str(erro.value).split())


def linhas(plano) -> dict[str, str]:
    return dict(plano.amostragem.calculo.linhas)


# ── A primeira rodada: o modelo ─────────────────────────────────────────────


class TestPrimeiraRodada:
    def test_a_simulacao_nao_cria_nada(self, projeto_vazio):
        plano = preparar_amostragem(projeto_vazio, agora=AGORA)
        assert plano.so_o_modelo
        assert plano.criar_pasta
        assert plano.arquivos == (ARQUIVO_DESENHO,)
        assert not (projeto_vazio / PASTA_AMOSTRAGEM).exists()

    def test_cria_a_pasta_e_o_modelo(self, projeto_vazio):
        _, resultado = rodar(projeto_vazio)
        caminho = projeto_vazio / PASTA_AMOSTRAGEM / ARQUIVO_DESENHO
        assert caminho.read_text(encoding="utf-8") == MODELO_DO_DESENHO
        assert resultado.criados == (caminho.parent, caminho)
        assert [p.name for p in (projeto_vazio / PASTA_AMOSTRAGEM).iterdir()] == [
            ARQUIVO_DESENHO
        ]

    def test_as_tres_pastas_do_novo_nao_mudam(self, projeto_vazio):
        def conteudo():
            return {nome: sorted(p.name for p in (projeto_vazio / nome).rglob("*"))
                    for nome in SUBPASTAS}

        antes = conteudo()
        rodar(projeto_vazio)
        assert conteudo() == antes

    def test_o_historico_ganha_uma_linha(self, projeto_vazio):
        antes = len(linhas_do_historico(projeto_vazio))
        rodar(projeto_vazio)
        ultimas = linhas_do_historico(projeto_vazio)
        assert len(ultimas) == antes + 1
        assert f"`{PASTA_AMOSTRAGEM}/{ARQUIVO_DESENHO}` escrito" in ultimas[-1]

    def test_o_modelo_como_veio_ja_e_um_desenho_valido(self, projeto_vazio):
        """Sem preencher nada, a conta é a de população grande: 385."""
        rodar(projeto_vazio)
        plano = preparar_amostragem(projeto_vazio, agora=DEPOIS)
        assert not plano.so_o_modelo
        assert plano.amostragem.tamanho.n_final == 385

    def test_o_modelo_explica_cada_chave(self):
        for chave in ("desenho", "populacao", "confianca", "margem", "proporcao",
                      "desvio", "perda", "n"):
            assert f"#   {chave}" in MODELO_DO_DESENHO

    def test_a_pasta_que_ja_existe_nao_e_recriada(self, projeto_vazio):
        (projeto_vazio / PASTA_AMOSTRAGEM).mkdir()
        (projeto_vazio / PASTA_AMOSTRAGEM / "lista_do_cliente.xlsx").write_bytes(b"x")
        plano, resultado = rodar(projeto_vazio)
        assert not plano.criar_pasta
        assert resultado.criados == (projeto_vazio / PASTA_AMOSTRAGEM / ARQUIVO_DESENHO,)
        assert (projeto_vazio / PASTA_AMOSTRAGEM / "lista_do_cliente.xlsx").is_file()

    def test_nunca_escreve_por_cima_do_desenho(self, projeto_vazio):
        """
        Entre a simulação e a execução, o arquivo apareceu: o modelo recusa, e o que você
        escreveu fica.
        """
        plano = preparar_amostragem(projeto_vazio, agora=AGORA)
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        with pytest.raises(DesenhoExistenteError):
            executar_amostragem(plano)
        caminho = projeto_vazio / PASTA_AMOSTRAGEM / ARQUIVO_DESENHO
        assert caminho.read_text(encoding="utf-8") == COM_POPULACAO

    def test_com_o_desenho_escrito_a_rodada_e_a_da_conta(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        plano = preparar_amostragem(projeto_vazio, agora=AGORA)
        assert not plano.so_o_modelo


# ── A conta, pelo desenho.yaml ──────────────────────────────────────────────


class TestConta:
    def test_o_caso_de_todo_dia(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO + "perda: 10\n")
        plano = preparar_amostragem(projeto_vazio, agora=AGORA)
        assert plano.amostragem.calculo.linhas == (
            ("Desenho", "aleatória simples, sem reposição"),
            ("População (N)", "1200"),
            ("Nível de confiança", "95% (z = 1,96)"),
            ("Margem de erro", "5 pontos percentuais"),
            ("Proporção esperada", "50%"),
            ("Tamanho sem a correção (n₀)", "385"),
            ("Tamanho com a correção (n)", "292"),
            ("Perda esperada", "10%"),
            ("Tamanho da amostra", "325"),
        )

    def test_sem_perda_a_ultima_linha_e_o_corrigido(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO + "perda: 0\n")
        tabela = linhas(preparar_amostragem(projeto_vazio, agora=AGORA))
        assert tabela[ROTULO_DO_TAMANHO] == "292"
        assert "Perda esperada" not in tabela
        assert "Tamanho com a correção (n)" not in tabela

    def test_sem_populacao_e_a_de_populacao_grande(self, projeto_vazio):
        escrever_desenho(
            projeto_vazio, "desenho: aas\npopulacao:\nconfianca: 95\nmargem: 5\nproporcao: 50\n"
        )
        plano = preparar_amostragem(projeto_vazio, agora=AGORA)
        tabela = linhas(plano)
        assert tabela["População (N)"].startswith("não informada")
        assert tabela[ROTULO_DO_TAMANHO] == "385"
        assert "Tamanho sem a correção (n₀)" not in tabela

    def test_a_media(self, projeto_vazio):
        escrever_desenho(projeto_vazio, "desenho: aas\nconfianca: 95\nmargem: 2\ndesvio: 10\n")
        tabela = linhas(preparar_amostragem(projeto_vazio, agora=AGORA))
        assert tabela["Desvio-padrão esperado"] == "10"
        assert tabela["Margem de erro"] == "2, na unidade da variável"
        assert tabela[ROTULO_DO_TAMANHO] == "97"

    def test_o_tamanho_decidido_a_mao(self, projeto_vazio):
        escrever_desenho(projeto_vazio, "desenho: aas\nn: 300\nperda: 10\n")
        plano = preparar_amostragem(projeto_vazio, agora=AGORA)
        assert plano.amostragem.calculo.linhas[-3:] == (
            ("Tamanho decidido (n)", "300"),
            ("Perda esperada", "10%"),
            ("Tamanho da amostra", "334"),
        )
        assert "Nível de confiança" not in linhas(plano)

    @pytest.mark.parametrize(
        ("escrito", "lido"),
        [
            ("1", "1 ponto percentual"),
            ("1,5", "1,5 ponto percentual"),
            ("2", "2 pontos percentuais"),
        ],
    )
    def test_o_ponto_no_singular_abaixo_de_dois(self, projeto_vazio, escrito, lido):
        escrever_desenho(projeto_vazio, COM_POPULACAO.replace("margem: 5", f"margem: {escrito}"))
        assert linhas(preparar_amostragem(projeto_vazio, agora=AGORA))["Margem de erro"] == lido

    def test_a_margem_em_fracao_avisa_e_calcula(self, projeto_vazio):
        """
        `margem: 0.05` querendo 5% passa por todas as recusas — 0,05 ponto cabe em 50% — e
        dá uma amostra cem vezes maior. Uma margem pequena existe, e por isso é aviso, e
        não recusa.
        """
        escrever_desenho(
            projeto_vazio, "desenho: aas\nconfianca: 95\nmargem: 0.05\nproporcao: 50\n"
        )
        plano = preparar_amostragem(projeto_vazio, agora=AGORA)
        (aviso,) = plano.amostragem.avisos
        assert "se a intenção era 5%, escreva `margem: 5`" in aviso
        assert linhas(plano)[ROTULO_DO_TAMANHO] == "3841459"

    @pytest.mark.parametrize("margem", ["0,3", "1", "0.5"])
    def test_a_margem_pequena_que_nao_parece_fracao_nao_avisa(self, projeto_vazio, margem):
        escrever_desenho(projeto_vazio, COM_POPULACAO.replace("margem: 5", f"margem: {margem}"))
        assert preparar_amostragem(projeto_vazio, agora=AGORA).amostragem.avisos == ()

    def test_a_virgula_decimal(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO.replace("margem: 5", "margem: 2,5"))
        plano = preparar_amostragem(projeto_vazio, agora=AGORA)
        assert linhas(plano)["Margem de erro"] == "2,5 pontos percentuais"
        assert plano.amostragem.pedido.margem == pytest.approx(0.025)

    def test_a_populacao_inteira_e_um_censo(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO.replace("1200", "2"))
        plano = preparar_amostragem(projeto_vazio, agora=AGORA)
        assert linhas(plano)[ROTULO_DO_TAMANHO] == "2 — a população inteira (censo)"
        assert any("censo" in aviso for aviso in plano.amostragem.avisos)

    @pytest.mark.parametrize("escrito", ["AAS", "Aleatória simples", " aas "])
    def test_o_nome_do_desenho_sem_caixa_nem_acento(self, projeto_vazio, escrito):
        escrever_desenho(projeto_vazio, COM_POPULACAO.replace("aas", escrito))
        plano = preparar_amostragem(projeto_vazio, agora=AGORA)
        assert plano.amostragem.pedido.desenho == DESENHO_AAS

    def test_o_resumo(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO + "perda: 10\n")
        tamanho = preparar_amostragem(projeto_vazio, agora=AGORA).amostragem.tamanho
        assert resumo_do_tamanho(tamanho) == "325 de 1200"


# ── As recusas ──────────────────────────────────────────────────────────────


class TestRecusas:
    def test_sem_desenho(self, projeto_vazio):
        texto = recusa(projeto_vazio, "populacao: 1200\nconfianca: 95\nmargem: 5\nproporcao: 50\n")
        assert "falta o `desenho:`" in texto
        assert "`aas`" in texto

    @pytest.mark.parametrize("previsto", ["estratificada", "Sistemática", "dois estágios"])
    def test_o_previsto_ainda_nao_existe(self, projeto_vazio, previsto):
        texto = recusa(projeto_vazio, COM_POPULACAO.replace("aas", previsto))
        assert "ainda não está no FlatCap" in texto

    def test_o_desconhecido_sugere_a_grafia(self, projeto_vazio):
        texto = recusa(projeto_vazio, COM_POPULACAO.replace("aas", "estratificda"))
        assert "não é um desenho do FlatCap" in texto
        assert "`estratificada`" in texto

    def test_a_chave_com_acento(self, projeto_vazio):
        texto = recusa(projeto_vazio, COM_POPULACAO.replace("populacao", "população"))
        assert "a chave `população:` não existe" in texto
        assert "`populacao:`" in texto

    def test_a_confianca_em_fracao(self, projeto_vazio):
        texto = recusa(projeto_vazio, COM_POPULACAO.replace("confianca: 95", "confianca: 0.95"))
        assert "a confiança vai em %: 95, e não 0.95" in texto

    @pytest.mark.parametrize("alfa", ["5", "1", "10"])
    def test_a_confianca_escrita_como_o_alfa(self, projeto_vazio, alfa):
        """`confianca: 5` querendo 95% daria z = 0,06 e uma amostra de uma unidade."""
        texto = recusa(projeto_vazio, COM_POPULACAO.replace("confianca: 95", f"confianca: {alfa}"))
        assert "é o nível de confiança, e não o α" in texto
        assert f"para um α de {alfa}%" in texto

    @pytest.mark.parametrize("escrito", ["0", "-95"])
    def test_a_confianca_que_nao_e_positiva(self, projeto_vazio, escrito):
        desenho = COM_POPULACAO.replace("confianca: 95", f"confianca: {escrito}")
        assert "a confiança fica entre 50 e 100%" in recusa(projeto_vazio, desenho)

    def test_a_confianca_de_cem(self, projeto_vazio):
        texto = recusa(projeto_vazio, COM_POPULACAO.replace("confianca: 95", "confianca: 100"))
        assert "abaixo de 100%" in texto

    def test_a_proporcao_em_fracao_nao_cabe_na_margem(self, projeto_vazio):
        """
        O `0.5` escrito querendo 50% é meio por cento, e com margem de 5 pontos o
        intervalo passaria de zero. Sem esta recusa, o tamanho sairia 8, sem erro nenhum.
        """
        texto = recusa(projeto_vazio, COM_POPULACAO.replace("proporcao: 50", "proporcao: 0.5"))
        assert "não cabe em `proporcao: 0.5`" in texto
        assert "0.5 é meio por cento" in texto

    def test_proporcao_e_desvio_juntos(self, projeto_vazio):
        texto = recusa(projeto_vazio, COM_POPULACAO + "desvio: 10\n")
        assert "`proporcao` e `desvio` juntos" in texto

    def test_sem_proporcao_nem_desvio(self, projeto_vazio):
        texto = recusa(projeto_vazio, "desenho: aas\nconfianca: 95\nmargem: 5\n")
        assert "falta a `proporcao:`" in texto

    def test_sem_margem(self, projeto_vazio):
        texto = recusa(projeto_vazio, "desenho: aas\nconfianca: 95\nproporcao: 50\n")
        assert "falta a `margem:`" in texto

    def test_o_ponto_de_milhar_no_yaml(self, projeto_vazio):
        """
        `12.000` em português é doze mil, e no YAML é doze. Aceitá-lo daria uma população
        de 12 sem erro nenhum.
        """
        texto = recusa(projeto_vazio, COM_POPULACAO.replace("1200", "12.000"))
        assert "precisa ser um número inteiro" in texto
        assert "12000, e não 12.000" in texto

    @pytest.mark.parametrize("escrito", ["'1.200'", "mil", "0", "-5", "true"])
    def test_a_populacao_que_nao_e_inteiro_positivo(self, projeto_vazio, escrito):
        texto = recusa(projeto_vazio, COM_POPULACAO.replace("1200", escrito))
        assert "`populacao:" in texto

    def test_a_populacao_escrita_como_texto_de_algarismos_vale(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO.replace("1200", "'1200'"))
        assert preparar_amostragem(projeto_vazio, agora=AGORA).amostragem.tamanho.n == 292

    def test_o_n_com_a_conta(self, projeto_vazio):
        texto = recusa(projeto_vazio, COM_POPULACAO + "n: 300\n")
        assert "com o `n` escrito, a conta não se faz" in texto
        assert "`confianca`, `margem` e `proporcao`" in texto

    def test_o_n_maior_que_a_populacao(self, projeto_vazio):
        texto = recusa(projeto_vazio, "desenho: aas\npopulacao: 200\nn: 300\n")
        assert "`n: 300` passa da população" in texto

    @pytest.mark.parametrize("perda", ["100", "-1", "150"])
    def test_a_perda_fora_do_intervalo(self, projeto_vazio, perda):
        texto = recusa(projeto_vazio, COM_POPULACAO + f"perda: {perda}\n")
        assert "a perda é um percentual de 0 a 100" in texto

    def test_o_que_nao_e_numero(self, projeto_vazio):
        texto = recusa(projeto_vazio, COM_POPULACAO.replace("margem: 5", "margem: cinco"))
        assert "`margem: cinco` não é um número" in texto

    def test_todos_os_problemas_de_uma_vez(self, projeto_vazio):
        """Descobrir o segundo engano depois de corrigir o primeiro é o jeito mais lento."""
        texto = recusa(
            projeto_vazio,
            "desenho: aas\npopulacao: 12.000\nconfianca: 0.95\nmargem: 5\nproporcao: 50\n"
            "pereda: 10\n",
        )
        assert "tem 3 problema(s)" in texto
        assert "pereda" in texto and "populacao" in texto and "confiança" in texto

    def test_o_arquivo_que_nao_e_uma_lista_de_chaves(self, projeto_vazio):
        texto = recusa(projeto_vazio, "- aas\n- 1200\n")
        assert "deveria ser uma lista de chaves" in texto

    def test_o_yaml_quebrado_tem_o_diagnostico_da_ficha(self, projeto_vazio):
        texto = recusa(projeto_vazio, "desenho: aas\n\tpopulacao: 1200\n")
        assert "não é um YAML válido" in texto
        assert "tabulação" in texto

    def test_a_recusa_e_um_erro_da_amostragem(self):
        assert issubclass(DesenhoInvalidoError, AmostragemError)
        assert issubclass(DesenhoExistenteError, AmostragemError)

    def test_nada_e_escrito(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO.replace("95", "0.95"))
        with pytest.raises(DesenhoInvalidoError):
            preparar_amostragem(projeto_vazio, agora=AGORA)
        assert [p.name for p in (projeto_vazio / PASTA_AMOSTRAGEM).iterdir()] == [
            ARQUIVO_DESENHO
        ]


# ── O que sai ───────────────────────────────────────────────────────────────


class TestSaidas:
    @pytest.fixture
    def rodada(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO + "perda: 10\n")
        plano, resultado = rodar(projeto_vazio)
        return projeto_vazio / PASTA_AMOSTRAGEM, plano, resultado

    def test_os_arquivos_da_rodada(self, rodada):
        pasta, plano, resultado = rodada
        nome = nome_do_relatorio_da_amostra("00742", AGORA.date())
        assert nome == "Amostragem_00742_2026-09-09.docx"
        assert sorted(p.name for p in pasta.iterdir()) == sorted(
            [ARQUIVO_DESENHO, ARQUIVO_TAMANHO, ARQUIVO_MANIFESTO, nome]
        )
        assert [p.name for p in resultado.criados] == [ARQUIVO_TAMANHO, nome, ARQUIVO_MANIFESTO]
        assert resultado.arquivado is None

    def test_o_csv_e_o_texto_da_tabela(self, rodada):
        pasta, plano, _ = rodada
        texto = (pasta / ARQUIVO_TAMANHO).read_text(encoding="utf-8")
        assert texto == plano.amostragem.tabela.texto()
        assert texto.startswith("\ufeff# Tamanho da amostra\n")
        assert "# fórmula: n₀ = z²·p(1−p) / e²" in texto
        assert texto.rstrip().endswith("Tamanho da amostra;325")

    def test_o_manifesto(self, rodada):
        pasta, _, _ = rodada
        corpo = json.loads((pasta / ARQUIVO_MANIFESTO).read_text(encoding="utf-8"))
        assert corpo["analise"] == "amostragem"
        assert corpo["banco"] == {}
        assert corpo["dicionario"] == {}
        assert corpo["regras"]["ficha"] == f"{PASTA_AMOSTRAGEM}/{ARQUIVO_DESENHO}"
        (item,) = corpo["variaveis"]
        assert item["colunas"] == []
        assert item["artefatos"] == [
            {"arquivo": ARQUIVO_TAMANHO, "especie": "tamanho", "formato": "csv",
             "titulo": ROTULO_DO_TAMANHO}
        ]
        detalhes = item["detalhes"]
        assert (detalhes["n"], detalhes["n_final"], detalhes["populacao"]) == (292, 325, 1200)
        assert detalhes["n0"] == pytest.approx(384.14588206941244, rel=1e-12)
        assert detalhes["escrito"] == {
            "desenho": "aas", "populacao": 1200, "confianca": 95, "margem": 5,
            "proporcao": 50, "perda": 10,
        }
        assert detalhes["desenho_yaml"] == COM_POPULACAO + "perda: 10\n"

    def test_o_escrito_guarda_a_virgula_como_veio(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO.replace("margem: 5", "margem: 2,5"))
        plano = preparar_amostragem(projeto_vazio, agora=AGORA)
        assert plano.manifesto.itens[0].detalhes["escrito"]["margem"] == "2,5"

    def test_o_relatorio_da_amostra(self, rodada):
        pasta, plano, _ = rodada
        doc = Document(str(plano.destino))
        textos = [p.text for p in doc.paragraphs if p.text.strip()]
        assert textos[0] == TITULO_DA_AMOSTRA
        assert textos[1] == "00742 - José Antônio de Sá"
        assert ROTULO_DO_TAMANHO in textos
        (tabela,) = doc.tables
        celulas = [[celula.text for celula in linha.cells] for linha in tabela.rows]
        assert celulas[0] == ["parâmetro", "valor"]
        assert [tuple(linha) for linha in celulas[1:]] == list(plano.amostragem.calculo.linhas)

    def test_o_documento_e_o_csv_dizem_o_mesmo(self, rodada):
        """O `.docx` não recalcula: a tabela dele é a do texto do `tamanho.csv`."""
        from flatcap.relatorio import ler_tabela

        pasta, plano, _ = rodada
        do_disco = ler_tabela(pasta / ARQUIVO_TAMANHO, "tamanho", ROTULO_DO_TAMANHO)
        assert plano.relatorio.secoes[0].tabelas[0] == do_disco

    def test_os_metadados_dizem_sem_banco(self, rodada):
        _, plano, _ = rodada
        comentario = Document(str(plano.destino)).core_properties.comments
        assert "rodada amostragem de 09/09/2026 14:30" in comentario
        assert comentario.endswith("sem banco")

    def test_a_primeira_pagina_e_a_da_ficha(self, rodada):
        _, plano, _ = rodada
        from conftest import FINALIDADE, OBJETIVOS

        assert any(FINALIDADE in paragrafo for paragrafo in plano.relatorio.texto)
        assert OBJETIVOS in plano.relatorio.texto
        assert plano.relatorio.alertas == ()

    def test_a_ficha_sem_finalidade_leva_o_alerta(self, projeto_vazio):
        escrever_ficha(projeto_vazio, finalidade=None)
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        plano, _ = rodar(projeto_vazio)
        assert [alerta.codigo for alerta in plano.relatorio.alertas] == ["texto_ausente"]
        doc = Document(str(plano.destino))
        caixa = doc.tables[0].cell(0, 0).text
        assert "Atenção — a primeira página está com campo por preencher" in caixa
        assert "Finalidade do estudo: «a preencher: a finalidade do estudo»" in [
            p.text for p in doc.paragraphs
        ]

    def test_o_historico(self, rodada):
        pasta, _, _ = rodada
        ultima = linhas_do_historico(pasta.parent)[-1]
        assert "`flatcap amostragem 42` — tamanho da amostra" in ultima
        assert (
            "325 de 1200 (95% de confiança e margem de 5 pontos percentuais; perda de 10%)"
            in ultima
        )
        assert "`Amostragem_00742_2026-09-09.docx`" in ultima

    def test_o_titulo_troca(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        plano = preparar_amostragem(projeto_vazio, agora=AGORA, titulo="Cálculo amostral")
        assert plano.relatorio.titulo == "Cálculo amostral"

    def test_o_modelo_indicado_que_nao_existe(self, projeto_vazio, tmp_path):
        from flatcap.relatorio import ModeloAusenteError

        escrever_desenho(projeto_vazio, COM_POPULACAO)
        with pytest.raises(ModeloAusenteError):
            preparar_amostragem(projeto_vazio, agora=AGORA, template=tmp_path / "nao.docx")


class TestMetodologia:
    def test_o_lugar_existe_e_esta_vazio(self):
        """A regra do `TEXTO_PADRAO`: nada de parágrafo de mentira guardando o lugar."""
        from flatcap.amostragem import METODOLOGIA

        assert set(METODOLOGIA) == set(DESENHOS)
        assert METODOLOGIA[DESENHO_AAS] == ()

    def test_o_texto_entra_depois_dos_objetivos_com_os_campos(self, projeto_vazio, monkeypatch):
        import flatcap.amostragem as modulo
        from conftest import OBJETIVOS

        monkeypatch.setitem(
            modulo.METODOLOGIA,
            DESENHO_AAS,
            ("Amostra {desenho} de {n_final} em {populacao}, com {confianca} e "
             "margem de {margem}.",),
        )
        escrever_desenho(projeto_vazio, COM_POPULACAO + "perda: 10\n")
        plano = preparar_amostragem(projeto_vazio, agora=AGORA)
        texto = plano.relatorio.texto
        assert texto[-1] == (
            "Amostra aleatória simples, sem reposição de 325 em 1200, com 95% e margem "
            "de 5 pontos percentuais."
        )
        assert texto.index(OBJETIVOS) < len(texto) - 1


# ── As versões antigas, dentro da pasta da amostra ──────────────────────────


class TestArquivamento:
    def test_refazer_arquiva_a_rodada_com_a_copia_do_desenho(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO + "perda: 10\n")
        rodar(projeto_vazio)
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        plano, resultado = rodar(projeto_vazio, agora=DEPOIS)

        pasta = projeto_vazio / PASTA_AMOSTRAGEM
        destino = pasta / PASTA_ANTIGAS_DA_AMOSTRAGEM / "amostragem_2026-09-09_1630"
        assert resultado.arquivado == destino
        assert sorted(p.name for p in destino.iterdir()) == sorted(
            [ARQUIVO_TAMANHO, ARQUIVO_MANIFESTO, "Amostragem_00742_2026-09-09.docx",
             ARQUIVO_DESENHO]
        )
        # a vigente continua no lugar, com o que está nela
        assert (pasta / ARQUIVO_DESENHO).read_text(encoding="utf-8") == COM_POPULACAO
        assert (pasta / ARQUIVO_TAMANHO).read_text(encoding="utf-8").rstrip().endswith(";292")
        antigo = (destino / ARQUIVO_TAMANHO).read_text(encoding="utf-8")
        assert antigo.rstrip().endswith("Tamanho da amostra;325")
        arquivada = f"`{PASTA_AMOSTRAGEM}/{PASTA_ANTIGAS_DA_AMOSTRAGEM}/{destino.name}/`"
        assert arquivada in linhas_do_historico(projeto_vazio)[-1]

    def test_a_copia_e_o_desenho_de_entao_e_nao_o_de_agora(self, projeto_vazio):
        """
        O caso de todo dia é mudar a ficha e rodar de novo: na hora de arquivar, o
        `desenho.yaml` da pasta já é o novo, e copiá-lo poria a ficha nova ao lado do
        relatório velho. A cópia vem do manifesto da rodada, que guarda o texto que ela
        leu — comentários incluídos.
        """
        primeiro = "# a primeira conversa com o cliente\n" + COM_POPULACAO + "perda: 10\n"
        escrever_desenho(projeto_vazio, primeiro)
        rodar(projeto_vazio)
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        _, resultado = rodar(projeto_vazio, agora=DEPOIS)
        copia = resultado.arquivado / ARQUIVO_DESENHO
        assert copia.read_text(encoding="utf-8") == primeiro

    def test_sem_o_manifesto_vai_sem_a_copia(self, projeto_vazio):
        """Sem saber qual foi a ficha de então, nenhuma cópia — e não a errada."""
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        rodar(projeto_vazio)
        (projeto_vazio / PASTA_AMOSTRAGEM / ARQUIVO_MANIFESTO).unlink()
        plano, resultado = rodar(projeto_vazio, agora=DEPOIS)
        assert plano.amostragem.avisos == ()
        assert sorted(p.name for p in resultado.arquivado.iterdir()) == [
            "Amostragem_00742_2026-09-09.docx", ARQUIVO_TAMANHO,
        ]

    def test_o_manifesto_quebrado_nao_impede_a_rodada(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        rodar(projeto_vazio)
        (projeto_vazio / PASTA_AMOSTRAGEM / ARQUIVO_MANIFESTO).write_text("{", encoding="utf-8")
        _, resultado = rodar(projeto_vazio, agora=DEPOIS)
        assert ARQUIVO_MANIFESTO in [p.name for p in resultado.arquivado.iterdir()]
        assert ARQUIVO_DESENHO not in [p.name for p in resultado.arquivado.iterdir()]

    def test_o_tamanho_que_muda_avisa(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO + "perda: 10\n")
        rodar(projeto_vazio)
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        plano = preparar_amostragem(projeto_vazio, agora=DEPOIS)
        (aviso,) = plano.amostragem.avisos
        assert "era 325, e passa a ser 292" in aviso

    def test_o_mesmo_tamanho_nao_avisa(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        rodar(projeto_vazio)
        plano = preparar_amostragem(projeto_vazio, agora=DEPOIS)
        assert plano.amostragem.avisos == ()
        assert plano.arquivamento is not None

    def test_duas_rodadas_no_mesmo_minuto(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        rodar(projeto_vazio)
        rodar(projeto_vazio, agora=DEPOIS)
        _, resultado = rodar(projeto_vazio, agora=DEPOIS)
        assert resultado.arquivado.name == "amostragem_2026-09-09_1630_2"

    def test_o_que_e_seu_fica_onde_esta(self, projeto_vazio):
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        rodar(projeto_vazio)
        (projeto_vazio / PASTA_AMOSTRAGEM / "anotacoes.txt").write_text("minhas", encoding="utf-8")
        rodar(projeto_vazio, agora=DEPOIS)
        assert (projeto_vazio / PASTA_AMOSTRAGEM / "anotacoes.txt").is_file()


# ── O desfazer ──────────────────────────────────────────────────────────────


class TestDesfazer:
    def test_a_falha_no_documento_devolve_a_rodada_anterior(self, projeto_vazio, monkeypatch):
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        rodar(projeto_vazio)
        pasta = projeto_vazio / PASTA_AMOSTRAGEM
        antes = {p.name: p.read_bytes() for p in pasta.iterdir() if p.is_file()}

        def quebrar(*_a, **_k):
            raise RuntimeError("o Word travou")

        monkeypatch.setattr("flatcap.documento.escrever", quebrar)
        plano = preparar_amostragem(projeto_vazio, agora=DEPOIS)
        with pytest.raises(RuntimeError, match="o Word travou"):
            executar_amostragem(plano)

        depois = {p.name: p.read_bytes() for p in pasta.iterdir() if p.is_file()}
        assert depois == antes
        assert not (pasta / PASTA_ANTIGAS_DA_AMOSTRAGEM).exists()

    def test_a_falha_no_modelo_nao_deixa_pasta(self, projeto_vazio, monkeypatch):
        def quebrar(*_a, **_k):
            raise OSError("disco cheio")

        monkeypatch.setattr("flatcap.amostragem.escrever_atomico", quebrar)
        plano = preparar_amostragem(projeto_vazio, agora=AGORA)
        with pytest.raises(OSError, match="disco cheio"):
            executar_amostragem(plano)
        assert not (projeto_vazio / PASTA_AMOSTRAGEM).exists()


# ── A arquitetura ───────────────────────────────────────────────────────────


class TestArquitetura:
    def test_nao_e_uma_analise_do_lote(self):
        from flatcap.analises import REGISTRO
        from flatcap.manifesto import ORDEM_PADRAO_DAS_ANALISES

        assert "amostragem" not in {registro.nome for registro in REGISTRO}
        assert "amostragem" not in ORDEM_PADRAO_DAS_ANALISES

    def test_o_relatorio_das_analises_nao_ve_a_amostra(self, projeto_com_rodada):
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_com_rodada()
        escrever_desenho(raiz, COM_POPULACAO)
        rodar(raiz)
        plano = preparar_relatorio(raiz, agora=DEPOIS)
        assert plano.relatorio.analises == ("descritiva",)
        assert ROTULO_DO_TAMANHO not in [secao.rotulo for secao in plano.relatorio.secoes]

    def test_o_registro_tem_o_espaco_para_os_outros(self):
        assert set(DESENHOS) == {DESENHO_AAS}
        assert all(desenho.sortear is None for desenho in DESENHOS.values())
        assert not set(PREVISTOS) & set(DESENHOS)

    def test_ler_desenho_e_publico(self, projeto_vazio):
        caminho = escrever_desenho(projeto_vazio, COM_POPULACAO)
        pedido, desenho = ler_desenho(caminho)
        assert desenho is DESENHOS[DESENHO_AAS]
        assert pedido.estima == "proporcao"
        assert ler_yaml(caminho)["populacao"] == 1200

    def test_a_conta_nao_traz_o_pandas(self, projeto_vazio):
        """
        Sem banco, nada na amostragem precisa do `pandas`, e o comando parte rápido. A
        conta inteira é preparada em processo limpo, e o `python-docx` também não vem —
        ele entra só na execução.
        """
        escrever_desenho(projeto_vazio, COM_POPULACAO)
        codigo = (
            "import sys\n"
            "from flatcap.amostragem import preparar_amostragem\n"
            f"preparar_amostragem({str(projeto_vazio)!r})\n"
            "print(sorted(m for m in ('pandas', 'scipy', 'numpy', 'matplotlib', 'docx')"
            " if m in sys.modules))\n"
        )
        saida = subprocess.run(
            [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
        ).stdout.strip()
        assert saida == "[]"
