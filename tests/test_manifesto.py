"""
O `manifesto.json` — Fase 5.

O índice da rodada. Ele responde três coisas que não são adivinháveis a partir
da pasta: de qual variável saiu cada arquivo, sobre qual banco, e com quais
versões de biblioteca.

Dois testes aqui são de arquitetura, não de formato: o módulo **não importa o
pandas nem o matplotlib**, e **não escreve no disco**. Sem os dois, a Fase 6
teria de carregar meio segundo de biblioteca para ler uma lista.
"""

from __future__ import annotations

import ast
import inspect
import json
from datetime import datetime

import pytest

from flatcap.manifesto import (
    ARQUIVO_MANIFESTO,
    FORMATO,
    Artefato,
    ItemDoManifesto,
    Manifesto,
    ManifestoInvalidoError,
    de_dicionario,
    ler,
    texto_do_manifesto,
)


def _manifesto(**alteracoes) -> Manifesto:
    base = {
        "flatcap": "1.0.0",
        "gerado_em": datetime(2026, 9, 9, 15, 0),
        "projeto": {"pasta": "00742 - José", "record_id": "42"},
        "banco": {"arquivo": "00_redcap_b.csv", "sha256": "a" * 64, "integridade": "confere"},
        "dicionario": {"arquivo": "dicionario.csv", "variaveis": 7, "analisaveis": 5},
        "ambiente": {"python": "3.11.15", "pandas": "3.0.2"},
        "regras": {"faixas_padrao": "quartis", "semente": 42},
        "itens": (
            ItemDoManifesto(
                variavel="sexo", slug="sexo", rotulo="Sexo", tipo="categorica",
                n=24, faltantes=0,
                artefatos=(
                    Artefato("freq_sexo.csv", "frequencia", "csv", "Frequência — Sexo"),
                    Artefato("graf_sexo.png", "barras", "png", "Sexo"),
                ),
            ),
            ItemDoManifesto(
                variavel="idade", slug="idade", rotulo="Idade", tipo="numerica",
                n=24, faltantes=2,
                artefatos=(Artefato("resumo_idade.csv", "resumo", "csv", "Resumo"),),
            ),
        ),
        "fora": ({"variavel": "obs", "tipo": "ignorar", "motivo": "marcada `ignorar`"},),
        "avisos": (),
    }
    base.update(alteracoes)
    return Manifesto(**base)


class TestArquitetura:
    def test_nao_importa_pandas_nem_matplotlib(self):
        import flatcap.manifesto as modulo

        arvore = ast.parse(inspect.getsource(modulo))
        nomes = {
            alias.name.split(".")[0]
            for no in ast.walk(arvore)
            if isinstance(no, ast.Import)
            for alias in no.names
        } | {
            no.module.split(".")[0]
            for no in ast.walk(arvore)
            if isinstance(no, ast.ImportFrom) and no.module
        }
        assert {"pandas", "matplotlib"}.isdisjoint(nomes)

    def test_nao_escreve_no_disco(self):
        """
        Monta o texto; quem grava é o `descritiva.py`, com a escrita atômica do
        `ficha.py`. É a mesma invariante das outras fases: o texto é o arquivo, e
        por isso a simulação pode mostrá-lo inteiro antes de ele existir.
        """
        import flatcap.manifesto as modulo

        fonte = inspect.getsource(modulo)
        for proibido in ("write_text", "write_bytes", "open(", "escrever_atomico"):
            assert proibido not in fonte


class TestTexto:
    def test_o_formato_e_a_primeira_chave(self):
        """
        Custa uma linha e compra a única coisa que um arquivo lido por outra
        versão do programa precisa: ser recusado com uma frase em vez de
        interpretado errado em silêncio.
        """
        texto = texto_do_manifesto(_manifesto())
        assert json.loads(texto)["formato"] == FORMATO
        assert texto.lstrip().startswith('{\n  "formato"')

    def test_sai_em_utf8_legivel_e_nao_em_escapes(self):
        assert "José" in texto_do_manifesto(_manifesto())
        assert "\\u00e9" not in texto_do_manifesto(_manifesto())

    def test_a_ordem_das_variaveis_e_preservada(self):
        corpo = json.loads(texto_do_manifesto(_manifesto()))
        assert [v["variavel"] for v in corpo["variaveis"]] == ["sexo", "idade"]

    def test_termina_com_quebra_de_linha(self):
        assert texto_do_manifesto(_manifesto()).endswith("\n")

    def test_ida_e_volta(self):
        original = _manifesto()
        volta = de_dicionario(json.loads(texto_do_manifesto(original)))
        assert volta.gerado_em == original.gerado_em
        assert [i.variavel for i in volta.itens] == [i.variavel for i in original.itens]
        assert volta.banco == original.banco


class TestConsultas:
    def test_tabelas_e_figuras_se_separam_pelo_formato(self):
        manifesto = _manifesto()
        assert [a.arquivo for a in manifesto.tabelas] == [
            "freq_sexo.csv", "resumo_idade.csv",
        ]
        assert [a.arquivo for a in manifesto.figuras] == ["graf_sexo.png"]

    def test_a_especie_e_um_campo_e_nao_a_extensao(self):
        """
        É o que decide se um arquivo vira tabela ou figura no documento — e por
        isso é campo próprio e não dedução.
        """
        item = _manifesto().item("sexo")
        assert item.artefato("frequencia").arquivo == "freq_sexo.csv"
        assert item.artefato("barras").arquivo == "graf_sexo.png"
        assert item.artefato("histograma") is None

    def test_total_de_artefatos(self):
        assert _manifesto().total_artefatos == 3

    def test_por_tipo(self):
        assert [i.variavel for i in _manifesto().por_tipo("numerica")] == ["idade"]

    def test_preenchidos(self):
        assert _manifesto().item("idade").preenchidos == 22

    def test_item_inexistente(self):
        assert _manifesto().item("nao_existe") is None


class TestLeitura:
    def test_le_de_uma_pasta_ou_de_um_arquivo(self, tmp_path):
        caminho = tmp_path / ARQUIVO_MANIFESTO
        caminho.write_text(texto_do_manifesto(_manifesto()), encoding="utf-8", newline="\n")
        assert ler(tmp_path).flatcap == "1.0.0"
        assert ler(caminho).flatcap == "1.0.0"

    def test_pasta_sem_manifesto(self, tmp_path):
        with pytest.raises(ManifestoInvalidoError) as erro:
            ler(tmp_path)
        # Desde a Fase 7 o manifesto é de qualquer análise: a mensagem manda
        # rodar "a análise", e não a descritiva — que numa pasta
        # `normalidade/` seria o comando errado.
        assert ARQUIVO_MANIFESTO in str(erro.value)
        assert "Rode a análise de novo" in str(erro.value)

    def test_json_invalido_manda_regerar(self, tmp_path):
        (tmp_path / ARQUIVO_MANIFESTO).write_text("{quebrado", encoding="utf-8")
        with pytest.raises(ManifestoInvalidoError) as erro:
            ler(tmp_path)
        assert "não é feito para ser editado à mão" in str(erro.value)

    def test_formato_mais_novo_e_recusado_com_uma_frase(self, tmp_path):
        corpo = json.loads(texto_do_manifesto(_manifesto()))
        corpo["formato"] = FORMATO + 1
        (tmp_path / ARQUIVO_MANIFESTO).write_text(
            json.dumps(corpo), encoding="utf-8", newline="\n"
        )
        with pytest.raises(ManifestoInvalidoError) as erro:
            ler(tmp_path)
        assert "Atualize o FlatCap" in str(erro.value)

    def test_formato_ausente_e_recusado(self, tmp_path):
        (tmp_path / ARQUIVO_MANIFESTO).write_text('{"flatcap": "1.0.0"}', encoding="utf-8")
        with pytest.raises(ManifestoInvalidoError):
            ler(tmp_path)

    def test_gerado_em_que_nao_e_data(self, tmp_path):
        corpo = json.loads(texto_do_manifesto(_manifesto()))
        corpo["gerado_em"] = "ontem"
        (tmp_path / ARQUIVO_MANIFESTO).write_text(json.dumps(corpo), encoding="utf-8")
        with pytest.raises(ManifestoInvalidoError) as erro:
            ler(tmp_path)
        assert "gerado_em" in str(erro.value)

    def test_arquivo_que_nao_e_utf8(self, tmp_path):
        (tmp_path / ARQUIVO_MANIFESTO).write_bytes('{"formato": 1, "n": "José"}'.encode("cp1252"))
        with pytest.raises(ManifestoInvalidoError) as erro:
            ler(tmp_path)
        assert "UTF-8" in str(erro.value)

    def test_corpo_que_nao_e_objeto(self):
        with pytest.raises(ManifestoInvalidoError) as erro:
            de_dicionario([1, 2, 3])
        assert "objeto JSON" in str(erro.value)
