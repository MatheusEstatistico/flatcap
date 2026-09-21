"""
O perfil do banco — Fase 4.

Duas metades: `perfilar`, que é função pura e é onde mora quase todo o teste, e
`preparar_perfil`/`executar_perfil`, que só encostam no disco.

O que este arquivo cobre além dos detectores é a promessa que a Fase 4 fez e que
a Fase 5 cobrou: **o `perfil.md` é o documento que vai para a mesa da reunião**.
Um número errado ali custa uma pergunta do cliente; uma coluna inteira marcada
em vermelho sem motivo custa a confiança no documento.
"""

from __future__ import annotations

import pandas as pd
import pytest

import bancos
from flatcap.banco import Banco, Leitura
from flatcap.dicionario import CATEGORICA, DATA, IGNORAR, NUMERICA
from flatcap.ficha import Ficha, Versao
from flatcap.perfil import (
    ARQUIVO_PERFIL,
    CONFIRMAR,
    CORRIGIR,
    NOTA,
    executar_perfil,
    perfilar,
    preparar_perfil,
    texto_do_perfil,
)

# ── Ajudantes ───────────────────────────────────────────────────────────────


def _ficha(tmp_path) -> Ficha:
    return Ficha(
        raiz=tmp_path,
        record_id="42",
        matricula="00742",
        nome="José Antônio de Sá",
        tipo="professor",
        status="em_analise",
        dados=(Versao("00_redcap_2026-09-01_banco.csv", "redcap", "a" * 64, 100),),
    )


def _banco(quadro: pd.DataFrame, tmp_path, confere: bool | None = True) -> Banco:
    """
    Um `Banco` montado à mão: é o que permite perfilar um `DataFrame` sem pasta
    de projeto, sem ficha no disco e sem arquivo nenhum.
    """
    return Banco(
        quadro=quadro,
        versao=Versao("00_redcap_2026-09-01_banco.csv", "redcap", "a" * 64, 100),
        leitura=Leitura(caminho=tmp_path / "banco.csv", separador=";", codificacao="utf-8"),
        confere=confere,
    )


def _codigos(perfil) -> set[str]:
    return {achado.codigo for achado in perfil.achados}


def _coluna(perfil, nome: str):
    return next(c for c in perfil.colunas if c.nome == nome)


@pytest.fixture
def perfilado(tmp_path):
    def perfilar_quadro(quadro: pd.DataFrame, confere: bool | None = True):
        return perfilar(_banco(quadro, tmp_path, confere), _ficha(tmp_path))

    return perfilar_quadro


# ── Como o leitor entendeu cada coluna ──────────────────────────────────────


class TestTipoLido:
    """
    A coluna "lido como" do `perfil.md` e da tabela do terminal.

    Ela responde a uma pergunta só — *o que o leitor achou que esta coluna era?*
    — e é a coluna que o `cli.py` pinta de vermelho quando a resposta é `misto`.
    Vermelho é um recado forte: significa "esta coluna tem duas naturezas
    convivendo e precisa ser consertada antes de qualquer conta".
    """

    def test_coluna_de_texto_e_lida_como_texto(self, perfilado):
        """
        REGRESSÃO — o defeito que a suíte de duas versões do pandas não pegou.

        `_tipo_lido` decide `misto` por `serie.dtype == object`. No pandas 3 uma
        coluna de texto tem dtype `str` e o teste passa; no pandas 2 ela tem
        dtype `object`, e **toda** categórica do banco sai marcada `misto`, em
        vermelho, no documento que vai para a reunião.

        O roteiro previu exatamente esta armadilha, na Fase 4: *"Um detector
        escrito como `if serie.dtype == object` funcionaria na sua máquina e
        sumiria em silêncio na próxima instalação."* Ele sumiu na direção
        contrária — o que some no pandas 3 é o falso positivo.

        O conserto é usar `_tipos_de(serie) > 1`, que já existe no módulo e já é
        o que a sugestão de tipo usa.
        """
        perfil = perfilado(bancos.completo())
        assert _coluna(perfil, "sexo").tipo_lido == "texto"
        assert _coluna(perfil, "escolaridade").tipo_lido == "texto"
        assert _coluna(perfil, "observacoes").tipo_lido == "texto"

    def test_so_a_coluna_de_duas_naturezas_e_lida_como_misto(self, perfilado):
        perfil = perfilado(bancos.com_tipos_misturados())
        assert _coluna(perfil, "imc").tipo_lido == "misto"
        assert _coluna(perfil, "sexo").tipo_lido == "texto"

    @pytest.mark.parametrize(
        ("coluna", "esperado"),
        [("idade", "inteiro"), ("imc", "decimal"), ("id_paciente", "texto")],
    )
    def test_numero_inteiro_e_decimal_se_distinguem(self, perfilado, coluna, esperado):
        perfil = perfilado(bancos.completo())
        assert _coluna(perfil, coluna).tipo_lido == esperado

    def test_coluna_sem_valor_nenhum_e_vazia_e_nao_decimal(self, perfilado):
        """
        Coluna sem nada chega como `float64` por convenção do pandas. Anunciá-la
        como "decimal" seria descrever a convenção, não o banco.
        """
        perfil = perfilado(bancos.com_coluna_vazia())
        assert _coluna(perfil, "peso_anterior").tipo_lido == "vazia"

    def test_coluna_de_data_de_verdade_e_lida_como_data(self, perfilado):
        quadro = bancos.completo()
        quadro["data_coleta"] = pd.to_datetime(quadro["data_coleta"], format="%d/%m/%Y")
        perfil = perfilado(quadro)
        assert _coluna(perfil, "data_coleta").tipo_lido == "data"

    def test_coluna_logica_e_lida_como_logico(self, perfilado):
        quadro = bancos.completo()
        quadro["fumante"] = [True, False] * (len(quadro) // 2)
        perfil = perfilado(quadro)
        assert _coluna(perfil, "fumante").tipo_lido == "lógico"


# ── Os dezesseis detectores ─────────────────────────────────────────────────


class TestDetectoresCorrigir:
    """
    Os que dizem "o banco precisa mudar antes de a análise começar".
    """

    def test_virgula_decimal(self, perfilado):
        perfil = perfilado(bancos.com_virgula_decimal())
        assert "virgula_decimal" in _codigos(perfil)
        achado = next(a for a in perfil.achados if a.codigo == "virgula_decimal")
        assert achado.gravidade == CORRIGIR
        assert achado.variavel == "imc"
        assert achado.exemplos, "sem exemplo o cliente procura; com exemplo ele acha"

    def test_numero_como_texto(self, perfilado):
        perfil = perfilado(bancos.com_numero_como_texto())
        assert "numero_como_texto" in _codigos(perfil)

    def test_virgula_decimal_e_numero_como_texto_nao_disparam_juntos(self, perfilado):
        """
        São o mesmo problema visto de dois ângulos; os dois na mesma lista fazem
        a reunião discutir duas vezes a mesma coluna.
        """
        codigos = _codigos(perfilado(bancos.com_virgula_decimal()))
        assert "numero_como_texto" not in codigos

    def test_data_como_texto_diz_o_formato(self, perfilado):
        perfil = perfilado(bancos.completo())
        achado = next(a for a in perfil.achados if a.codigo == "data_como_texto")
        assert "%d/%m/%Y" in achado.titulo

    def test_data_com_dois_formatos_nao_e_denunciada_como_formato_unico(self, perfilado):
        """
        Nenhum formato explica a coluna, então não há formato a nomear. Ela é
        indecidível — e é a Fase 5 que a recusa.
        """
        assert "data_como_texto" not in _codigos(perfilado(bancos.com_datas_misturadas()))

    def test_tipos_misturados_nomeia_as_naturezas_e_da_exemplo_de_cada(self, perfilado):
        perfil = perfilado(bancos.com_tipos_misturados())
        achado = next(a for a in perfil.achados if a.codigo == "tipos_misturados")
        assert achado.gravidade == CORRIGIR
        assert "texto" in achado.titulo
        assert len(achado.exemplos) >= 2

    def test_cabecalho_repetido(self, perfilado):
        assert "cabecalho_repetido" in _codigos(perfilado(bancos.com_cabecalho_repetido()))

    def test_cabecalho_vazio(self, perfilado):
        quadro = bancos.completo()
        quadro["Unnamed: 7"] = [None] * len(quadro)
        assert "cabecalho_vazio" in _codigos(perfilado(quadro))


class TestDetectoresConfirmar:
    """
    Os que dizem "é decisão do cliente, e ele precisa ser perguntado".
    """

    def test_variacao_de_grafia_agrupa_as_quatro(self, perfilado):
        perfil = perfilado(bancos.com_variacao_de_grafia())
        achado = next(a for a in perfil.achados if a.codigo == "variacao_de_grafia")
        assert achado.gravidade == CONFIRMAR
        assert "Feminino" in " ".join(achado.exemplos)

    def test_sentinela_numerica_so_dispara_quando_destoa(self, perfilado):
        """
        Um `999` numa coluna que vai até 62 é código de faltante. O mesmo `999`
        numa coluna de valores da mesma ordem é um valor como outro — e um
        detector que dispara em banco limpo é pior do que detector nenhum,
        porque você aprende a ignorar a lista.
        """
        assert "sentinela_numerica" in _codigos(perfilado(bancos.com_sentinela_numerica()))

        quadro = bancos.completo()
        quadro["pressao"] = [99, 120, 130, 110] * (len(quadro) // 4)
        assert "sentinela_numerica" not in _codigos(perfilado(quadro))

    def test_sentinela_textual(self, perfilado):
        assert "sentinela_textual" in _codigos(perfilado(bancos.com_sentinela_textual()))

    def test_muitos_faltantes_a_partir_de_20_por_cento(self, perfilado):
        assert "muitos_faltantes" in _codigos(perfilado(bancos.com_muitos_faltantes(0.25)))
        assert "muitos_faltantes" not in _codigos(perfilado(bancos.completo()))

    def test_coluna_vazia(self, perfilado):
        assert "coluna_vazia" in _codigos(perfilado(bancos.com_coluna_vazia()))

    def test_linhas_duplicadas_conta_quantas(self, perfilado):
        perfil = perfilado(bancos.com_linhas_duplicadas())
        assert perfil.duplicadas == 2
        assert "linhas_duplicadas" in _codigos(perfil)

    def test_espaco_sobrando_nao_repete_a_variacao_de_grafia(self, perfilado):
        """
        `"Sim "` e `"Sim"` já aparecem como variação de grafia. O detector de
        espaço existe para o caso em que **só** há espaço sobrando.
        """
        quadro = bancos.completo()
        quadro["consentiu"] = ["Sim "] * len(quadro)
        assert "espaco_sobrando" in _codigos(perfilado(quadro))


class TestDetectoresNota:
    def test_coluna_constante(self, perfilado):
        perfil = perfilado(bancos.com_coluna_constante())
        achado = next(a for a in perfil.achados if a.codigo == "coluna_constante")
        assert achado.gravidade == NOTA

    def test_poucas_linhas(self, perfilado):
        assert "poucas_linhas" in _codigos(perfilado(bancos.minusculo(3)))

    def test_cabecalho_com_espaco(self, perfilado):
        quadro = bancos.completo().rename(columns={"sexo": "sexo "})
        assert "cabecalho_com_espaco" in _codigos(perfilado(quadro))

    def test_banco_limpo_nao_dispara_nada_alem_da_data(self, perfilado):
        """
        A data escrita como texto é inevitável num `.csv`. Fora ela, o banco de
        referência precisa passar limpo — senão a lista da reunião vira ruído.
        """
        assert _codigos(perfilado(bancos.completo())) == {"data_como_texto"}


# ── A sugestão de tipo ──────────────────────────────────────────────────────


class TestSugestao:
    """
    A automação propõe, você decide. Mas a proposta precisa ser conferível: ela
    viaja com o motivo, e é por isso que o motivo é um campo e não um comentário.
    """

    @pytest.mark.parametrize(
        ("coluna", "tipo"),
        [
            ("sexo", CATEGORICA),
            ("escolaridade", CATEGORICA),
            ("idade", NUMERICA),
            ("imc", NUMERICA),
            ("data_coleta", DATA),
            ("id_paciente", IGNORAR),
        ],
    )
    def test_o_banco_de_referencia_sai_todo_certo(self, perfilado, coluna, tipo):
        assert _coluna(perfilado(bancos.completo()), coluna).sugestao == tipo

    def test_toda_sugestao_traz_o_motivo(self, perfilado):
        for c in perfilado(bancos.completo()).colunas:
            assert c.motivo, f"`{c.nome}` sugerida sem motivo — não dá para conferir"

    def test_inteiro_pequeno_que_se_repete_e_codigo(self, perfilado):
        perfil = perfilado(bancos.com_codigos_numericos())
        assert _coluna(perfil, "sexo_cod").sugestao == CATEGORICA
        assert _coluna(perfil, "fumante").sugestao == CATEGORICA

    def test_idade_num_banco_pequeno_nao_vira_codigo(self, perfilado):
        """
        A trava dupla. Só "poucos valores distintos" classificaria como código
        toda coluna numérica de um banco de seis linhas: os valores precisam
        **se repetir** e precisam ser **pequenos** — código é 0/1, 1/2, uma
        escala de 1 a 5, nunca 27, 38, 61.
        """
        assert _coluna(perfilado(bancos.minusculo(6)), "idade").sugestao == NUMERICA

    def test_texto_livre_vira_ignorar(self, perfilado):
        assert _coluna(perfilado(bancos.completo()), "observacoes").sugestao == IGNORAR

    def test_coluna_vazia_vira_ignorar(self, perfilado):
        assert _coluna(perfilado(bancos.com_coluna_vazia()), "peso_anterior").sugestao == IGNORAR


class TestCategoriasSugeridas:
    def test_ordem_e_frequencia_decrescente_com_empate_alfabetico(self, perfilado):
        """
        Determinística de propósito: duas execuções idênticas precisam produzir
        o mesmo arquivo, senão o `dicionario.csv` gera diff falso.
        """
        quadro = bancos.completo()
        quadro["grupo"] = ["B"] * 10 + ["A"] * 7 + ["C"] * 7
        sugeridas = _coluna(perfilado(quadro), "grupo").categorias_sugeridas
        assert sugeridas == ("B", "A", "C")

    def test_coluna_a_corrigir_nao_recebe_proposta(self, perfilado):
        """
        Os valores que ela tem hoje são exatamente os que vão deixar de existir
        quando o cliente corrigir. Propor uma ordem sobre eles é encher o
        arquivo de linha para apagar.
        """
        perfil = perfilado(bancos.com_variacao_de_grafia())
        assert _coluna(perfil, "sexo").categorias_sugeridas == ()

    def test_categoria_com_barra_fica_em_branco_e_avisa(self, perfilado):
        perfil = perfilado(bancos.com_categoria_com_barra())
        assert _coluna(perfil, "escolaridade").categorias_sugeridas == ()
        assert "categoria_com_barra" in _codigos(perfil)


# ── Contagem, e a fidelidade ao arquivo ─────────────────────────────────────


class TestMedidas:
    def test_faltantes_e_unicos(self, perfilado):
        perfil = perfilado(bancos.com_muitos_faltantes(0.25))
        coluna = _coluna(perfil, "escolaridade")
        assert coluna.faltantes == 6
        assert coluna.preenchidos == 18
        assert coluna.proporcao_faltante == pytest.approx(0.25)

    def test_o_resumo_das_numericas_tem_as_sete_estatisticas(self, perfilado):
        resumo = _coluna(perfilado(bancos.completo()), "idade").resumo_numerico
        assert set(resumo) == {"minimo", "q1", "mediana", "q3", "maximo", "media", "desvio"}

    def test_nome_de_coluna_repetido_nao_derruba_o_perfil(self, perfilado):
        """
        O perfil precisa medir justamente o banco que mais precisa de
        diagnóstico. `quadro[nome]` devolveria um `DataFrame` no lugar de uma
        coluna; a leitura é por posição.
        """
        quadro = bancos.completo()
        quadro.columns = ["sexo"] + list(quadro.columns[1:])
        perfil = perfilado(quadro)
        assert perfil.total_colunas == len(quadro.columns)

    def test_o_perfil_nao_conserta_nada(self, perfilado):
        """
        Vírgula decimal continua vírgula decimal. O arquivo é do cliente, a
        correção é dele — e a Fase 3 tem o lugar certo para a versão corrigida.
        """
        quadro = bancos.com_virgula_decimal()
        antes = list(quadro["imc"])
        perfilado(quadro)
        assert list(quadro["imc"]) == antes


# ── O perfil.md ─────────────────────────────────────────────────────────────


class TestTextoDoPerfil:
    def test_o_checklist_vem_antes_das_tabelas(self, perfilado, tmp_path):
        """
        O checklist é o que exige decisão; tabela é consulta, e consulta se
        procura quando precisa.
        """
        from flatcap.dicionario import fundir

        perfil = perfilado(bancos.com_virgula_decimal())
        fusao = fundir((), tuple(c.como_sugestao().como_linha() for c in perfil.colunas))
        texto = texto_do_perfil(perfil, fusao)
        assert texto.index("## O que levar para a reunião") < texto.index("## Variáveis")

    def test_o_cabecalho_registra_as_tres_decisoes_do_leitor(self, tmp_path):
        """
        Planilha, separador e codificação. São as três decisões que o leitor
        tomou sozinho, e a única forma de descobrir que ele tomou a errada é
        vê-las escritas.
        """
        from flatcap.dicionario import fundir

        banco = Banco(
            quadro=bancos.completo(),
            versao=Versao("00_redcap_2026-09-01_b.xlsx", "redcap", "a" * 64, 100),
            leitura=Leitura(
                caminho=tmp_path / "b.xlsx", aba="Dados", abas=("Dados", "Dicionário")
            ),
            confere=True,
        )
        perfil = perfilar(banco, _ficha(tmp_path))
        texto = texto_do_perfil(perfil, fundir((), ()))
        assert 'planilha "Dados"' in texto

    def test_o_valor_com_barra_vertical_nao_desalinha_a_tabela(self, perfilado):
        from flatcap.dicionario import fundir

        perfil = perfilado(bancos.com_categoria_com_barra())
        texto = texto_do_perfil(perfil, fundir((), ()))
        for linha in texto.splitlines():
            if linha.startswith("| ") and "técnico" in linha:
                assert "\\|" in linha

    def test_a_integridade_alterada_aparece_no_documento(self, perfilado):
        from flatcap.dicionario import fundir

        perfil = perfilado(bancos.completo(), confere=False)
        texto = texto_do_perfil(perfil, fundir((), ()))
        assert "não confere" in texto


# ── Prepare e execute ───────────────────────────────────────────────────────


class TestPrepararEExecutar:
    def test_preparar_nao_escreve_nada(self, projeto_com_banco):
        raiz = projeto_com_banco()
        preparar_perfil(raiz)
        assert not (raiz / ARQUIVO_PERFIL).exists()
        assert not (raiz / "dicionario.csv").exists()

    def test_executar_escreve_os_dois_arquivos(self, projeto_com_banco):
        raiz = projeto_com_banco()
        plano = preparar_perfil(raiz)
        resultado = executar_perfil(plano)
        assert (raiz / ARQUIVO_PERFIL).is_file()
        assert (raiz / "dicionario.csv").is_file()
        assert len(resultado.criados) == 2

    def test_o_texto_do_plano_e_exatamente_o_arquivo_gravado(self, projeto_com_banco):
        """
        A invariante que faz a simulação valer alguma coisa: o texto é o
        arquivo, e não uma aproximação dele.
        """
        raiz = projeto_com_banco()
        plano = preparar_perfil(raiz)
        executar_perfil(plano)
        assert (raiz / ARQUIVO_PERFIL).read_text(encoding="utf-8") == plano.texto_perfil

    def test_rodar_duas_vezes_preserva_o_dicionario_preenchido(self, projeto_com_banco):
        """
        A regra central da Fase 4, e a que protege a reunião: linha que já
        existe no arquivo não é tocada. Nunca. Nem um campo.
        """
        raiz = projeto_com_banco()
        executar_perfil(preparar_perfil(raiz))

        caminho = raiz / "dicionario.csv"
        texto = caminho.read_text(encoding="utf-8-sig").replace(
            "sexo;sexo;categorica", "sexo;Sexo do participante;categorica"
        )
        caminho.write_text(texto, encoding="utf-8", newline="\n")

        executar_perfil(preparar_perfil(raiz))
        assert "Sexo do participante" in caminho.read_text(encoding="utf-8-sig")

    def test_o_perfil_nao_fala_com_o_redcap(self, projeto_com_banco, env_valido):
        """
        O token de `env_valido` é inválido de propósito. Se o `perfil` tocasse a
        rede, este teste falharia — e é a única forma de garantir a promessa.
        """
        raiz = projeto_com_banco()
        assert preparar_perfil(raiz).perfil.linhas == len(bancos.completo())

    def test_escreve_uma_linha_no_historico(self, projeto_com_banco):
        from conftest import linhas_do_historico

        raiz = projeto_com_banco()
        antes = len(linhas_do_historico(raiz))
        executar_perfil(preparar_perfil(raiz))
        assert len(linhas_do_historico(raiz)) == antes + 1

    def test_a_simulacao_diz_de_quando_e_o_perfil_que_sera_substituido(
        self, projeto_com_banco
    ):
        """
        Um `perfil.md` de hoje de manhã é uma coisa; um de três semanas atrás,
        com as suas anotações da reunião, é outra.
        """
        from conftest import AGORA

        raiz = projeto_com_banco()
        executar_perfil(preparar_perfil(raiz, agora=AGORA))
        plano = preparar_perfil(raiz)
        assert plano.perfil_anterior == AGORA


# ── As travas que impedem a classe, e não só o caso ─────────────────────────


class TestTravasEstruturais:
    """
    Dois testes que afirmam propriedades do **código**, não do comportamento.

    Eles existem porque os dois defeitos graves deste módulo não foram erros de
    lógica: foram perguntas trocadas. Um teste de comportamento pega a coluna
    que falhou; estes pegam a próxima.
    """

    def test_todo_achado_esta_classificado_como_volatil_ou_estavel(self):
        """
        Um detector novo não pode ficar sem resposta para "os valores desta
        coluna vão mudar quando o cliente corrigir?".

        `CORRIGIR` é volátil por definição, e `NOTA` é estável pela regra do
        `_categorias_sugeridas`, que só consulta `CORRIGIR` e `CODIGOS_VOLATEIS`.
        Os de `CONFIRMAR` são os que pedem escolha consciente, e quem responde é
        o `codigo_classificado` do próprio módulo — e não uma lista mantida aqui
        em paralelo, que foi como `categoria_sem_rotulo` entrou no módulo
        classificado e saiu deste teste sem classificação.
        """
        import ast
        import inspect

        import flatcap.perfil as modulo
        from flatcap.perfil import CODIGOS_ESTAVEIS, CODIGOS_VOLATEIS, codigo_classificado

        arvore = ast.parse(inspect.getsource(modulo))
        emitidos: set[str] = set()
        por_confirmar: set[str] = set()
        for no in ast.walk(arvore):
            if not (isinstance(no, ast.Call) and getattr(no.func, "id", "") == "Achado"):
                continue
            argumentos = {kw.arg: kw.value for kw in no.keywords}
            codigo = argumentos.get("codigo")
            if not isinstance(codigo, ast.Constant):
                continue
            emitidos.add(codigo.value)
            gravidade = argumentos.get("gravidade")
            if isinstance(gravidade, ast.Name) and gravidade.id == "CONFIRMAR":
                por_confirmar.add(codigo.value)

        assert emitidos, "nenhum Achado encontrado — o parser deste teste quebrou"
        sem_classificacao = sorted(c for c in por_confirmar if not codigo_classificado(c))
        assert not sem_classificacao, f"detector sem classificação: {sem_classificacao}"
        # E o contrário: classificação de um código que nenhum detector emite é
        # uma lista que ficou para trás de uma mudança de nome.
        orfaos = sorted((CODIGOS_VOLATEIS | CODIGOS_ESTAVEIS) - emitidos)
        assert not orfaos, f"classificado e nunca emitido: {orfaos}"
        assert not (CODIGOS_VOLATEIS & CODIGOS_ESTAVEIS)

    def test_ninguem_pergunta_o_dtype_fora_dos_predicados(self):
        """
        `serie.dtype == object` é a pergunta errada: ela responde "como o pandas
        guardou isto", quando o que se quer saber é o que há na coluna. A
        resposta muda entre o pandas 2 e o 3 sem que nada avise — foi assim que
        toda categórica do banco passou a sair marcada `misto`, em vermelho, no
        documento que vai para a reunião.

        As perguntas certas têm nome: `_e_numerica`, `_e_data`, `_e_booleana` e
        `_tipos_de`. Só elas podem olhar o `dtype`.
        """
        import re
        from pathlib import Path

        import flatcap

        permitido = {"_tipos_de", "_e_numerica", "_e_data", "_e_booleana"}
        culpados: list[str] = []

        for arquivo in sorted(Path(flatcap.__file__).parent.glob("*.py")):
            texto = arquivo.read_text(encoding="utf-8")
            atual = ""
            for numero, bruta in enumerate(texto.splitlines(), 1):
                casamento = re.match(r"\s*def\s+(\w+)", bruta)
                if casamento:
                    atual = casamento.group(1)
                # comentário e docstring podem citar a forma errada de propósito,
                # que é o caso desta própria linha
                linha = bruta.split("#")[0]
                if linha.lstrip().startswith(('"', "'")):
                    continue
                if re.search(r"\.dtype\s*[!=]=", linha) and atual not in permitido:
                    culpados.append(f"{arquivo.name}:{numero} em `{atual}`")

        assert not culpados, (
            "compare o dtype só dentro dos predicados nomeados: " + ", ".join(culpados)
        )
