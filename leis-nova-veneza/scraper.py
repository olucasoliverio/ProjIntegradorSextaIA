# -*- coding: utf-8 -*-
"""
scraper.py - Scraper completo das 10.000 leis de Nova Veneza
Usa Camoufox (Firefox stealth) para bypass de Cloudflare + reCAPTCHA.

Fluxo:
  1. Abre o browser - Cloudflare resolve automaticamente (ou voce ajuda 1 vez)
  2. Coleta todos os links das 1000 paginas de listagem
  3. Acessa cada lei e salva como .md em /leis/

Retomada automatica: se interrompido, continua de onde parou.

Execucao: python scraper.py
"""
import sys, io
import builtins

# Configura stdout para Windows CMD (forcar flush)
class FlushFile(io.TextIOWrapper):
    def write(self, x):
        super().write(x)
        self.flush()

sys.stdout = FlushFile(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = FlushFile(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Monkey patch print para garantir flush
_print = builtins.print
def custom_print(*args, **kwargs):
    kwargs['flush'] = True
    _print(*args, **kwargs)
builtins.print = custom_print

import asyncio
import json
import os
import re
import time
from pathlib import Path
from camoufox.async_api import AsyncCamoufox

# ===================== CONFIG =====================
CITY_ID   = 4656
CITY_SLUG = "leis-de-nova-veneza"
TOTAL_PAGES  = 1000         # 10.000 leis / 10 por pagina
OUTPUT_DIR   = Path("leis") # onde os .md serao salvos
LINKS_CACHE  = Path("links_cache.json")
DELAY_LIST   = 1.5          # segundos entre paginas de listagem
DELAY_DETAIL = 2.5          # segundos entre paginas de detalhe
HEADLESS     = False        # mantem visivel para debugging

BASE_URL = "https://leismunicipais.com.br"
LIST_URL = (
    f"{BASE_URL}/legislacao-municipal/{CITY_ID}/{CITY_SLUG}"
    "?q=&page={page}&types=28&types=4&types=5&types=35&types=228&types=229&types=230"
)
# ==================================================


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:120]


def url_to_filename(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    return slugify(slug)


def clean_text(text: str) -> str:
    """Remove linhas de ruido do texto da lei."""
    noise = [
        "Favoritar essa Lei", "Funcionalidade Anotacoes", "Adicionar Anotacao",
        "Pesquise por palavras", "Salvar essa Lei em formato PDF",
        "Imprimir esta norma", "Expande o texto", "Download do documento",
        "Nota: Este texto nao substitui", "Data de Insercao no Sistema",
        "Acessar menu", "Minha Conta", "Servicos", "Cidades", "Contato",
        "Institucional", "Todos os Direitos Reservados", "LeisMunicipais",
        "Valorizamos sua privacidade", "Utilizamos cookies", "Aceitar todos",
        "Personalizar", "Rejeitar",
    ]
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            cleaned.append("")
            continue
        skip = False
        for n in noise:
            if n.lower() in line_stripped.lower():
                skip = True
                break
        if not skip:
            cleaned.append(line)
    # Remove multiplas linhas em branco consecutivas
    result = []
    prev_blank = False
    for line in cleaned:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank
    return "\n".join(result).strip()


def lei_to_markdown(titulo: str, ementa: str, corpo: str, url: str,
                    tipo: str = "", numero: str = "", data: str = "",
                    situacao: str = "") -> str:
    """Gera o Markdown da lei."""
    # Extrai info do titulo se nao veio separado
    if not tipo or not numero:
        m = re.match(r'^(.+?)\s+([\d.]+),?\s+[dD][eE]\s+(.+)', titulo)
        if m:
            tipo_num = m.group(1)
            data_str = m.group(3).strip()
            if not tipo:
                tipo = tipo_num
            if not data:
                data = data_str

    lines = [
        f"# {titulo}",
        "",
        f"**Tipo:** {tipo}",
        f"**Número:** {numero}",
        f"**Data:** {data}",
        f"**Situação:** {situacao}",
        f"**URL:** {url}",
        "",
    ]

    if ementa:
        lines += ["## Ementa", "", ementa.strip(), ""]

    if corpo:
        lines += ["## Texto Completo", "", corpo.strip()]

    return "\n".join(lines)


async def wait_cloudflare(page, timeout=30000) -> bool:
    try:
        await page.wait_for_function(
            r"""() => {
                const t = document.title;
                return !t.includes('momento') && !t.includes('Checking')
                    && !t.includes('Just a moment')
                    && document.querySelectorAll('a[href]').length > 5;
            }""",
            timeout=timeout, polling=2000,
        )
        return True
    except Exception:
        return False


async def wait_lei_loaded(page, timeout=30000) -> bool:
    """Aguarda o conteudo da lei carregar (reCAPTCHA resolver automaticamente)."""
    try:
        await page.wait_for_function(
            r"""() => {
                const mainCol = document.querySelector('.col-md-8.col-print-12, .col-sm-12.col-md-8');
                if (!mainCol) return false;
                const txt = mainCol.innerText || '';
                // Verifica que o texto da lei esta la (tem 'Art.' ou numero da lei)
                return txt.length > 200 && (txt.includes('Art.') || txt.includes('LEI') || txt.includes('DECRETO'));
            }""",
            timeout=timeout, polling=2000,
        )
        return True
    except Exception:
        return False


async def collect_links(page, page_num: int) -> list:
    url = LIST_URL.format(page=page_num)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception:
        pass

    await wait_cloudflare(page, timeout=20000)
    await page.wait_for_timeout(1000)

    links = await page.evaluate(r"""() => {
        // Pega links unicos de leis da cidade
        const seen = new Set();
        const result = [];
        for (const a of document.querySelectorAll('a[href*="/a/sc/n/nova-veneza"]')) {
            const h = a.href.split('?')[0].split('#')[0];
            if (!seen.has(h)) {
                seen.add(h);
                result.push(h);
            }
        }
        return result;
    }""")

    return links


async def scrape_lei(page, url: str) -> dict | None:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        print(f"    [ERRO goto] {e}")
        return None

    await wait_cloudflare(page, timeout=20000)

    # Aguarda o reCAPTCHA invisible resolver (Camoufox faz isso automaticamente)
    loaded = await wait_lei_loaded(page, timeout=30000)
    if not loaded:
        # Tenta aguardar mais um pouco
        await page.wait_for_timeout(5000)
        loaded = await wait_lei_loaded(page, timeout=10000)

    if not loaded:
        print(f"    [AVISO] Conteudo pode nao ter carregado completamente")

    await page.wait_for_timeout(500)

    data = await page.evaluate("""() => {
        // Titulo
        let titulo = '';
        const mainCol = document.querySelector('.col-md-8.col-print-12')
                     || document.querySelector('.col-sm-12.col-md-8');

        if (mainCol) {
            // Primeiro h2 ou h1 dentro do mainCol
            const h = mainCol.querySelector('h1, h2, h3');
            if (h) titulo = h.innerText.trim();
        }
        if (!titulo) {
            titulo = document.title.replace(/ - LeisMunicipais.*/, '').trim();
        }

        // Texto principal
        let corpo = '';
        if (mainCol) {
            // Remove elements de UI que nao sao conteudo
            const clone = mainCol.cloneNode(true);
            const uiSelectors = [
                '[class*="options"]', '[class*="share"]', '[class*="banner"]',
                '[class*="favorite"]', '[class*="anotacao"]', '[class*="acessib"]',
                '.hidden-print', '.auxnav', '.btn', 'script', 'style',
                '[class*="follow"]', '[class*="vinculado"]', '[class*="chart"]',
                '[class*="sumario"]',
            ];
            for (const sel of uiSelectors) {
                for (const el of clone.querySelectorAll(sel)) el.remove();
            }
            corpo = clone.innerText.trim();
        }

        // Situacao (norma em vigor ou revogada)
        const situacaoEl = document.querySelector('.url');
        const situacao = situacaoEl ? situacaoEl.innerText.trim() : '';

        // Data de insercao
        const allText = document.body.innerText;
        const dataMatch = allText.match(/Data de Insercao[^:]*:\\s*([^\\n]+)/i)
                       || allText.match(/(\\d{2}\\/\\d{2}\\/\\d{4})/);
        const data = dataMatch ? dataMatch[1] : '';

        return { titulo, corpo, situacao, data, url: window.location.href };
    }""")

    if not data:
        return None

    # Limpa o corpo
    data["corpo"] = clean_text(data.get("corpo", ""))

    # Extrai metadados do titulo
    titulo = data.get("titulo", "")
    tipo = ""
    numero = ""
    data_lei = data.get("data", "")

    m = re.match(r'^(Lei\s+\w+|Decreto\s*\w*|Resolucao|Portaria)\s+[Nn][-°.\s]?\s*([\d.]+)', titulo, re.IGNORECASE)
    if m:
        tipo = m.group(1)
        numero = m.group(2)

    return {
        "titulo": titulo,
        "tipo": tipo,
        "numero": numero,
        "data": data_lei,
        "situacao": data.get("situacao", ""),
        "corpo": data.get("corpo", ""),
        "url": data.get("url", url),
    }


async def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("=" * 60)
    print("  SCRAPER - LEIS DE NOVA VENEZA - SC")
    print("=" * 60)
    print(f"  Output: {OUTPUT_DIR.absolute()}")
    print(f"  Total paginas: {TOTAL_PAGES}")
    print()

    async with AsyncCamoufox(headless=HEADLESS, geoip=True) as browser:
        page = await browser.new_page()

        # ── FASE 1: Coleta de links ──────────────────────────────────
        all_links = []
        start_page = 1
        
        if LINKS_CACHE.exists():
            with open(LINKS_CACHE, encoding="utf-8") as f:
                all_links = json.load(f)
            print(f"[CACHE] {len(all_links)} links carregados de {LINKS_CACHE}")
            
            # Se tem menos links do que esperado, retoma de onde parou
            start_page = (len(all_links) // 10) + 1

        if start_page <= TOTAL_PAGES:
            print(f"\n[FASE 1] Coletando links (pag {start_page} ate {TOTAL_PAGES})...")
            
            # Abre a pagina para passar pelo Cloudflare se for comecar a buscar
            await page.goto(LIST_URL.format(page=start_page), wait_until="domcontentloaded", timeout=60000)
            ok = await wait_cloudflare(page, timeout=60000)
            if not ok:
                input("[MANUAL] Resolva o Cloudflare e aperte ENTER: ")
            
            print("[OK] Sessao pronta. Iniciando...\n")

            for pg in range(start_page, TOTAL_PAGES + 1):
                links = await collect_links(page, pg)
                new_links = [l for l in links if l not in all_links]
                all_links.extend(new_links)

                pct = pg / TOTAL_PAGES * 100
                print(f"  Pag {pg:4d}/{TOTAL_PAGES} | +{len(new_links):2d} | Total: {len(all_links):6d} | {pct:.1f}%")

                if pg % 50 == 0:
                    with open(LINKS_CACHE, "w", encoding="utf-8") as f:
                        json.dump(all_links, f, ensure_ascii=False)
                    print(f"  [CHECKPOINT] {len(all_links)} links salvos.")

                await page.wait_for_timeout(int(DELAY_LIST * 1000))

            with open(LINKS_CACHE, "w", encoding="utf-8") as f:
                json.dump(all_links, f, ensure_ascii=False)
            print(f"\n[FASE 1] Concluida! {len(all_links)} links foram coletados no total.")

        # ── FASE 2: Scraping ─────────────────────────────────────────
        print(f"\n[FASE 2] Scraping de {len(all_links)} leis...")
        print()

        done_filenames = {f.stem for f in OUTPUT_DIR.glob("*.md")}
        todo = [l for l in all_links if url_to_filename(l) not in done_filenames]

        print(f"  Ja baixadas: {len(all_links) - len(todo)}")
        print(f"  Pendentes:   {len(todo)}")
        print()

        if not todo:
            print("[CONCLUIDO] Todas as leis ja foram baixadas!")
            return

        # Precisa passar pelo Cloudflare antes de comecar
        print("[INFO] Abrindo pagina inicial para garantir sessao valida...")
        await page.goto(LIST_URL.format(page=1), wait_until="domcontentloaded", timeout=60000)
        ok = await wait_cloudflare(page, timeout=60000)
        if not ok:
            input("[MANUAL] Resolva o Cloudflare e aperte ENTER: ")
        print("[OK] Sessao pronta!\n")

        errors = []
        start_time = time.time()

        for i, url in enumerate(todo, 1):
            filename = url_to_filename(url)
            filepath = OUTPUT_DIR / f"{filename}.md"

            # Nome curto para display
            display = url.split("/a/sc/n/nova-veneza/")[-1][:70]
            print(f"  [{i:5d}/{len(todo)}] {display}")

            try:
                data = await scrape_lei(page, url)
                if data and (data.get("corpo") or data.get("titulo")):
                    md = lei_to_markdown(
                        titulo=data.get("titulo", filename),
                        ementa="",
                        corpo=data.get("corpo", ""),
                        url=data.get("url", url),
                        tipo=data.get("tipo", ""),
                        numero=data.get("numero", ""),
                        data=data.get("data", ""),
                        situacao=data.get("situacao", ""),
                    )
                    filepath.write_text(md, encoding="utf-8")
                    print(f"         [OK] {len(data.get('corpo',''))} chars")
                else:
                    errors.append(url)
                    print(f"         [VAZIO] Sem conteudo")
            except Exception as e:
                errors.append(url)
                print(f"         [ERRO] {e}")

            await page.wait_for_timeout(int(DELAY_DETAIL * 1000))

            # Progresso a cada 100
            if i % 100 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                remaining = (len(todo) - i) / rate / 60
                done = len(list(OUTPUT_DIR.glob("*.md")))
                print(f"\n  [PROGRESSO] {done} arquivos | {len(errors)} erros | ~{remaining:.0f}min restantes\n")

        print()
        print("=" * 60)
        print("  CONCLUIDO!")
        total_md = len(list(OUTPUT_DIR.glob("*.md")))
        print(f"  Arquivos .md salvos: {total_md}")
        print(f"  Erros: {len(errors)}")
        print(f"  Local: {OUTPUT_DIR.absolute()}")
        print("=" * 60)

        if errors:
            err_file = Path("errors.json")
            with open(err_file, "w", encoding="utf-8") as f:
                json.dump(errors, f, ensure_ascii=False, indent=2)
            print(f"\n  URLs com erro: {err_file}")


asyncio.run(main())
