## O que muda, e por quê

## O ritual

- [ ] `pytest` e `pytest -m e2e` passam
- [ ] `ruff check src tests tools` sem nenhum achado
- [ ] se a mudança toca o relatório ou os gráficos: um `.docx` gerado e aberto no Word
- [ ] se algum comentário mudou: `python tools/gerar_doc.py`
- [ ] número estatístico novo conferido contra o R, com o código R no comentário do teste

## Privacidade

- [ ] nenhum dado de cliente, token ou `.env` no diff, nos testes ou nos prints
