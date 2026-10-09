# Avisos de direitos autorais, de licença e de terceiros

## FlatCap

Copyright (C) 2026 Matheus Fernandes

O FlatCap é software livre: você pode redistribuí-lo e modificá-lo sob os termos da GNU
General Public License, publicada pela Free Software Foundation, na versão 3 da licença ou
(a seu critério) em qualquer versão posterior — `GPL-3.0-or-later`.

O FlatCap é distribuído na esperança de ser útil, mas **sem nenhuma garantia**, nem mesmo a
garantia implícita de comercialização ou de adequação a um propósito específico. O texto
integral da licença, que é o que vale, está no arquivo [`LICENSE`](LICENSE), em inglês.

Todo arquivo de código do repositório começa com duas linhas no formato SPDX, que dizem o
mesmo de um jeito que uma ferramenta lê:

```python
# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
```

## Trechos derivados do R

Algumas funções do FlatCap são transcrições, para Python, de código do R — *The R Project for
Statistical Computing*, <https://www.r-project.org>. O R é distribuído sob a GNU General
Public License, versão 2 ou (a seu critério) qualquer versão posterior, e a
`GPL-3.0-or-later` do FlatCap é uma das licenças que essa opção permite. Os arquivos em que
esses trechos moram trazem também a linha de direitos autorais do R no cabeçalho, e cada
função diz no docstring de onde veio.

| no FlatCap | no R (pacote `stats`) | direitos autorais do original |
|---|---|---|
| `correlacao.prho` e a tabela `_EDGEWORTH` — o p exato do Spearman | `src/library/stats/src/prho.c` | (C) 2000-2024 The R Core Team; (C) 2003-2024 The R Foundation; baseado no algoritmo AS 89, (C) 1975 Royal Statistical Society |
| `correlacao.spearman` e `correlacao.kendall` — a escolha entre o p exato e a aproximação, e a variância do Kendall corrigida para empates | `src/library/stats/R/cor.test.R` | (C) 1995-2022 The R Core Team |
| `associacao.qui_quadrado` — a correção de continuidade de Yates | `src/library/stats/R/chisq.test.R` | (C) 1995-2013 The R Core Team |
| `associacao._fisher_2x2` — o Fisher exato na tabela 2×2 | `src/library/stats/R/fisher.test.R` | (C) 1995-2026 The R Core Team |
| `hipoteses.anova_de_medidas_repetidas` — a ANOVA de medidas repetidas com a correção de Greenhouse-Geisser | `anova.mlm`, em `src/library/stats/R/mlm.R` | (C) 1998-2018 The R Core Team; (C) 1998 B. D. Ripley |

As linhas de direitos autorais são as dos cabeçalhos dos arquivos do R, conferidas no
código-fonte do R em outubro de 2026.

O Fisher exato das tabelas maiores que 2×2 (`associacao._fisher_rede`) **não** é
transcrição: é uma implementação do algoritmo de rede de Mehta e Patel (1983) escrita a partir
do artigo, com limites de poda próprios. Do FEXACT que o R usa (`src/library/stats/src/fexact.c`,
baseado no algoritmo 643 da ACM TOMS) vem só a constante de tolerância `3.45254e-7`.

Os números de referência dos testes — as constantes `*_DO_R` e `REFERENCIAS_DO_R_*` — são
saídas do R 4.3.3 e dos exemplos da documentação do R, usados para conferir o FlatCap.

### Referências

- Best, D. J.; Roberts, D. E. (1975). Algorithm AS 89: The upper tail probabilities of
  Spearman's rho. *Applied Statistics*, 24(3), 377–379.
- Mehta, C. R.; Patel, N. R. (1983). A network algorithm for performing Fisher's exact test
  in r × c contingency tables. *Journal of the American Statistical Association*, 78(382),
  427–434.
- Mehta, C. R.; Patel, N. R. (1986). Algorithm 643: FEXACT, a Fortran subroutine for Fisher's
  exact test on unordered r × c contingency tables. *ACM Transactions on Mathematical
  Software*, 12(2), 154–161.

## REDCap

REDCap é marca da Vanderbilt University. O FlatCap **não é afiliado** à Vanderbilt nem ao
REDCap Consortium, nem endossado por eles: ele só conversa com a API que o servidor REDCap de
uma instituição expõe, com o token que a própria instituição concede.

## Bibliotecas usadas

O FlatCap não inclui código de outras bibliotecas: ele as usa, instaladas pelo `pip`, cada uma
sob a sua licença — typer, rich, python-dotenv e PyYAML (MIT ou BSD), requests (Apache-2.0),
pandas e SciPy (BSD-3-Clause), openpyxl, ruamel.yaml e python-docx (MIT) e matplotlib (licença
do Matplotlib, de estilo BSD). Todas são compatíveis com a GPL-3.0. Quem distribuir o FlatCap
num pacote que as inclua — um executável do PyInstaller, por exemplo — precisa levar junto os
avisos de licença delas.
