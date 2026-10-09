# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Construção das funções sobre regras de nomenclatura das pastas dos `Clientes` e
dos seus projetos, e como reencontrá-las no disco.

São dois níveis, e a separação é a mudança da versão 1.1.0:

    FLATCAP_ROOT/
    └── 00742 - José Antônio de Sá/      a pasta do CLIENTE — `nome_pasta`
        ├── Projeto 006/                 a pasta do PROJETO — `nome_do_projeto`
        └── Projeto 041/                 o mesmo cliente, outra solicitação

Até a 1.0.0 as duas eram a mesma pasta, porque a premissa era um projeto por
cliente. Ela não se sustenta: o mesmo professor volta ao REDCap com um estudo
novo, e o formulário gera um `record_id` novo para a mesma matrícula. A
matrícula continua identificando **a pessoa** e passa a não identificar mais
**o trabalho** — quem faz isso agora é o `record_id`, que é único por
solicitação.

Daí as duas regras deste módulo:

**A pasta do cliente é procurada pela matrícula**, e por prefixo, porque ela
pode ter sido criada à mão, renomeada, ou ter a grafia do nome corrigida
depois. A matrícula é a parte que não muda.

**A pasta do projeto é nomeada pelo `record_id`**, com zero à esquerda até três
dígitos. O zero não é enfeite: o Explorer e o Finder ordenam nome de pasta como
texto, e sem ele `Projeto 10` aparece antes de `Projeto 6`. Acima de 999 o
número cresce sozinho — `Projeto 1234` —, e aí a ordenação volta a depender do
acaso; é o preço de não truncar um identificador, que seria pior.
"""

from __future__ import annotations

import re
from pathlib import Path

PROIBIDOS = r'/\:*?"<>|' # caracteres proibidos para fazer nome de pasta no windows

_TRADUCAO = str.maketrans({caractere: None for caractere in PROIBIDOS})

_CONTROLE = re.compile(r"[\x00-\x08\x0e-\x1f\x7f]") # caracteres de controle

_ESPACOS = re.compile(r"\s+") # espaços escritos em "formato de sistema"

SEPARADOR = " - " # separador do número de matrícula e do nome completo

PREFIXO_PROJETO = "Projeto " # o que abre o nome da pasta de um projeto

LARGURA_DO_NUMERO = 3 # zeros à esquerda: 6 -> 006. Acima de 999 o número cresce

SEPARADOR_ROTULO = " · " # entre o cliente e o projeto, no que vai para a tela


class NomeInvalidoError(ValueError):
    """
    Não sobrou caractere para nomear a pasta.
    """

def sanitizar(texto: str) -> str:
    """
    Limpar o texto antes de criar o nome da pasta. Ajusta:
    1. remove caracteres de controle;
    2. remove caracteres proibidos (windows);
    3. corrige espaços em excesso;
    4. tira os espaços das duas pontas e os pontos do final — que o Windows
       apagaria em silêncio, e a pasta deixaria de ter o nome que o FlatCap procura.

    """
    limpo = _CONTROLE.sub("", texto or "")
    limpo = limpo.translate(_TRADUCAO)
    limpo = _ESPACOS.sub(" ", limpo).strip()
    return limpo.rstrip(" .")

def nome_pasta(matricula: str, nome: str) -> str:
    """
    Monta o nome da pasta do cliente: `123456789 - Matheus Fernandes`

    Raises:
        NomeInvalidoError: erro para quando não tem número de matrícula válido.
    """
    matricula_limpa = sanitizar(matricula)
    nome_limpo = sanitizar(nome)

    if not matricula_limpa:
        raise NomeInvalidoError(
            f"Matrícula vazia. Recebido: {matricula!r}\n"
            "Confira o cadastro no REDCap."
        )
    if not nome_limpo:
        """
        Nome vazio não impede o trabalho, apenas a matrícula é indispensável.
        """
        return matricula_limpa

    return f"{matricula_limpa}{SEPARADOR}{nome_limpo}"


def nome_do_projeto(record_id: str) -> str:
    """
    Monta o nome da pasta do projeto: `6` vira `Projeto 006`.

    O zero à esquerda existe para a ordenação alfabética do Explorer bater com a
    numérica: sem ele, `Projeto 10` vem antes de `Projeto 6` na tela, e a pasta
    de um cliente com quatro trabalhos deixa de ser lida de cima para baixo.

    `int()` antes de formatar torna a função idempotente: tanto `"6"` quanto
    `"006"` produzem `Projeto 006`, o que é o que permite reencontrar a pasta
    quando você digita o número como ele aparece no nome dela em vez de como ele
    aparece no `flatcap listar`.

    `record_id` que não é número — nenhum REDCap comum gera um, mas o campo é
    texto e o FlatCap nunca assumiu o contrário — passa pela mesma `sanitizar`
    das pastas e entra como está.

    Raises:
        NomeInvalidoError: `record_id` vazio, ou sem nada depois da limpeza.
    """
    limpo = sanitizar(str(record_id))
    if not limpo:
        raise NomeInvalidoError(
            f"record_id vazio. Recebido: {record_id!r}\n"
            "A pasta do projeto é nomeada pelo record_id — sem ele não há nome."
        )
    if limpo.isdigit():
        return f"{PREFIXO_PROJETO}{int(limpo):0{LARGURA_DO_NUMERO}d}"
    return f"{PREFIXO_PROJETO}{limpo}"


def e_pasta_de_projeto(nome_da_pasta: str) -> bool:
    """
    Este nome de pasta foi escrito pelo `nome_do_projeto`?

    Serve para separar as subpastas de projeto das outras coisas que moram na
    pasta do cliente — um `template.docx`, uma pasta de anotações suas. Exige
    algo depois do prefixo: uma pasta chamada exatamente `Projeto` não é um.
    """
    return nome_da_pasta.startswith(PREFIXO_PROJETO) and bool(
        nome_da_pasta[len(PREFIXO_PROJETO):].strip()
    )


def localizar_pasta(root: Path, matricula: str) -> Path | None:
    """
    Procura a pasta do CLIENTE dentro do `FLATCAP_ROOT`.

    Busca por prefixo para garantir que não perca quando a pasta foi criada ou
    renomeada à mão. Continua devolvendo a pasta do cliente, e não a do projeto:
    quem desce o segundo nível é `caminho_do_projeto` (por nome) ou
    `ficha.localizar_projeto` (lendo as fichas).
    """
    matricula_limpa = sanitizar(matricula)
    if not matricula_limpa or not Path(root).is_dir():
        return None

    for item in sorted(Path(root).iterdir()):
        if not item.is_dir():
            continue
        if _combina(item.name, matricula_limpa):
            return item
    return None

def _combina(nome_da_pasta: str, matricula: str) -> bool:
    """
    Função que diz o resultado da busca pela pasta usando a matrícula.
    Busca só a matrícula, então aceita vários formatos de nomes, para garantir que
    não quebre com pastas feitas a mão ou com mudanças de configurações em server.
    """
    if not nome_da_pasta.startswith(matricula):
        return False
    resto = nome_da_pasta[len(matricula): ]
    return not resto or not resto[0].isdigit()


def projetos_do_cliente(pasta_do_cliente: Path) -> tuple[Path, ...]:
    """
    As pastas `Projeto *` que existem dentro da pasta de um cliente, em ordem.

    Só pelo nome — não abre `projeto.yaml` nenhum. É o que o `flatcap listar`
    usa, e ele roda várias vezes por dia sobre o root inteiro: ler uma ficha por
    projeto para desenhar uma coluna da tabela seria pagar caro por uma pergunta
    que o nome da pasta já responde.
    """
    pasta = Path(pasta_do_cliente)
    if not pasta.is_dir():
        return ()
    return tuple(
        sorted(
            item for item in pasta.iterdir()
            if item.is_dir() and e_pasta_de_projeto(item.name)
        )
    )


def caminho_do_projeto(root: Path, matricula: str, record_id: str) -> Path | None:
    """
    A pasta deste projeto deste cliente, se ela já estiver no disco.

    Só pelo nome, como `projetos_do_cliente` e pelo mesmo motivo. Devolve `None`
    quando o cliente não tem pasta, ou tem e ainda não tem **este** projeto — e
    essa distinção é justamente a que o `listar` precisava passar a fazer: até a
    1.0.0 ele respondia "este cliente já tem pasta", e com mais de um projeto por
    cliente essa resposta faria a segunda solicitação parecer já atendida.
    """
    pasta_do_cliente = localizar_pasta(root, matricula)
    if pasta_do_cliente is None:
        return None
    try:
        nome = nome_do_projeto(record_id)
    except NomeInvalidoError:
        return None
    candidato = pasta_do_cliente / nome
    return candidato if candidato.is_dir() else None


def localizar_projeto_por_record(root: Path, record_id: str) -> Path | None:
    """
    Procura `Projeto NNN` em **todas** as pastas de cliente do root.

    Existe para uma situação só, e ela acontece: a matrícula foi corrigida no
    REDCap depois de a pasta ter sido criada. O `localizar_pasta` não encontra
    mais o cliente pela matrícula nova, o `novo` acharia que é um cliente
    inédito, e o mesmo `record_id` ganharia uma segunda pasta em outro lugar —
    duas pastas para o mesmo trabalho, cada uma com metade da história.

    Pelo nome, e não lendo fichas, porque este módulo é o de baixo: `ficha.py`
    importa daqui, então importar `ficha.py` aqui fecharia um ciclo. A busca por
    nome é suficiente para o que ela precisa impedir.
    """
    caminho = Path(root)
    if not caminho.is_dir():
        return None
    try:
        alvo = nome_do_projeto(record_id)
    except NomeInvalidoError:
        return None

    for pasta_do_cliente in sorted(p for p in caminho.iterdir() if p.is_dir()):
        candidato = pasta_do_cliente / alvo
        if candidato.is_dir():
            return candidato
    return None


def rotulo_do_projeto(raiz: Path) -> str:
    """
    Como um projeto se chama na tela e nos documentos:
    `00742 - José Antônio de Sá · Projeto 006`.

    Só o nome da pasta não serve mais. Ele era `00742 - José Antônio de Sá` e
    passou a ser `Projeto 006`, que não identifica ninguém — e é esse texto que
    encabeça o `perfil.md` impresso que vai para a reunião.

    Pasta fora da convenção (uma raiz de teste, uma pasta que você montou à mão)
    sai com o próprio nome, sem inventar um cliente que não existe.
    """
    raiz = Path(raiz)
    if e_pasta_de_projeto(raiz.name) and raiz.parent.name:
        return f"{raiz.parent.name}{SEPARADOR_ROTULO}{raiz.name}"
    return raiz.name
