"""
FlatCap — o pacote é organizado em camadas finas, cada uma com uma responsabilidade:

    config.py   lê e valida credenciais e caminhos (.env)
    redcap.py   conversa com a API do REDCap
    modelo.py   traduz o questionário para o domínio (Cliente)
    nomes.py    regra de nomenclatura das pastas e busca no disco
    projeto.py  monta a pasta do projeto: decide um Plano e depois o escreve
    ficha.py    lê e escreve o projeto.yaml; encontra o projeto a partir de um id
    dados.py    versiona os bancos: adiciona, roda a anterior, confere o disco
    
    cli.py      expõe os comandos no terminal

A dependência anda sempre para cima nessa lista: `dados` conhece `ficha`, `ficha` conhece `projeto`, 
e nenhuma delas conhece a `cli`. 

É o que permite testar tudo sem simular terminal — e trocar a implementação de `ficha.py` 
(ruamel.yaml ou PyYAML) sem que nenhum outro módulo perceba.

"""

__version__ = "0.4.0"