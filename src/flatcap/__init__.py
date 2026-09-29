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
    cruzamento.py  cruza pares de categóricas: uma tabela por par
    associacao.py  testa a associação entre pares de categóricas (qui-quadrado ou Fisher)
    correlacao.py  correlaciona pares de numéricas (Pearson, Spearman ou Kendall)
    hipoteses.py   a aritmética dos testes de comparação, como o R (sem pandas)
    comparacao.py  compara médias: contra uma referência, e entre grupos
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

## 1.4.0 — o cruzamento

**`cruzamento.py`: uma tabela por par de categóricas.** Cada combinação de
categorias, quantos casos e o percentual sobre quem respondeu as duas — o `cruz()`
que se fazia à mão. Os pares vêm da lista `cruzamento:` da ficha, e a numérica de
poucos valores entra marcada `categorica` no dicionário. Sem teste e sem gráfico.

É a terceira análise e a primeira a entrar sem que o `relatorio.py` mude uma
linha: a varredura de `3. Análises/*/` da 1.3.1 a encontra sozinha. E o campo
`colunas` do manifesto, que a 1.2.0 criou esperando um par, é o que mantém as
conferências do relatório certas para uma seção que fala de duas colunas.

**`serie_de_texto` e `percentual` ficaram públicas no `descritiva.py`.** A
categoria do cruzamento sai escrita pelas mesmas funções que escrevem a tabela de
frequência da mesma variável: `1` vira `Feminino` do mesmo jeito nas duas, e um
código que o Excel leu como `1.0` não sai `1.0` em nenhuma delas.

**O `documento.py` alinha pelo conteúdo, e não pela posição.** Texto à esquerda,
número à direita. Até aqui só a primeira coluna ia à esquerda, e a segunda coluna
do cruzamento — que também é rótulo — sairia empurrada para a direita. A coluna
`leitura` da normalidade já saía assim, e passa a sair à esquerda.

## 1.5.0 — a associação

**`associacao.py`: qui-quadrado ou exato de Fisher, escolhido pela regra de
Cochran.** Os pares vêm da lista `associacao:` da ficha, em duas formas — o par
`[sexo, desfecho]` e a variável contra várias, `desfecho: [sexo, escolaridade]` —,
e saem numa tabela só: variável 1, variável 2, n, teste, p-valor e o V de Cramér.
A justificativa de cada escolha — a menor esperada e quantas caselas ficaram
abaixo de 5 — vai para as notas do `.csv` e para o manifesto, com a tabela de
contingência inteira.

**O V de Cramér sai ao lado do p**, porque o p depende do n e o V mede o tamanho
da associação. Ele usa sempre o X² de Pearson sem correção, qualquer que seja o
teste da linha, e sai também nas linhas do Fisher.

Os dois testes são os do R. O qui-quadrado é o `chisq.test` com o padrão dele:
Yates só na 2×2, e nunca maior do que a diferença. O Fisher é o `fisher.test`:
2×2 pela hipergeométrica e as maiores **exatas**, pelo algoritmo de rede. Essa
aritmética está escrita no módulo, e não importada, porque o `scipy` calcula a
tabela maior que 2×2 por simulação, sem semente — o p mudaria a cada rodada. A
conferência é contra os exemplos da documentação do R e contra a força bruta.

É a quarta análise, e de novo o `relatorio.py` não muda uma linha. Ela entra na
`ORDEM_PADRAO_DAS_ANALISES` logo depois do cruzamento, e o `valor_p` da
normalidade ficou público: o p sai escrito do mesmo jeito nas duas tabelas.

## 1.6.0 — a correlação

**`correlacao.py`: Pearson, Spearman ou Kendall, escolhido pelos pressupostos de
cada par.** Os pares vêm da lista `correlacao:` da ficha, nas duas formas da
associação, e o par aceita um terceiro nome, que é o método: `[dor, ansiedade,
kendall]`. Sem ele, a regra escolhe — Kendall quando alguma das duas tem até 10
valores distintos, com repetição; Spearman quando alguma é categórica ou quando o
Shapiro-Wilk rejeita a normal em alguma; Pearson nos outros casos. A frase de cada
escolha vai para as notas do `.csv`, para o terminal e para o manifesto, e o
método escrito contra a regra sai com aviso.

Sai uma tabela só — variável 1, variável 2, n, método, coeficiente, IC 95% e
p-valor — e uma dispersão por par, em que o ponto cresce onde vários casos
coincidem. Os três são o `cor.test` do R, e o Spearman pede aritmética escrita
aqui: o `scipy` usa sempre a aproximação t, e o R é exato até n = 1290 sem
empates, pelo algoritmo AS 89 — transcrito do `prho.c`. O intervalo do Spearman e
o do Kendall, que o R não dá, saem pela transformação de Fisher com os
erros-padrão de Bonett e Wright.

Uma escala marcada `categorica` entra, se o código for número: pela ordem dos
códigos, e só por Spearman ou Kendall.

É a quinta análise, e o `relatorio.py` continua sem mudar uma linha. O
`graficos.py` ganhou a espécie `dispersao`, o Shapiro-Wilk da normalidade ficou
público — a tabela de normalidade e a escolha da correlação saem da mesma
chamada —, e a correlação entra na `ORDEM_PADRAO_DAS_ANALISES` logo depois da
normalidade.

## 1.7.0 — a comparação

**`comparacao.py`: a média de uma numérica contra um valor de referência — o t de
Student para uma amostra.** Os itens vêm da lista `comparacao:` da ficha, `[imc,
25]`, e um terceiro nome, `t`, força o teste. Sai uma tabela só — variável, n,
média (DP), IC 95% da média, referência, teste e p-valor —, com a frase de cada
escolha nas notas do `.csv`, no terminal e no manifesto.

**Uma análise para todos os testes de comparação**, e não um módulo por teste: o
que se escreve na reunião é a pergunta, e o teste sai do delineamento e dos
pressupostos. A regra é a da correlação: o Shapiro-Wilk sobre os valores da
variável, pela mesma função da normalidade; o t quando ele não rejeita a normal, e
o Wilcoxon quando rejeita. O Wilcoxon está na regra e ainda não no cálculo: a linha
dele sai sem teste, com o motivo, e o aviso ensina a escrever `t` no item quando o
t valer ali.

**`hipoteses.py`: a aritmética dos testes, fora da análise.** Recebe números e
devolve um `Resultado`, que é o `htest` do R. O t de uma amostra é o `t.test`, pelo
`scipy`, que aqui faz igual. A fronteira existe porque o pareado é a uma amostra
sobre as diferenças, e o motor precisa estar onde os próximos delineamentos o
alcancem.

**A vírgula decimal da ficha.** `[imc, 24,9]` é lido pelo YAML como três itens, e a
recusa reconhece o engano e escreve o número certo para copiar — com o zero à
esquerda da parte decimal, que o `24,05` perderia, e o aviso de que o sinal de
`-0,5` não sobrevive à leitura.

**`descritiva.resumo_numerico` ficou pública**, com o apelido privado: a média da
tabela da comparação é, letra por letra, a do `resumo_<variável>.csv`.

É a sexta análise, e o `relatorio.py` continua sem mudar uma linha. Ela entra na
`ORDEM_PADRAO_DAS_ANALISES` no fim, depois da correlação.

## 1.8.0 — dois grupos, e o t de Student

**A comparação entre os dois grupos de uma categórica.** `[imc, sexo]` na lista
`comparacao:`, ou `sexo: [imc, idade]` para várias de uma vez. Os grupos saem do
banco, e não do dicionário: os rótulos com resposta entre os casos que responderam
as duas variáveis, pelas mesmas `serie_de_texto` e `rotulo_de` da associação, na
ordem do dicionário — que decide o sinal da diferença. Três ou mais grupos ainda não
estão no FlatCap, e o item é recusado com a frase que diz isso.

**A regra é a mesma, grupo a grupo.** O Shapiro-Wilk em cada grupo; a normal se
sustenta quando se sustenta em todos. O paramétrico da regra é o **t de Welch** — o
padrão do `t.test` do R, que não supõe variâncias iguais e dispensa o Levene —, e
ele ainda não está no FlatCap: sem método escrito, a linha sai sem teste, e o aviso
ensina a escrever `student`. **O t de Student** roda quando está escrito no item, é o
`t.test(var.equal = TRUE)` do R pelo `scipy`, e sai com o aviso de quanto o maior
desvio padrão passa do menor quando passa de duas vezes.

**Uma tabela por delineamento, na mesma pasta.** `uma_amostra.csv`, como antes, e
`dois_grupos.csv`, com um bloco por item: a linha da comparação — n, diferença das
médias com o IC 95%, teste e p — e uma linha por grupo, com n, média e desvio. O
manifesto ganha um artefato por tabela, e o documento, as duas tabelas na mesma
seção. O `relatorio.py` não mudou.

**`associacao.na_ordem_do_dicionario` ficou pública**, com o apelido privado: os
grupos da comparação saem na mesma ordem das categorias da associação.

## 1.9.0 — o t de Welch

**O paramétrico da regra entre dois grupos passa a rodar.** `[imc, sexo]` sem método
dá o t de Welch quando o Shapiro-Wilk não rejeita a normal em nenhum dos grupos: o
`t.test(x, y)` do R, o padrão dele, pelo `scipy` — cada grupo com a sua variância, os
graus de liberdade de Welch-Satterthwaite, fracionários, e o IC 95% da diferença. As
linhas que saíam sem teste por falta dele viram linhas de Welch; as que saem sem
teste agora são as da normal rejeitada, onde a regra escolhe o Mann-Whitney.

**`t` entre grupos é o de Welch**, como o `t.test` sem argumento; `welch` também, e
`welsh` é lido como ele. O de Student continua escrito, `student`, com o aviso das
variâncias — que agora diz que o de Welch não as supõe, sem o "ainda não está".

**A barreira do R para ele**: dois valores em cada grupo, porque cada grupo entra com a
sua variância, e a de um valor só não existe — o `not enough 'x' observations`. Um
grupo que não varia não barra: o t existe, com os gl do outro grupo, e o aviso de
«perda de precisão» que o `scipy` emite nesse caso é calado, porque ali a conta está
certa.

## 1.10.0 — três grupos ou mais, e a ANOVA

**A comparação entre três grupos ou mais.** O mesmo item, `[imc, escolaridade]`: o
banco diz quantos grupos há, e com três ou mais a comparação vai para a tabela
`k_grupos.csv` — o bloco da comparação e uma linha por grupo, sem a coluna da
diferença, que com k grupos não é uma só. A recusa dos três grupos, da 1.8.0, saiu.

**A regra escolhe a ANOVA de Welch**, o padrão do `oneway.test` do R, pela razão do t
de Welch — e ela ainda não está no FlatCap: sem método escrito, a linha sai sem teste,
e o aviso ensina a escrever `anova`. **A ANOVA clássica** roda quando está escrita no
item: o `oneway.test(var.equal = TRUE)`, escrito no `hipoteses.py` — quatro linhas —
porque o `f_oneway` do `scipy` dá o F e o p do R, mas não os graus de liberdade, e eles
vão para a nota. O aviso das variâncias vale para ela como para o t de Student.

**A barreira do R é a do `oneway.test`**: dois valores em cada grupo — o `aov`
aceitaria um. E uma que o R não tem: grupos que não variam por dentro, onde ele
devolve F infinito e p zero, saem sem teste.

**O método do número errado de grupos recusa e ensina a troca**: `student` numa
variável de três grupos pede `anova`; `anova` numa de dois pede `student` — com dois
grupos, o F é o t ao quadrado. Só o banco sabe quantos grupos há, e por isso essa
recusa vem depois de abri-lo, junto das outras do mesmo tipo.

**A ANOVA diz se as médias diferem, e não quais.** O pós-teste — Tukey depois da
clássica, Games-Howell depois da de Welch — fica para depois, e a nota da tabela diz
isso.

## 1.11.0 — a ANOVA de Welch

**O paramétrico da regra entre três grupos ou mais passa a rodar.** `[imc,
escolaridade]` sem método dá a ANOVA de Welch quando o Shapiro-Wilk não rejeita a
normal em nenhum dos grupos: o `oneway.test(y ~ g)` do R, o padrão dele — cada grupo
pesado pelo inverso da variância da média, e os graus de liberdade do denominador de
Welch, fracionários. Escrita no `hipoteses.py`, como a clássica, pela mesma razão: o
`f_oneway(equal_var=False)` dá o F e o p do R, e não os gl.

**`welch` escrito é o de Welch do número de grupos que o banco trouxer**: o t com dois,
a ANOVA com três ou mais. E o `t` escrito numa variável de três grupos passa a ensinar
`welch`, que agora existe.

**A barreira que o R não tem**: um grupo que não varia. O peso dele é n/0, e o R
devolve `NaN`; aqui a linha sai sem teste, com o nome do grupo. A clássica, que usa a
variância combinada dos outros, roda sobre os mesmos dados.
"""

__version__ = "1.11.0"
