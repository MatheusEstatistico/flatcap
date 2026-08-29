"""
Esse módulo serve para transformar professores/colaboradores e alunos em apenas `Cliente`.
Sua principal utilidade é que caso a variável `intro` receba outras categorias, só vai ser necessário acrescentar aqui e todo o resto vai funcionar. 
Todo o resto do sistema só trata `Cliente`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

PROFESSOR = 'professor'
ALUNO = 'aluno'
INDEFINIDO = 'indefinido'

CAMPO_ANEXO = 'database' # campo de anexo do questionário 

_MAPA_INTRO: dict[str, tuple[str, str, str]] = {
    "1": (PROFESSOR, "matricula1", "prof1"),
    "2": (ALUNO, "matricula2", "aluno2"),
}

_PARES = [(campo_matricula, campo_nome) for _, campo_matricula, campo_nome in _MAPA_INTRO.values()] # Os pares tentados quando `intro` não responde, na ordem.

CAMPOS_REDCAP: list[str] = [
    "record_id",
    "intro",
    "matricula1",
    "prof1",
    "matricula2",
    "aluno2",
    CAMPO_ANEXO,
]

@dataclass(frozen = True)
class Cliente:
    """
    Imutável de propósito igual no `Config`
    """
    record_id: str
    tipo: str
    matricula: str
    nome: str
    tem_anexo: str

    @property
    def identificado(self)-> bool:
        """
        Testa se da pra criar a pasta automaticamente.
        """
        return bool(self.matricula and self.nome)

def normalizar(registro: Mapping[str, Any]) -> Cliente:
    """
    Converte um registro cru do REDCap para `Cliente`

    Mostra que o registro está incompleto direto e não apenas quebra...
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
    )

def normalizar_varios(registros: Iterable[Mapping[str, Any]]) -> list[Cliente]:
    """
    Aplica a função `normalizar` à resposta toda mantendo a ordem do REDCap.
    """
    return [normalizar(registro) for registro in registros]



# Funções auxiliares

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
