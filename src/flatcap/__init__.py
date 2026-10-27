# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
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
    manifesto.py   o formato do manifesto.json e o contrato de saída das análises
    graficos.py    desenha os .png a partir das tabelas já calculadas
    descritiva.py  obedece ao dicionário: conta, resume e monta as tabelas
    normalidade.py testa a normalidade das numéricas (Shapiro-Wilk, forma, Q-Q)
    cruzamento.py  cruza pares de categóricas: uma tabela por par
    associacao.py  testa a associação entre pares de categóricas (qui-quadrado ou Fisher)
    correlacao.py  correlaciona pares de numéricas (Pearson, Spearman ou Kendall)
    hipoteses.py   a aritmética dos testes de comparação, como o R (sem pandas)
    comparacao.py  compara contra uma referência, entre grupos e entre medidas repetidas
    analises.py    o lote: roda as análises da lista `analises:` da ficha, em ordem
    relatorio.py   lê o manifesto e monta o conteúdo do documento
    documento.py   escreve o .docx a partir do conteúdo já montado
    amostral.py    a aritmética do tamanho da amostra, só com a biblioteca padrão
    amostragem.py  o desenho.yaml, a conta e o relatório da amostra, em 4. Amostragem/

    cli.py         expõe os comandos no terminal

A dependência anda sempre para cima nessa lista: `dados` conhece `ficha`, `ficha` conhece
`projeto`, `perfil` conhece `banco` e `dicionario`, `descritiva` conhece `banco`, `dicionario`
e `manifesto`, `relatorio` conhece `manifesto`, `dicionario`, `dados` e `ficha`, e nenhuma
delas conhece a `cli`. A exceção é o par `relatorio`–`documento`: o `documento` conhece o
`Relatorio` que recebe, e o `relatorio` só chama o `documento` de dentro do
`executar_relatorio`. A `amostragem` conhece `amostral`, `ficha`, `manifesto` e `relatorio`,
e chama o `documento` do mesmo jeito, de dentro do `executar_amostragem`.

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

## 1.12.0 — as medidas repetidas

**A mesma medida, três vezes ou mais, nos mesmos casos.** O item tem a marca
`repetidas:` — `- repetidas: [pas_0, pas_1, pas_2]` —, e o método, quando vier, numa
chave ao lado, `metodo: anova`, porque a lista das medidas não tem um terceiro lugar.
Duas numéricas soltas seriam um pareado, ou um `[idade, imc]` escrito por engano; a
marca diz que são a mesma medida. Com duas medidas a recusa diz que a pergunta é a do
t pareado, que ainda não está no FlatCap e vai usar esta mesma forma.

**A ANOVA de medidas repetidas, sempre com a correção de Greenhouse-Geisser**, pela
razão do Welch: a correção custa pouco quando a esfericidade vale, protege quando não
vale, e o Mauchly sai da frente. É o `anova.mlm` do R com `test = "Spherical"` — o F do
`aov` com `Error(caso / medida)`, e o p da coluna `G-G Pr` —, transcrito no
`hipoteses.py`, porque o `scipy` não tem; o ε e o F conferem com a conta em frações
melhor do que o próprio `anova.mlm`, que erra na décima casa. O `Resultado` ganha o
campo `epsilon`, e a frase da escolha o traz: `F = 37,04; 1,84 e 67,96 gl; ε = 0,918`.

**A regra olha cada medida**: o Shapiro-Wilk em cada uma, sobre os casos completos; a
normal rejeitada em alguma leva ao Friedman, que ainda não está no FlatCap.

**Os faltantes são por item, e inteiros**: entra quem tem todas as medidas. A média de
cada medida na tabela é a desses casos — e difere da do `resumo` da descritiva quando
alguma medida tem faltante, o que a nota diz.

**A tabela `repetidas.csv`**: uma linha por medida, com o teste e o p na primeira. E
uma barreira que o R não tem: medidas que não variam dentro dos casos — cada caso
mudando o mesmo tanto —, em que o R devolve um F de 10²⁹ feito de arredondamento.

## 1.13.0 — o lote

**`flatcap analisar <id>`: as análises da lista `analises:` da ficha, de uma vez.**
A lista existia desde a Fase 2 e ordenava as seções do relatório desde a 1.3.1; agora
ela também diz o que roda. O comando obedece e não escolhe: lista vazia recusa, e a
recusa escreve a linha pronta para copiar a partir dos blocos que a ficha já tem;
nome que o FlatCap não conhece recusa com a grafia certa — `associação` pede
`associacao`, `anova` ensina que o teste roda dentro da `comparacao`; nome repetido
recusa, porque a posição na lista é a posição da seção no documento. Os seis comandos
de cada análise continuam iguais.

**`analises.py` é a soma dos comandos, e nada além.** Cada análise é preparada e
escrita pelas funções dela, com os argumentos que o comando dela passaria e o mesmo
relógio para todas — e a rodada sai, byte a byte, a que o comando dela escreveria. É
o critério de pronto, e o primeiro teste do `test_analises.py`. As três regras vêm do
plano da Fase 7: **prepara todas antes de escrever qualquer uma** (se uma recusar,
nada é arquivado, e as recusas saem todas juntas; o que vale para todas — a ficha, o
banco, o dicionário — para na primeira); **um registro nome → módulo, com import
preguiçoso** (importar o `analises.py` não traz o `pandas`); e **o relatório fica de
fora**, porque entre as análises e o documento há uma leitura sua. Nenhum dos seis
módulos de análise mudou uma linha.

**Uma falha no meio para o lote.** A análise que falhou se desfaz sozinha, como no
comando dela; as anteriores ficam; as seguintes não rodam. A frase de onde ele parou
vai para o `historico.md` e presa ao erro, e um Ctrl+C sai com 130 e a mesma frase —
dizendo que a pasta da análise interrompida pode ter ficado pela metade, porque o
desfazer de cada `executar_*` pega `Exception`, e o Ctrl+C não é uma.

**Na CLI, a saída de cada análise é a do comando dela.** O que cada comando mostrava
antes de escrever virou uma `_mostrar_*`, e o que dizia depois, a `_rodada_escrita`:
o `analisar` chama as mesmas funções, uma análise depois da outra, e fecha com uma
tabela do lote. `--resumo` mostra só a tabela. O `_NA_TELA` é o registro da tela, e
há teste que o exige igual ao `analises.REGISTRO`.

## 1.13.1 — a revisão antes da abertura do código

Uma revisão de todos os arquivos antes de o repositório virar público, e nenhuma
funcionalidade nova. Cada correção tem o seu teste de regressão.

**O perfil escreve as categorias como as análises.** Uma coluna de código com uma
célula vazia chega como `float64`, e o perfil escrevia `1.0|2.0` no `dicionario.csv` e
`1.0=Feminino` na dica; a descritiva escreve `1`, e a tabela saía com `Feminino 0` ao
lado de `1 20`. A `serie_de_texto` desceu para o `banco.py`, ao lado dos
`FORMATOS_DATA` e pelo mesmo motivo deles. O dicionário já escrito com `1.0=` não é
reescrito — a fusão nunca toca linha existente —, e o conserto é à mão.

**O `#` só é comentário no começo do arquivo.** No dicionário, a variável `#id` sumia a
cada leitura; na tabela de uma análise, a categoria `#N/D` saía do `.docx` e o `Total`
deixava de fechar. E as mensagens do dicionário passam a dar a linha do arquivo.

**O que o disco e o terminal mostram.** O cifrão do banco não vira fórmula nos
gráficos; o arquivo gravado segue o `umask`, e não `0o600`; todo erro HTTP do REDCap
vira `RedcapError`; a falha inesperada no relatório devolve o anterior ao lugar; e a
codificação do `.csv` é confirmada no arquivo inteiro, e não só nos primeiros 64 KiB.

**A distribuição por pacote.** O `.env` da sua conta é o terceiro degrau da procura,
para quem instala o FlatCap com o `pipx` ou o `uv` e roda o comando de qualquer pasta;
`flatcap doctor --criar-env` o escreve. A versão passou a morar só aqui — o
`pyproject.toml` a lê com `dynamic = ["version"]`.

**A abertura.** `LICENSE` com a GPL-3.0, `NOTICE.md` com os trechos derivados do R, o
cabeçalho SPDX em todo arquivo de código, e o `flatcap --version` dizendo a licença.

## 1.14.0 — os testes de postos

**Onde a normal não se sustenta, a comparação passa a ter teste.** O Wilcoxon contra uma
referência, o Mann-Whitney entre dois grupos, o Kruskal-Wallis entre três ou mais e o
Friedman nas medidas repetidas — os quatro que a regra já nomeava desde a 1.7.0, e que
deixavam a linha sem teste. A regra não mudou: o Shapiro-Wilk em cada vetor do
delineamento, o paramétrico quando ele não rejeita, o de postos quando rejeita ou não pode
ser verificado, e o método escrito no item por cima dos dois — `wilcoxon`, `mannwhitney`,
`kruskal`, `metodo: friedman`.

**Os quatro são os do R, com a escolha do R escrita.** O `wilcox.test` decide o p exato com
menos de 50 valores, sem empate e sem zero, e a aproximação normal com as correções de
empate e de continuidade nos outros casos; o `scipy` decide por outro critério, e por isso
a aritmética do Wilcoxon e do Mann-Whitney está no `hipoteses.py` — as distribuições exatas
contadas em inteiros, servindo ao p e ao intervalo. O Kruskal-Wallis é o `kruskal` do
`scipy`, igual ao do R; o Friedman é escrito, como a ANOVA, porque o `scipy` recusa duas
medidas, que o R aceita.

**O Wilcoxon e o Mann-Whitney saem com a estimativa de Hodges-Lehmann e o intervalo de 95%
dela** — o `conf.int = TRUE` do R: a pseudomediana na uma amostra, a diferença de locação
entre dois grupos, que não é a diferença das medianas. No caminho aproximado, o R acha os
limites com o `uniroot`, e ele está transcrito — o `R_zeroin2` —, para os limites saírem
os do R, e não outros a menos de 1e-4 deles. Com poucos valores, o intervalo de 95% pode
não existir na distribuição exata, e o menor p possível pode passar de 0,05: os dois saem
com aviso, e o intervalo que não chega a 95% fica fora da tabela.

**O resumo, linha a linha.** `média (DP)` nas linhas do t e da ANOVA, `mediana [Q1 a Q3]`
nas dos testes de postos, como o `compareGroups` — o cabeçalho diz o que a coluna tem, e
uma tabela só de paramétricos sai como antes. O mesmo no intervalo da uma amostra (`IC 95%
da média`, `da pseudomediana`, ou `IC 95%` quando a tabela tem os dois) e na diferença
entre dois grupos: `diferença de locação (IC 95%)` no Mann-Whitney, porque o documento não
leva as notas do `.csv`, e a de locação, ao lado da mediana de cada grupo, seria lida como
a diferença das duas. O manifesto guarda as duas formas do resumo de cada linha, de cada
grupo e de cada medida.

**Cada teste com a sua barreira.** O Friedman roda onde a ANOVA de medidas repetidas não
pode — cada caso mudando o mesmo tanto entre as medidas —, e o aviso da ANOVA ensina a
escrevê-lo; e recusa o caso em que cada caso tem o mesmo valor em todas as medidas, onde o
R devolve `NaN`.

**Os nomes.** `wilcoxon` é o `wilcox.test` do R: o do posto sinalizado contra uma
referência, e o Mann-Whitney entre dois grupos. O `signed rank` escrito por extenso recusa,
em vez de levar ao Mann-Whitney quem pediu o posto sinalizado; as outras grafias dos livros
— `U de Mann-Whitney`, `Wilcoxon rank sum`, `Kruskal-Wallis` — valem.

O `relatorio.py` não mudou uma linha.

## 1.14.1 — o que chega do Excel

As quatro correções de gravidade alta da varredura do repositório público, cada uma
com o seu teste de regressão. Nenhuma funcionalidade nova; as quatro são entradas comuns
que o FlatCap lia errado.

**A vírgula decimal do `.csv` do Excel em português é lida como número.** É o formato
mais comum de chegar — `;` entre campos, `70,5` na célula —, e a coluna chegava como
texto: o perfil mandava o cliente "corrigir" um arquivo certo, e toda análise recusava a
coluna. A decisão "a leitura é fiel ao que o cliente mandou" continua valendo para todo o
resto; aqui ela cede pela razão que já fazia a data escrita como texto ser convertida —
exigir do cliente o conserto de um formato que o Excel dele sempre escreve é exigir o
impossível. A conversão é da coluna inteira ou de nada, só vale onde a vírgula não separa
campos, e fica escrita no perfil e no manifesto. As condições estão no `banco.py`.

**Número de escala pequena não sai mais zero.** As estatísticas tinham duas casas fixas, e
uma concentração na casa de 0,003 saía `0` no resumo inteiro, com faixas `[0 a 0)`, e a
comparação imprimia "média 0 (0)" nos dois grupos ao lado de uma diferença "0,00 (0,00 a
0,00)" e de um p < 0,001. O `banco.casas_do_resumo` decide as casas de cada variável pela
escala dela; de 0,01 para cima nada muda.

**O nome de coluna sai numa linha e sem espaço nas pontas.** `Idade ` travava o projeto: o
perfil gravava o nome com o espaço, a leitura do dicionário o aparava, a descritiva não
achava a coluna e mandava rodar o perfil, que a acrescentava de novo — e na volta a
variável aparecia duas vezes. `Peso` e `(kg)` em duas linhas partiam o comentário das
tabelas, e o relatório saía com tabelas de uma coluna só, sem aviso. O leitor limpa os
dois, e o comentário das tabelas sai sempre numa linha só, mesmo quando o rótulo ou uma
categoria trazem a quebra.

## 1.15.0 — a amostragem

**`flatcap amostragem <id>`: o tamanho da amostra, na pasta dela, com o relatório dela.** O
projeto costuma começar com a amostragem e evoluir depois para a análise, e o fluxo começa
sempre no `flatcap novo`, que não muda — as três pastas de sempre. A amostragem vem depois
dele. A primeira rodada cria `4. Amostragem/` e escreve o `desenho.yaml`, o plano da amostra,
para preencher à mão, e para; as seguintes leem o `desenho.yaml`, fazem a conta e escrevem o
`tamanho.csv`, o `manifesto.json` e o relatório da amostra,
`Amostragem_<matrícula>_AAAA-MM-DD.docx`. Tudo da amostra mora em `4. Amostragem/`, inclusive
as versões antigas dela, e as pastas 1, 2 e 3 ficam para a análise que vem depois.

**A pasta nasce na amostragem, e não no `novo`.** O `novo` não tem como saber se o pedido é de
amostragem — o formulário do REDCap não tem essa opção —, o projeto que nunca amostra não
ganha uma pasta vazia, e o que já existia ganha a pasta do mesmo jeito, sem migração. A
amostragem não cria projeto: sem a pasta do `novo`, recusa e diz isso.

**A amostragem não é uma análise.** Não está no `analises.REGISTRO`, na
`ORDEM_PADRAO_DAS_ANALISES` nem no `flatcap analisar`. O relatório das análises varre só
`3. Análises/` e nunca vê a amostra, e o relatório da amostra nunca vê as análises. O
`ANALISE_AMOSTRAGEM` do `manifesto.py` existe para o manifesto dela dizer de que ele é.

**Um desenho, e o espaço para os outros.** A aleatória simples, sem reposição: a do pedido
mais comum, o do cliente que informa só o tamanho da população. O modelo do `desenho.yaml` já
vem com 95% de confiança, margem de 5 pontos e proporção esperada de 50%, e preencher a
`populacao` basta. A média entra com o `desvio` no lugar da `proporcao`; o tamanho decidido à
mão, no `n`; a perda esperada, na `perda`. Cada desenho é uma entrada no
`amostragem.DESENHOS`, com as chaves e a conta dele, e os previstos — sistemática,
estratificada, conglomerados, PPT, dois estágios — recusam dizendo que ainda não estão no
FlatCap, e não que não existem.

**A conta é a do OpenEpi.** n₀ = z²·V/e², corrigido pela população na forma
n = N·z²·V/[(N − 1)·e² + z²·V], arredondado para cima em cada passo, com a perda somada no fim
e o tamanho nunca maior que N. O z é o `qnorm` do R, pelo `statistics.NormalDist`. A
aritmética mora no `amostral.py`, só com a biblioteca padrão, e o teste a confere contra os
tamanhos publicados e contra o `qnorm`.

**As recusas são as do engano que muda o número em silêncio.** `12.000` é doze no YAML, e não
doze mil; `confianca: 0.95` é a confiança escrita como fração, e `confianca: 5`, o α no lugar
dela; `proporcao: 0.5` querendo 50% é meio por cento, e daria n = 8 sem erro nenhum. Saem
todas de uma vez, como nas análises. A margem escrita como fração, `margem: 0.05`, passa por
todas — 0,05 ponto existe —, e por isso sai com aviso, e não recusada. A vírgula decimal vale,
e `AAS` ou `Aleatória simples` são lidos como `aas`.

**O relatório da amostra é montado com as peças do das análises**, e três delas ficaram
públicas no `relatorio.py`: o `tabela_do_texto` — o miolo do `ler_tabela`, para a tabela do
documento ser lida do mesmo texto que vai para o `tamanho.csv` —, o `localizar_template` e o
`conferir_texto`, com os nomes privados como apelido. A primeira página é a mesma, com a
finalidade e os objetivos da ficha. O texto de metodologia tem o lugar dele, o
`amostragem.METODOLOGIA`, vazio de propósito, pela regra do `TEXTO_PADRAO`.

**O `desenho.yaml` é seu.** O FlatCap escreve o modelo uma vez e, dali em diante, só lê — e
quem lê é o `ficha.ler_yaml`, para um YAML quebrado ganhar o diagnóstico da ficha. Refazer a
rodada arquiva a anterior em `4. Amostragem/Versões antigas/`, com o `desenho.yaml` de então:
o texto que ela leu, guardado no manifesto dela, e não o da pasta, que a essa altura já é o
novo. O tamanho que muda em relação à rodada vigente sai com aviso, antes de escrever.

**O número escrito à mão desceu para o `ficha.py`.** A regra do `numero_escrito` era a do
`comparacao.referencia_escrita`, e a amostragem lê o `desenho.yaml` por ela.

**As propriedades do `.docx` dizem de qual rodada ele é.** O comentário dizia "a partir da
descritiva" em todo documento e, sem banco, "banco ?"; passa a dizer a análise do manifesto,
e "sem banco" quando não há.
"""

__version__ = "1.15.0"
