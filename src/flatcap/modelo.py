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
    "record_id"
    "intro"
    "matricula1"
    "prof1"
    "matricula2"
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
    def indentificado(self)-> bool:
        """
        Testa se da pra criar a pasta automaticamente.
        """
        return bool(self.matricula and self.nome)

