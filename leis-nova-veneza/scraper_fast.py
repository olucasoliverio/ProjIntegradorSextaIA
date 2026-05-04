# -*- coding: utf-8 -*-
"""
scraper_fast.py - Versão PARALELA do scraper de leis de Nova Veneza
Usa pool de N browsers Camoufox simultâneos para acelerar o download.

Retomada automática: pula leis já salvas em /leis/.

Execução: python scraper_fast.py
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
import threading
from pathlib import Path
from camoufox.async_api import AsyncCamoufox

# ===================== CONFIG =====================
CITY_ID   = 4656
CITY_SLUG = "leis-de-nova-veneza"
OUTPUT_DIR   = Path("leis")
LINKS_CACHE  = Path("links_cache.json")

# ── AJUSTE AQUI ──────────────────────────────────
# Quantos browsers paralelos abrir.
# Recomendado: comece com 3, aumente para 5 se não tomar ban.
# Cada browser usa ~200-300MB de RAM.
N_WORKERS    = 3

# Delay entre requisições POR WORKER (menor = mais rápido, maior = mais seguro)
DELAY_DETAIL = 1.5   # segundos (era 2.5 no scraper original)

HEADLESS     = False   # True = mais rápido (sem janela); False = debug visual
# ==================================================

BASE_URL = "https://leismunicipais.com.br"
LIST_URL = (
    f"{BASE_URL}/legislacao-municipal/{CITY_ID}/{CITY_SLUG}"
    "?q=&page={page}&types=28&types=4&types=5&types=35&types=228&types=229&types=230"
)

# Lock para acesso thread-safe ao contador de progresso
_print_lock = asyncio.Lock()
_counter = {"done": 0, "errors": 0, "total": 0, "start": 0.0}


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:120]


def url_to_filename(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    return slugify(slug)


def clean_text(text: str) -> str:
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
    result = []
    prev_blank = False
    for line in cleaned:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank
    return "\n".join(result).strip()


def lei_to_markdown(titulo, ementa, corpo, url, tipo="", numero="", data="", situacao="") -> str:
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
        f"# {titulo}", "",
        f"**Tipo:** {tipo}",
        f"**Número:** {numero}",
        f"**Data:** {data}",
        f"**Situação:** {situacao}",
        f"**URL:** {url}", "",
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


async def wait_lei_loaded(page, timeout=25000) -> bool:
    try:
        await page.wait_for_function(
            r"""() => {
                const mainCol = document.querySelector('.col-md-8.col-print-12, .col-sm-12.col-md-8');
                if (!mainCol) return false;
                const txt = mainCol.innerText || '';
                return txt.length > 200 && (txt.includes('Art.') || txt.includes('LEI') || txt.includes('DECRETO'));
            }""",
            timeout=timeout, polling=1500,
        )
        return True
    except Exception:
        return False


async def scrape_lei(page, url: str) -> dict | None:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        return None

    await wait_cloudflare(page, timeout=20000)

    loaded = await wait_lei_loaded(page, timeout=25000)
    if not loaded:
        await page.wait_for_timeout(3000)
        loaded = await wait_lei_loaded(page, timeout=8000)

    await page.wait_for_timeout(300)  # pequena pausa (era 500ms)

    data = await page.evaluate("""() => {
        let titulo = '';
        const mainCol = document.querySelector('.col-md-8.col-print-12')
                     || document.querySelector('.col-sm-12.col-md-8');
        if (mainCol) {
            const h = mainCol.querySelector('h1, h2, h3');
            if (h) titulo = h.innerText.trim();
        }
        if (!titulo) {
            titulo = document.title.replace(/ - LeisMunicipais.*/, '').trim();
        }
        let corpo = '';
        if (mainCol) {
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
        const situacaoEl = document.querySelector('.url');
        const situacao = situacaoEl ? situacaoEl.innerText.trim() : '';
        const allText = document.body.innerText;
        const dataMatch = allText.match(/Data de Insercao[^:]*:\\s*([^\\n]+)/i)
                       || allText.match(/(\\d{2}\\/\\d{2}\\/\\d{4})/);
        const data = dataMatch ? dataMatch[1] : '';
        return { titulo, corpo, situacao, data, url: window.location.href };
    }""")

    if not data:
        return None

    data["corpo"] = clean_text(data.get("corpo", ""))
    titulo = data.get("titulo", "")
    tipo = ""
    numero = ""

    m = re.match(r'^(Lei\s+\w+|Decreto\s*\w*|Resolucao|Portaria)\s+[Nn][-°.\s]?\s*([\d.]+)', titulo, re.IGNORECASE)
    if m:
        tipo = m.group(1)
        numero = m.group(2)

    return {
        "titulo": titulo,
        "tipo": tipo,
        "numero": numero,
        "data": data.get("data", ""),
        "situacao": data.get("situacao", ""),
        "corpo": data.get("corpo", ""),
        "url": data.get("url", url),
    }


async def worker(worker_id: int, queue: asyncio.Queue, errors: list):
    """Worker: abre um browser próprio e processa URLs da fila."""
    async with AsyncCamoufox(headless=HEADLESS, geoip=True) as browser:
        page = await browser.new_page()

        # Passa pelo Cloudflare na primeira requisição
        try:
            await page.goto(LIST_URL.format(page=1), wait_until="domcontentloaded", timeout=60000)
            await wait_cloudflare(page, timeout=30000)
        except Exception:
            pass

        while True:
            try:
                url = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            filename = url_to_filename(url)
            filepath = OUTPUT_DIR / f"{filename}.md"

            # Pula se já foi baixada (outro worker pode ter feito antes)
            if filepath.exists():
                queue.task_done()
                _counter["done"] += 1
                continue

            display = url.split("/a/sc/n/nova-veneza/")[-1][:60]

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
                    async with _print_lock:
                        _counter["done"] += 1
                        done = _counter["done"]
                        total = _counter["total"]
                        elapsed = time.time() - _counter["start"]
                        rate = done / elapsed if elapsed > 0 else 0
                        remaining_min = (total - done) / rate / 60 if rate > 0 else 0
                        print(f"  [W{worker_id}] [{done:5d}/{total}] {display} | {len(data.get('corpo',''))} chars | ~{remaining_min:.0f}min")
                else:
                    async with _print_lock:
                        _counter["errors"] += 1
                        _counter["done"] += 1
                        print(f"  [W{worker_id}] [VAZIO] {display}")
                    errors.append(url)
            except Exception as e:
                async with _print_lock:
                    _counter["errors"] += 1
                    _counter["done"] += 1
                    print(f"  [W{worker_id}] [ERRO] {display}: {e}")
                errors.append(url)

            queue.task_done()
            await asyncio.sleep(DELAY_DETAIL)


async def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("=" * 60)
    print("  SCRAPER PARALELO - LEIS DE NOVA VENEZA - SC")
    print("=" * 60)
    print(f"  Workers paralelos: {N_WORKERS}")
    print(f"  Delay por worker:  {DELAY_DETAIL}s")
    print(f"  Throughput est.:   ~{N_WORKERS / DELAY_DETAIL:.1f} leis/seg = ~{N_WORKERS / DELAY_DETAIL * 3600:.0f} leis/hora")
    print(f"  Output: {OUTPUT_DIR.absolute()}")
    print()

    # Carrega links
    if not LINKS_CACHE.exists():
        print("[ERRO] links_cache.json não encontrado! Rode o scraper.py primeiro para coletar os links.")
        return

    with open(LINKS_CACHE, encoding="utf-8") as f:
        all_links = json.load(f)
    print(f"[CACHE] {len(all_links)} links carregados.")

    # Filtra os já baixados
    done_filenames = {f.stem for f in OUTPUT_DIR.glob("*.md")}
    todo = [l for l in all_links if url_to_filename(l) not in done_filenames]

    print(f"  Já baixadas: {len(all_links) - len(todo)}")
    print(f"  Pendentes:   {len(todo)}")
    print()

    if not todo:
        print("[CONCLUIDO] Todas as leis já foram baixadas!")
        return

    # Estima tempo
    est_min = len(todo) / (N_WORKERS / DELAY_DETAIL) / 60
    print(f"  Tempo estimado: ~{est_min:.0f} minutos ({est_min/60:.1f} horas)")
    print()

    # Monta a fila
    queue = asyncio.Queue()
    for url in todo:
        await queue.put(url)

    _counter["total"] = len(todo)
    _counter["done"] = 0
    _counter["errors"] = 0
    _counter["start"] = time.time()

    errors = []

    print(f"[START] Iniciando {N_WORKERS} workers...\n")

    # Lança workers em paralelo
    tasks = [
        asyncio.create_task(worker(i + 1, queue, errors))
        for i in range(N_WORKERS)
    ]
    await asyncio.gather(*tasks)

    # Relatório final
    elapsed = time.time() - _counter["start"]
    print()
    print("=" * 60)
    print("  CONCLUÍDO!")
    total_md = len(list(OUTPUT_DIR.glob("*.md")))
    print(f"  Arquivos .md salvos: {total_md}")
    print(f"  Erros:               {len(errors)}")
    print(f"  Tempo total:         {elapsed/60:.1f} minutos")
    print(f"  Velocidade média:    {_counter['done'] / elapsed:.2f} leis/seg")
    print(f"  Local: {OUTPUT_DIR.absolute()}")
    print("=" * 60)

    if errors:
        err_file = Path("errors.json")
        with open(err_file, "w", encoding="utf-8") as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)
        print(f"\n  URLs com erro salvas em: {err_file}")


asyncio.run(main())
