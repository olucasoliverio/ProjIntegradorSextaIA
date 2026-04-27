# Contexto: Transformação das Leis (Markdown) para SQLite via Docker

Este documento foi criado para **servir de contexto em futuros prompts de IA** ou como documentação técnica da próxima fase do projeto. 

**Objetivo Futuro:** Pegar ~10.000 arquivos `.md` gerados pelo scraper e criar um script em Python que lê cada um, converte em registros estruturados e insere num banco de dados SQLite (`leis-nova-veneza.db`). O banco de dados e possivelmente uma API simples deverão ser posteriormente contêinerizados (usando `Dockerfile`) para facilitar o compartilhamento desse conjunto de dados.

---

## 📄 1. Estrutura dos Arquivos `.md`

Todos os arquivos processados estão na pasta `/leis/`. Cada arquivo possui o conteúdo rigorosamente no seguinte formato:

```markdown
# [TÍTULO DA LEI]

**Tipo:** [Ex: Lei Ordinária, Decreto, Portaria]
**Número:** [Ex: 3198]
**Data:** [Ex: 27 de março de 2026]
**Situação:** [Ex: Norma em vigor ou Revogada]
**URL:** [URL original do LeisMunicipais]

## Ementa
[Resumo da lei. Este bloco é opcional e só aparece caso a lei o possua.]

## Texto Completo
[Todo o texto bruto do documento com Artigos, Parágrafos etc...]
```

> **Aviso para o Futuro DEV/IA:** A biblioteca `re` do Python é ideal para realizar o parse das linhas que iniciam com `**Tipo:**`, `**Número:**` etc., em propriedades de um objeto/dicionário. Tudo que estiver entre o cabeçalho `## Texto Completo` e o final do arquivo deve ser absorvido como o conteúdo bruto da lei.

---

## 🗄️ 2. Proposta de Schema do SQLite

Sugestão de estrutura para a tabela no SQLite (exemplo: `tabela: leis_municipais`):

| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| `id` | INTEGER | Chave primária (Auto-increment) |
| `filename` | TEXT | Nome do arquivo original (ex: `lei-n-123.md`) |
| `titulo` | TEXT | O Título 1 extraído da primeira linha (`# ...`) |
| `tipo` | TEXT | Lei Ordinária, Decreto, Resolução, etc. |
| `numero` | TEXT | O número identificador do documento |
| `data` | TEXT | Data promulgada da lei |
| `situacao` | TEXT | Situação atual (Revogada, Em Vigor) |
| `url` | TEXT | URL de origem |
| `texto_completo`| TEXT | O corpo legislativo da lei na íntegra |

---

## 🏗️ 3. O Que Deve Ser Construído na Próxima Fase

Quando este projeto retomar os trabalhos, a IA ou o Desenvolvedor deverá implementar:

1. **`build_db.py`**: Um script que fará um loop (`os.listdir`) pelo diretório `/leis/`, lerá cada `.md`, estruturará o objeto e realizará comandos de `INSERT` na connection local do `.db` com bulk insert.
2. **`Dockerfile`**: Uma receita simples e enxuta via Docker para encapsular a base rodando em Python com acesso ao DB via biblioteca padrão `sqlite3` ou mesmo servindo tudo via uma API simples (`FastAPI` ou `Flask`), facilitando absurdamente que este acervo de 10k leis locais seja consultado sob demanda por outras ferramentas de vetorização (RAG/LLM).
3. **Consulta de Busca Simples**: Uma maneira de disparar query textual pra ver se a lei contendo a palavra `X` existe (exemplo: `LIKE '%veículo%'`).
