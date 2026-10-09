# Segurança

O FlatCap lida com duas coisas que não podem vazar: o **token da API do REDCap**, que dá
acesso às solicitações de uma instituição, e os **dados dos clientes** — bancos de pesquisa,
nomes, matrículas, relatórios.

## Se um token vazar

Num commit, numa issue, num print de tela, num e-mail: **troque o token no REDCap** (menu
*API* do projeto → *Regenerate token*) e atualize o `.env`. O token antigo deixa de valer na
hora. É mais rápido e mais seguro do que reescrever o histórico do Git, que não alcança as
cópias que alguém já tenha feito.

O `.env` nunca vai para o Git: o `.gitignore` o bloqueia, e o `pre-commit` procura chaves e
segredos antes de cada commit. O `.env` da sua conta, escrito pelo
`flatcap doctor --criar-env`, nasce legível só por você no Linux e no macOS.

## Dados de clientes

Nunca anexe banco, relatório, `projeto.yaml` ou `perfil.md` de um atendimento de verdade a
uma issue ou a um pull request, nem cole trechos deles. Reproduza o defeito com um banco
inventado. O `FLATCAP_ROOT`, onde os dados moram, fica fora de qualquer repositório Git, e o
backup dele é responsabilidade de quem o usa.

## Relatar uma vulnerabilidade

Não abra uma issue pública. Use o relato privado do GitHub —
[*Report a vulnerability*](https://github.com/MatheusEstatistico/flatcap/security/advisories/new),
na aba *Security* do repositório — com o que você encontrou e como reproduzir. O relato
chega só a quem mantém o projeto, e a correção é combinada com você antes de ser publicada.

## Versões que recebem correção

Só a versão mais recente. O FlatCap é instalado por ferramenta (`pipx`, `uv`), e atualizar é
um comando.
