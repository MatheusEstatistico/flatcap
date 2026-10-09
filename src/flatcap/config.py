# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Leitura e validação da configuração do FlatCap.

Este é o único lugar do sistema que lê variáveis de ambiente. Todo o resto recebe
um objeto `Config` pronto. Consequência prática: nenhum caminho fixo e nenhum
`os.environ` espalhado pelo código.
Regra de precedência: variáveis já definidas no ambiente do sistema prevalecem
sobre o `.env` (`override=False`). Isso permite rodar em outra máquina, em um
servidor ou em um teste sem editar arquivo nenhum.

## Qual `.env`

Nesta ordem, e o primeiro que existir é o lido:

1. o arquivo do `--env`, quando o comando o recebe;
2. um `.env` na pasta atual ou em alguma acima dela — é o de quem trabalha num
   clone do repositório, na raiz dele;
3. o `.env` da sua conta, na pasta de configuração do sistema
   (`pasta_de_configuracao`) — é o de quem instalou o FlatCap por um pacote, com
   o `pipx` ou o `uv`, e roda o comando de qualquer pasta.

O terceiro degrau entrou na 1.13.1, junto com a distribuição por pacote: sem ele,
o FlatCap instalado só achava a configuração quando o comando rodava de dentro da
pasta certa. `flatcap doctor --criar-env` escreve esse arquivo com as três chaves
em branco.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

"""
Chave: explicação mostrada quando ela falta.
As mensagens são o produto principal deste módulo: um erro de configuração precisa
dizer o que fazer.
"""

CHAVES: dict[str, str] = {
    "REDCAP_API_URL": (
        "URL da API do REDCap, no formato https://<servidor>/redcap/api/ "
        "(NÃO É O LINK DO SURVEY). Veja a página 'API Playground' do projeto."
    ),
    "REDCAP_TOKEN": (
        "Token da API, obtido no menu 'API' do projeto do REDCap. "
        "Precisa ter permissão de exportar registros, metadados e arquivos."
    ),
    "FLATCAP_ROOT": (
        "Caminho absoluto da pasta onde ficam os diretórios "
        "'matrícula - nome completo'. Precisa ficar fora de qualquer repositório Git: "
        "é onde moram os dados dos clientes."
    ),
}

NOME_DO_APLICATIVO = "flatcap"

# O modelo do `.env`, com as três chaves em branco. É o que o `doctor --criar-env`
# escreve, e o `.env.example` da raiz do repositório tem de ser igual a ele — o
# `test_config.py` confere. Em branco, e não com valores de exemplo: com o exemplo
# copiado sem preencher, a falta não era acusada e o `doctor` ia tentar falar com
# `https://<seu-servidor>`.
TEXTO_DO_ENV = """\
# FlatCap — a configuração. Preencha as três chaves; nenhuma tem valor padrão.
# Este arquivo guarda o token do REDCap: não o envie a ninguém e não o ponha no Git.

# A URL da API, no formato https://<servidor>/redcap/api/ — não é o link do survey.
REDCAP_API_URL=

# O token do projeto, no menu API do REDCap. Precisa exportar registros, metadados
# e arquivos: a última permissão é a que se esquece, e é a que baixa o banco.
REDCAP_TOKEN=

# A pasta onde ficam as pastas dos clientes. Caminho absoluto, fora de qualquer
# repositório Git: é onde moram os dados.
FLATCAP_ROOT=
"""


class ConfigError(RuntimeError):
    """
    Configuração ausente ou inválida!

    Erro próprio (e não ValueError genérico) para que a CLI possa capturá-lo e
    transformar em mensagem amigável, sem engolir bugs de verdade.
    """

@dataclass(frozen=True)
class Config:
    """
    Configuração válida. Imutável de propósito: ninguém altera em trânsito.
    """
    api_url: str
    token: str
    root: Path
    origem_env: str | None = None # caminho do .env efetivamente carregado

    @property
    def token_mascarado(self) -> str:
        """
        Versão segura para imprimir no terminal e em logs.
        """
        if len(self.token) <= 8:
            return "*" * len(self.token)
        return f"{self.token[:4]}{'*' * (len(self.token) - 8)}{self.token[-4:]}"

def carregar(env_file: str | Path | None = None, criar_root: bool = False) -> Config:
    """
    Lê o `.env`, valida as três chaves e devolve um `Config`.

    Args:
        env_file: caminho explícito de um `.env`. Se omitido, procura a partir do
            diretório atual e sobe na árvore; não achando, usa o `.env` da sua
            conta, se ele existir. Ver o docstring do módulo.
        criar_root: se True, cria `FLATCAP_ROOT` caso não exista. O padrão é False
            de propósito — um caminho digitado errado deve dar erro, não virar uma
            pasta vazia silenciosa em lugar nenhum.

    Raises:
        ConfigError: com a lista do que falta e por quê cada item importa.
    """
    caminho_env = _localizar_env(env_file)
    if caminho_env:
        load_dotenv(caminho_env, override = False)

    valores = {chave: (os.environ.get(chave) or "").strip() for chave in CHAVES}

    faltando = [chave for chave, valor in valores.items() if not valor]
    if faltando:
        raise ConfigError(_mensagem_faltando(faltando, caminho_env))

    api_url = _validar_api_url(valores["REDCAP_API_URL"])
    root = _validar_root(valores["FLATCAP_ROOT"], criar = criar_root)

    return Config(
        api_url = api_url,
        token = valores["REDCAP_TOKEN"],
        root = root,
        origem_env = caminho_env or None,
    )


# O `.env` da sua conta

def pasta_de_configuracao() -> Path:
    """
    A pasta de configuração da sua conta, onde mora o `.env` de quem instalou o
    FlatCap por um pacote:

        Windows   C:\\Users\\<você>\\AppData\\Roaming\\flatcap
        macOS     ~/Library/Application Support/flatcap
        Linux     ~/.config/flatcap   (ou $XDG_CONFIG_HOME/flatcap)

    Quem calcula é o `typer.get_app_dir`, a regra de cada sistema escrita uma vez —
    nenhuma dependência nova.
    """
    import typer

    return Path(typer.get_app_dir(NOME_DO_APLICATIVO))


def arquivo_env_da_conta() -> Path:
    """
    O `.env` da sua conta: o terceiro degrau da procura, e o que o
    `doctor --criar-env` escreve.
    """
    return pasta_de_configuracao() / ".env"


def criar_env_da_conta() -> Path | None:
    """
    Escreve o `.env` da sua conta com as três chaves em branco. Devolve o caminho,
    ou `None` quando ele já existe — o arquivo é seu, e nunca é sobrescrito.

    No Linux e no macOS o arquivo nasce `0o600`, legível só por você: ele guarda o
    token do REDCap, e um token é uma senha.
    """
    caminho = arquivo_env_da_conta()
    if caminho.exists():
        return None
    caminho.parent.mkdir(parents = True, exist_ok = True)
    modo = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    with open(os.open(caminho, modo, 0o600), "w", encoding = "utf-8", newline = "\n") as arquivo:
        arquivo.write(TEXTO_DO_ENV)
    return caminho


# Validações individuais

def _localizar_env(env_file: str | Path | None) -> str:
    """
    Decide qual `.env` carregar. Devolve uma string vazia quando não tem nenhum.

    Um `--env` apontado para um arquivo que não existe é barrado.
    """
    if env_file is None:
        encontrado = find_dotenv(usecwd = True)
        if encontrado:
            return encontrado
        da_conta = arquivo_env_da_conta()
        return str(da_conta) if da_conta.is_file() else ""

    caminho = Path(env_file).expanduser()
    if not caminho.exists():
        raise ConfigError(
            f"O arquivo indicado em `--env` não existe\n"
            f"Confira o caminho do arquivo. Atual: {caminho}"
        )
    return str(caminho)

def _validar_api_url(valor: str) -> str:
    """
    Normaliza a URL da API e barra os dois enganos mais comuns.
    """
    if "redcap.link" in valor:
        raise ConfigError(
            "REDCAP_API_URL aponta para 'redcap.link', é o link do survey, não o endpoint da API.\n"
            "Use o formato 'https://<servidor>/redcap/api/'."
        )
    if not valor.startswith(("http://", "https://")):
        raise ConfigError(
            "REDCAP_API_URL precisa começar com https:// ou http://"
        )
    # A barra final serve para o servidor não responder "301".
    return valor if valor.endswith("/") else valor + "/"

def _validar_root(valor: str, criar: bool = False) -> Path:
    """
    Expande `~`, resolve o caminho e confirma que dá para escrevê-lo.
    """
    root = Path(valor).expanduser()

    if not root.is_absolute():
        raise ConfigError(
            "FLATCAP_ROOT precisa de um caminho absoluto.\n"
            f"Caminho atual: {valor!r}."
        )

    if not root.exists():
        if not criar:
            raise ConfigError(
                f"FLATCAP_ROOT não existe: {root}.\n"
                "Confira se o caminho está correto ou se a nuvem está montada"
            )
        root.mkdir(parents = True, exist_ok = True)

    if not root.is_dir():
        raise ConfigError(
            f"FLATCAP_ROOT existe mas não é uma pasta: {root}"
        )

    if not os.access(root, os.W_OK):
        raise ConfigError(
            f"Sem permissão de escrita no FLATCAP_ROOT: {root}"
        )
    return root.resolve()


# Mensagens

def _mensagem_faltando(faltando: list[str], caminho_env: str) -> str:
    """
    Monta o texto do erro de chaves ausentes, com o próximo passo explícito.
    """
    linhas = ["Configuração incompleta. Faltam:", ""]
    linhas += [f"{chave}\n {CHAVES[chave]}" for chave in faltando]

    if caminho_env:
        linhas.append(f"Arquivo .env lido: {caminho_env}")
        linhas.append("Preencha as chaves acima e rode o comando de novo.")
    else:
        linhas.append(
            "Nenhum arquivo .env foi encontrado — nem na pasta atual e nas de cima, "
            f"nem o da sua conta, em {arquivo_env_da_conta()}."
        )
        linhas.append("")
        linhas.append("Para criar o da sua conta, com as três chaves em branco:")
        linhas.append("     flatcap doctor --criar-env")
        linhas.append("Num clone do repositório, ele também pode ficar na raiz:")
        linhas.append("     cp .env.example .env")
    return "\n".join(linhas)
