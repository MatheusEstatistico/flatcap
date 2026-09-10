"""
Os `.png` — Fase 5.

Este módulo desenha e não calcula. O teste central não é sobre pixels: é que
**nada aqui recalcula nada**. Se o desenho recontasse, bastaria uma diferença de
arredondamento para o `.png` dizer 37 e o `.csv` ao lado dizer 38 sobre a mesma
coisa — e ninguém confere gráfico contra tabela.

O resto é o que dá para verificar sem olhar a imagem. O que não dá está escrito
no fim, como lembrete: dois dos defeitos da Fase 5 só apareceram ao ampliar o
`.png`.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from flatcap.descritiva import Grafico
from flatcap.graficos import (
    ALTURA_MAXIMA,
    DPI,
    LARGURA_POLEGADAS,
    SERIE,
    desenhar,
    versao_do_matplotlib,
)

BARRAS = Grafico(
    nome="graf_sexo.png", especie="barras", variavel="sexo", titulo="Sexo",
    subtitulo="n = 24", rotulo_valor="casos",
    categorias=("Feminino", "Masculino"), valores=(12.0, 12.0),
    rotulos=("12  (50,0%)", "12  (50,0%)"),
)

HISTOGRAMA = Grafico(
    nome="hist_idade.png", especie="histograma", variavel="idade", titulo="Idade",
    subtitulo="n = 24", rotulo_categoria="Idade", rotulo_valor="casos",
    bordas=(20.0, 30.0, 40.0, 50.0, 62.0), contagens=(6, 7, 6, 5),
)

COLUNAS = Grafico(
    nome="graf_periodo.png", especie="colunas", variavel="data_coleta",
    titulo="Data da coleta", subtitulo="n = 24", rotulo_categoria="mês",
    rotulo_valor="casos",
    categorias=("2026-01", "2026-02", "2026-03"), valores=(8.0, 9.0, 7.0),
    rotulos=("8", "9", "7"),
)


class TestArquitetura:
    def test_e_o_unico_modulo_que_importa_o_matplotlib(self):
        from pathlib import Path

        import flatcap

        pacote = Path(flatcap.__file__).parent
        culpados = []
        for arquivo in pacote.glob("*.py"):
            if arquivo.name == "graficos.py":
                continue
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            for no in ast.walk(arvore):
                if isinstance(no, ast.Import) and any(
                    a.name.split(".")[0] == "matplotlib" for a in no.names
                ):
                    culpados.append(arquivo.name)
                if (
                    isinstance(no, ast.ImportFrom)
                    and (no.module or "").split(".")[0] == "matplotlib"
                ):
                    culpados.append(arquivo.name)
        assert culpados == []

    def test_nao_recalcula_nada(self):
        """
        Recebe as contagens prontas. O módulo não pode ter `sum`, `mean`,
        `value_counts` nem aritmética sobre os dados — só sobre coordenadas.
        """
        import flatcap.graficos as modulo

        fonte = inspect.getsource(modulo)
        for proibido in ("value_counts", ".mean(", ".sum(", "quantile", "dropna"):
            assert proibido not in fonte

    def test_o_agg_e_escolhido_antes_de_importar_o_pyplot(self):
        """
        Sem isso a biblioteca procura um servidor gráfico, que não existe em
        terminal nem em servidor, e o comando morre por um motivo que não tem
        nada a ver com estatística.
        """
        import matplotlib

        assert matplotlib.get_backend().lower() == "agg"

    def test_nao_declara_erro_proprio(self):
        """
        O que pode falhar aqui é escrita em disco, que é `OSError`, e quem sabe
        o que fazer com ela é o `executar_descritiva` — que desfaz a rodada.
        """
        import flatcap.graficos as modulo

        assert not [
            nome
            for nome, objeto in vars(modulo).items()
            if isinstance(objeto, type)
            and issubclass(objeto, Exception)
            and objeto.__module__ == modulo.__name__
        ]


class TestDesenho:
    @pytest.mark.parametrize("grafico", [BARRAS, HISTOGRAMA, COLUNAS])
    def test_escreve_um_png_valido(self, tmp_path, grafico):
        caminho = desenhar(grafico, tmp_path / grafico.nome)
        assert caminho.is_file()
        assert caminho.read_bytes().startswith(b"\x89PNG")

    def test_a_largura_cabe_na_mancha_de_um_a4(self, tmp_path):
        from PIL import Image

        caminho = desenhar(BARRAS, tmp_path / "g.png")
        largura, _ = Image.open(caminho).size
        assert largura <= LARGURA_POLEGADAS * DPI * 1.1

    def test_muitas_categorias_nao_estouram_a_altura(self, tmp_path):
        from PIL import Image

        grafico = Grafico(
            nome="g.png", especie="barras", variavel="v", titulo="V",
            categorias=tuple(f"cat {i}" for i in range(40)),
            valores=tuple(float(i + 1) for i in range(40)),
            rotulos=tuple(str(i + 1) for i in range(40)),
        )
        caminho = desenhar(grafico, tmp_path / "g.png")
        _, altura = Image.open(caminho).size
        assert altura <= ALTURA_MAXIMA * DPI * 1.15

    def test_nao_deixa_figura_aberta(self, tmp_path):
        """
        Uma figura que não fecha vaza memória, e a descritiva de um banco com
        cinquenta variáveis desenha cinquenta.
        """
        import matplotlib.pyplot as plt

        plt.close("all")
        for i in range(5):
            desenhar(BARRAS, tmp_path / f"g{i}.png")
        assert plt.get_fignums() == []

    def test_a_falha_de_escrita_tambem_fecha_a_figura(self, tmp_path):
        import matplotlib.pyplot as plt

        plt.close("all")
        with pytest.raises(OSError):
            desenhar(BARRAS, tmp_path / "sem" / "pasta" / "g.png")
        assert plt.get_fignums() == []

    def test_duas_chamadas_iguais_produzem_o_mesmo_arquivo(self, tmp_path):
        """
        Nada aqui sorteia coisa nenhuma. Um `.png` que muda entre duas execuções
        idênticas é um `.png` que produz diff falso.
        """
        a = desenhar(BARRAS, tmp_path / "a.png").read_bytes()
        b = desenhar(BARRAS, tmp_path / "b.png").read_bytes()
        assert a == b

    def test_uma_cor_so_para_a_serie(self):
        """
        Colorir cada barra de um tom diferente codificaria o tamanho duas vezes,
        gastando o único canal livre para repetir o que o gráfico já mostra.
        """
        import flatcap.graficos as modulo

        fonte = inspect.getsource(modulo)
        assert fonte.count("color=SERIE") >= 3
        assert "colormap" not in fonte and "cmap" not in fonte

    def test_a_versao_e_informavel(self):
        assert versao_do_matplotlib()[0].isdigit()

    def test_a_cor_da_serie_tem_nome(self):
        assert SERIE.startswith("#")


def test_o_que_so_se_ve_ampliando_o_png():
    """
    Lembrete, não teste. Dois defeitos da Fase 5 não teriam sido pegos por
    nenhuma asserção: o eixo do gráfico de colunas oferecendo `12,5 casos` —
    meio caso não existe —, e o rabo do `_` de `data_coleta` no título riscando
    o `n = 240` do subtítulo.

    Antes de mesclar: abrir os `.png` de um projeto de verdade e olhar. É o
    passo 4 do ritual do roteiro.
    """
    assert True
