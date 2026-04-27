# Passo a Passo: Execução e Retomada do Scraper em Outras Máquinas

Este manual detalha o que é necessário para copiar o projeto para um novo computador, dando continuidade ao download das leis de Nova Veneza sem perder o progresso e sem baixar arquivos duplicados.

O sistema possui uma trava de segurança que lê dados persistentes. Graças a isso, é possível montar um exército de máquinas rodando o mesmo script ou simplesmente migrar o trabalho.

---

## 📂 1. O que você precisa copiar (para subir no Git ou transferir)

Apenas **3 itens** são estritamente necessários para retomar exatamente de onde parou:

1. `scraper.py` - O código-fonte principal que orquestra a raspagem.
2. `links_cache.json` - O arquivo que contém os 10.000 `links` mapeados. **Sem ele, o script começará da Fase 1 novamente**.
3. A pasta `/leis/` - Que contém os arquivos `.md` já finalizados. O script valida o que tem nesta pasta para ignorar na hora de baixar.

---

## ⚙️ 2. Preparação do Novo PC 

### Instalação do Python
1. Instale o Python (versão 3.10 ou superior).
2. Durante a instalação (se for Windows), **marque a caixa "Add Python to PATH"**.

### Instalação das Dependências
Para conseguir lidar com a proteção pesada de Anti-Bot (Cloudflare Turnstile) e reCAPTCHA invisible sem travar, usamos o **Camoufox**.

Abra o terminal (CMD ou PowerShell) na pasta onde estão os arquivos e rode os dois comandos nesta ordem:

```powershell
# 1. Instala a biblioteca com suporte a Geolocalização
pip install camoufox[geoip]

# 2. Faz o download do navegador stealth local
python -m camoufox fetch
```

---

## ▶️ 3. Rodando o Script de Forma Inteligente

Abra o terminal na pasta em que você uniu o seu `scraper.py`, o `links_cache.json` e a pasta `leis` (mesmo se a pasta leis estiver vazia), e inicie a raspagem:

```powershell
python scraper.py
```

### O Comportamento do Script:
1. **Pula a Fase 1:** Ele notará o arquivo `links_cache.json` contendo os 10.000 links e pulará a varredura lenta pelas mil páginas de lista.
2. **Elimina Tarefas Feitas:** O script olhará dentro de `/leis/` e deduzirá da lista tudo o que já existe (comparação exata de nomes).
3. **Download Residual:** Ele te informará `Pendentes: X` e baixará apenas o restante até fechar as 10.000.  


---

## 🛠️ Resolução de Problemas
- **Parou no meio do caminho?** Pode usar um `Ctrl+C` ou desligar a máquina. Quando você rodar o comando na próxima vez, ele prosseguirá exatamente da próxima ausência.
- **Arquivo veio vazio (`[OK] 0 chars`)?** Isso muitas vezes decorre de *timeout* ou da falta de conteúdo no órgão público. Se quiser que o script tente rodar ele de novo, **simplesmente apague o `.md` defeituoso da pasta**. Na próxima vez que o script for executado, o arquivo ausente entrará na fila novamente. 
