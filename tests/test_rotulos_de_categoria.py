# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Os rótulos de valor das categorias — `categorias_ordem = 1=Feminino|2=Masculino`.

> **Ao mesclar: este arquivo se desfaz em três.** A regra da pasta é "um módulo em
> `src/flatcap/` pede um `test_` de mesmo nome", e esta é uma funcionalidade que
> atravessa três módulos. As seções abaixo estão separadas e nomeadas para isso:
>
>     O FORMATO      → tests/test_dicionario.py
>     A DESCRITIVA   → tests/test_descritiva.py
>     O PERFIL       → tests/test_perfil.py
>
> Vieram juntas porque o `conftest.py` e o `bancos.py` do repositório não estavam
> à mão quando isto foi escrito; os ajudantes `_linha` e `_serie` daqui devem
> ceder o lugar aos de lá.

O critério de pronto da mudança tem teste próprio, no fim:
**dicionário sem nenhum `=` produz exatamente o que produzia antes.**
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from flatcap.descritiva import _descrever_categorica
from flatcap.dicionario import (
    CATEGORICA,
    COLUNAS,
    NUMERICA,
    DicionarioInvalidoError,
    Linha,
    ler_arquivo,
    texto_do_dicionario,
)
from flatcap.perfil import CONFIRMAR, _perfilar_coluna

CABECALHO = "variavel;rotulo;tipo;categorias_ordem;faixas;no_banco\n"


def _arquivo(*linhas: str) -> Path:
    caminho = Path(tempfile.mkdtemp()) / "dicionario.csv"
    caminho.write_text("\ufeff" + CABECALHO + "".join(linhas), encoding="utf-8")
    return caminho


def _linha(codigos: tuple[str, ...], rotulos: tuple[tuple[str, str], ...] = ()) -> Linha:
    return Linha(
        variavel="sexo",
        rotulo="Sexo",
        tipo=CATEGORICA,
        categorias_ordem=codigos,
        rotulos_das_categorias=rotulos,
    )


def _celulas(variavel) -> list[tuple[str, ...]]:
    return list(variavel.tabelas[0].linhas)


# ─────────────────────────────────────────────────────────────────────────────
#  O FORMATO  →  tests/test_dicionario.py
# ─────────────────────────────────────────────────────────────────────────────


def test_separa_o_codigo_do_rotulo():
    linha = ler_arquivo(_arquivo("sexo;Sexo;categorica;1=Feminino|2=Masculino;;sim\n"))[0]

    assert linha.categorias_ordem == ("1", "2")
    assert linha.rotulos_das_categorias == (("1", "Feminino"), ("2", "Masculino"))
    assert linha.rotulo_de("1") == "Feminino"
    assert linha.tem_rotulos


def test_celula_sem_sinal_continua_valendo():
    """
    O dicionário escrito antes desta versão abre sem mudar um caractere: sem `=`,
    o valor é o próprio rótulo. É o que dispensa migração.
    """
    linha = ler_arquivo(_arquivo("e;Escolaridade;categorica;Fundamental|Médio;;sim\n"))[0]

    assert linha.categorias_ordem == ("Fundamental", "Médio")
    assert linha.rotulos_das_categorias == ()
    assert not linha.tem_rotulos
    assert linha.rotulo_de("Fundamental") == "Fundamental"


def test_codigo_desconhecido_devolve_ele_mesmo():
    """
    É o valor que está no banco e não foi declarado. Ele sai cru na tabela, com o
    aviso que a Fase 5 já emitia — e não pode estourar aqui.
    """
    linha = _linha(("1",), (("1", "Feminino"),))

    assert linha.rotulo_de("9") == "9"


def test_a_divisao_e_no_primeiro_sinal():
    """
    `1=Sim = confirmado` é um rótulo com `=` dentro, não duas categorias. Mesma
    regra que o `modelo._opcoes` usa para a primeira vírgula do REDCap.
    """
    linha = ler_arquivo(_arquivo("r;R;categorica;1=Sim = confirmado|2=Não;;sim\n"))[0]

    assert linha.categorias_ordem == ("1", "2")
    assert linha.rotulo_de("1") == "Sim = confirmado"


def test_recusa_codigo_repetido_na_mesma_celula():
    with pytest.raises(DicionarioInvalidoError) as erro:
        ler_arquivo(_arquivo("s;S;categorica;1=Feminino|1=Fem;;sim\n"))

    assert "duas vezes" in str(erro.value)
    # A mensagem ensina o caminho de quem queria agrupar, que é o engano provável.
    assert "juntar" in str(erro.value)


def test_recusa_sinal_sem_codigo_antes():
    with pytest.raises(DicionarioInvalidoError) as erro:
        ler_arquivo(_arquivo("s;S;categorica;=Feminino|2=Masculino;;sim\n"))

    assert "começa com `=`" in str(erro.value)


def test_a_ida_e_volta_preserva_o_que_voce_escreveu():
    """
    A promessa do cabeçalho do arquivo vale para o `=` também: um sinal que
    sumisse na primeira gravação seria uma edição sua desfeita pelo programa.
    """
    original = "s;S;categorica;1=Feminino|2=Masculino|9=;;sim"
    linhas = ler_arquivo(_arquivo(original + "\n"))
    gravado = texto_do_dicionario(linhas, COLUNAS)

    assert original in gravado


# ─────────────────────────────────────────────────────────────────────────────
#  A DESCRITIVA  →  tests/test_descritiva.py
# ─────────────────────────────────────────────────────────────────────────────


def test_a_tabela_sai_com_o_rotulo_e_conta_pelo_codigo():
    linha = _linha(("1", "2"), (("1", "Feminino"), ("2", "Masculino")))
    v = _descrever_categorica(linha, pd.Series([1, 1, 1, 2, 2]), "sexo", 5, 0)

    assert _celulas(v)[0][:2] == ("Feminino", "3")
    assert _celulas(v)[1][:2] == ("Masculino", "2")


def test_o_grafico_recebe_os_mesmos_rotulos_da_tabela():
    """
    Quem calcula é um só, e por isso a figura não pode discordar da tabela ao lado
    dela. É a invariante da Fase 5 aplicada a mais um campo.
    """
    linha = _linha(("1", "2"), (("1", "Feminino"), ("2", "Masculino")))
    v = _descrever_categorica(linha, pd.Series([1, 1, 2]), "sexo", 3, 0)

    assert v.graficos[0].categorias == ("Feminino", "Masculino")


def test_dois_codigos_com_o_mesmo_rotulo_somam_em_uma_linha():
    """
    É a promessa que o `dicionario.py` faz desde a Fase 4 — *"reagrupar categorias
    vira editar uma célula, não caçar código"*. Duas linhas chamadas «Sim» na
    mesma tabela seriam a promessa quebrada.
    """
    linha = Linha(
        variavel="r",
        rotulo="Resposta",
        tipo=CATEGORICA,
        categorias_ordem=("1", "2", "3"),
        rotulos_das_categorias=(("1", "Sim"), ("2", "Sim"), ("3", "Não")),
    )
    v = _descrever_categorica(linha, pd.Series([1, 1, 2, 3]), "r", 4, 0)

    assert _celulas(v)[0][:2] == ("Sim", "3")
    assert _celulas(v)[1][:2] == ("Não", "1")
    assert any("foram somados" in aviso for aviso in v.avisos)


def test_o_agrupamento_acidental_e_avisado_com_nome():
    """
    Somar em silêncio seria o defeito. O aviso nomeia quais códigos entraram em
    qual rótulo, e viaja para a tela e para o manifesto.
    """
    linha = Linha(
        variavel="r",
        rotulo="R",
        tipo=CATEGORICA,
        categorias_ordem=("1", "2"),
        rotulos_das_categorias=(("1", "Sim"), ("2", "Sim")),
    )
    v = _descrever_categorica(linha, pd.Series([1, 2]), "r", 2, 0)

    assert any("1 + 2 → «Sim»" in aviso for aviso in v.avisos)
    assert v.detalhes["agrupadas"] == {"Sim": ["1", "2"]}


def test_sinal_sem_rotulo_cai_no_codigo_e_avisa():
    linha = _linha(("1", "2"), (("1", "Sim"), ("2", "")))
    v = _descrever_categorica(linha, pd.Series([1, 2, 2]), "r", 3, 0)

    assert _celulas(v)[1][0] == "2"
    assert any("nada depois" in aviso for aviso in v.avisos)


def test_o_valor_nao_declarado_continua_saindo_cru():
    """
    Ele é o `"Sim "` com espaço que se denuncia sozinho. Rotular o que o
    dicionário não conhece seria inventar.
    """
    linha = _linha(("1",), (("1", "Feminino"),))
    v = _descrever_categorica(linha, pd.Series([1, 1, 9]), "sexo", 3, 0)

    assert [c[0] for c in _celulas(v)][:2] == ["Feminino", "9"]
    assert any("fora da ordem" in aviso for aviso in v.avisos)


def test_o_csv_registra_de_onde_veio_o_rotulo():
    """
    Um `freq_sexo.csv` aberto sozinho seis meses depois precisa dizer por que a
    coluna do banco tem `1` e a tabela diz «Feminino».
    """
    linha = _linha(("1", "2"), (("1", "Feminino"), ("2", "Masculino")))
    v = _descrever_categorica(linha, pd.Series([1, 2]), "sexo", 2, 0)
    texto = v.tabelas[0].texto()

    assert "# categorias rotuladas pelo dicionário: 1 = Feminino, 2 = Masculino." in texto
    assert v.detalhes["rotulos"] == {"1": "Feminino", "2": "Masculino"}


def test_o_criterio_de_pronto_dicionario_sem_sinal_nao_muda_nada():
    """
    **O critério de pronto da mudança.** Uma coluna de texto atravessa o caminho
    novo sem nada acontecer: sem `=`, o valor é o próprio rótulo, não há
    agrupamento, não há aviso e não há nota a mais no `.csv`.
    """
    linha = _linha(("Fundamental", "Médio", "Superior"))
    serie = pd.Series(["Fundamental", "Médio", "Médio", "Superior"])
    v = _descrever_categorica(linha, serie, "e", 4, 0)

    assert [c[0] for c in _celulas(v)][:3] == ["Fundamental", "Médio", "Superior"]
    assert v.avisos == ()
    assert v.detalhes["rotulos"] == {}
    assert v.detalhes["agrupadas"] == {}
    assert "rotuladas pelo dicionário" not in v.tabelas[0].texto()


# ─────────────────────────────────────────────────────────────────────────────
#  O PERFIL  →  tests/test_perfil.py
# ─────────────────────────────────────────────────────────────────────────────


def test_o_perfil_aponta_a_coluna_de_codigo_sem_rotulo():
    """
    É o que faz a sintaxe ser descoberta. Sem este achado, `1=Feminino` fica
    documentado no cabeçalho do arquivo e ninguém repara que existe.
    """
    coluna = _perfilar_coluna(pd.Series([1, 2] * 20), "sexo", 1, 40)
    achado = next(a for a in coluna.achados if a.codigo == "categoria_sem_rotulo")

    assert coluna.sugestao == CATEGORICA
    assert achado.gravidade == CONFIRMAR
    assert "categorias_ordem" in achado.detalhe


def test_a_ordem_continua_sendo_proposta_para_a_coluna_de_codigo():
    """
    O achado é `CONFIRMAR` e **não** entra em `CODIGOS_VOLATEIS`: rotular `1` não
    apaga o `1` da coluna. Se entrasse, a ordem deixaria de ser proposta
    justamente nas colunas que mais precisam dela.
    """
    coluna = _perfilar_coluna(pd.Series([1, 2] * 20), "sexo", 1, 40)

    assert coluna.categorias_sugeridas == ("1", "2")


def test_coluna_de_texto_nao_ganha_o_achado():
    coluna = _perfilar_coluna(pd.Series(["Feminino", "Masculino"] * 20), "sexo", 1, 40)

    assert coluna.sugestao == CATEGORICA
    assert not any(a.codigo == "categoria_sem_rotulo" for a in coluna.achados)


def test_coluna_numerica_de_verdade_nao_ganha_o_achado():
    """
    O achado é da coluna que o perfil vai tratar como categórica. Uma idade
    continua sendo numérica e não tem código para rotular.
    """
    coluna = _perfilar_coluna(pd.Series(range(30, 70)), "idade", 1, 40)

    assert coluna.sugestao == NUMERICA
    assert not any(a.codigo == "categoria_sem_rotulo" for a in coluna.achados)
