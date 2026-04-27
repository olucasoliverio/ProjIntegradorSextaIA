# -*- coding: utf-8 -*-
"""
inspect_lei_final.py - Captura a lei APOS o reCAPTCHA resolver (URL?pass=TOKEN)
Monitora o redirecionamento e salva o HTML final com o conteudo real.
Execucao: python inspect_lei_final.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import asyncio
import json
import re
from camoufox.async_api import AsyncCamoufox

TEST_URL = "https://leismunicipais.com.br/a/sc/n/nova-veneza/lei-ordinaria/2026/320/3198/lei-ordinaria-n-3198-2026-autoriza-a-doacao-de-veiculo-e-demais-bens-moveis-do-municipio-de-nova-veneza-sc-ao-estado-de-santa-catarina-por-intermedio-do-fundo-de-melhoria-da-policia-civil-fumpc-e-da-outras-providencias"

async def main():
    async with AsyncCamoufox(headless=False, geoip=True) as browser:
        page = await browser.new_page()

        # Cloudflare na pagina inicial
        await page.goto("https://leismunicipais.com.br/legislacao-municipal/4656/leis-de-nova-veneza", wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_function("() => !document.title.includes('momento') && document.querySelectorAll('a').length > 10", timeout=60000, polling=2000)
            print("Cloudflare OK!")
        except:
            input("Resolva Cloudflare e aperte ENTER: ")

        # Agora acessa a lei
        print("Abrindo lei...")
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=30000)

        # Aguarda o reCAPTCHA resolver e redirecionar (URL muda para ?pass=TOKEN)
        print("Aguardando reCAPTCHA resolver e redirecionar (ate 60s)...")
        print("O browser vai redirecionar automaticamente com ?pass=TOKEN na URL...")

        try:
            await page.wait_for_function(
                "() => window.location.search.includes('pass=')",
                timeout=60000, polling=1000
            )
            print("Redirecionamento detectado!")
        except Exception as e:
            print(f"Timeout: {e}")
            print("URL atual:", page.url)

        await page.wait_for_timeout(3000)

        final_url = page.url
        print(f"\nURL final: {final_url}")
        print(f"Titulo: {await page.title()}")

        # Agora inspeciona o conteudo real
        data = await page.evaluate("""() => {
            const info = {
                title: document.title,
                url: window.location.href,
                allText: document.body.innerText.trim().substring(0, 8000),
                classes: [...new Set([...document.querySelectorAll('*')].map(e=>e.className).filter(c=>typeof c==='string').flatMap(c=>c.split(' ')).filter(Boolean))],
                selectors: {},
            };

            // Testa todos os seletores possiveis
            const sels = [
                '.norma', '[class*="norma"]', '.lei', '[class*="lei"]',
                '.law', '[class*="law"]', '.texto', '[class*="texto"]',
                'pre', '.pre', '.content', '#content',
                '.lei-content', '.law-content', '.full-text',
                '.article-content', 'article main', 'main',
                '.body', '.law-body', '.norma-body',
                '[id*="lei"]', '[id*="law"]', '[id*="norma"]',
                '.col-md-8', '.col-md-9', '.col-md-10',
                'h1', 'h2', 'h3',
            ];

            for (const sel of sels) {
                const el = document.querySelector(sel);
                if (el) {
                    const t = (el.innerText || '').trim();
                    if (t.length > 20) {
                        info.selectors[sel] = { tag: el.tagName, cls: el.className, text: t.substring(0, 500) };
                    }
                }
            }

            return info;
        }""")

        print(f"\nClasses: {' | '.join(data['classes'][:80])}")
        print(f"\nSeletores com conteudo:")
        for sel, info in data['selectors'].items():
            print(f"\n  [{sel}] {info['tag']}.{info['cls'][:50]}:")
            print(f"    {info['text'][:300]}")

        print(f"\nTexto completo (8000 chars):\n{data['allText']}")

        html = await page.content()
        with open("lei_final.html", "w", encoding="utf-8") as f:
            f.write(html)
        with open("lei_final_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("\nHML salvo em lei_final.html")
        print("JSON salvo em lei_final_data.json")

        input("\nAperte ENTER para fechar...")

asyncio.run(main())
