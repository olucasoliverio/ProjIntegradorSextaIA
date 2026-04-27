# -*- coding: utf-8 -*-
"""
inspect_camoufox.py - Inspeciona leismunicipais.com.br usando Camoufox
Camoufox eh um Firefox modificado especificamente para bypassar Cloudflare.

Execucao: python inspect_camoufox.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import asyncio
import json
from camoufox.async_api import AsyncCamoufox

URL_LIST = "https://leismunicipais.com.br/legislacao-municipal/4656/leis-de-nova-veneza?q=&types=28&types=4&types=5&types=35&types=228&types=229&types=230"


async def main():
    print("🦊 Iniciando Camoufox (Firefox stealth)...")
    print("   Aguarde — pode levar alguns segundos para passar pelo Cloudflare.\n")

    async with AsyncCamoufox(headless=False, geoip=True) as browser:
        page = await browser.new_page()

        print("🌐 Abrindo o site...")
        await page.goto(URL_LIST, wait_until="domcontentloaded", timeout=60000)

        # Aguarda o Cloudflare resolver
        print("⏳ Aguardando Cloudflare... (até 60s)")
        try:
            await page.wait_for_function(
                """() => {
                    const title = document.title;
                    return !title.includes('momento') &&
                           !title.includes('Checking') &&
                           document.querySelectorAll('a[href]').length > 10;
                }""",
                timeout=60000,
                polling=2000,
            )
            print("✅ Cloudflare passou!\n")
        except Exception:
            print("⚠️  Timeout no Cloudflare. Continuando mesmo assim...\n")

        await page.wait_for_timeout(2000)

        title = await page.title()
        url = page.url
        print(f"📊 Título: {title}")
        print(f"🔗 URL: {url}")

        if "momento" in title.lower():
            print("\n❌ Ainda no Cloudflare :(")
            input("Resolva manualmente e aperte ENTER para continuar...")

        # ===== INSPEÇÃO =====
        data = await page.evaluate("""() => {
            const info = {
                totalText: null,
                classes: [],
                listItems: {},
                links: [],
                paging: [],
                bodyText: document.body.innerText.substring(0, 3000),
            };

            // Total de leis
            const m = document.body.innerText.match(/[\\d.,]+\\s*(result|lei|legislaç)/i);
            info.totalText = m ? m[0] : null;

            // Classes
            info.classes = [...new Set(
                [...document.querySelectorAll('*')]
                    .map(el => el.className)
                    .filter(c => typeof c === 'string')
                    .flatMap(c => c.split(/\\s+/))
                    .filter(Boolean)
            )].slice(0, 200);

            // Seletores de lista
            const sels = ['li', 'article', 'tr', '[class*="item"]', '[class*="result"]',
                '[class*="lei"]', '[class*="law"]', '[class*="card"]', 'ul > li', 'ol > li'];
            for (const sel of sels) {
                const els = document.querySelectorAll(sel);
                if (els.length >= 2 && els.length <= 300) {
                    info.listItems[sel] = {
                        count: els.length,
                        html: els[0].outerHTML.substring(0, 800),
                        text: (els[0].innerText || '').substring(0, 300),
                    };
                }
            }

            // Links de leis
            info.links = Array.from(document.querySelectorAll('a[href]'))
                .map(a => ({ href: a.href, text: (a.innerText || '').trim().substring(0, 120) }))
                .filter(a => a.href.includes('leismunicipais') || a.href.includes('/lei') || a.href.includes('/leis'))
                .slice(0, 30);

            // Paginação
            const pagEls = [];
            for (const sel of ['[class*="pag"] a', '[class*="page"] a', 'nav a', 'a[rel="next"]', '.next a']) {
                for (const el of document.querySelectorAll(sel)) {
                    pagEls.push({ text: (el.innerText||'').trim(), href: el.href||'', cls: el.className });
                }
            }
            info.paging = pagEls.slice(0, 15);

            return info;
        }""")

        print(f"\n📋 Total mencionado: {data['totalText'] or 'não encontrado'}")
        print(f"\n🏷️  Classes ({len(data['classes'])} únicas):")
        print(" | ".join(data["classes"][:80]))

        print(f"\n📦 Seletores de lista ({len(data['listItems'])} encontrados):")
        for sel, info in data["listItems"].items():
            print(f"\n  \"{sel}\" → {info['count']} elementos")
            print(f"  Texto: {info['text'][:200].replace(chr(10), ' | ')}")
            print(f"  HTML: {info['html'][:400].replace(chr(10), ' ')}")

        print(f"\n🔗 Links ({len(data['links'])}):")
        for l in data["links"]:
            print(f"  \"{l['text']}\" → {l['href']}")

        print(f"\n📄 Paginação ({len(data['paging'])}):")
        for p in data["paging"]:
            print(f"  [{p['cls']}] \"{p['text']}\" → {p['href']}")

        print(f"\n📝 Texto da página:")
        print(data["bodyText"])

        # Salva HTML
        html = await page.content()
        with open("inspect_full.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("\n💾 HTML salvo em inspect_full.html")

        # Salva JSON com os dados
        with open("inspect_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("💾 Dados salvos em inspect_data.json")

        input("\nAperte ENTER para fechar...")


asyncio.run(main())
