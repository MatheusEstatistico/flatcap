"""
Esse módulo serve para transformar professores/colaboradores e alunos em apenas `Cliente`.
Sua principal utilidade é que caso a variável `intro` receba outras categorias, só vai ser
necessário acrescentar aqui e todo o resto vai funcionar.
Todo o resto do sistema só trata `Cliente`.

Além da identificação, o `Cliente` carrega dois campos que o cliente escreve no
formulário e que saem impressos na primeira página do relatório: a **finalidade**
(`fin`) e os **objetivos** (`obj1`). Eles entram aqui, e não direto no
`relatorio.py`, por uma razão de arquitetura: o relatório não fala com o REDCap.
O caminho é sempre o mesmo — o `flatcap novo` traz do formulário, o
`projeto.yaml` guarda, e o relatório lê a ficha.

Uma armadilha do formulário atual, que vale ler antes de mexer aqui: `fin` é um
campo `radio`, então o que chega da API é um **código** (`"1"`, `"2"`…), nunca o
texto. O rótulo vem do `content=metadata` e é resolvido em `mapa_de_rotulos`.
E a opção "Outros" tem a resposta de verdade em outro campo, o `outros1` —
por isso são três campos do REDCap para um campo da ficha.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

PROFESSOR = 'professor'
ALUNO = 'aluno'
INDEFINIDO = 'indefinido'

CAMPO_ANEXO = 'database'              # campo de anexo do questionário
CAMPO_FINALIDADE = 'fin'              # radio: para que o cliente quer a análise
CAMPO_FINALIDADE_OUTROS = 'outros1'   # text: o que ele escreveu ao marcar "Outros"
CAMPO_OBJETIVOS = 'obj1'              # notes: objetivo geral e específicos

_MAPA_INTRO: dict[str, tuple[str, str, str]] = {
    "1": (PROFESSOR, "matricula1", "prof1"),
    "2": (ALUNO, "matricula2", "aluno2"),
}

# Os pares tentados quando `intro` não responde, na ordem.
_PARES = [
    (campo_matricula, campo_nome)
    for _, campo_matricula, campo_nome in _MAPA_INTRO.values()
]

CAMPOS_REDCAP: list[str] = [
    "record_id",
    "intro",
    "matricula1",
    "prof1",
    "matricula2",
    "aluno2",
    CAMPO_FINALIDADE,
    CAMPO_FINALIDADE_OUTROS,
    CAMPO_OBJETIVOS,
    CAMPO_ANEXO,
]

# Como o REDCap escreve as opções de um `radio` ou `checkbox` no `content=metadata`:
#     "1, Artigo científico | 2, Projeto de iniciação científica | 4, Outros: {outros1}"
# O separador de opções é `|`, e o código vai até a **primeira** vírgula — o
# rótulo pode ter vírgulas dentro e frequentemente tem.
_SEPARADOR_OPCOES = "|"

# `{outros1}` é *piping*: o REDCap mostra ali o que foi digitado no outro campo.
# No texto do relatório ele não serve para nada, então sai — junto com os dois
# pontos que sobrariam pendurados em "Outros: ".
_PIPING = re.compile(r"\s*\{[^}]*\}")

_ESPACOS = re.compile(r"[ \t]+")
_LINHAS_VAZIAS = re.compile(r"\n{3,}")


@dataclass(frozen = True)
class Cliente:
    """
    Imutável de propósito igual no `Config`

    `finalidade` e `objetivos` têm default vazio porque nem todo caminho até aqui
    tem como preenchê-los: o `flatcap listar` normaliza centenas de registros sem
    pedir os metadados do projeto, e não precisa deles para montar a tabela.
    Campo vazio não é erro — é o que o relatório denuncia com o alerta
    `texto_ausente`, em vez de imprimir um código ou um marcador de banco de dados.
    """
    record_id: str
    tipo: str
    matricula: str
    nome: str
    tem_anexo: bool
    finalidade: str = ""
    objetivos: str = ""

    @property
    def identificado(self)-> bool:
        """
        Testa se da pra criar a pasta automaticamente.
        """
        return bool(self.matricula and self.nome)

def normalizar(
    registro: Mapping[str, Any],
    rotulos: Mapping[str, Mapping[str, str]] | None = None,
) -> Cliente:
    """
    Converte um registro cru do REDCap para `Cliente`

    Mostra que o registro está incompleto direto e não apenas quebra...

    Args:
        rotulos: o mapa `campo → {código: rótulo}` do `mapa_de_rotulos`. Sem ele,
            `finalidade` sai vazia em vez de sair com o código cru: `"2"` na
            primeira página de um relatório é pior do que um campo em branco, que
            pelo menos dispara o alerta.
    """
    intro = _texto(registro, "intro")
    tipo, campo_matricula, campo_nome = _MAPA_INTRO.get(intro, (INDEFINIDO, "", ""))

    if tipo == INDEFINIDO:
        matricula, nome = _primeiro_par_preenchido(registro)
    else:
        matricula = _texto(registro, campo_matricula)
        nome = _texto(registro, campo_nome)

    return Cliente(
        record_id = _texto(registro, "record_id"),
        tipo = tipo,
        matricula = matricula,
        nome = nome,
        tem_anexo = bool(_texto(registro, CAMPO_ANEXO)),
        finalidade = _finalidade(registro, rotulos),
        objetivos = _texto_longo(registro, CAMPO_OBJETIVOS),
    )

def normalizar_varios(
    registros: Iterable[Mapping[str, Any]],
    rotulos: Mapping[str, Mapping[str, str]] | None = None,
) -> list[Cliente]:
    """
    Aplica a função `normalizar` à resposta toda mantendo a ordem do REDCap.
    """
    return [normalizar(registro, rotulos) for registro in registros]

def mapa_de_rotulos(
    metadados: Iterable[Mapping[str, Any]],
    campos: Sequence[str] | None = None,
) -> dict[str, dict[str, str]]:
    """
    Traduz o `content=metadata` do REDCap em `campo → {código: rótulo}`.

    Função pura: recebe a resposta já baixada e não fala com a rede. Quem baixa é
    o `projeto.py`, que é a camada que compõe — este módulo continua sendo só
    "questionário → Cliente".

    Ler o rótulo do servidor, e não de um dicionário escrito no código, é o que
    evita o defeito silencioso: no dia em que alguém acrescentar uma quinta opção
    ao `fin` no REDCap, um mapa fixo devolveria vazio sem avisar ninguém.

    Args:
        campos: quais campos interessam. Sem isso, todos os que tiverem opções.
    """
    desejados = set(campos) if campos else None
    mapa: dict[str, dict[str, str]] = {}

    for linha in metadados:
        nome = _texto(linha, "field_name")
        if not nome or (desejados is not None and nome not in desejados):
            continue
        opcoes = _opcoes(_texto(linha, "select_choices_or_calculations"))
        if opcoes:
            mapa[nome] = opcoes

    return mapa

def mais_recentes(clientes: Sequence[Cliente], quantos: int) -> list[Cliente]:
    """

    """
    if quantos <= 0 or quantos >= len(clientes):
        return list(clientes)

    posicoes = sorted(
        range(len(clientes)),
        key = lambda i: _chave_recencia(i, clientes[i]),
        reverse = True,
    )
    escolhidas = set(posicoes[: quantos])
    return [cliente for i, cliente in enumerate(clientes) if i in escolhidas]


# Funções auxiliares

def _chave_recencia(indice: int, cliente: Cliente) -> tuple[int, int, int]:
    """
    Ordena o `record_id`.
    """
    texto = (cliente.record_id or "").strip()
    if texto.isdigit():
        return (1, int(texto), indice)
    return (0, 0, indice)

def _texto(registro: Mapping[str, Any], chave: str) -> str:
    """
    Lê um campo como texto limpo, tolerando ausência, None e espaços de sobra.
    """
    if not chave:
        return ""
    valor = registro.get(chave)
    if valor is None:
        return ""
    return str(valor).strip()

def _texto_longo(registro: Mapping[str, Any], chave: str) -> str:
    """
    Lê um campo `notes` preservando os parágrafos que o cliente escreveu.

    Três limpezas, e cada uma tem um motivo concreto:

    * **CRLF vira LF.** O REDCap devolve quebra de linha do Windows, e um `\\r`
      sobrevivente faz o PyYAML desistir do bloco literal e gravar os objetivos
      como uma string entre aspas com `\\n` no meio — YAML válido e ilegível num
      arquivo que existe para ser aberto no editor.
    * **Espaço no fim da linha some.** Pelo mesmo motivo: linha terminada em
      espaço também derruba o bloco literal.
    * **Três linhas em branco viram uma.** O cliente aperta Enter várias vezes;
      cada uma viraria um parágrafo vazio no documento.
    """
    bruto = _texto(registro, chave)
    if not bruto:
        return ""
    texto = bruto.replace("\r\n", "\n").replace("\r", "\n")
    linhas = [_ESPACOS.sub(" ", linha).rstrip() for linha in texto.split("\n")]
    return _LINHAS_VAZIAS.sub("\n\n", "\n".join(linhas)).strip()

def _finalidade(
    registro: Mapping[str, Any],
    rotulos: Mapping[str, Mapping[str, str]] | None,
) -> str:
    """
    Resolve o `fin` para o texto que vai impresso no documento.

    O campo é `radio`: chega `"3"`, e `"3"` não se imprime em relatório. A ordem
    de preferência é:

    1. o que o cliente **escreveu** em `outros1`, quando a opção marcada é a de
       "Outros" — é a resposta de verdade, e o rótulo seria só a palavra "Outros";
    2. o rótulo da opção, vindo dos metadados;
    3. nada.

    O `outros1` só é usado quando a opção é a de "Outros" (ou quando o código não
    tem rótulo nenhum): o REDCap **guarda** o que foi digitado mesmo depois de a
    ramificação esconder o campo, então um `outros1` de uma resposta anterior
    apareceria no lugar da finalidade escolhida.
    """
    codigo = _texto(registro, CAMPO_FINALIDADE)
    if not codigo:
        return ""

    rotulo = (rotulos or {}).get(CAMPO_FINALIDADE, {}).get(codigo, "")
    escrito = _texto(registro, CAMPO_FINALIDADE_OUTROS)

    if escrito and (not rotulo or _e_outros(rotulo)):
        return escrito
    return rotulo

def _e_outros(rotulo: str) -> bool:
    return "outro" in rotulo.casefold()

def _opcoes(bruto: str) -> dict[str, str]:
    """
    `"1, Artigo | 4, Outros: {outros1}"` → `{"1": "Artigo", "4": "Outros"}`.

    A divisão do código é na **primeira** vírgula, e só nela: rótulo com vírgula
    dentro é comum ("Artigo científico, revisão ou capítulo") e partir em todas
    devolveria um rótulo cortado no meio.
    """
    opcoes: dict[str, str] = {}
    for parte in bruto.split(_SEPARADOR_OPCOES):
        codigo, separador, rotulo = parte.partition(",")
        if not separador:
            continue
        codigo = codigo.strip()
        rotulo = _PIPING.sub("", rotulo).strip().rstrip(":").strip()
        if codigo and rotulo:
            opcoes[codigo] = rotulo
    return opcoes

def _primeiro_par_preenchido(registro: Mapping[str, Any]) -> tuple[str, str]:
    """
    Procura nos campos de nome e matricula mesmo quando o `intro` estiver em branco.
    """
    for campo_matricula, campo_nome in _PARES:
        if matricula := _texto(registro, campo_matricula):
            return matricula, _texto(registro, campo_nome)

    for _, campo_nome in _PARES:
        if nome := _texto(registro, campo_nome):
            return "", nome
    return "", ""
