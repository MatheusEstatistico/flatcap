#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Escreve a referência do código no `docs/Doc.Flatcap.md`: todo docstring, todo
comentário `#` e toda string solta usada como comentário em `src/flatcap/`, módulo
por módulo, na ordem em que aparecem no arquivo.

O documento tem duas partes. A primeira é escrita à mão — o projeto, a instalação,
o fluxo, a arquitetura — e este script não a toca. A segunda começa no `MARCADOR` e
é reescrita inteira a cada execução: mudou um comentário, rode o script.

    python tools/gerar_doc.py             reescreve a parte gerada
    python tools/gerar_doc.py --conferir  não escreve nada; sai com 1 se a parte
                                          gerada estiver desatualizada ou se algum
                                          comentário do código não estiver no documento

Só biblioteca padrão, e sem importar o FlatCap: roda sem instalar nada.

Como cada coisa aparece:

* o docstring do módulo abre a seção dele, com os títulos internos rebaixados
  para caber debaixo do título do módulo;
* cada classe e cada função ganha um título com o nome e os parâmetros, e o
  docstring logo abaixo;
* um comentário de uma linha sozinho entre dois trechos de código do módulo é
  título de seção no código-fonte (`# Camada de rede`), e vira título aqui;
* o comentário logo acima de uma constante do módulo vai com ela, debaixo de um
  título com o nome dela;
* os outros comentários saem em citação (`>`), na ordem do arquivo, com a linha;
* o comentário no fim de uma linha de código sai numa lista, ao lado do código.
"""

from __future__ import annotations

import argparse
import ast
import inspect
import io
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PACOTE = RAIZ / "src" / "flatcap"
DOCUMENTO = RAIZ / "docs" / "Doc.Flatcap.md"

MARCADOR = (
    "<!-- Daqui para baixo, o documento é gerado por tools/gerar_doc.py a partir dos "
    "comentários de src/flatcap/. Não edite à mão: mude o comentário no código e rode "
    "o script. -->"
)

# A ordem das camadas do `__init__.py`: cada módulo só conhece os que vêm antes dele.
# Um módulo novo que não esteja aqui entra no fim, em ordem alfabética — e o
# `--conferir` não deixa ele faltar.
ORDEM = (
    "__init__",
    "config",
    "redcap",
    "modelo",
    "nomes",
    "projeto",
    "ficha",
    "dados",
    "painel",
    "banco",
    "dicionario",
    "perfil",
    "manifesto",
    "graficos",
    "descritiva",
    "normalidade",
    "cruzamento",
    "associacao",
    "correlacao",
    "hipoteses",
    "comparacao",
    "analises",
    "metodologia",
    "relatorio",
    "documento",
    "amostral",
    "amostragem",
    "cli",
    "__main__",
)

_DEFINICOES = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
_TOKENS_SEM_CODIGO = {
    tokenize.COMMENT,
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENDMARKER,
    tokenize.ENCODING,
}


# O que se extrai de um arquivo


@dataclass(frozen=True)
class Comentario:
    """Um comentário `#`: a linha, a coluna e o texto, com o `#`."""

    linha: int
    coluna: int
    texto: str
    codigo: str  # o código antes dele, na mesma linha; vazio quando ele está sozinho


@dataclass(frozen=True)
class Bloco:
    """Comentários sozinhos em linhas seguidas, na mesma coluna."""

    inicio: int
    fim: int
    coluna: int
    linhas: tuple[str, ...]  # o texto de cada linha, sem o `#`


@dataclass(frozen=True)
class StringSolta:
    """Uma string que não é docstring, usada como comentário."""

    inicio: int
    fim: int
    texto: str


def _sem_cerquilha(texto: str) -> str:
    corpo = texto[1:]
    return corpo[1:] if corpo.startswith(" ") else corpo


def comentarios(fonte: str) -> list[Comentario]:
    """Todos os comentários `#` do arquivo, pelo `tokenize` — os de dentro de strings não contam."""
    tokens = list(tokenize.generate_tokens(io.StringIO(fonte).readline))
    linhas = fonte.splitlines()
    achados: list[Comentario] = []
    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue
        linha, coluna = token.start
        antes = linhas[linha - 1][:coluna]
        achados.append(Comentario(linha, coluna, token.string, antes.strip()))
    return achados


def blocos(achados: list[Comentario]) -> list[Bloco]:
    """Junta em blocos os comentários sozinhos que estão em linhas seguidas e na mesma coluna."""
    resultado: list[Bloco] = []
    atual: list[Comentario] = []
    for comentario in (c for c in achados if not c.codigo):
        seguido = atual and comentario.linha == atual[-1].linha + 1
        if seguido and comentario.coluna == atual[0].coluna:
            atual.append(comentario)
            continue
        if atual:
            resultado.append(_bloco(atual))
        atual = [comentario]
    if atual:
        resultado.append(_bloco(atual))
    return resultado


def _bloco(comentarios_do_bloco: list[Comentario]) -> Bloco:
    return Bloco(
        inicio=comentarios_do_bloco[0].linha,
        fim=comentarios_do_bloco[-1].linha,
        coluna=comentarios_do_bloco[0].coluna,
        linhas=tuple(_sem_cerquilha(c.texto) for c in comentarios_do_bloco),
    )


def _docstring_de(no: ast.AST) -> ast.Expr | None:
    corpo = getattr(no, "body", None)
    if (
        corpo
        and isinstance(corpo[0], ast.Expr)
        and isinstance(corpo[0].value, ast.Constant)
        and isinstance(corpo[0].value.value, str)
    ):
        return corpo[0]
    return None


def strings_soltas(arvore: ast.Module) -> list[StringSolta]:
    """As strings sozinhas numa linha que não são o docstring de ninguém."""
    docstrings = {
        id(expr)
        for no in ast.walk(arvore)
        if isinstance(no, (ast.Module, *_DEFINICOES)) and (expr := _docstring_de(no)) is not None
    }
    return [
        StringSolta(no.lineno, no.end_lineno or no.lineno, inspect.cleandoc(no.value.value))
        for no in ast.walk(arvore)
        if isinstance(no, ast.Expr)
        and isinstance(no.value, ast.Constant)
        and isinstance(no.value.value, str)
        and id(no) not in docstrings
    ]


def docstrings(arvore: ast.Module) -> list[str]:
    """O docstring do módulo e os de todas as classes e funções, já limpos."""
    textos = []
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, *_DEFINICOES)):
            texto = ast.get_docstring(no, clean=True)
            if texto is not None:
                textos.append(texto)
    return textos


# Markdown


def _rebaixar_titulos(texto: str, nivel_do_conteiner: int) -> str:
    """
    Rebaixa os títulos de um docstring para caber debaixo do título de quem o tem.

    Só os títulos fora de bloco de código: uma linha `# comentário` dentro de um
    exemplo indentado é código, e não título.
    """
    linhas = texto.split("\n")
    niveis = [
        len(m.group(1))
        for linha in _fora_de_codigo(linhas)
        if (m := re.match(r"^(#{1,6})\s", linha))
    ]
    if not niveis:
        return texto
    deslocamento = nivel_do_conteiner + 1 - min(niveis)
    saida = []
    for linha, em_codigo in _marcar_codigo(linhas):
        m = None if em_codigo else re.match(r"^(#{1,6})(\s.*)$", linha)
        if m:
            nivel = min(6, max(1, len(m.group(1)) + deslocamento))
            linha = "#" * nivel + m.group(2)
        saida.append(linha)
    return "\n".join(saida)


_SECAO_DO_DOCSTRING = re.compile(
    r"^\s*(Args|Arguments|Raises|Returns|Yields|Attributes|Examples?|Notes?|Devolve)\s*:\s*$"
)


def _abrir_secoes(texto: str) -> str:
    """
    Uma linha em branco entre o `Args:` (ou `Raises:`, `Returns:`...) e as linhas
    indentadas logo abaixo dele.

    Sem ela o Markdown não abre o bloco de código — um bloco indentado não
    interrompe um parágrafo —, e os argumentos se juntam numa linha só. O texto
    não muda: só ganha a linha em branco.
    """
    linhas = texto.split("\n")
    saida = []
    for posicao, linha in enumerate(linhas):
        saida.append(linha)
        seguinte = linhas[posicao + 1] if posicao + 1 < len(linhas) else ""
        if _SECAO_DO_DOCSTRING.match(linha) and seguinte.startswith("    ") and seguinte.strip():
            saida.append("")
    return "\n".join(saida)


def _marcar_codigo(linhas: list[str]) -> list[tuple[str, bool]]:
    """Cada linha, e se ela está num bloco de código (cercado ou indentado)."""
    marcadas = []
    cercado = False
    anterior_em_branco = True
    em_indentado = False
    for linha in linhas:
        if linha.lstrip().startswith("```"):
            cercado = not cercado
            marcadas.append((linha, True))
            anterior_em_branco = False
            continue
        if cercado:
            marcadas.append((linha, True))
            continue
        indentada = linha.startswith("    ") and linha.strip() != ""
        if indentada and (anterior_em_branco or em_indentado):
            em_indentado = True
        elif linha.strip():
            em_indentado = False
        marcadas.append((linha, em_indentado and indentada))
        anterior_em_branco = linha.strip() == ""
    return marcadas


def _fora_de_codigo(linhas: list[str]) -> list[str]:
    return [linha for linha, em_codigo in _marcar_codigo(linhas) if not em_codigo]


def _escapar(texto: str) -> str:
    """
    Escapa o `<` que o Markdown leria como etiqueta HTML — `<id>` sumiria da página.

    Nada muda dentro de código, de crase ou de bloco.
    """
    saida = []
    for linha, em_codigo in _marcar_codigo(texto.split("\n")):
        if em_codigo:
            saida.append(linha)
            continue
        partes = re.split(r"(`+[^`]*`+)", linha)
        saida.append(
            "".join(
                parte if parte.startswith("`") else re.sub(r"<(?=[A-Za-z/!?])", "&lt;", parte)
                for parte in partes
            )
        )
    return "\n".join(saida)


def _citacao(linhas: list[str]) -> str:
    texto = _escapar("\n".join(linhas))
    return "\n".join(f"> {linha}".rstrip() for linha in texto.split("\n"))


def _assinatura(no: ast.AST) -> str:
    if isinstance(no, ast.ClassDef):
        bases = [ast.unparse(base) for base in no.bases]
        return f"class {no.name}" + (f"({', '.join(bases)})" if bases else "")
    argumentos = no.args
    nomes = [a.arg for a in (*argumentos.posonlyargs, *argumentos.args)]
    if argumentos.vararg:
        nomes.append("*" + argumentos.vararg.arg)
    elif argumentos.kwonlyargs:
        nomes.append("*")
    nomes += [a.arg for a in argumentos.kwonlyargs]
    if argumentos.kwarg:
        nomes.append("**" + argumentos.kwarg.arg)
    prefixo = "async def" if isinstance(no, ast.AsyncFunctionDef) else "def"
    return f"{prefixo} {no.name}({', '.join(nomes)})"


def _nome_da_instrucao(no: ast.stmt, linhas: list[str]) -> str:
    if isinstance(no, ast.Assign):
        return ", ".join(ast.unparse(alvo) for alvo in no.targets)
    if isinstance(no, (ast.AnnAssign, ast.AugAssign)):
        return ast.unparse(no.target)
    primeira = linhas[no.lineno - 1].strip()
    return primeira if len(primeira) <= 70 else primeira[:67] + "..."


# A seção de um módulo


@dataclass(frozen=True)
class _Evento:
    linha: int
    ordem: int  # desempate na mesma linha
    texto: str


def secao_do_modulo(caminho: Path) -> str:
    """O Markdown de um módulo: o docstring dele e todos os comentários, na ordem do arquivo."""
    fonte = caminho.read_text(encoding="utf-8")
    linhas = fonte.splitlines()
    arvore = ast.parse(fonte)
    todos = comentarios(fonte)
    eventos: list[_Evento] = []

    # O cabeçalho SPDX: os comentários antes do docstring do módulo.
    docstring_do_modulo = _docstring_de(arvore)
    inicio_do_codigo = docstring_do_modulo.lineno if docstring_do_modulo else len(linhas) + 1
    cabecalho = [c for c in todos if c.linha < inicio_do_codigo and not c.codigo]
    usados: set[int] = {c.linha for c in cabecalho}

    partes = [f"## `flatcap/{caminho.name}`", ""]
    if cabecalho:
        partes.append(" · ".join(f"`{_sem_cerquilha(c.texto)}`" for c in cabecalho))
        partes.append("")
    partes.append(f"*{len(linhas)} linhas.*")
    partes.append("")
    if docstring_do_modulo is not None:
        texto = _abrir_secoes(inspect.cleandoc(docstring_do_modulo.value.value))
        partes.append(_escapar(_rebaixar_titulos(texto, 2)))
        partes.append("")

    # As definições, com o nível do título pela profundidade.
    definicoes: dict[int, tuple[ast.AST, int]] = {}

    def visitar(no: ast.AST, profundidade: int) -> None:
        for filho in ast.iter_child_nodes(no):
            if isinstance(filho, _DEFINICOES):
                definicoes[id(filho)] = (filho, profundidade)
                visitar(filho, profundidade + 1)
            else:
                visitar(filho, profundidade)

    visitar(arvore, 0)

    inicio_de = {
        id(no): min([no.lineno, *(d.lineno for d in no.decorator_list)])
        for no, _ in definicoes.values()
    }

    # Blocos e strings que descrevem a instrução logo abaixo deles.
    instrucoes_do_modulo = [no for no in arvore.body if no is not docstring_do_modulo]
    instrucao_na_linha = {}
    for no in instrucoes_do_modulo:
        primeira = inicio_de.get(id(no), no.lineno)
        instrucao_na_linha[primeira] = no

    anexos: dict[int, list[str]] = {}  # primeira linha da instrução → textos anexados

    for bloco in blocos([c for c in todos if c.linha not in usados]):
        usados.update(range(bloco.inicio, bloco.fim + 1))
        linha_seguinte = bloco.fim + 1
        seguinte_e_codigo = (
            linha_seguinte <= len(linhas)
            and linhas[linha_seguinte - 1].strip() != ""
            and not linhas[linha_seguinte - 1].lstrip().startswith("#")
        )
        no_modulo = bloco.coluna == 0
        if no_modulo and not seguinte_e_codigo and _e_titulo(bloco):
            # Uma linha curta sozinha entre trechos do módulo: é título de seção no código.
            eventos.append(_Evento(bloco.inicio, 0, f"### {_escapar(bloco.linhas[0])}\n"))
            continue
        if no_modulo and seguinte_e_codigo and linha_seguinte in instrucao_na_linha:
            anexos.setdefault(linha_seguinte, []).append(
                f"*linha {bloco.inicio}*\n\n{_citacao(list(bloco.linhas))}\n"
            )
            continue
        # Um comentário do módulo entre duas definições sairia debaixo do título da
        # de cima, como se fosse dela: o rótulo diz de quem ele é.
        rotulo = f"*No módulo, linha {bloco.inicio}:*" if no_modulo else f"*linha {bloco.inicio}*"
        eventos.append(_Evento(bloco.inicio, 1, f"{rotulo}\n\n{_citacao(list(bloco.linhas))}\n"))

    for solta in strings_soltas(arvore):
        # A string solta do módulo descreve a instrução de baixo, mesmo com uma
        # linha em branco no meio — é como ela é usada no `config.py`.
        linha_seguinte = solta.fim + 1
        while linha_seguinte <= len(linhas) and not linhas[linha_seguinte - 1].strip():
            linha_seguinte += 1
        texto = f"*linha {solta.inicio}*\n\n{_citacao(solta.texto.split(chr(10)))}\n"
        no_modulo = any(no.lineno == solta.inicio for no in arvore.body)
        if no_modulo and linha_seguinte in instrucao_na_linha:
            anexos.setdefault(linha_seguinte, []).append(texto)
        else:
            eventos.append(_Evento(solta.inicio, 1, texto))

    # Os comentários no fim de uma linha de código, cada um no lugar dele.
    for comentario in todos:
        if comentario.codigo and comentario.linha not in usados:
            eventos.append(
                _Evento(
                    comentario.linha,
                    3,
                    f"- *linha {comentario.linha}* — `{comentario.codigo}` — "
                    f"{_escapar(_sem_cerquilha(comentario.texto))}\n",
                )
            )

    # As definições.
    for no, profundidade in definicoes.values():
        nivel = min(6, 3 + profundidade)
        texto = [f"{'#' * nivel} `{_assinatura(no)}`", "", f"*linha {no.lineno}*", ""]
        for anexo in anexos.pop(inicio_de[id(no)], []):
            texto.append(anexo)
        docstring = ast.get_docstring(no, clean=True)
        if docstring is not None:
            texto.append(_escapar(_rebaixar_titulos(_abrir_secoes(docstring), nivel)))
            texto.append("")
        eventos.append(_Evento(inicio_de[id(no)], 2, "\n".join(texto)))

    # As instruções do módulo que têm comentário em cima delas.
    for primeira, textos in anexos.items():
        no = instrucao_na_linha[primeira]
        cabeca = f"### `{_nome_da_instrucao(no, linhas)}`\n\n" + "\n".join(textos)
        eventos.append(_Evento(primeira, 2, cabeca))

    eventos.sort(key=lambda evento: (evento.linha, evento.ordem))
    partes += [evento.texto for evento in eventos]
    return "\n".join(partes).rstrip() + "\n"


def _e_titulo(bloco: Bloco) -> bool:
    """
    `# Camada de rede` é título; `# O .docx fica na raiz do projeto.` é nota.

    Uma linha só, curta, e sem o ponto final de uma frase.
    """
    texto = bloco.linhas[0].strip()
    return len(bloco.linhas) == 1 and 0 < len(texto) <= 70 and not texto.endswith(".")


# O documento


def modulos() -> list[Path]:
    caminhos = {caminho.stem: caminho for caminho in PACOTE.glob("*.py")}
    ordenados = [caminhos.pop(nome) for nome in ORDEM if nome in caminhos]
    return ordenados + [caminhos[nome] for nome in sorted(caminhos)]


def parte_gerada() -> str:
    indice = "\n".join(
        f"- [`flatcap/{caminho.name}`](#{_ancora(caminho.name)})" for caminho in modulos()
    )
    secoes = "\n\n".join(secao_do_modulo(caminho).rstrip() for caminho in modulos())
    return (
        f"{MARCADOR}\n\n"
        "# Parte II — O código, comentário por comentário\n\n"
        "Tudo o que o código de `src/flatcap/` diz de si mesmo: o docstring de cada módulo, "
        "de cada classe e de cada função, e cada comentário, na ordem em que aparecem no "
        "arquivo, com a linha. Os módulos vêm na ordem das camadas — cada um só conhece "
        "os de cima.\n\n"
        f"{indice}\n\n"
        f"{secoes}\n"
    )


def _ancora(nome_do_arquivo: str) -> str:
    # O GitHub monta a âncora do título `` `flatcap/config.py` ``: minúsculas, sem
    # pontuação além de `-` e `_`.
    titulo = f"flatcap/{nome_do_arquivo}".lower()
    return re.sub(r"[^a-z0-9_\- ]", "", titulo).replace(" ", "-")


def documento_atualizado(atual: str) -> str:
    """O documento com a parte gerada nova; a parte escrita à mão fica como está."""
    manual = atual.split(MARCADOR, 1)[0] if MARCADOR in atual else atual.rstrip() + "\n\n"
    return manual.rstrip() + "\n\n" + parte_gerada()


# A conferência


def _normalizar(texto: str) -> str:
    """Para comparar o texto do código com o do documento sem o que a formatação acrescenta."""
    texto = texto.replace("&lt;", "<")
    return re.sub(r"[#>*`\s]+", " ", texto).strip()


def faltando_no_documento(documento: str) -> list[str]:
    """Cada comentário, docstring e string solta do código que não está no documento."""
    alvo = _normalizar(documento)
    faltas = []
    for caminho in modulos():
        fonte = caminho.read_text(encoding="utf-8")
        arvore = ast.parse(fonte)
        textos = [(c.linha, c.texto) for c in comentarios(fonte)]
        textos += [(s.inicio, s.texto) for s in strings_soltas(arvore)]
        textos += [(0, d) for d in docstrings(arvore)]
        for linha, texto in textos:
            normalizado = _normalizar(texto)
            if normalizado and normalizado not in alvo:
                faltas.append(f"{caminho.name}:{linha}: {texto.strip()[:70]!r}")
    return faltas


def main(argumentos: list[str] | None = None) -> int:
    leitor = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    leitor.add_argument(
        "--conferir",
        action="store_true",
        help="não escreve; sai com 1 se o documento estiver desatualizado ou incompleto",
    )
    opcoes = leitor.parse_args(argumentos)

    atual = DOCUMENTO.read_text(encoding="utf-8") if DOCUMENTO.exists() else ""
    novo = documento_atualizado(atual)

    if opcoes.conferir:
        problemas = []
        if novo != atual:
            problemas.append(
                f"{DOCUMENTO.relative_to(RAIZ)} está desatualizado: "
                "rode `python tools/gerar_doc.py`."
            )
        faltas = faltando_no_documento(atual)
        if faltas:
            problemas.append(f"{len(faltas)} comentário(s) do código fora do documento:")
            problemas += [f"  {falta}" for falta in faltas[:50]]
        for problema in problemas:
            print(problema, file=sys.stderr)
        if not problemas:
            total = sum(
                len(comentarios(c.read_text(encoding="utf-8"))) for c in modulos()
            )
            print(
                f"Em dia: {len(modulos())} módulos, {total} comentários `#` "
                "e todos os docstrings."
            )
        return 1 if problemas else 0

    DOCUMENTO.parent.mkdir(parents=True, exist_ok=True)
    DOCUMENTO.write_text(novo, encoding="utf-8", newline="\n")
    faltas = faltando_no_documento(novo)
    print(f"Escrevi {DOCUMENTO.relative_to(RAIZ)} — {len(modulos())} módulos.")
    if faltas:
        print(f"Atenção: {len(faltas)} comentário(s) não aparecem no documento:", file=sys.stderr)
        for falta in faltas[:50]:
            print(f"  {falta}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
