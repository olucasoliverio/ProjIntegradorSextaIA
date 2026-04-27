# -*- coding: utf-8 -*-
"""
inspect_lei.py - Inspeciona uma lei individualmente para validar os seletores.
Execucao: python inspect_lei.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import asyncio
from camoufox.async_api import AsyncCamoufox

# URL de uma lei especifica para testar
TEST_URL = "https://leismunicipais.com.br/a/sc/n/nova-veneza/lei-ordinaria/2026/320/3198/lei-ordinaria-n-3198-2026-autoriza-a-doacao-de-veiculo-e-demais-bens-moveis-do-municipio-de-nova-veneza-sc-ao-estado-de-santa-catarina-por-intermedio-do-fundo-de-melhoria-da-policia-civil-fumpc-e-da-outras-providencias"

async def main():
    print("Abrindo Camoufox para inspecionar lei...")

    async with AsyncCamoufox(headless=False, geoip=True) as browser:
        page = await browser.new_page()

        # Primeiro passa pelo Cloudflare na pagina inicial
        print("Abrindo pagina inicial para passar pelo Cloudflare...")
        await page.goto("https://leismunicipais.com.br/legislacao-municipal/4656/leis-de-nova-veneza", wait_until="domcontentloaded", timeout=30000)

        try:
            await page.wait_for_function(
                "() => !document.title.includes('momento') && document.querySelectorAll('a[href]').length > 10",
                timeout=60000, polling=2000
            )
            print("Cloudflare passou automaticamente!")
        except:
            input("Resolva o Cloudflare e aperte ENTER: ")

        # Agora acessa a lei especifica
        print(f"\nAcessando lei: {TEST_URL[:80]}...")
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        print("\nTitulo:", await page.title())
        print("URL:", page.url)

        # Dump de todos os elementos com classes relevantes
        data = await page.evaluate("""() => {
            const result = {
                h1: document.querySelector('h1') ? document.querySelector('h1').innerText : '',
                h2: document.querySelector('h2') ? document.querySelector('h2').innerText : '',
                title_tag: document.title,
                all_classes: [...new Set([...document.querySelectorAll('*')].map(e => e.className).filter(c => typeof c === 'string').flatMap(c => c.split(' ')).filter(Boolean))],
                body_structure: [],
            };

            // Mostra os primeiros 20 blocos de texto significativos
            const paras = [...document.querySelectorAll('p, h1, h2, h3, div, article, section, pre')]
                .filter(el => el.children.length === 0 || el.querySelector('p') === null)
                .filter(el => (el.innerText || '').trim().length > 30)
                .slice(0, 20);

            result.body_structure = paras.map(el => ({
                tag: el.tagName,
                cls: el.className,
                text: (el.innerText || '').trim().substring(0, 200),
            }));

            // Tenta seletores especificos
            const trySelectors = [
                '.ementa', '[class*="ementa"]',
                '.law-text', '[class*="law-text"]',
                '.law-body', '[class*="law-body"]',
                '.body-text', '[class*="body-text"]',
                '.text-content', '[class*="text-content"]',
                '.lei-text', '[class*="lei-text"]',
                '.article-content', 'article',
                '.content-text', '.full-text',
                '[class*="content"]', '[class*="full"]',
                '.lei-content', '.law-content',
                '#law-text', '#lei-texto',
            ];

            result.selectors = {};
            for (const sel of trySelectors) {
                const el = document.querySelector(sel);
                if (el) {
                    result.selectors[sel] = {
                        tag: el.tagName,
                        cls: el.className,
                        text: (el.innerText || '').trim().substring(0, 300),
                    };
                }
            }

            return result;
        }""")

        print(f"\nH1: {data['h1'][:200]}")
        print(f"\nClasses presentes: {' | '.join(data['all_classes'][:80])}")

        print(f"\nSeletores com resultado:")
        for sel, info in data['selectors'].items():
            print(f"  {sel} [{info['tag']}.{info['cls'][:50]}]:")
            print(f"    {info['text'][:200]}")

        print(f"\nEstrutura do corpo (blocos de texto):")
        for blk in data['body_structure']:
            print(f"  [{blk['tag']}.{blk['cls'][:40]}]: {blk['text'][:150]}")

        # Salva HTML
        html = await page.content()
        with open("lei_detail.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("\nHTML salvo em lei_detail.html")

        input("\nAperte ENTER para fechar...")

asyncio.run(main())
