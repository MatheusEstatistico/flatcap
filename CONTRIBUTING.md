# Como contribuir

Obrigado pelo interesse. O FlatCap é escrito e documentado em português, que é a língua de
quem o usa; issues e pull requests em inglês também são bem-vindos.

## Antes de tudo: dado de cliente nunca entra aqui

Banco de pesquisa, nome de aluno, relatório, `projeto.yaml` de um atendimento de verdade e o
`.env` **nunca** vão para uma issue, um pull request, um commit ou um anexo — nem "só para
mostrar o erro". O histórico do Git é praticamente irreversível, e uma issue pública é
pública. Para mostrar um defeito, reproduza-o com um banco inventado: os construtores de
`tests/bancos.py` são o modelo, e cada um tem nome de esquisitice (`com_virgula_decimal`,
`csv_do_excel_ptbr`...).

## Preparar o ambiente

```bash
git clone https://github.com/MatheusEstatistico/flatcap.git
cd flatcap
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

## O ritual de cada mudança

Na ordem, antes de pedir a revisão:

1. `git diff` — releia o que mudou, inteiro.
2. `pytest` — a suíte offline. Leva alguns minutos: os gráficos são desenhados a 600 DPI.
3. `pytest -m e2e` — a ponta a ponta: o `flatcap` como subprocesso contra um REDCap falso.
4. `ruff check src tests tools` — sem nenhum achado.
5. **Gere um relatório de um projeto de teste e abra o `.docx` no Word**, e os `.png` que a
   mudança tocar. Quatro dos cinco defeitos de formatação da Fase 6 não teriam sido pegos por
   asserção nenhuma — os testes `test_o_que_so_se_ve_*` estão lá para lembrar.
6. Só então o commit, com uma mensagem que diga o porquê, e não só o quê.

O `pre-commit` roda o `ruff` e as conferências de arquivo em cada commit; a CI roda os passos
2 a 4 no Linux, no Windows e no macOS.

## As regras da casa

- **Um módulo em `src/flatcap/` pede um `test_` de mesmo nome** em `tests/`. Um teste novo
  tem exatamente um lugar possível.
- **Nenhum número estatístico é conferido contra o próprio FlatCap.** A referência é o R —
  os valores copiados para constantes `*_DO_R`, com o código R que os produziu num
  comentário —, a documentação do R, ou a força bruta em frações exatas.
- **Nada toca a rede nos testes**, e o relógio é injetado (`agora=`), nunca lido.
- **Decidir e escrever são funções separadas**: `preparar_*` devolve um plano imutável,
  `executar_*` só escreve, e desfaz o que escreveu se falhar no meio.
- **Os comandos que escrevem simulam por padrão**; `--sim` executa.
- **Erro previsto vira painel, não traceback**: cada módulo tem a sua classe de erro, e a
  CLI a captura. Qualquer outra exceção é bug, e deve subir inteira.
- **Os comentários explicam o porquê**, e o docstring de cada módulo conta as decisões que o
  moldaram. A [documentação](docs/Doc.Flatcap.md) é gerada a partir deles:
  `python tools/gerar_doc.py` depois de mudar um comentário, e a CI confere que ela está em
  dia.
- **Cabeçalho SPDX** em todo arquivo novo de código:

  ```python
  # SPDX-FileCopyrightText: 2026 <seu nome>
  # SPDX-License-Identifier: GPL-3.0-or-later
  ```

## Licença das contribuições

Ao abrir um pull request, você concorda em licenciar a sua contribuição sob a mesma licença do
projeto, a GNU General Public License versão 3 ou posterior (`GPL-3.0-or-later`). Código
transcrito de outro projeto precisa vir de uma licença compatível com a GPL-3.0, com a origem
no docstring e uma linha no [`NOTICE.md`](NOTICE.md).

## Relatar um defeito ou propor uma ideia

Pelas [issues](https://github.com/MatheusEstatistico/flatcap/issues), com os modelos que
aparecem ao abrir uma. Vulnerabilidade de segurança **não** vai numa issue: ver o
[`SECURITY.md`](SECURITY.md).
