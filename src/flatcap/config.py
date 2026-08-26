"""
Anotações...

"""

from __future__ import annotations
from dataclasses import dataclass
from dotenv import find_dotenv, load_dotenv
from pathlib import Path

import os

"""
Chaves: 

"""

CHAVES: dict[str, srt] = {
    "REDCAP_API_URL": (
        "URL da API do REDCap, no formato https://<servidor>/redcap/api/ "
        "(NÃO É O LINK DO SERVEY). Veja a página 'API Playground' do projeto." 
    ),
    "REDCAP_TOKEN": (

    ),
    "FLATCAP_ROOT": (
        
    ),
}