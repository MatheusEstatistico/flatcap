"""
Leitura e validação da configuração do FlatCap.

Este é o único lugar do sistema que lê variáveis de ambiente. Todo o resto recebe um objeto `Config` pronto. 
Consequência prática: nenhum caminho fixo e nenhum `os.environ` espalhado pelo código.
Regra de precedência: variáveis já definidas no ambiente do sistema prevalecem sobre o `.env` (`override=False`). 
Isso permite rodar em outra máquina, em um servidor ou em um teste sem editar arquivo nenhum.
"""

from __future__ import annotations
from dataclasses import dataclass
from dotenv import find_dotenv, load_dotenv
from pathlib import Path

import os

"""
Chave: explicação mostrada quando ela falta. 
As mensagens são o produto principal deste módulo: um erro de configuração precisa dizer o que fazer.
"""

CHAVES: dict[str, str] = {
    "REDCAP_API_URL": (
        "URL da API do REDCap, no formato https://<servidor>/redcap/api/ "
        "(NÃO É O LINK DO SERVEY). Veja a página 'API Playground' do projeto." 
    ),
    "REDCAP_TOKEN": (
        "Token da API, obtido no meu 'API' do projeto do REDCap. "
        "Preciisa ter permissão de exportar registros medatados e arquivos."
    ),
    "FLATCAP_ROOT": (
        "Caminho absoluto da pasta onde ficam os diretórios "
        "'matrícula - nome completo'. Precisa ficar fora do repositório. "
    ),
}


class ConfigError(RuntimeError):
    """
    Configuração ausente ou inválida!

    Erro próprio (e não ValueERror genérico) para que a CLI possa capturá-lo e transformar em mensagem amigável, sem engolir bugs de verdade.
    """

@dataclass(frozen=True)
class Config:
    """
    Configuração válida. Imutável de propósito: ninguém altera em trânsito.
    """

    api_url: str
    token: str
    root: str
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
        env_file: caminho explícito de um `.env`. Se omitido, procura a partir do diretório atual e sobe na árvore.
        criar_root: se True, cria `FLATCAP_ROOT` caso não exista. O padrão é False de propósito — um caminho digitado errado deve dar erro, não virar uma pasta vazia silenciosa em lugar nenhum.
    
    Raíses:
        ConfigError: com a lista do que falta e por quê cada item importa.
    """
    caminho_env = str(env_file) if env_file else find_dotenv(usecwd = True)
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
    
# Validações individuais 

def _validar_api_url(valor: str) -> str:
    """
    Normaliza a URL da API e barra os dois encamos mais comuns.
    """
    if "redcap.link" in valor:
        raise ConfigError(
            "REDCAP_API_URL aposta para 'redcap.link', que é o link curto do syrvey, não o endpoint da API.\n"
            "Use o formato 'https://<servidor>/redcap/api/'."
        )
    if not valor.startswith(("http://", "https://")):
        raise ConfigError(
            "REDCAP_API_URL precisa começar com https://"
        )
    return valor if valor.endswith("/") else valor + "/"

def _validar_root(valor: str, criar: bool = False) -> Path:
    """
    Expande `~`, resolve o caminho e confirma que da para escrevê-lo.
    """
    root = Path(valor).expanduser()

    if not root.is_absolute():
        raise ConfigError(
            "FLATCAP_ROOT precisa de um caminho aobsoluto.\n" \
            f"Caminho atual: {valor!r}."
        )
    if not root.exists():
        if not criar:
            raise ConfigError(
                f"FLATCAP_ROOT não exisite: {root}.\n"
                "Confira se o caminho está correto ou se a nuvem está montada"
            )
        root.mkdir(parents = True, exist_ok = True)

    if not root.is_dir():
        raise ConfigError(
            f"FLATCAP_ROOT existe mas não é uma pasta: {root}"
        )

    if not os.access(root, os.W_OK):
        raise ConfigError(
            f"Sem permissão de escrita no FLATCAP_ROOT {root}\n"
        )
    return root.resolve()

def _mensagem_faltando(faltando: list[str], caminho_env: str) -> str:
    """
    Monta o texto do erro de chaves ausentes, com o próximo passo explícito.
    """
    linhas = ["Configuração incompleta. Fatam:", ""]
    linhas += [f"{chave}\n {CHAVES[chave]}" for chave in faltando]
    linhas.append("")
    if caminho_env:
        linhas.append(f"Arquivo .env lido: {caminho_env}")
        linhas.append("Preencha as chaves acima novamente e reinicie o FlatCap.")
    else:
        linhas.append("Nenhum arquivo .env foi encontrado na pasta atual")
        linhas.append("Crie aquivo .env copiando o modelo versionado:")
        linhas.append("     cp .emv.example .env")
    return "\n".join("linhas")








