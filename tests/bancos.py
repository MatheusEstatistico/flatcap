"""
Os bancos de mentira.

Um lugar só para eles, pela mesma razão que o `servidor_falso.py` existe: um
banco montado dentro do arquivo de teste que precisa dele vira quatro bancos
quase iguais em quatro arquivos, e no dia em que o formato mudar três deles
ficam para trás.

## A regra dos bancos daqui

**Eles são feios de propósito.** Um banco limpo não exercita nada: os dezesseis
detectores da Fase 4 existem porque o arquivo que o cliente manda tem vírgula
decimal, quatro grafias de "Feminino", uma observação escrita no meio de uma
coluna de número e um `999` que quer dizer "não sei". Um fixture bem-comportado
é um fixture que passa em código quebrado.

**Cada esquisitice tem nome.** `com_virgula_decimal()` não é "o banco 2": é o
arquivo que faz `virgula_decimal` disparar, e o teste que o usa diz isso na
primeira linha.

**Nenhum deles é aleatório.** Nada aqui sorteia; um banco que muda entre duas
execuções é um teste que falha uma vez por semana e ninguém descobre por quê.
"""

from __future__ import annotations

import pandas as pd

N = 24


def _repetir(valores: list, tamanho: int = N) -> list:
    return [valores[i % len(valores)] for i in range(tamanho)]


# ── O banco de referência ───────────────────────────────────────────────────


def completo() -> pd.DataFrame:
    """
    Um banco bem-comportado, com um exemplar de cada tipo do dicionário.

    É o único banco limpo da casa, e serve para o caminho feliz: uma
    categórica nominal, uma categórica ordinal, uma numérica inteira, uma
    numérica decimal, uma data escrita como texto (que é como ela chega num
    `.csv`), um identificador e uma coluna de texto livre.
    """
    return pd.DataFrame(
        {
            "id_paciente": [f"P{i:03d}" for i in range(1, N + 1)],
            "sexo": _repetir(["Feminino", "Masculino"]),
            "escolaridade": _repetir(["Fundamental", "Médio", "Superior", "Médio"]),
            "idade": [
                23, 45, 31, 62, 28, 55, 39, 47, 33, 51, 29, 60,
                41, 36, 58, 27, 44, 49, 34, 53, 30, 46, 38, 57,
            ],
            "imc": [
                22.5, 27.1, 24.3, 31.2, 19.8, 28.4, 26.0, 23.7,
                30.1, 21.9, 25.5, 29.3, 22.1, 26.8, 24.9, 27.7,
                23.2, 28.9, 25.1, 30.8, 21.4, 26.3, 24.6, 29.9,
            ],
            "data_coleta": [f"{(i % 28) + 1:02d}/{(i % 6) + 1:02d}/2026" for i in range(N)],
            "observacoes": [f"anotação livre número {i}" for i in range(N)],
        }
    )


# ── Um defeito por banco ────────────────────────────────────────────────────


def com_virgula_decimal() -> pd.DataFrame:
    """
    `imc` com vírgula decimal, guardada como texto. Dispara `virgula_decimal`.

    É o caso que faz a Fase 5 **recusar** a rodada inteira, e a recusa é a
    decisão central daquela fase: converter em silêncio é como uma média sai de
    80% dos casos sem que nada na tabela diga que os outros 20% não entraram.
    """
    quadro = completo()
    quadro["imc"] = [f"{valor:.1f}".replace(".", ",") for valor in quadro["imc"]]
    return quadro


def com_numero_como_texto() -> pd.DataFrame:
    """
    `idade` toda numérica e guardada como texto. Dispara `numero_como_texto`.
    """
    quadro = completo()
    quadro["idade"] = [f" {valor} " for valor in quadro["idade"]]
    return quadro


def com_tipos_misturados() -> pd.DataFrame:
    """
    `imc` com uma observação escrita no meio dos números.

    O caso que o `_achados_mistos` procura, e o que separa "a coluna é texto"
    de "a coluna tem duas naturezas": aqui há `float` e `str` convivendo, e
    nenhum dos dois some quando o `pandas` novo passa a ler texto como `str`.
    """
    quadro = completo()
    valores: list = list(quadro["imc"])
    valores[3] = "não realizado"
    valores[7] = "<0,5"
    valores[11] = "12 (repetido)"
    quadro["imc"] = valores
    return quadro


def com_variacao_de_grafia() -> pd.DataFrame:
    """
    `sexo` com quatro grafias da mesma coisa. Dispara `variacao_de_grafia`.

    As quatro diferem só por acento, caixa e espaço — que é exatamente o que
    ninguém vê olhando a planilha e o que faz cada grafia virar uma linha
    própria na tabela de frequência.
    """
    quadro = completo()
    quadro["sexo"] = _repetir(["Feminino", "feminino", "FEMININO ", "Masculino"])
    return quadro


def com_sentinela_numerica() -> pd.DataFrame:
    """
    `idade` com `999` como código de faltante.

    Repare que o resto da coluna vai até 62: o detector só denuncia quando o
    valor **destoa**. Um `999` numa coluna de valores da mesma ordem de
    grandeza é um valor como outro, e um detector que dispara em banco limpo é
    pior do que detector nenhum.
    """
    quadro = completo()
    idades = list(quadro["idade"])
    idades[2] = 999
    idades[9] = 999
    quadro["idade"] = idades
    return quadro


def com_sentinela_textual() -> pd.DataFrame:
    """
    `escolaridade` com "não informado" escrito à mão como se fosse categoria.
    """
    quadro = completo()
    valores = list(quadro["escolaridade"])
    valores[1] = "não informado"
    valores[5] = "ignorado"
    quadro["escolaridade"] = valores
    return quadro


def com_muitos_faltantes(proporcao: float = 0.25) -> pd.DataFrame:
    """
    `escolaridade` acima do limite de 20% de faltantes.
    """
    quadro = completo()
    quantos = int(N * proporcao)
    valores = list(quadro["escolaridade"])
    for posicao in range(quantos):
        valores[posicao] = None
    quadro["escolaridade"] = valores
    return quadro


def com_coluna_vazia() -> pd.DataFrame:
    """
    Uma coluna que não chegou a ser coletada.
    """
    quadro = completo()
    quadro["peso_anterior"] = [None] * N
    return quadro


def com_coluna_constante() -> pd.DataFrame:
    """
    Uma variável que não varia — costuma ser critério de inclusão do estudo.
    """
    quadro = completo()
    quadro["servico"] = ["Ambulatório"] * N
    return quadro


def com_linhas_duplicadas() -> pd.DataFrame:
    """
    Duas linhas idênticas de ponta a ponta.
    """
    quadro = completo()
    return pd.concat([quadro, quadro.iloc[[0, 1]]], ignore_index=True)


def com_cabecalho_repetido() -> pd.DataFrame:
    """
    Duas colunas com o mesmo nome, diferindo só por caixa.

    O dicionário usa o nome como chave, então duas colunas que se leem iguais
    não podem ser distinguidas — e o leitor renomeia a segunda para `sexo.1`
    sem que nada na tabela diga o que ela era.
    """
    quadro = completo()
    quadro["Sexo"] = quadro["sexo"]
    return quadro


def com_datas_misturadas() -> pd.DataFrame:
    """
    `data_coleta` com dois formatos convivendo.

    É o caso indecidível: nenhum formato único explica a coluna, então a Fase 4
    não a denuncia como `data_como_texto` e a Fase 5 a recusa em vez de
    inventar datas. Os exemplos da mensagem precisam ser valores **distintos**,
    senão os cinco primeiros são cinco vezes o mesmo formato.
    """
    quadro = completo()
    valores = [f"{(i % 28) + 1:02d}/{(i % 6) + 1:02d}/2026" for i in range(N)]
    for posicao in range(0, N, 2):
        dia = (posicao % 28) + 1
        mes = (posicao % 6) + 1
        valores[posicao] = f"2026-{mes:02d}-{dia:02d}"
    quadro["data_coleta"] = valores
    return quadro


def com_categoria_com_barra() -> pd.DataFrame:
    """
    Uma categoria contendo `|`, que é o separador da lista no dicionário.
    """
    quadro = completo()
    quadro["escolaridade"] = _repetir(["Fundamental", "Médio | técnico", "Superior"])
    return quadro


def com_categoria_com_ponto_e_virgula() -> pd.DataFrame:
    """
    Uma variável de **uma categoria só**, contendo `;` no valor.

    Uma categoria só é o detalhe que importa: com duas ou mais, o `|` que junta
    a lista protege o campo na volta. Com uma, não há `|` no campo, e a leitura
    tolerante do `;` parte o valor em dois.
    """
    quadro = completo()
    quadro["desfecho"] = ["Alta; a pedido"] * N
    return quadro


def com_codigos_numericos() -> pd.DataFrame:
    """
    `sexo` como `1`/`2` e `fumante` como `0`/`1`.

    A heurística "inteiro pequeno com poucos valores distintos é código" precisa
    de trava dupla: os valores têm de **se repetir** e de ser **pequenos**.
    `idade` continua no banco justamente para não ser classificada como código.
    """
    quadro = completo()
    quadro["sexo_cod"] = _repetir([1, 2])
    quadro["fumante"] = _repetir([0, 1, 1, 0])
    return quadro


def para_cruzar() -> pd.DataFrame:
    """
    `sexo` em código e `escolaridade` em texto, com quatro linhas sem uma das duas
    respostas — o exemplo do `cruzamento-o-que-construir.md`, que o `cruz()` feito à
    mão imprimia com três defeitos.

    Sessenta linhas: 56 com as duas respostas, em seis combinações de tamanhos
    diferentes, e quatro com uma só. As três esquisitices estão aqui de propósito:

    * a coluna de código tem célula vazia, então ela chega **decimal** — é o `1.0`
      que o `pd.crosstab` imprime no lugar de `1`;
    * `Masculino · Fundamental` é a menor combinação, com 3 casos — a que o `cruz()`
      apagava com o `drop` da última linha;
    * as quatro linhas incompletas são as que o `pd.crosstab` descarta em silêncio,
      e que fazem o total dele dar 56 num banco de 60.
    """
    combinacoes = [
        (1, "Superior", 15),
        (1, "Médio", 12),
        (2, "Médio", 11),
        (2, "Superior", 9),
        (1, "Fundamental", 6),
        (2, "Fundamental", 3),
    ]
    linhas: list[tuple] = [
        (sexo, escolaridade)
        for sexo, escolaridade, quantos in combinacoes
        for _ in range(quantos)
    ]
    linhas += [(None, "Médio"), (None, "Superior"), (1, None), (2, None)]
    return pd.DataFrame(linhas, columns=["sexo", "escolaridade"])


def para_associar() -> pd.DataFrame:
    """
    Dois grupos de 40 e uma variável para cada caminho da regra de Cochran.

    Cruzada com `grupo`, cada coluna cai num teste diferente — é o banco da forma
    "uma contra várias", `grupo: [desfecho, complicacao, escolaridade,
    faixa_etaria]`:

    * `desfecho` — código `0`/`1` com **uma célula vazia**, que chega decimal da
      leitura; 2×2 com todas as esperadas acima de 5: **qui-quadrado com Yates**,
      sobre 79 casos e não 80;
    * `complicacao` — evento raro, 1 e 5 casos: esperada 3 em duas das quatro
      caselas, **exato de Fisher 2×2**;
    * `escolaridade` — `Pós-graduação` com 1 e 2 casos: 2×4 com duas caselas de
      oito (25%) abaixo de 5, **exato de Fisher maior que 2×2**;
    * `faixa_etaria` — três faixas equilibradas: 2×3 com tudo acima de 5,
      **qui-quadrado sem Yates**;
    * `servico` — uma categoria só: **não há teste**.

    As contagens de cada grupo estão escritas por extenso, em blocos, e não
    sorteadas: o teste confere o p contra uma conta independente feita sobre estes
    mesmos números.
    """
    controle = {
        "desfecho": [1] * 12 + [0] * 27 + [None],
        "complicacao": ["Sim"] * 1 + ["Não"] * 39,
        "escolaridade": ["Fundamental"] * 10 + ["Médio"] * 20 + ["Superior"] * 9
        + ["Pós-graduação"] * 1,
        "faixa_etaria": ["18 a 39"] * 15 + ["40 a 59"] * 15 + ["60 ou mais"] * 10,
    }
    intervencao = {
        "desfecho": [1] * 24 + [0] * 16,
        "complicacao": ["Sim"] * 5 + ["Não"] * 35,
        "escolaridade": ["Fundamental"] * 8 + ["Médio"] * 15 + ["Superior"] * 15
        + ["Pós-graduação"] * 2,
        "faixa_etaria": ["18 a 39"] * 12 + ["40 a 59"] * 14 + ["60 ou mais"] * 14,
    }
    quadro = pd.DataFrame(
        {
            "grupo": ["Controle"] * 40 + ["Intervenção"] * 40,
            **{
                coluna: controle[coluna] + intervencao[coluna]
                for coluna in ("desfecho", "complicacao", "escolaridade", "faixa_etaria")
            },
            "servico": ["Ambulatório"] * 80,
        }
    )
    return quadro


def para_correlacionar() -> pd.DataFrame:
    """
    Sessenta casos e uma variável para cada caminho da regra dos pressupostos.

    Correlacionada com `idade`, cada coluna cai num método diferente:

    * `imc` — soma de duas colunas de escores normais, com **três células vazias**:
      as duas contínuas e nenhuma com a normal rejeitada, **Pearson**, sobre 57
      casos e não 60;
    * `renda` — a exponencial de escores normais, assimétrica à direita: o
      Shapiro-Wilk rejeita, **Spearman**;
    * `dor` — escala de 0 a 5, **categórica com código numérico**: seis valores
      distintos, com repetição, **Kendall**;
    * `escolaridade` — categórica **em texto**: não tem ordem que se possa ler, e o
      par é recusado;
    * `servico` — código `1` em todas as linhas, um valor só: **não há
      correlação**.

    Nada é sorteado. Os escores normais são os quantis da normal em posições
    igualmente espaçadas, e o "ruído" é a mesma lista embaralhada por uma
    permutação fixa — `(7 i) mod 60`. Os p do teste são conferidos contra o R sobre
    estes mesmos números.
    """
    from statistics import NormalDist

    n = 60
    normal = NormalDist()
    escores = [normal.inv_cdf((i + 0.5) / n) for i in range(n)]
    ruido = [escores[(7 * i) % n] for i in range(n)]
    outro = [escores[(13 * i + 5) % n] for i in range(n)]

    idade = [round(45 + 12 * z, 1) for z in escores]
    imc: list[float | None] = [
        round(26 + 2.4 * (0.6 * z + 0.8 * r), 2) for z, r in zip(escores, ruido, strict=True)
    ]
    for posicao in (4, 31, 50):
        imc[posicao] = None
    renda = [round(2500 * 2.718281828459045 ** (0.9 * (0.5 * z + 0.87 * o)), 2)
             for z, o in zip(escores, outro, strict=True)]
    dor = [
        min(5, max(0, round(2.5 + 1.1 * z + 0.9 * r)))
        for z, r in zip(escores, ruido, strict=True)
    ]
    return pd.DataFrame(
        {
            "idade": idade,
            "imc": imc,
            "renda": renda,
            "dor": dor,
            "escolaridade": _repetir(["Fundamental", "Médio", "Superior"], n),
            "servico": [1] * n,
        }
    )


def para_comparar() -> pd.DataFrame:
    """
    Sessenta casos e uma variável para cada caminho da regra da comparação com um
    valor de referência.

    Comparada com a referência da ficha, cada coluna cai num caminho diferente:

    * `imc` — escores normais, com **três células vazias**: o Shapiro-Wilk não
      rejeita, **t de Student**, sobre 57 valores e não 60;
    * `renda` — a exponencial de escores normais, assimétrica à direita: o
      Shapiro-Wilk rejeita, a regra escolhe o **Wilcoxon**, que ainda não existe, e a
      linha sai **sem teste**;
    * `pas` — medida em doze casos só: **t com menos de 20 valores**, e o aviso;
    * `dor` — escala de 0 a 5 marcada `numerica`: seis valores distintos, o
      Shapiro-Wilk rejeita, e o **aviso de variável discreta**;
    * `servico` — `1` em todas as linhas: **um valor só**, sem teste;
    * `sexo` — código `1`/`2`, marcada `categorica`: **recusada** — a média de um
      código não é uma média.

    Nada é sorteado: os escores normais são os quantis da normal em posições
    igualmente espaçadas, e a ordem é embaralhada por uma permutação fixa — `(7 i)
    mod 60` —, como no `para_correlacionar`. Os p do teste são conferidos contra o R
    sobre estes mesmos números.
    """
    from statistics import NormalDist

    n = 60
    normal = NormalDist()
    escores = [normal.inv_cdf((i + 0.5) / n) for i in range(n)]
    embaralhados = [escores[(7 * i) % n] for i in range(n)]

    imc: list[float | None] = [round(26 + 3.2 * z, 1) for z in embaralhados]
    for posicao in (4, 31, 50):
        imc[posicao] = None
    renda = [round(2500 * 2.718281828459045 ** (0.8 * z), 2) for z in embaralhados]
    pas: list[float | None] = [None] * n
    for ordem, posicao in enumerate(range(0, n, 5)):
        pas[posicao] = float(round(128 + 14 * normal.inv_cdf((ordem + 0.5) / 12)))
    dor = [min(5, max(0, round(2.5 + 1.2 * z))) for z in embaralhados]
    return pd.DataFrame(
        {
            "imc": imc,
            "renda": renda,
            "pas": pas,
            "dor": dor,
            "servico": [1] * n,
            "sexo": _repetir([1, 2], n),
        }
    )


def para_comparar_grupos() -> pd.DataFrame:
    """
    Sessenta casos para a comparação entre grupos, com cada coluna num caminho da regra.

    `sexo` é o código `1`/`2`, alternando linha a linha, com **duas células vazias** no
    segundo grupo: 30 casos no primeiro e 28 no segundo. Entre os grupos de `sexo`:

    * `imc` — normal nos dois grupos, com a média do segundo 2,4 acima e o desvio 4
      contra 3, e **uma célula vazia** no primeiro: o Shapiro-Wilk não rejeita em
      nenhum, e a regra escolhe o **t de Welch**; com n de 29 e 28 e desvios
      diferentes, o de Student e o de Welch dão números diferentes;
    * `renda` — a exponencial de escores normais, assimétrica nos dois: o Shapiro-Wilk
      rejeita, e a regra escolhe o **Mann-Whitney**;
    * `pas` — normal nos dois, com o desvio do segundo **três vezes** o do primeiro: o
      aviso das variâncias quando o t de Student é escrito no item;

    e mais duas categóricas para os caminhos que não comparam dois grupos:
    `escolaridade`, com **três** categorias, e `unico`, com `Sim` em todas as linhas —
    **um grupo só**.

    Nada é sorteado: dentro de cada grupo, os escores são os quantis da normal em
    posições igualmente espaçadas, na ordem da permutação fixa `(7 j) mod 30`, como no
    `para_comparar`. Os números são conferidos contra o R sobre estes mesmos valores.
    """
    from statistics import NormalDist

    n = 60
    metade = n // 2
    normal = NormalDist()
    escores = [normal.inv_cdf((j + 0.5) / metade) for j in range(metade)]

    def z(i: int) -> float:
        return escores[(7 * (i // 2)) % metade]

    def segundo(i: int) -> bool:
        return i % 2 == 1

    sexo: list[float | None] = [2 if segundo(i) else 1 for i in range(n)]
    for posicao in (3, 7):
        sexo[posicao] = None
    imc: list[float | None] = [
        round((27.4 + 4.0 * z(i)) if segundo(i) else (25.0 + 3.0 * z(i)), 1) for i in range(n)
    ]
    imc[10] = None
    renda = [
        round(2.718281828459045 ** ((8.3 if segundo(i) else 8.0) + 0.8 * z(i)), 2)
        for i in range(n)
    ]
    pas = [
        float(round((125 + 15 * z(i)) if segundo(i) else (120 + 5 * z(i)))) for i in range(n)
    ]
    return pd.DataFrame(
        {
            "imc": imc,
            "renda": renda,
            "pas": pas,
            "sexo": sexo,
            "escolaridade": _repetir(["Fundamental", "Médio", "Superior"], n),
            "unico": ["Sim"] * n,
        }
    )


def minusculo(linhas: int = 3) -> pd.DataFrame:
    """
    Um banco de três linhas: abaixo do mínimo em que proporção quer dizer algo.
    """
    return completo().head(linhas).reset_index(drop=True)


# ── Arquivos no disco, com as esquisitices que só existem em bytes ──────────


def csv_do_excel_ptbr(caminho, quadro: pd.DataFrame | None = None):
    """
    `;` entre campos e cp1252 — o que sai do Excel em português.
    """
    quadro = completo() if quadro is None else quadro
    caminho.write_bytes(
        quadro.to_csv(sep=";", index=False, lineterminator="\r\n").encode("cp1252")
    )
    return caminho


def csv_do_r(caminho, quadro: pd.DataFrame | None = None):
    """
    `,` entre campos e UTF-8 — o que sai do R ou do Python.

    Chega com a mesma extensão do de cima e sem marca nenhuma que os distinga:
    ou o leitor descobre, ou metade dos arquivos abre como uma coluna só.
    """
    quadro = completo() if quadro is None else quadro
    caminho.write_bytes(quadro.to_csv(sep=",", index=False).encode("utf-8"))
    return caminho


def csv_de_uma_coluna(caminho):
    """
    Uma coluna só, com vírgula decimal nos valores.

    O defeito que a Fase 5 consertou: o cabeçalho `peso` não tem separador,
    `70,5` virava dois campos, e o `pandas` promovia a primeira metade a índice.
    O que chegava à análise era `peso` valendo 5, 2, 0 — e nada denunciava.
    """
    caminho.write_text("peso\n70,5\n82,3\n61,0\n", encoding="utf-8", newline="\n")
    return caminho


def csv_utf8_com_acento_no_corte(caminho, tamanho_amostra: int = 64 * 1024):
    """
    Um `.csv` UTF-8 grande, com um caractere de dois bytes **partido** no byte
    em que a amostra do detector de codificação termina.

    Não é uma curiosidade: é a forma de um arquivo de cliente em português,
    maior que a amostra, ser lido inteiro em cp1252 — e `São Paulo` chegar à
    tabela, ao dicionário e ao documento como `SÃ£o Paulo`.
    """
    cabecalho = b"nome;cidade\n"
    enchimento = b"A" * (tamanho_amostra - len(cabecalho) - 1)
    caminho.write_bytes(
        cabecalho
        + enchimento
        + "ção;Belo Horizonte\n".encode()
        + ("Ana;São Paulo\n" * 40).encode()
    )
    return caminho


def xlsx_com_duas_abas(caminho, quadro: pd.DataFrame | None = None):
    """
    `Dados` primeiro e `Dicionário` depois.

    A escolha da primeira aba é determinística e explicável, e o aviso sobre as
    outras é o que impede que ela passe despercebida — um `perfil.md` de 800
    linhas gerado a partir da aba errada parece normal até alguém ler o
    cabeçalho.
    """
    quadro = completo() if quadro is None else quadro
    with pd.ExcelWriter(caminho) as escritor:
        quadro.to_excel(escritor, sheet_name="Dados", index=False)
        pd.DataFrame({"campo": ["sexo"], "descrição": ["Sexo"]}).to_excel(
            escritor, sheet_name="Dicionário", index=False
        )
    return caminho


def arquivo_corrompido(caminho):
    """
    Um `.xlsx` que não é um `.xlsx` — o `.csv` renomeado do dia a dia.
    """
    caminho.write_bytes(b"nome;idade\nAna;30\n")
    return caminho
