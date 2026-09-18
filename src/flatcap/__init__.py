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
    normalidade.py testa a normalidade das numéricas (Shapiro-Wilk, forma, Q-Q)
    graficos.py    desenha os .png a partir das tabelas já calculadas
    manifesto.py   o formato do manifesto.json e o contrato de saída das análises
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

## 1.2.0 — a segunda análise, e o que ela cobrou

A Fase 7 acrescenta um módulo (`normalidade.py`) e um comando, e o resto da
versão é o preço de deixar de ter uma análise só. Quatro coisas mudaram de casa,
todas na mesma direção de sempre — para baixo, para o módulo que é dono da
pergunta:

**`Tabela` e `Grafico` desceram para o `manifesto.py`.** Eles são o contrato de
saída de **qualquer** análise, e moravam no módulo que importa o `pandas`. Deixá-los
lá obrigaria toda análise nova a importar a descritiva, acoplando duas análises
que não têm nada a ver uma com a outra. O `descritiva.py` reexporta os dois.

**A `SEMENTE` desceu junto**, pelo mesmo motivo que `versao_vigente` e
`formato_de_data` já tinham descido: é um valor que todo manifesto registra, e
duas sementes em dois módulos é como duas rodadas do mesmo projeto deixam de ser
reproduzíveis uma contra a outra.

**As duas recusas do dicionário ficaram públicas no `descritiva.py`**, com a
classe de erro como parâmetro. Duas regras da casa se cruzam ali: a conferência
precisa ser **uma só** (senão um comando aceita o que o outro recusou) e o painel
precisa levar o nome do comando que o usuário rodou. Passar a classe resolve as
duas sem escolher entre elas.

**O `manifesto.json` ganhou `analise` e `colunas`.** O primeiro diz de qual
análise é a rodada, sem depender do nome da pasta. O segundo diz **quais colunas
do banco** o item usou — e é ele que faz as conferências do relatório continuarem
valendo quando um item não é uma variável, como a tabela de normalidade, que fala
de todas de uma vez. O número de formato continua em `1`: os dois campos são
aditivos e não produzem interpretação errada nenhuma em quem não os conhece.

E uma que não mudou, contra a expectativa: **o `graficos.py` nunca escolheu a
pasta.** O `desenhar` sempre recebeu o caminho como parâmetro, e por isso a
normalidade escreve em `3. Análises/normalidade/` sem que uma linha dele mude. O
que ele ganhou foi a espécie `qq` e um registro de espécies no lugar do
`if/elif/else` — que, com mais de uma análise, desenhava espécie desconhecida como
gráfico de colunas em silêncio.

## 1.3.1 — o relatório passa a enxergar a segunda análise

A Fase 7 escreveu a normalidade no disco e **não** no documento. O
`preparar_relatorio` lia uma pasta de nome fixo, `3. Análises/descritiva/`, e o
`normalidade.csv` e os `qq_*.png` ficavam no disco sem que nada os apanhasse — os
dois comandos saindo com código 0, e a falta aparecendo só para quem abrisse o
`.docx` procurando. O teste t e o qui-quadrado cairiam no mesmo buraco.

São três peças, e elas se sustentam:

**O relatório varre `3. Análises/*/`.** Quem responde onde as rodadas moram é o
`projeto.pastas_das_analises`, ao lado do `pasta_da_analise` que a Fase 7 já tinha
criado para isso. Pasta com `manifesto.json` dentro é rodada; pasta sem, é pasta
sua. Nenhum nome de análise está escrito no `relatorio.py` — a próxima análise
entra no documento sem que uma linha dele mude, que era a promessa da arquitetura.

**A lista `analises:` da ficha dirige a ordem das seções.** Ela é prometida desde
a Fase 2 — *"o que foi combinado na reunião"* — e até aqui não era lida por
ninguém. O que não estiver nela sai na `ORDEM_PADRAO_DAS_ANALISES` do
`manifesto.py`, e nome escrito na ficha sem rodada no disco vira aviso no
terminal, porque quase sempre é a análise que você combinou e ainda não rodou.

**A conferência do dicionário pergunta por `colunas_usadas`.** O campo
`ItemDoManifesto.colunas` existia desde a Fase 7 e nada o lia. Comparar por
`item.variavel` funcionava enquanto todo item era uma variável; com a tabela de
normalidade, que fala de doze de uma vez e sai com `variavel=""`, todo relatório
passaria a dizer «`` saiu da descritiva depois da rodada».

O `Relatorio` ganhou `rodadas`, e `manifesto` passou a ser o **principal** — o da
descritiva quando ela existe. As propriedades do `.docx` e o cabeçalho do terminal
precisam de um banco e de uma data, e com mais de uma rodada isso deixou de ser
automático.
"""

__version__ = "1.3.1"
