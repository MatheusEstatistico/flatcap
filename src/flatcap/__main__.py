# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Permite rodar `python -m flatcap` sem depender do executável instalado.

Útil quando o .venv não está ativado ou quando algo deu errado com o entry point
declarado no pyproject.toml.
"""

from flatcap.cli import app

if __name__ == "__main__":
    app()
