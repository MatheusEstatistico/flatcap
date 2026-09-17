# FlatCap 
Ferramenta para orquestrar o fluxo de trabalho estatístico com Python e REDCap: 

**REDCap (entrada) → organização de pastas → versionamento dos bancos → análise descritiva → relatório `.docx`**.

## Princípio norteador 
Automatizar o que é repetitivo e mecânico e manter manual o que é decisão técnica. Tudo que é automatizado fica documentado em disco, para que qualquer projeto possa ser reaberto meses depois e compreendido sem depender da memória. Nada é apagado, as versões antigas são documentadas na pasta do cliente/projeto. 

> A documentação completa pode ser encontrada em [`Doc.Flatcap`]().
---

## Instalação 
Requer **Python 3.11+** <br>
Requer **Git** <br>
Requer **_** <br>

```bash
git clone git@github.com:<usuario>/flatcap.git
cd flatcap
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```
 
## Configuração 
Copie `.env.example` para `.env` e preencha: 
```env
REDCAP_API_URL=https://<servidor-institucional>/redcap/api/
REDCAP_TOKEN=32caracteres
FLATCAP_ROOT=pasta_local
```

| Chave | Onde obter |
|---|---|
| `REDCAP_API_URL` | Página **API Playground** do projeto. **Não** é o link curto do survey. |
| `REDCAP_TOKEN` | Menu **API** do projeto → *Request API token*. <br>Precisa de permissão para exportar **registros, metadados e arquivos**. |
| `FLATCAP_ROOT` | Caminho absoluto da pasta onde os projetos vivem. |
--- 

## Comandos disponíveis  
| Comando | Função |
|---|---|
| `flatcap doctor` | Testa credenciais, conexão e `FLATCAP_ROOT`. |
| `flatcap listar -n N` | Lista os clientes do REDCap e o status local de cada um. |
| `` |---|


> Comandos que escrevem em disco **simulam por padrão**. Use `--sim` para executar de fato.
--- 

## 
