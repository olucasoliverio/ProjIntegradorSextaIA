# -*- coding: utf-8 -*-
"""
inspect_lei2.py - Inspeciona lei aguardando carregamento dinamico do JS
Execucao: python inspect_lei2.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import asyncio
from camoufox.async_api import AsyncCamoufox

TEST_URL = "https://leismunicipais.com.br/a/sc/n/nova-veneza/lei-ordinaria/2026/320/3198/lei-ordinaria-n-3198-2026-autoriza-a-doacao-de-veiculo-e-demais-bens-moveis-do-municipio-de-nova-veneza-sc-ao-estado-de-santa-catarina-por-intermedio-do-fundo-de-melhoria-da-policia-civil-fumpc-e-da-outras-providencias"

async def main():
    async with AsyncCamoufox(headless=False, geoip=True) as browser:
        page = await browser.new_page()

        # Passa pelo Cloudflare primeiro
        await page.goto("https://leismunicipais.com.br/legislacao-municipal/4656/leis-de-nova-veneza", wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_function("() => !document.title.includes('momento') && document.querySelectorAll('a').length > 10", timeout=60000, polling=2000)
            print("Cloudflare OK!")
        except:
            input("Resolva Cloudflare e aperte ENTER: ")

        # Acessa a lei
        print(f"Abrindo lei...")
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=30000)

        # Aguarda o conteudo dinamico carregar (subtitle muda de "carregando" para conteudo real)
        print("Aguardando JS carregar o conteudo (ate 30s)...")
        try:
            await page.wait_for_function(
                """() => {
                    const sub = document.querySelector('.subtitle');
                    if (!sub) return false;
                    const t = sub.innerText || '';
                    return t.length > 10 && !t.includes('carregada') && !t.includes('carregando');
                }""",
                timeout=30000, polling=1000
            )
            print("Conteudo carregado!")
        except Exception as e:
            print(f"Timeout ou erro: {e}")

        await page.wait_for_timeout(2000)

        # Dump completo da estrutura
        data = await page.evaluate("""() => {
            const result = {
                title: document.querySelector('.title') ? document.querySelector('.title').innerText.trim() : '',
                subtitle: document.querySelector('.subtitle') ? document.querySelector('.subtitle').innerText.trim() : '',
                all_classes: [...new Set([...document.querySelectorAll('*')].map(e=>e.className).filter(c=>typeof c==='string').flatMap(c=>c.split(' ')).filter(Boolean))],
                selectors_found: {},
                body_blocks: [],
                full_text: document.body.innerText.trim().substring(0, 5000),
            };

            // Testa seletores
            const sels = [
                '.title', '.subtitle', '.wrp', '.content', '.text', '.law-text',
                '.article-content', 'article', '.main', '#content', '.lei-content',
                '[class*="text"]', '[class*="body"]', '[class*="lei"]', '[class*="law"]',
                '[class*="article"]', '[class*="norma"]', '[class*="ementa"]',
                '.col-md-8', '.col-md-12:not(.links):not(.copyright)',
                'pre', '.pre', '[class*="pre"]',
            ];
            for (const sel of sels) {
                const els = document.querySelectorAll(sel);
                if (els.length > 0) {
                    result.selectors_found[sel] = {
                        count: els.length,
                        tag: els[0].tagName,
                        cls: els[0].className,
                        text: (els[0].innerText || '').trim().substring(0, 400),
                    };
                }
            }

            // Blocos de texto
            result.body_blocks = [...document.querySelectorAll('*')]
                .filter(el => {
                    const t = (el.innerText || '').trim();
                    return t.length > 50 && el.children.length < 5;
                })
                .slice(0, 25)
                .map(el => ({
                    tag: el.tagName,
                    cls: el.className,
                    text: (el.innerText || '').trim().substring(0, 300),
                }));

            return result;
        }""")

        print(f"\nTitle: {data['title']}")
        print(f"Subtitle: {data['subtitle'][:300]}")
        print(f"\nClasses: {' | '.join(data['all_classes'][:60])}")

        print(f"\nSeletores encontrados:")
        for sel, info in data['selectors_found'].items():
            if info['text']:  # so mostra se tem texto
                print(f"  [{sel}] {info['tag']}.{info['cls'][:50]}: {info['text'][:200]}")

        print(f"\nTexto completo da pagina (primeiros 5000 chars):")
        print(data['full_text'])

        html = await page.content()
        with open("lei_detail2.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("\nHTML salvo em lei_detail2.html")

        input("\nAperte ENTER para fechar...")

asyncio.run(main())
