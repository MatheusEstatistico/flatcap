"""
Os testes do `normalidade.py`.

A regra da pasta desde os ajustes pós-Fase 3: um módulo em `src/flatcap/` pede um
`test_` de mesmo nome, e um teste novo tem exatamente um lugar possível.

O miolo é testado pela função pura `avaliar(banco, ficha, linhas)`, como o
`perfilar` da Fase 4 e o `descrever` da Fase 5: um `DataFrame` montado à mão e uma
lista de `Linha` entram, e as afirmações são sobre a tabela — sem pasta de projeto
e sem disco. O banco e a ficha em memória são os do `conftest.py`, os mesmos da
descritiva e do cruzamento.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from conftest import banco_em_memoria, ficha_em_memoria
from flatcap.dicionario import CATEGORICA, DATA, IGNORAR, NUMERICA, Linha
from flatcap.manifesto import ANALISE_NORMALIDADE
from flatcap.normalidade import (
    ALFA,
    MAXIMO_CONFIAVEL,
    MINIMO_CONFIAVEL,
    POUCOS_DISTINTOS,
    NadaParaAnalisarError,
    VariavelIncompativelError,
    VariavelPedidaInexistenteError,
    avaliar,
    montar_manifesto,
)

QUANDO = datetime(2026, 9, 17, 15, 0, 0)


# Ajudantes


def _linha(variavel: str, tipo: str = NUMERICA, **extras) -> Linha:
    return Linha(variavel=variavel, rotulo=extras.pop("rotulo", variavel), tipo=tipo, **extras)


def _normal(n: int = 120, semente: int = 7) -> list[float]:
    return list(np.random.default_rng(semente).normal(50, 10, n))


def _assimetrica(n: int = 120, semente: int = 7) -> list[float]:
    return list(np.random.default_rng(semente).exponential(5, n))


def _rodar(quadro: pd.DataFrame, linhas, raiz: Path | None = None):
    return avaliar(banco_em_memoria(quadro), ficha_em_memoria(raiz), linhas, (), QUANDO)


# O caminho feliz


def test_uma_linha_por_variavel_numerica():
    quadro = pd.DataFrame({"idade": _normal(), "imc": _assimetrica()})
    resultado = _rodar(quadro, [_linha("idade"), _linha("imc")])

    assert [v.variavel for v in resultado.variaveis] == ["idade", "imc"]
    assert len(resultado.tabela.linhas) == 2


def test_uma_tabela_so_e_nao_uma_por_variavel():
    """
    A diferença de forma em relação à descritiva, e ela é decisão: uma tabela de
    pressupostos é lida atravessando as variáveis, e uma linha por arquivo daria
    doze arquivos de uma linha e doze cabeçalhos repetidos no documento.
    """
    quadro = pd.DataFrame({"idade": _normal(), "imc": _assimetrica()})
    resultado = _rodar(quadro, [_linha("idade"), _linha("imc")])

    assert resultado.tabela.nome == "normalidade.csv"
    # A tabela não é de uma variável, então o cabeçalho do `.csv` não traz a linha
    # `# variável:` — ela seria uma legenda mentindo.
    assert resultado.tabela.variavel == ""
    assert "# variável:" not in resultado.tabela.texto()


def test_o_teste_reconhece_a_normal_e_a_assimetrica():
    quadro = pd.DataFrame({"boa": _normal(300), "torta": _assimetrica(300)})
    resultado = _rodar(quadro, [_linha("boa"), _linha("torta")])
    boa, torta = resultado.variaveis

    assert not boa.rejeita
    assert torta.rejeita
    assert torta.assimetria > 1
    assert "assimétrica à direita" in torta.leitura


def test_faltantes_sao_por_variavel():
    """
    Cada variável é testada sobre os próprios valores preenchidos, e por isso o `n`
    muda de linha. O contrário — descartar a linha inteira do banco por uma célula
    vazia — faria o teste de `idade` depender de quem respondeu `imc`.
    """
    valores = _normal(100)
    quadro = pd.DataFrame({"idade": valores, "imc": [None] * 20 + valores[20:]})
    resultado = _rodar(quadro, [_linha("idade"), _linha("imc")])
    idade, imc = resultado.variaveis

    assert (idade.n, idade.faltantes) == (100, 0)
    assert (imc.n, imc.faltantes) == (80, 20)


# As recusas nomeadas


def test_recusa_numerica_que_chegou_como_texto():
    """
    A mesma recusa da Fase 5, pela mesma função. Se as duas discordassem, o
    relatório sairia com um teste sobre uma coluna que nenhuma tabela descreve.
    """
    quadro = pd.DataFrame({"peso": ["70,5", "81,2", "66,0", "72,4"]})
    with pytest.raises(VariavelIncompativelError) as erro:
        _rodar(quadro, [_linha("peso")])

    assert "peso" in str(erro.value)
    assert "chegou como texto" in str(erro.value)


def test_uma_data_torta_nao_bloqueia_a_normalidade():
    """
    O escopo da recusa é de quem chama: a normalidade só olha as `numerica`, então
    uma coluna `data` com dois formatos misturados — que recusa a descritiva — não
    trava um teste que nunca a abriria.
    """
    quadro = pd.DataFrame(
        {
            "idade": _normal(10),
            "coleta": ["01/03/2024", "2024-03-15"] * 5,
        }
    )
    resultado = _rodar(quadro, [_linha("idade"), _linha("coleta", DATA)])

    assert [v.variavel for v in resultado.variaveis] == ["idade"]
    assert "coleta" in [f.variavel for f in resultado.fora]


def test_recusa_quando_nao_ha_nenhuma_numerica():
    quadro = pd.DataFrame({"sexo": ["F", "M"] * 10, "obs": ["a"] * 20})
    with pytest.raises(NadaParaAnalisarError) as erro:
        _rodar(quadro, [_linha("sexo", CATEGORICA), _linha("obs", IGNORAR)])

    assert "normalidade só se pergunta de variável numérica" in str(erro.value)


def test_recusa_variavel_pedida_que_nao_existe():
    quadro = pd.DataFrame({"idade": _normal(30)})
    with pytest.raises(VariavelPedidaInexistenteError) as erro:
        avaliar(
            banco_em_memoria(quadro),
            ficha_em_memoria(),
            [_linha("idade")],
            ("idade", "imc"),
            QUANDO,
        )

    assert "imc" in str(erro.value)
    assert "não está no dicionario.csv" in str(erro.value)


def test_recusa_variavel_pedida_que_nao_e_numerica():
    quadro = pd.DataFrame({"idade": _normal(30), "sexo": ["F", "M"] * 15})
    with pytest.raises(VariavelPedidaInexistenteError) as erro:
        avaliar(
            banco_em_memoria(quadro),
            ficha_em_memoria(),
            [_linha("idade"), _linha("sexo", CATEGORICA)],
            ("sexo",),
            QUANDO,
        )

    assert "está marcada `categorica`" in str(erro.value)


def test_a_lista_da_ficha_restringe_e_o_resto_vai_para_fora():
    quadro = pd.DataFrame({"idade": _normal(40), "imc": _normal(40, 9)})
    resultado = avaliar(
        banco_em_memoria(quadro),
        ficha_em_memoria(),
        [_linha("idade"), _linha("imc")],
        ("idade",),
        QUANDO,
    )

    assert [v.variavel for v in resultado.variaveis] == ["idade"]
    assert [f.variavel for f in resultado.fora] == ["imc"]
    assert "fora da lista" in resultado.fora[0].motivo


# O que não é recusa, e sai na tabela assim mesmo


def test_variavel_constante_sai_na_tabela_sem_teste():
    """
    A linha sai, com o motivo escrito. Uma variável que simplesmente não aparecesse
    na tabela seria uma variável que ninguém repara que faltou.
    """
    quadro = pd.DataFrame({"idade": _normal(30), "constante": [1.0] * 30})
    resultado = _rodar(quadro, [_linha("idade"), _linha("constante")])
    constante = resultado.variaveis[1]

    assert not constante.testada
    assert constante.w is None and constante.p is None
    assert "um único valor" in constante.leitura


def test_a_constante_nao_sai_com_assimetria_zero():
    """
    O `pandas` devolve **0,0** para a assimetria de uma coluna constante, e não
    `nan`. Impresso na tabela, esse zero se lê como "perfeitamente simétrica" sobre
    uma coluna que não tem forma nenhuma — e é indistinguível do zero de uma
    variável que é mesmo simétrica.
    """
    quadro = pd.DataFrame({"constante": [3.0] * 50})
    resultado = avaliar(
        banco_em_memoria(quadro), ficha_em_memoria(), [_linha("constante")], (), QUANDO
    )
    constante = resultado.variaveis[0]

    assert constante.assimetria is None
    assert constante.curtose is None
    assert resultado.tabela.linhas[0][3] == "—"


def test_variavel_sem_quartis_distintos_nao_gera_figura():
    """
    Sem reta de referência não há Q-Q: Q1 e Q3 coincidem, e a inclinação seria uma
    divisão por zero. Mesma decisão que a Fase 5 tomou com os quartis que
    coincidem — não sai figura, e a linha continua na tabela.

    Note que uma dicotômica **equilibrada** (0 e 1 meio a meio) tem Q1 = 0 e
    Q3 = 1 e gera figura: o caso sem reta é o da variável que é quase toda o mesmo
    valor, que é o que acontece de verdade com um desfecho raro.
    """
    quadro = pd.DataFrame({"desfecho": [0.0] * 45 + [1.0] * 5})
    resultado = avaliar(
        banco_em_memoria(quadro), ficha_em_memoria(), [_linha("desfecho")], (), QUANDO
    )

    assert len(resultado.variaveis) == 1
    assert resultado.variaveis[0].testada  # o teste roda; o que não sai é a figura
    assert resultado.graficos == ()


def test_avisa_quando_n_e_pequeno_demais_para_o_teste_valer():
    quadro = pd.DataFrame({"idade": _normal(MINIMO_CONFIAVEL - 5)})
    resultado = _rodar(quadro, [_linha("idade")])

    assert any("quase não rejeita" in aviso for aviso in resultado.avisos)


def test_avisa_quando_n_e_grande_demais_para_o_valor_p():
    quadro = pd.DataFrame({"idade": _normal(MAXIMO_CONFIAVEL + 50)})
    resultado = _rodar(quadro, [_linha("idade")])

    assert any("deixa de ser exato" in aviso for aviso in resultado.avisos)
    # E o aviso do próprio `scipy` não vazou para o `stderr`: ele foi capturado e
    # virou aviso do FlatCap, como o `ParserWarning` do `banco.py`.
    assert resultado.variaveis[0].testada


def test_avisa_quando_a_variavel_e_discreta():
    """
    O Shapiro-Wilk supõe variável contínua. Sobre uma escala de 0 a 5 ele rejeita
    quase sempre, e o que a rejeição diz é «esta variável é discreta».
    """
    quadro = pd.DataFrame({"dor": [float(v % POUCOS_DISTINTOS) for v in range(200)]})
    resultado = _rodar(quadro, [_linha("dor")])

    assert any("valor(es) distinto(s)" in aviso for aviso in resultado.avisos)
    assert any("`categorica`" in aviso for aviso in resultado.avisos)


# A formatação, que é o que alguém vai conferir


def test_valor_p_nunca_sai_como_zero():
    """
    Um valor-p é estritamente maior que zero, e `p = 0,000` impresso em um
    relatório assinado é um número que não existe.
    """
    quadro = pd.DataFrame({"torta": _assimetrica(400)})
    resultado = _rodar(quadro, [_linha("torta")])
    celula_p = resultado.tabela.linhas[0][6]

    assert celula_p == "< 0,001"


def test_os_numeros_saem_com_virgula_decimal():
    quadro = pd.DataFrame({"idade": _normal(120)})
    resultado = _rodar(quadro, [_linha("idade")])
    _, _, _, assimetria, curtose, w, p, _ = resultado.tabela.linhas[0]

    for celula in (assimetria, curtose, w, p):
        assert "." not in celula, celula
    # Assimetria e curtose saem com sinal e casas fixas: a coluna é lida de cima
    # para baixo, comparando variáveis entre si, e desalinhada ela não se lê.
    assert assimetria[0] in "+-"
    assert len(assimetria.split(",")[1]) == 2


def test_a_leitura_descreve_a_forma_e_nao_escolhe_um_teste():
    """
    "Use Mann-Whitney" depende da comparação que se vai fazer, e este módulo olha
    uma coluna, não um delineamento.
    """
    quadro = pd.DataFrame({"torta": _assimetrica(200)})
    resultado = _rodar(quadro, [_linha("torta")])
    leitura = resultado.variaveis[0].leitura.lower()

    assert "assimétrica" in leitura
    for proibido in ("mann-whitney", "wilcoxon", "spearman", "use ", "recomend"):
        assert proibido not in leitura


def test_a_tabela_avisa_que_o_valor_p_depende_do_n():
    quadro = pd.DataFrame({"idade": _normal(50)})
    resultado = _rodar(quadro, [_linha("idade")])
    notas = " ".join(resultado.tabela.notas)

    assert "depende do n" in notas
    assert "resíduos" in notas  # o engano mais fácil de cometer lendo a tabela
    assert f"nível de {ALFA:.2f}".replace(".", ",") in notas


# O manifesto


def test_o_manifesto_declara_a_analise_e_as_colunas():
    """
    O item da normalidade é **um só** e não é de uma variável. É o `colunas` que
    responde "quais colunas esta rodada usou?" — a pergunta que as conferências do
    relatório fazem a toda rodada.
    """
    quadro = pd.DataFrame({"idade": _normal(60), "imc": _normal(60, 3)})
    linhas = [_linha("idade"), _linha("imc"), _linha("sexo", CATEGORICA)]
    quadro["sexo"] = ["F", "M"] * 30
    resultado = _rodar(quadro, linhas)
    manifesto = montar_manifesto(resultado, linhas, com_graficos=True)

    assert manifesto.analise == ANALISE_NORMALIDADE
    assert len(manifesto.itens) == 1
    item = manifesto.itens[0]
    assert item.variavel == ""
    assert item.rotulo == "Normalidade"
    assert item.colunas == ("idade", "imc")
    assert manifesto.colunas_usadas == ("idade", "imc")


def test_o_manifesto_registra_a_versao_do_scipy():
    """
    "De onde saiu esse p?" precisa ter como resposta uma versão. É o mesmo
    argumento do `ambiente` desde a Fase 5, e é o que sustenta importar o `scipy`
    em vez de implementar o Shapiro-Wilk à mão.
    """
    quadro = pd.DataFrame({"idade": _normal(60)})
    linhas = [_linha("idade")]
    manifesto = montar_manifesto(_rodar(quadro, linhas), linhas, com_graficos=False)

    assert manifesto.ambiente["scipy"]
    # Sem gráfico, o `matplotlib` não é sequer importado para perguntar a versão.
    assert manifesto.ambiente["matplotlib"] is None
    assert manifesto.regras["teste"] == "shapiro-wilk"


def test_sem_graficos_o_manifesto_lista_so_a_tabela():
    quadro = pd.DataFrame({"idade": _normal(60)})
    linhas = [_linha("idade")]
    resultado = _rodar(quadro, linhas)

    com = montar_manifesto(resultado, linhas, com_graficos=True)
    sem = montar_manifesto(resultado, linhas, com_graficos=False)

    assert [a.arquivo for a in sem.tabelas] == ["normalidade.csv"]
    assert sem.figuras == ()
    assert [a.arquivo for a in com.figuras] == ["qq_idade.png"]


def test_as_nao_numericas_aparecem_em_fora():
    """
    "Não está no relatório" e "ninguém reparou que ela existia" são coisas
    diferentes, e só a primeira é uma decisão.
    """
    quadro = pd.DataFrame(
        {"idade": _normal(30), "sexo": ["F", "M"] * 15, "id": range(30)}
    )
    linhas = [_linha("idade"), _linha("sexo", CATEGORICA), _linha("id", IGNORAR)]
    resultado = _rodar(quadro, linhas)

    fora = {f.variavel: f.motivo for f in resultado.fora}
    assert set(fora) == {"sexo", "id"}
    assert "só se pergunta de numérica" in fora["sexo"]
    assert "ignorar" in fora["id"]


# O Q-Q


def test_a_reta_do_qq_passa_pelos_quartis_e_nao_pelos_minimos_quadrados():
    """
    A diferença aparece justamente no caso em que se consulta a figura: um valor
    extremo inclina a reta dos mínimos quadrados o bastante para o resto dos pontos
    parecer curvo — e o que se queria ver era o valor extremo.
    """
    valores = _normal(200)
    limpa = pd.DataFrame({"x": valores})
    suja = pd.DataFrame({"x": valores[:-1] + [500.0]})  # um extremo absurdo

    reta_limpa = _rodar(limpa, [_linha("x")]).variaveis[0].reta
    reta_suja = _rodar(suja, [_linha("x")]).variaveis[0].reta

    # A inclinação praticamente não se move: os quartis não enxergam o extremo.
    assert abs(reta_limpa[1] - reta_suja[1]) / reta_limpa[1] < 0.05


def test_os_pontos_do_qq_estao_ordenados_e_sao_um_por_caso():
    quadro = pd.DataFrame({"idade": _normal(45)})
    variavel = _rodar(quadro, [_linha("idade")]).variaveis[0]

    assert len(variavel.pontos_x) == len(variavel.pontos_y) == 45
    assert list(variavel.pontos_y) == sorted(variavel.pontos_y)
    assert list(variavel.pontos_x) == sorted(variavel.pontos_x)


def test_a_figura_nao_repete_o_valor_p_que_ja_esta_na_tabela():
    """
    Os dois ficam na mesma seção do documento, duas linhas um do outro. É o mesmo
    argumento pelo qual a categórica da Fase 5 saiu sem eixo de valores.
    """
    quadro = pd.DataFrame({"idade": _normal(60)})
    grafico = _rodar(quadro, [_linha("idade")]).graficos[0]

    assert grafico.subtitulo == "n = 60"
    assert "p" not in grafico.subtitulo.lower().replace("n = 60", "")
    assert grafico.especie == "qq"
