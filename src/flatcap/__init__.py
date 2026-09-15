"""
FlatCap — o pacote é organizado em camadas finas, cada uma com uma responsabilidade:

    config.py      lê e valida credenciais e caminhos (.env)
    redcap.py      conversa com a API do REDCap
    modelo.py      traduz o questionário para o domínio (Cliente)
    nomes.py       regra de nomenclatura das pastas (cliente e projeto) e busca no disco
    projeto.py     monta a pasta do projeto: decide um Plano e depois o escreve
    ficha.py       lê e escreve o projeto.yaml; encontra o projeto a partir de um id
    dados.py       versiona os bancos: adiciona, roda a anterior, confere o disco
    banco.py       abre a versão vigente do banco como um quadro do pandas
    dicionario.py  lê, funde e escreve o dicionario.csv
    perfil.py      diagnostica o banco e escreve o perfil.md
    descritiva.py  obedece ao dicionário: conta, resume e monta as tabelas
    graficos.py    desenha os .png a partir das tabelas já calculadas
    manifesto.py   escreve e lê o manifesto.json da descritiva
    relatorio.py   lê o manifesto e monta o conteúdo do documento
    documento.py   escreve o .docx a partir do conteúdo já montado

    cli.py         expõe os comandos no terminal

A dependência anda sempre para cima nessa lista: `dados` conhece `ficha`, `ficha` conhece
`projeto`, `perfil` conhece `banco` e `dicionario`, `descritiva` conhece `banco`, `dicionario`
e `manifesto`, `relatorio` conhece `manifesto`, `dicionario`, `dados` e `ficha`, e nenhuma
delas conhece a `cli`.

É o que permite testar tudo sem simular terminal — e trocar a implementação de `ficha.py` sem
que nenhum outro módulo perceba.

Duas divisões da Fase 4 valem ser lidas juntas: `banco.py` é o único módulo que abre o arquivo
do cliente, para que as Fases 5 e 6 não voltem a decidir qual arquivo é o banco; e
`dicionario.py` não importa o `pandas`, porque o formato do arquivo que guarda as decisões da
reunião não depende de como o banco foi lido.

A Fase 5 repete a divisão em outro eixo: `descritiva.py` calcula e não desenha, `graficos.py`
desenha e não calcula, e `manifesto.py` não importa nem o `pandas` nem o `matplotlib` — é o
índice que a Fase 6 lê para montar o `.docx` sem reabrir o banco.

A Fase 6 repete a divisão pela terceira vez, e cobra a promessa da segunda: `relatorio.py`
monta o conteúdo e não formata, `documento.py` formata e não decide, e **nenhum dos dois abre
o banco**. Um número que aparece no `.docx` é, letra por letra, o número que está no `.csv`
que a Fase 5 escreveu — não há uma segunda fonte para o mesmo 37%. Foi por isso que
`versao_vigente` desceu para `ficha.py` e `PASTA_DESCRITIVA` para `projeto.py`: as duas
perguntas moravam em módulos que carregam o `pandas`, e nenhuma das duas precisa dele.

## 1.1.0 — um cliente, vários projetos

A pasta do cliente deixou de ser a pasta do projeto:

    FLATCAP_ROOT/00742 - José Antônio de Sá/Projeto 006/projeto.yaml

O mesmo professor volta ao REDCap com um estudo novo e recebe um `record_id`
novo para a mesma matrícula. Antes, a segunda solicitação batia em "já existe
pasta para essa matrícula" e não tinha para onde ir.

A consequência que atravessa o pacote é de **identidade**: a matrícula
identifica a pessoa e parou de identificar o trabalho. Quem identifica o
trabalho é o `record_id`. Onde os dois eram intercambiáveis — a busca do
`ficha.localizar_projeto`, a coluna "Pasta local" do `listar`, a recusa de
duplicata do `novo` — agora há uma ordem: `record_id` primeiro, matrícula
depois e só quando ela não for ambígua.

`nomes.py` ganhou o segundo nível (`nome_do_projeto`, `projetos_do_cliente`,
`caminho_do_projeto`, `rotulo_do_projeto`) e continua sendo o único módulo que
sabe como uma pasta se chama. Pasta no formato antigo é reconhecida e
diagnosticada, nos dois módulos que esbarram nela, com um texto só
(`projeto.texto_da_migracao`) — a migração é manual, e de propósito: mover
pasta do usuário é coisa que o FlatCap nunca fez sozinho.
"""

__version__ = "1.1.0"
