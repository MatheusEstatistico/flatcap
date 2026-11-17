# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Os testes do `caracterizacao.py` — a Tabela 1.

O miolo é testado pela função pura `caracterizar(banco, ficha, linhas, pedidos)`, como o
`comparar` da comparação e o `associar` da associação. O caminho do disco — a ficha com a
lista `caracterizacao:`, a rodada escrita, o manifesto — usa os fixtures do `conftest.py`.

**Nenhum número daqui é conferido contra o próprio módulo.** As referências são três:

* o **R 4.5.0**, sobre o `bancos.para_caracterizar()`: o p de cada linha — o `t.test`, o
  `wilcox.test`, o `oneway.test`, o `kruskal.test`, o `chisq.test` e o `fisher.test` —, o
  `shapiro.test` de cada grupo que decide a forma, o resumo de cada grupo e do Total, e as
  contagens do `table`, em `POR_SEXO_DO_R`, `POR_GRUPO_DO_R`, `RESUMOS_DO_R` e
  `CONTAGENS_DO_R`;
* a **descritiva**: o Total de uma tabela sem caso fora sai, letra por letra, o do
  `resumo_<variável>.csv`;
* a **contagem**: os grupos somam o Total, as categorias somam os válidos, e os válidos
  mais a `(sem informação)` somam o n do cabeçalho.

E uma conferência que **não é referência**, num bloco à parte: o p de cada linha é o que
a comparação e a associação dão para o mesmo par, no mesmo banco. É a promessa de "sem
conta nova", e não a prova de que a conta está certa — essa é a do R.
"""

from __future__ import annotations

import json
import re

import pandas as pd
import pytest

import bancos
from conftest import (
    AGORA,
    RECORD_ID,
    acrescentar_a_ficha,
    banco_em_memoria,
    ficha_em_memoria,
    linhas_do_historico,
)
from flatcap.associacao import associar
from flatcap.caracterizacao import (
    PERCENTUAIS,
    CaracterizacaoError,
    ItemInvalidoError,
    Pedido,
    SemItensError,
    caracterizar,
    executar_caracterizacao,
    itens_da_ficha,
    montar_manifesto,
    preparar_caracterizacao,
)
from flatcap.comparacao import COLUNA_DA_MEDIA, COLUNA_DA_MEDIANA, comparar
from flatcap.descritiva import descrever
from flatcap.dicionario import CATEGORICA, DATA, IGNORAR, NUMERICA, Linha, texto_do_dicionario
from flatcap.manifesto import ANALISE_CARACTERIZACAO, ARQUIVO_MANIFESTO
from flatcap.manifesto import ler as ler_manifesto
from flatcap.normalidade import ALFA, valor_p
from flatcap.projeto import PASTA_ANALISES, PASTA_ANTIGAS, PASTA_CARACTERIZACAO

SEXO = Linha(
    "sexo",
    "Sexo",
    CATEGORICA,
    ("1", "2"),
    rotulos_das_categorias=(("1", "Feminino"), ("2", "Masculino")),
)
GRUPO = Linha("grupo", "Grupo", CATEGORICA, ("Controle", "Dose baixa", "Dose alta"))
IDADE = Linha("idade", "Idade (anos)", NUMERICA)
PAS = Linha("pas", "PAS na inclusão (mmHg)", NUMERICA)
IMC = Linha("imc", "IMC (kg/m²)", NUMERICA)
ESCOLARIDADE = Linha(
    "escolaridade",
    "Escolaridade",
    CATEGORICA,
    ("Fundamental", "Médio", "Superior", "Pós-graduação"),
)
TABAGISMO = Linha("tabagismo", "Tabagismo atual", CATEGORICA, ("Sim", "Não"))
AVC = Linha(
    "avc", "AVC prévio", CATEGORICA, ("1", "0"), rotulos_das_categorias=(("1", "Sim"), ("0", "Não"))
)
DATA_INCLUSAO = Linha("data_inclusao", "Data de inclusão", DATA)
OBS = Linha("obs", "Observações", IGNORAR)
DICIONARIO = (SEXO, GRUPO, IDADE, PAS, IMC, ESCOLARIDADE, TABAGISMO, AVC, DATA_INCLUSAO, OBS)

# O exemplo do plano: o grupo antes dos dois-pontos, as linhas na ordem da lista.
POR_SEXO = Pedido(
    grupo="sexo", variaveis=("idade", "pas", "imc", "escolaridade", "tabagismo", "avc")
)
BLOCO = "caracterizacao:\n  - sexo: [idade, pas, imc, escolaridade, tabagismo, avc]\n"

# No R 4.5.0, sobre o `bancos.para_caracterizar()` gravado com `to_csv(index=False)`, nos
# casos com `sexo`:
#
#     d <- read.csv("caracterizar.csv", na.strings = "", encoding = "UTF-8")
#     s <- d[!is.na(d$sexo), ]
#     t.test(idade ~ sexo, data = s)$p.value
#     t.test(pas ~ sexo, data = s)$p.value
#     wilcox.test(imc ~ sexo, data = s)$p.value
#     chisq.test(table(s$sexo, s$escolaridade))$p.value
#     chisq.test(table(s$sexo, s$tabagismo))$p.value
#     fisher.test(table(s$sexo, s$avc))$p.value
#
#     (variável, teste, p)
POR_SEXO_DO_R = [
    ("idade", "t de Welch", 0.0175751356721702),
    ("pas", "t de Welch", 1.7813581945790692e-09),
    ("imc", "Mann-Whitney", 0.091237072378268835),
    ("escolaridade", "Qui-quadrado", 0.10633333272480541),
    ("tabagismo", "Qui-quadrado com correção de Yates", 0.088986038565000092),
    ("avc", "Exato de Fisher", 0.094367581343870757),
]

# E entre os três grupos de `grupo`, sobre os 120 casos — nenhum sem o grupo:
#
#     chisq.test(table(d$grupo, d$sexo))$p.value
#     oneway.test(idade ~ grupo, data = d)$p.value
#     oneway.test(pas ~ grupo, data = d)$p.value
#     kruskal.test(imc ~ grupo, data = d)$p.value
#     chisq.test(table(d$grupo, d$escolaridade))$p.value
#     chisq.test(table(d$grupo, d$tabagismo))$p.value
#     fisher.test(table(d$grupo, d$avc))$p.value
POR_GRUPO_DO_R = [
    ("sexo", "Qui-quadrado", 0.99148879418892832),
    ("idade", "ANOVA de Welch", 0.93234176118961487),
    ("pas", "ANOVA de Welch", 0.94284116418864183),
    ("imc", "Kruskal-Wallis", 0.96097275994732034),
    ("escolaridade", "Qui-quadrado", 0.99294637693665477),
    ("tabagismo", "Qui-quadrado", 0.94586197244007453),
    ("avc", "Exato de Fisher", 0.90776820878268905),
]

# O resumo de cada sexo e do Total, no R 4.5.0 — `mean`, `sd` e o `quantile`, do tipo 7 —,
# e o `shapiro.test` de cada sexo, que decide a forma, sobre os valores preenchidos:
#
#     x <- s$idade[s$sexo == 1 & !is.na(s$idade)]
#     c(length(x), mean(x), sd(x), quantile(x, c(.25, .5, .75)), shapiro.test(x)$p.value)
#
#     (variável, (n, média, DP, Q1, mediana, Q3, p do Shapiro-Wilk) de Feminino, e de
#      Masculino, (n, média, DP, Q1, mediana, Q3) do Total)
RESUMOS_DO_R = [
    ("idade",
     (59, 52.062711864406779, 9.0413017506651627, 45.95, 52.2, 58.05, 0.99999999983817056),
     (58, 56.106896551724141, 9.1144547251318944, 49.825, 56.4, 62.175, 0.99999995854574708),
     (117, 54.067521367521366, 9.2637393680565552, 47.6, 54.3, 60.4)),
    ("pas",
     (59, 121.93220338983051, 9.1063910993582464, 116, 122, 128, 0.99999996785020384),
     (58, 133, 9.1995423227119524, 127, 133, 139, 0.9999999051427908),
     (117, 127.41880341880342, 10.674041438218975, 120, 127, 135)),
    ("imc",
     (57, 26.998245614035088, 5.6662374524165431, 23, 25.7, 29.3, 2.5250092188193664e-05),
     (57, 25.366666666666667, 4.605948534749591, 22.2, 24.3, 27.4, 1.5962619337731169e-05),
     (114, 26.182456140350876, 5.2053792056919788, 22.525, 24.9, 28.375)),
]

# O `table` do R sobre os mesmos casos, com o `useNA = "ifany"`:
#
#     table(s$sexo, s$escolaridade, useNA = "ifany")
#
#     (variável, {categoria: (Feminino, Masculino)}, (sem resposta em Feminino, em Masculino))
CONTAGENS_DO_R = [
    ("escolaridade",
     {"Fundamental": (25, 15), "Médio": (19, 21), "Superior": (13, 21), "Pós-graduação": (0, 0)},
     (2, 1)),
    ("tabagismo", {"Sim": (7, 15), "Não": (52, 43)}, (0, 0)),
    ("avc", {"Sim": (2, 7), "Não": (57, 51)}, (0, 0)),
]

# O `shapiro.test` da variável inteira, que decide a forma na tabela sem grupo:
#
#     shapiro.test(d$idade)$p.value; shapiro.test(d$imc[!is.na(d$imc)])$p.value
SHAPIRO_SEM_GRUPO_DO_R = {"idade": 0.99999717662006704, "imc": 7.2219359964013908e-09}


def _caracterizar(*pedidos, quadro=None, linhas=DICIONARIO, **opcoes):
    quadro = bancos.para_caracterizar() if quadro is None else quadro
    return caracterizar(
        banco_em_memoria(quadro), ficha_em_memoria(), linhas, pedidos or (POR_SEXO,), AGORA,
        **opcoes,
    )


def _tabela(*pedidos, **opcoes):
    return _caracterizar(*pedidos, **opcoes).tabelas[0]


def _linha(tabela, variavel: str):
    return next(c for c in tabela.caracteristicas if c.variavel == variavel)


def _detalhe(manifesto, variavel: str, tabela: int = 0) -> dict:
    tabelas = manifesto.itens[0].detalhes["tabelas"]
    return next(linha for linha in tabelas[tabela]["linhas"] if linha["variavel"] == variavel)


def _n(celula: str) -> int:
    """`39 (38,2)` → 39; o traço da coluna sem resposta, zero."""
    return 0 if celula == "—" else int(celula.split(" ")[0])


def _como_a_descritiva(valor: float) -> str:
    """O número com até duas casas, sem os zeros do fim — escrito aqui de novo."""
    texto = f"{round(valor, 2):.2f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


# ── O R ─────────────────────────────────────────────────────────────────────


class TestReferenciasDoR:
    @pytest.mark.parametrize(
        ("variavel", "teste", "p"), POR_SEXO_DO_R, ids=[v for v, *_ in POR_SEXO_DO_R]
    )
    def test_o_teste_e_o_p_de_cada_linha_entre_dois_grupos(self, variavel, teste, p):
        linha = _linha(_tabela(), variavel)
        assert linha.teste == teste
        assert linha.p == pytest.approx(p, rel=1e-9)

    @pytest.mark.parametrize(
        ("variavel", "teste", "p"), POR_GRUPO_DO_R, ids=[v for v, *_ in POR_GRUPO_DO_R]
    )
    def test_o_teste_e_o_p_de_cada_linha_entre_tres_grupos(self, variavel, teste, p):
        linha = _linha(_tabela(Pedido(grupo="grupo", todas=True)), variavel)
        assert linha.teste == teste
        assert linha.p == pytest.approx(p, rel=1e-9)

    @pytest.mark.parametrize(
        ("variavel", "feminino", "masculino", "total"),
        RESUMOS_DO_R,
        ids=[v for v, *_ in RESUMOS_DO_R],
    )
    def test_o_resumo_e_o_shapiro_de_cada_grupo(self, variavel, feminino, masculino, total):
        """
        A forma sai do Shapiro-Wilk do R: a média quando ele não rejeita em nenhum
        grupo, a mediana quando rejeita em algum.
        """
        detalhe = _detalhe(montar_manifesto(_caracterizar(), DICIONARIO), variavel)
        for grupo, do_r in zip(detalhe["grupos"], (feminino, masculino), strict=True):
            n, media, desvio, q1, mediana, q3, p_shapiro = do_r
            assert grupo["n"] == n
            assert (grupo["media"], grupo["desvio"]) == pytest.approx((media, desvio), abs=1e-6)
            assert (grupo["q1"], grupo["mediana"], grupo["q3"]) == pytest.approx(
                (q1, mediana, q3), abs=1e-6
            )
            assert grupo["shapiro"]["p"] == pytest.approx(p_shapiro, rel=1e-5)
        n, media, desvio, q1, mediana, q3 = total
        assert detalhe["total"]["n"] == n
        assert (detalhe["total"]["media"], detalhe["total"]["desvio"]) == pytest.approx(
            (media, desvio), abs=1e-6
        )
        assert (detalhe["total"]["q1"], detalhe["total"]["mediana"], detalhe["total"]["q3"]) == (
            pytest.approx((q1, mediana, q3), abs=1e-6)
        )
        rejeita = min(feminino[-1], masculino[-1]) < ALFA
        assert detalhe["forma"] == (COLUNA_DA_MEDIANA if rejeita else COLUNA_DA_MEDIA)

    def test_as_medias_sao_as_do_r_com_as_casas_da_descritiva(self):
        """`52,06 (9,04)`: a média e o desvio do R, escritos como a descritiva escreve."""
        tabela = _tabela()
        idade = _linha(tabela, "idade").linhas[0]
        (_, media_f, dp_f, *_), (_, media_m, dp_m, *_), (_, media_t, dp_t, *_) = RESUMOS_DO_R[0][1:]
        assert idade == (
            "Idade (anos), média (DP)",
            f"{_como_a_descritiva(media_f)} ({_como_a_descritiva(dp_f)})",
            f"{_como_a_descritiva(media_m)} ({_como_a_descritiva(dp_m)})",
            f"{_como_a_descritiva(media_t)} ({_como_a_descritiva(dp_t)})",
        )

    @pytest.mark.parametrize(
        ("variavel", "por_categoria", "sem_resposta"),
        CONTAGENS_DO_R,
        ids=[v for v, *_ in CONTAGENS_DO_R],
    )
    def test_as_contagens_sao_as_do_table_do_r(self, variavel, por_categoria, sem_resposta):
        linhas = _linha(_tabela(), variavel).linhas
        categorias = {linha[0]: (_n(linha[1]), _n(linha[2])) for linha in linhas[1:]
                      if linha[0] != "(sem informação)"}
        assert categorias == por_categoria
        faltantes = [linha for linha in linhas if linha[0] == "(sem informação)"]
        if any(sem_resposta):
            assert tuple(int(c) for c in faltantes[0][1:3]) == sem_resposta
        else:
            assert faltantes == []

    def test_sem_grupo_a_forma_e_a_do_shapiro_da_variavel_inteira(self):
        caracterizacao = _caracterizar(Pedido(variaveis=("idade", "imc")))
        manifesto = montar_manifesto(caracterizacao, DICIONARIO)
        for variavel, p in SHAPIRO_SEM_GRUPO_DO_R.items():
            detalhe = _detalhe(manifesto, variavel)
            assert detalhe["total"]["shapiro"]["p"] == pytest.approx(p, rel=1e-5)
            forma = COLUNA_DA_MEDIANA if p < ALFA else COLUNA_DA_MEDIA
            assert detalhe["forma"] == forma
            assert _linha(caracterizacao.tabelas[0], variavel).linhas[0][0].endswith(forma)


# ── Sem conta nova ──────────────────────────────────────────────────────────


class TestOPDeCadaLinhaEODasOutrasAnalises:
    """
    Consistência, e não referência: o p de cada linha é, bit a bit, o que a comparação
    ou a associação dão para o mesmo par.
    """

    @pytest.mark.parametrize(
        ("grupo", "pedido"),
        [("sexo", POR_SEXO), ("grupo", Pedido(grupo="grupo", todas=True))],
        ids=["dois grupos", "três grupos"],
    )
    def test_o_p_e_o_da_comparacao_ou_o_da_associacao(self, grupo, pedido):
        quadro = bancos.para_caracterizar()
        banco = banco_em_memoria(quadro)
        tabela = _tabela(pedido, quadro=quadro)
        for linha in tabela.caracteristicas:
            if linha.tipo == NUMERICA:
                outra = comparar(banco, ficha_em_memoria(), DICIONARIO, [(linha.variavel, grupo)])
                variavel = outra.variaveis[0]
                assert (linha.teste, linha.p) == (variavel.metodo, variavel.resultado.p)
            else:
                outra = associar(banco, ficha_em_memoria(), DICIONARIO, [(grupo, linha.variavel)])
                par = outra.pares[0]
                assert (linha.teste, linha.p) == (par.teste, par.p)
                assert linha.escolha == par.justificativa
            assert valor_p(linha.p) in tabela.celula_do_p(linha)

    def test_a_regra_manda_mesmo_com_metodo_escrito_na_comparacao(self, projeto_com_banco):
        """
        `[pas, sexo, student]` na lista `comparacao:` não muda a linha da Tabela 1: ela é
        a regra dos pressupostos, sempre — e a nota do `.csv` diz isso.
        """
        raiz = projeto_com_banco(bancos.para_caracterizar())
        _escrever_dicionario(raiz)
        acrescentar_a_ficha(raiz, BLOCO + "comparacao:\n  - [pas, sexo, student]\n")
        plano = preparar_caracterizacao(raiz, agora=AGORA)
        tabela = plano.caracterizacao.tabelas[0]
        assert _linha(tabela, "pas").teste == "t de Welch"
        assert any("manda mesmo quando a lista `comparacao:`" in nota for nota in tabela.notas)


# ── A tabela ────────────────────────────────────────────────────────────────


class TestColunas:
    def test_uma_coluna_por_grupo_com_o_n_o_total_e_o_p(self):
        assert _tabela().cabecalho == (
            "Característica",
            "Feminino (n = 59)",
            "Masculino (n = 58)",
            "Total (n = 117)",
            "p-valor",
        )

    def test_o_titulo_tem_o_rotulo_do_grupo_como_no_dicionario(self):
        assert _tabela().titulo == "Características dos participantes, por Sexo"
        assert _tabela(Pedido(variaveis=("idade",))).titulo == "Características dos participantes"

    def test_quem_nao_tem_o_grupo_fica_fora_da_tabela_com_aviso_e_nota(self):
        caracterizacao = _caracterizar()
        tabela = caracterizacao.tabelas[0]
        assert (tabela.n, tabela.fora_do_grupo) == (117, 3)
        aviso = next(a for a in caracterizacao.avisos if a.startswith("`sexo`: 3 caso(s)"))
        assert "o Total (117) pode diferir do n da descritiva" in aviso
        assert any("ficaram fora da tabela inteira" in nota for nota in tabela.notas)
        manifesto = montar_manifesto(caracterizacao, DICIONARIO)
        assert manifesto.itens[0].detalhes["tabelas"][0]["fora_do_grupo"] == 3
        assert aviso in manifesto.avisos

    def test_os_grupos_somam_o_total(self):
        tabela = _tabela()
        assert sum(coluna.n for coluna in tabela.colunas) == tabela.n

    def test_categoria_do_grupo_sem_caso_nao_vira_coluna(self):
        """`Outro` está declarado e ninguém o marcou: não é grupo, como na comparação."""
        sexo = Linha(
            "sexo", "Sexo", CATEGORICA, ("1", "2", "3"),
            rotulos_das_categorias=(("1", "Feminino"), ("2", "Masculino"), ("3", "Outro")),
        )
        tabela = _tabela(linhas=(sexo, *DICIONARIO[1:]))
        assert [coluna.rotulo for coluna in tabela.colunas] == ["Feminino", "Masculino"]

    def test_tres_grupos_ou_mais_pedem_a_pagina_deitada(self):
        assert _tabela().deitada is False
        assert _tabela(Pedido(grupo="grupo", variaveis=("idade",))).deitada is True


class TestContagens:
    @pytest.mark.parametrize(
        "pedido",
        [POR_SEXO, Pedido(grupo="grupo", todas=True), Pedido(variaveis=("imc", "escolaridade"))],
        ids=["dois grupos", "três grupos", "sem grupo"],
    )
    def test_as_contas_fecham(self, pedido):
        """
        Em cada variável: as colunas dos grupos somam o Total, as categorias somam os
        válidos da coluna, e os válidos mais a `(sem informação)` somam o n do cabeçalho.
        """
        tabela = _tabela(pedido)
        cabecalho = [int(n) for n in re.findall(r"\(n = (\d+)\)", " ".join(tabela.cabecalho))]
        largura = len(cabecalho)
        if largura > 1:
            assert sum(cabecalho[:-1]) == cabecalho[-1]
        for linha in tabela.caracteristicas:
            assert linha.validos + linha.faltantes == tabela.n
            faltantes = next(
                (
                    [int(n) for n in celulas[1 : 1 + largura]]
                    for celulas in linha.linhas
                    if celulas[0] == "(sem informação)"
                ),
                [0] * largura,
            )
            assert faltantes[-1] == linha.faltantes
            if largura > 1:
                assert sum(faltantes[:-1]) == faltantes[-1]
            if linha.tipo == CATEGORICA:
                categorias = [
                    celulas[1 : 1 + largura]
                    for celulas in linha.linhas[1:]
                    if celulas[0] != "(sem informação)"
                ]
                validos = [sum(_n(celulas[j]) for celulas in categorias) for j in range(largura)]
                assert [v + f for v, f in zip(validos, faltantes, strict=True)] == cabecalho


class TestNumerica:
    def test_a_forma_vai_no_rotulo_e_o_total_segue_a_forma(self):
        imc = _linha(_tabela(), "imc").linhas[0]
        assert imc[0] == "IMC (kg/m²), mediana [Q1 a Q3]"
        assert all(re.fullmatch(r"[\d,]+ \[[\d,]+ a [\d,]+\]", celula) for celula in imc[1:])

    def test_sem_informacao_so_quando_ha(self):
        tabela = _tabela()
        assert len(_linha(tabela, "idade").linhas) == 1
        assert _linha(tabela, "imc").linhas[1] == ("(sem informação)", "2", "1", "3")

    def test_o_total_sem_caso_fora_e_letra_por_letra_o_resumo_da_descritiva(self):
        """
        Na tabela por `grupo` ninguém fica fora, e o Total é a variável inteira: a média
        e o desvio — e a mediana e os quartis — saem como no `resumo_<variável>.csv`.
        """
        quadro = bancos.para_caracterizar()
        tabela = _tabela(Pedido(grupo="grupo", variaveis=("idade", "imc")), quadro=quadro)
        descritiva = descrever(banco_em_memoria(quadro), ficha_em_memoria(), DICIONARIO)
        for variavel in ("idade", "imc"):
            resumo = dict(
                next(v for v in descritiva.variaveis if v.variavel == variavel).tabelas[0].linhas
            )
            total = _linha(tabela, variavel).linhas[0][-1]
            if _linha(tabela, variavel).forma == COLUNA_DA_MEDIA:
                assert total == f"{resumo['média']} ({resumo['desvio padrão']})"
            else:
                assert total == f"{resumo['mediana']} [{resumo['q1']} a {resumo['q3']}]"

    def test_as_casas_da_escala_pequena_sao_as_da_descritiva(self):
        """Uma concentração na casa de 0,003 não sai `0 (0)`: as casas são as da coluna."""
        quadro = pd.DataFrame({"y": [0.0031, 0.0029, 0.0035, 0.0027, 0.0033, 0.0030] * 4})
        linhas = (Linha("y", "Y", NUMERICA),)
        tabela = _tabela(Pedido(variaveis=("y",)), quadro=quadro, linhas=linhas)
        resumo = dict(
            descrever(banco_em_memoria(quadro), ficha_em_memoria(), linhas)
            .variaveis[0].tabelas[0].linhas
        )
        # Seis valores repetidos não passam no Shapiro-Wilk: a linha sai pela mediana.
        assert tabela.linhas[0] == (
            "Y, mediana [Q1 a Q3]",
            f"{resumo['mediana']} [{resumo['q1']} a {resumo['q3']}]",
        )
        assert resumo["q1"] == "0,0029"

    def test_o_grupo_sem_valor_sai_com_traco_e_a_linha_sem_teste(self):
        quadro = bancos.para_caracterizar()
        quadro.loc[quadro["sexo"] == 2, "pas"] = None
        caracterizacao = _caracterizar(quadro=quadro)
        tabela = caracterizacao.tabelas[0]
        pas = _linha(tabela, "pas")
        assert pas.linhas[0][2] == "—"
        assert pas.linhas[1] == ("(sem informação)", "0", "58", "58")
        assert pas.p is None and pas.motivo == "um grupo só"
        assert tabela.celula_do_p(pas) == "—"
        assert any("`pas` por `sexo`: um grupo só" in aviso for aviso in caracterizacao.avisos)


class TestCategorica:
    def test_as_categorias_embaixo_da_variavel_com_n_e_percentual(self):
        escolaridade = _linha(_tabela(), "escolaridade").linhas
        assert escolaridade[0] == ("Escolaridade, n (%)", "", "", "")
        assert escolaridade[1] == ("Fundamental", "25 (43,9)", "15 (26,3)", "40 (35,1)")

    def test_categoria_declarada_sem_caso_sai_zero_e_fica_fora_do_teste(self):
        caracterizacao = _caracterizar()
        linhas = _linha(caracterizacao.tabelas[0], "escolaridade").linhas
        assert ("Pós-graduação", "0 (0,0)", "0 (0,0)", "0 (0,0)") in linhas
        detalhe = _detalhe(montar_manifesto(caracterizacao, DICIONARIO), "escolaridade")
        assert "Pós-graduação" in detalhe["categorias"]
        assert detalhe["contingencia"]["categorias"] == ["Fundamental", "Médio", "Superior"]

    def test_binaria_sai_nas_duas_linhas(self):
        avc = _linha(_tabela(), "avc").linhas
        assert [linha[0] for linha in avc] == ["AVC prévio, n (%)", "Sim", "Não"]

    def test_valor_que_o_dicionario_nao_declara_entra_no_fim_com_aviso(self):
        quadro = bancos.para_caracterizar()
        quadro.loc[0, "escolaridade"] = "Técnico"
        caracterizacao = _caracterizar(quadro=quadro)
        linhas = _linha(caracterizacao.tabelas[0], "escolaridade").linhas
        assert [linha[0] for linha in linhas][-2:] == ["Técnico", "(sem informação)"]
        assert any("`escolaridade`: 1 valor(es) no banco fora da ordem declarada" in aviso
                   for aviso in caracterizacao.avisos)

    def test_a_coluna_sem_resposta_sai_com_traco(self):
        quadro = bancos.para_caracterizar()
        quadro.loc[quadro["sexo"] == 2, "tabagismo"] = None
        tabagismo = _linha(_tabela(quadro=quadro), "tabagismo").linhas
        assert tabagismo[1][2] == "—"
        assert tabagismo[-1] == ("(sem informação)", "0", "58", "58")

    def test_o_fisher_alem_do_limite_sai_sem_p_e_com_o_motivo(self):
        caracterizacao = _caracterizar(Pedido(grupo="grupo", variaveis=("avc",)), limite=1)
        tabela = caracterizacao.tabelas[0]
        avc = _linha(tabela, "avc")
        assert (avc.teste, avc.p) == ("Exato de Fisher", None)
        assert tabela.celula_do_p(avc) == "—"
        assert tabela.rodape == (PERCENTUAIS,)
        assert any("passou do limite do cálculo exato" in aviso for aviso in caracterizacao.avisos)
        detalhe = _detalhe(montar_manifesto(caracterizacao, DICIONARIO), "avc")
        assert detalhe["motivo"] == "tabela grande demais para o cálculo exato"
        assert detalhe["letra"] is None


class TestOPEAsLetras:
    def test_a_letra_segue_a_ordem_em_que_cada_teste_aparece(self):
        tabela = _tabela()
        letras = {variavel: (teste, p) for variavel, teste, p in POR_SEXO_DO_R}
        esperadas = {"idade": "a", "pas": "a", "imc": "b", "escolaridade": "c",
                     "tabagismo": "d", "avc": "e"}
        for variavel, letra in esperadas.items():
            assert tabela.celula_do_p(_linha(tabela, variavel)) == (
                valor_p(letras[variavel][1]) + letra
            )
        assert tabela.celula_do_p(_linha(tabela, "pas")) == "< 0,001a"

    def test_o_p_vai_so_na_linha_da_variavel(self):
        tabela = _tabela()
        for linha in tabela.caracteristicas:
            celulas = tabela.linhas_de(linha)
            assert celulas[0][-1] != ""
            assert all(celula[-1] == "" for celula in celulas[1:])

    def test_a_legenda_lista_so_os_testes_que_apareceram(self):
        assert _tabela().rodape == (
            "a t de Welch; b Mann-Whitney; c Qui-quadrado; d Qui-quadrado com correção de "
            "Yates; e Exato de Fisher.",
            PERCENTUAIS,
        )
        so_numericas = _tabela(Pedido(grupo="sexo", variaveis=("idade", "pas")))
        assert so_numericas.rodape == ("a t de Welch.",)

    def test_o_recuo_marca_as_linhas_debaixo_de_cada_variavel(self):
        tabela = _tabela(Pedido(grupo="sexo", variaveis=("idade", "imc", "tabagismo")))
        rotulos = [linha[0] for linha in tabela.linhas]
        assert rotulos == [
            "Idade (anos), média (DP)",
            "IMC (kg/m²), mediana [Q1 a Q3]",
            "(sem informação)",
            "Tabagismo atual, n (%)",
            "Sim",
            "Não",
        ]
        assert tabela.recuo == (2, 4, 5)
        assert not any(celula != celula.strip() for linha in tabela.linhas for celula in linha)


class TestSemGrupoESemP:
    def test_sem_grupo_so_o_total_e_nenhum_p(self):
        tabela = _tabela(Pedido(variaveis=("idade", "imc", "sexo")))
        assert tabela.cabecalho == ("Característica", "Total (n = 120)")
        assert tabela.com_p is False
        assert all(len(linha) == 2 for linha in tabela.linhas)
        assert tabela.rodape == (PERCENTUAIS,)
        assert tabela.arquivo == "caracterizacao_geral.csv"

    @pytest.mark.parametrize("escrito", ["nao", "não", "no", "false", "False", "NAO"])
    def test_p_nao_em_qualquer_grafia(self, projeto_vazio, escrito):
        acrescentar_a_ficha(
            projeto_vazio, f"caracterizacao:\n  - sexo: [idade]\n    p: {escrito}\n"
        )
        assert itens_da_ficha(projeto_vazio) == (
            Pedido(grupo="sexo", variaveis=("idade",), com_p=False),
        )

    def test_p_nao_tira_a_coluna_e_a_legenda_e_deixa_os_percentuais(self):
        caracterizacao = _caracterizar(
            Pedido(grupo="sexo", variaveis=("idade", "imc", "avc"), com_p=False)
        )
        tabela = caracterizacao.tabelas[0]
        assert tabela.cabecalho[-1] == "Total (n = 117)"
        assert tabela.rodape == (PERCENTUAIS,)
        assert all(linha.p is None and not linha.teste for linha in tabela.caracteristicas)

    def test_sem_o_p_nenhum_teste_aparece_nas_notas_no_manifesto_nem_nos_avisos(self):
        caracterizacao = _caracterizar(
            Pedido(grupo="sexo", variaveis=("idade", "imc", "avc"), com_p=False)
        )
        tabela = caracterizacao.tabelas[0]
        assert _linha(tabela, "imc").escolha.endswith(
            "o Shapiro-Wilk rejeita a normal em Feminino (p < 0,001) e Masculino (p < 0,001) "
            "→ mediana [Q1 a Q3]."
        )
        texto = json.dumps(montar_manifesto(caracterizacao, DICIONARIO).itens[0].detalhes)
        notas = " ".join(tabela.notas)
        for teste in ("Welch", "Mann-Whitney", "Fisher", "Qui-quadrado"):
            assert teste not in notas
            assert teste not in texto
            assert not any(teste in aviso for aviso in caracterizacao.avisos)


class TestPor:
    def test_todas_as_analisaveis_na_ordem_do_dicionario_menos_o_grupo(self):
        caracterizacao = _caracterizar(Pedido(grupo="grupo", todas=True))
        tabela = caracterizacao.tabelas[0]
        assert [linha.variavel for linha in tabela.caracteristicas] == [
            "sexo", "idade", "pas", "imc", "escolaridade", "tabagismo", "avc",
        ]
        fora = {f.variavel: f.motivo for f in caracterizacao.fora}
        assert fora == {
            "data_inclusao": "marcada `data` — a caracterização descreve numéricas e "
            "categóricas",
            "obs": "marcada `ignorar` no dicionário",
        }


# ── A ficha ─────────────────────────────────────────────────────────────────


class TestFicha:
    def test_as_tres_formas_de_item(self, projeto_vazio):
        acrescentar_a_ficha(
            projeto_vazio,
            "caracterizacao:\n"
            "  - sexo: [idade, imc]\n"
            "  - por: grupo\n"
            "    p: nao\n"
            "  - [idade, sexo]\n",
        )
        assert itens_da_ficha(projeto_vazio) == (
            Pedido(grupo="sexo", variaveis=("idade", "imc")),
            Pedido(grupo="grupo", todas=True, com_p=False),
            Pedido(variaveis=("idade", "sexo")),
        )

    def test_sem_a_chave_e_vazio(self, projeto_vazio):
        assert itens_da_ficha(projeto_vazio) == ()

    def test_as_recusas_de_formato_saem_todas_de_uma_vez(self, projeto_vazio):
        acrescentar_a_ficha(
            projeto_vazio,
            "caracterizacao:\n"
            "  - sexo\n"
            "  - sexo: [idade, sexo]\n"
            "  - [idade, imc, idade]\n"
            "  - sexo: [idade]\n"
            "    p: talvez\n"
            "  - {sexo: [idade], grupo: [imc]}\n"
            "  - p: nao\n"
            "  - por: [sexo]\n"
            "  - sexo: []\n",
        )
        with pytest.raises(ItemInvalidoError) as erro:
            itens_da_ficha(projeto_vazio)
        mensagem = str(erro.value)
        assert "tem 8 item(ns) fora do formato. Nada foi gerado." in mensagem
        assert "1º item: `sexo` — um item é o grupo e a lista das variáveis" in mensagem
        assert "`sexo` é o grupo e está também na lista" in mensagem
        assert "`idade` duas vezes" in mensagem
        assert "`p: talvez` — escreva `p: nao`" in mensagem
        assert "2 grupos num item só" in mensagem
        assert "o `p:` vai na linha de baixo de um item com grupo" in mensagem
        assert "depois de `por:` vem o nome do grupo, sem colchetes" in mensagem
        assert "a lista das variáveis está vazia" in mensagem
        assert "- sexo: [idade, imc, escolaridade]" in mensagem

    def test_a_chave_que_nao_e_lista(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "caracterizacao: sexo\n")
        with pytest.raises(ItemInvalidoError) as erro:
            itens_da_ficha(projeto_vazio)
        assert "deveria ser uma lista" in str(erro.value)


class TestRecusasDoDicionario:
    def test_sem_itens_recusa_e_ensina_a_forma(self):
        with pytest.raises(SemItensError) as erro:
            caracterizar(
                banco_em_memoria(bancos.para_caracterizar()), ficha_em_memoria(), DICIONARIO, ()
            )
        mensagem = str(erro.value)
        assert "não diz o que caracterizar" in mensagem
        assert "- sexo: [idade, imc, escolaridade]" in mensagem
        assert "que formam os grupos, são: sexo, grupo, escolaridade, tabagismo, avc" in mensagem

    def test_as_recusas_do_dicionario_saem_todas_de_uma_vez(self):
        fora = Linha("antigo", "Antigo", NUMERICA, no_banco=False)
        with pytest.raises(ItemInvalidoError) as erro:
            _caracterizar(
                Pedido(grupo="sexo", variaveis=("peso",)),
                Pedido(grupo="idade", variaveis=("imc",)),
                Pedido(grupo="sexo", variaveis=("obs", "antigo")),
                Pedido(grupo="obs", variaveis=("imc",)),
                linhas=(*DICIONARIO, fora),
            )
        mensagem = str(erro.value)
        assert "tem 4 item(ns) que não podem ser caracterizados. Nada foi gerado." in mensagem
        assert "sexo: [peso] — `peso` não está no dicionario.csv" in mensagem
        assert "idade: [imc] — `idade`, o grupo, está marcada `numerica`" in mensagem
        assert "`obs` está marcada `ignorar` no dicionario.csv" in mensagem
        assert "`antigo` não está nesta versão do banco (`no_banco = nao`)" in mensagem
        assert "obs: [imc] — `obs` está marcada `ignorar`" in mensagem

    def test_a_data_nao_e_recusa_e_vai_para_a_lista_fora(self):
        caracterizacao = _caracterizar(Pedido(grupo="sexo", variaveis=("idade", "data_inclusao")))
        assert [c.variavel for c in caracterizacao.tabelas[0].caracteristicas] == ["idade"]
        fora = {f.variavel: f.motivo for f in caracterizacao.fora}
        assert "marcada `data`" in fora["data_inclusao"]

    def test_o_item_que_nao_deixa_linha_recusa(self):
        with pytest.raises(ItemInvalidoError) as erro:
            _caracterizar(Pedido(grupo="sexo", variaveis=("data_inclusao",)))
        assert "nenhuma variável numérica ou categórica para a tabela: `data_inclusao` é data" in (
            str(erro.value)
        )

    def test_o_grupo_com_uma_categoria_so_recusa_depois_de_contar(self):
        quadro = bancos.para_caracterizar()
        quadro["grupo"] = "Controle"
        with pytest.raises(ItemInvalidoError) as erro:
            _caracterizar(Pedido(grupo="grupo", variaveis=("idade",)), quadro=quadro)
        mensagem = str(erro.value)
        assert "que este banco não deixa caracterizar" in mensagem
        assert "`grupo`, o grupo, tem uma categoria só entre os casos com resposta (Controle)" in (
            mensagem
        )

    def test_toda_recusa_e_um_erro_da_caracterizacao(self):
        assert issubclass(ItemInvalidoError, CaracterizacaoError)
        assert issubclass(SemItensError, CaracterizacaoError)


# ── O manifesto e o .csv ────────────────────────────────────────────────────


class TestManifesto:
    def test_um_item_com_as_colunas_e_os_artefatos(self):
        caracterizacao = _caracterizar(POR_SEXO, Pedido(grupo="grupo", variaveis=("idade",)))
        manifesto = montar_manifesto(caracterizacao, DICIONARIO)
        assert manifesto.analise == ANALISE_CARACTERIZACAO
        (item,) = manifesto.itens
        assert (item.variavel, item.rotulo) == ("", "Caracterização dos participantes")
        assert item.colunas == (
            "sexo", "idade", "pas", "imc", "escolaridade", "tabagismo", "avc", "grupo",
        )
        primeira, segunda = item.artefatos
        assert primeira.arquivo == "caracterizacao_sexo.csv"
        assert primeira.titulo == "Características dos participantes, por Sexo"
        assert primeira.recuo == caracterizacao.tabelas[0].recuo
        assert primeira.rodape == caracterizacao.tabelas[0].rodape
        assert (primeira.deitada, segunda.deitada) == (False, True)

    def test_cada_linha_com_o_teste_o_p_inteiro_a_letra_e_a_frase(self):
        caracterizacao = _caracterizar()
        manifesto = montar_manifesto(caracterizacao, DICIONARIO)
        pas = _detalhe(manifesto, "pas")
        assert (pas["teste"], pas["letra"]) == ("t de Welch", "a")
        assert pas["p"] == pytest.approx(POR_SEXO_DO_R[1][2], rel=1e-9)
        assert pas["escolha"].startswith("PAS na inclusão (mmHg) por Sexo: n = 117")
        assert [grupo["grupo"] for grupo in pas["grupos"]] == ["Feminino", "Masculino"]
        assert pas["grupos"][0]["shapiro"]["rejeita"] is False
        avc = _detalhe(manifesto, "avc")
        assert avc["contingencia"] == {
            "grupos": ["Feminino", "Masculino"],
            "categorias": ["Sim", "Não"],
            "contagens": [[2, 57], [7, 51]],
        }
        detalhes = manifesto.itens[0].detalhes
        assert (detalhes["testados"], detalhes["sem_teste"]) == (6, 0)
        assert detalhes["tabelas"][0]["letras"] == {
            "a": "t de Welch", "b": "Mann-Whitney", "c": "Qui-quadrado",
            "d": "Qui-quadrado com correção de Yates", "e": "Exato de Fisher",
        }

    def test_as_regras_tem_o_alfa_e_a_falta_de_correcao(self):
        regras = montar_manifesto(_caracterizar(), DICIONARIO).regras
        assert regras["alfa"] == 0.05
        assert regras["comparacoes_multiplas"] == "nenhuma correção"

    def test_fora_lista_quem_nao_esta_em_tabela(self):
        manifesto = montar_manifesto(_caracterizar(), DICIONARIO)
        assert {entrada["variavel"] for entrada in manifesto.fora} == {
            "grupo", "data_inclusao", "obs",
        }


def _escrever_dicionario(raiz) -> None:
    """O dicionário da reunião: os rótulos, os códigos e os tipos, escritos à mão."""
    (raiz / "dicionario.csv").write_text(
        texto_do_dicionario(DICIONARIO), encoding="utf-8", newline="\n"
    )


@pytest.fixture
def projeto_para_caracterizar(projeto_com_banco):
    def montar(bloco: str = BLOCO):
        raiz = projeto_com_banco(bancos.para_caracterizar())
        _escrever_dicionario(raiz)
        acrescentar_a_ficha(raiz, bloco)
        return raiz

    return montar


class TestEscrita:
    def test_preparar_nao_toca_no_disco(self, projeto_para_caracterizar):
        raiz = projeto_para_caracterizar()
        antes = linhas_do_historico(raiz)
        preparar_caracterizacao(raiz, agora=AGORA)
        assert not (raiz / PASTA_ANALISES / PASTA_CARACTERIZACAO).exists()
        assert linhas_do_historico(raiz) == antes

    def test_escreve_um_csv_por_item_e_o_manifesto(self, projeto_para_caracterizar):
        raiz = projeto_para_caracterizar(BLOCO + "  - [idade, sexo]\n")
        executar_caracterizacao(preparar_caracterizacao(raiz, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_CARACTERIZACAO
        assert sorted(p.name for p in pasta.iterdir()) == [
            "caracterizacao_geral.csv",
            "caracterizacao_sexo.csv",
            ARQUIVO_MANIFESTO,
        ]
        manifesto = ler_manifesto(pasta)
        assert manifesto.analise == ANALISE_CARACTERIZACAO
        assert manifesto.itens[0].artefatos[0].rodape[0].startswith("a t de Welch; b Mann")

    def test_o_csv_tem_as_celulas_do_documento_e_as_notas(self, projeto_para_caracterizar):
        raiz = projeto_para_caracterizar()
        executar_caracterizacao(preparar_caracterizacao(raiz, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_CARACTERIZACAO
        texto = (pasta / "caracterizacao_sexo.csv").read_text(encoding="utf-8-sig")
        notas = [linha[2:] for linha in texto.splitlines() if linha.startswith("#")]
        corpo = [linha.split(";") for linha in texto.splitlines() if not linha.startswith("#")]
        assert notas[0] == "Características dos participantes, por Sexo"
        assert corpo[0] == [
            "Característica", "Feminino (n = 59)", "Masculino (n = 58)", "Total (n = 117)",
            "p-valor",
        ]
        assert corpo[1][0] == "Idade (anos), média (DP)"
        assert corpo[1][-1] == "0,018a"
        assert ["(sem informação)", "2", "1", "3", ""] in corpo
        assert not any(celula != celula.strip() for linha in corpo for celula in linha)
        assert "a t de Welch; b Mann-Whitney; c Qui-quadrado; d Qui-quadrado com correção de " \
            "Yates; e Exato de Fisher." in notas
        assert PERCENTUAIS in notas
        assert "cada linha é um teste; não há correção para comparações múltiplas." in notas
        assert any(nota.startswith("Sexo × AVC prévio: 2×2, n = 117") for nota in notas)

    def test_escreve_uma_linha_no_historico(self, projeto_para_caracterizar):
        raiz = projeto_para_caracterizar()
        antes = len(linhas_do_historico(raiz))
        executar_caracterizacao(preparar_caracterizacao(raiz, agora=AGORA))
        linhas = linhas_do_historico(raiz)
        assert len(linhas) == antes + 1
        assert f"`flatcap caracterizacao {RECORD_ID}`" in linhas[-1]
        assert "1 tabela(s) da lista `caracterizacao:` (6 linha(s) com p)" in linhas[-1]

    def test_regerar_arquiva_a_rodada_anterior(self, projeto_para_caracterizar):
        raiz = projeto_para_caracterizar()
        executar_caracterizacao(preparar_caracterizacao(raiz, agora=AGORA))
        depois = AGORA.replace(hour=16)
        plano = preparar_caracterizacao(raiz, agora=depois)
        executar_caracterizacao(plano)
        assert (raiz / PASTA_ANTIGAS / "caracterizacao_2026-09-09_1630").is_dir()
        assert "A rodada anterior foi para" in linhas_do_historico(raiz)[-1]

    def test_a_ficha_sem_a_lista_recusa_com_a_forma(self, projeto_para_caracterizar):
        raiz = projeto_para_caracterizar("")
        with pytest.raises(SemItensError):
            preparar_caracterizacao(raiz, agora=AGORA)
