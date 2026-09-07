"""
FlatCap — o pacote é organizado em camadas finas, cada uma com uma responsabilidade:

    config.py      lê e valida credenciais e caminhos (.env)
    redcap.py      conversa com a API do REDCap
    modelo.py      traduz o questionário para o domínio (Cliente)
    nomes.py       regra de nomenclatura das pastas e busca no disco
    projeto.py     monta a pasta do projeto: decide um Plano e depois o escreve
    ficha.py       lê e escreve o projeto.yaml; encontra o projeto a partir de um id
    dados.py       versiona os bancos: adiciona, roda a anterior, confere o disco
    banco.py       abre a versão vigente do banco como um quadro do pandas
    dicionario.py  lê, funde e escreve o dicionario.csv
    perfil.py      diagnostica o banco e escreve o perfil.md

    cli.py         expõe os comandos no terminal

A dependência anda sempre para cima nessa lista: `dados` conhece `ficha`, `ficha` conhece
`projeto`, `perfil` conhece `banco` e `dicionario`, e nenhuma delas conhece a `cli`.

É o que permite testar tudo sem simular terminal — e trocar a implementação de `ficha.py` sem
que nenhum outro módulo perceba.

Duas divisões da Fase 4 valem ser lidas juntas: `banco.py` é o único módulo que abre o arquivo
do cliente, para que as Fases 5 e 6 não voltem a decidir qual arquivo é o banco; e
`dicionario.py` não importa o `pandas`, porque o formato do arquivo que guarda as decisões da
reunião não depende de como o banco foi lido.
"""

__version__ = "0.5.0"