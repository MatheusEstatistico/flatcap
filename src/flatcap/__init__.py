"""
FlatCap — O pacote e organizado em camadas finas, cada uma com uma responsabilidade:
    config.py   le e valida credenciais e caminhos (.env)
    redcap.py   conversa com a API do REDCap
    modelo.py   traduz o questionário para o domínio (Cliente)
    nomes.py    regra de nomenclatura das pastas e busca no disco

    cli.py      expoe os comandos no terminal
"""

__version__ = "0.2.0"
