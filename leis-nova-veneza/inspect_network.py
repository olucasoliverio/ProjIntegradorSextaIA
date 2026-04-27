# -*- coding: utf-8 -*-
"""
inspect_network.py - Intercepta requests de rede para descobrir a API das leis
Execucao: python inspect_network.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import asyncio
import json
from camoufox.async_api import AsyncCamoufox

TEST_URL = "https://leismunicipais.com.br/a/sc/n/nova-veneza/lei-ordinaria/2026/320/3198/lei-ordinaria-n-3198-2026-autoriza-a-doacao-de-veiculo-e-demais-bens-moveis-do-municipio-de-nova-veneza-sc-ao-estado-de-santa-catarina-por-intermedio-do-fundo-de-melhoria-da-policia-civil-fumpc-e-da-outras-providencias"

captured = []

async def main():
    async with AsyncCamoufox(headless=False, geoip=True) as browser:
        page = await browser.new_page()

        # Intercepta todas as requests
        async def on_request(request):
            url = request.url
            if any(x in url for x in ['api', 'json', 'lei', 'law', 'content', 'texto', 'norma', 'ajax']):
                captured.append({
                    'method': request.method,
                    'url': url,
                    'headers': dict(request.headers),
                })

        async def on_response(response):
            url = response.url
            if any(x in url for x in ['api', 'json', 'lei', 'law', 'content', 'texto', 'norma', 'ajax']):
                try:
                    body = await response.text()
                    captured.append({
                        'type': 'response',
                        'status': response.status,
                        'url': url,
                        'body_preview': body[:500],
                    })
                except:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # Passa pelo Cloudflare
        await page.goto("https://leismunicipais.com.br/legislacao-municipal/4656/leis-de-nova-veneza", wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_function("() => !document.title.includes('momento') && document.querySelectorAll('a').length > 10", timeout=60000, polling=2000)
            print("Cloudflare OK!")
        except:
            input("Resolva Cloudflare e aperte ENTER: ")

        # Limpa o log e acessa a lei
        captured.clear()
        print("Abrindo pagina da lei e interceptando requests...")
        await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=30000)

        # Aguarda 15s para o JS fazer todas as requests
        print("Aguardando 15s para capturar requests...")
        await page.wait_for_timeout(15000)

        print(f"\n=== REQUESTS CAPTURADAS ({len(captured)}) ===")
        for r in captured:
            if r.get('type') == 'response':
                print(f"\n[RESP {r['status']}] {r['url']}")
                print(f"  Body: {r['body_preview'][:300]}")
            else:
                print(f"\n[REQ {r.get('method','')}] {r['url']}")

        # Tambem mostra TODAS as requests (nao filtradas)
        all_reqs = []
        page2 = await browser.new_page()

        async def capture_all(request):
            all_reqs.append({'method': request.method, 'url': request.url})
        page2.on("request", capture_all)

        await page2.goto(TEST_URL, wait_until="domcontentloaded", timeout=30000)
        await page2.wait_for_timeout(12000)

        print(f"\n=== TODAS AS REQUESTS ({len(all_reqs)}) ===")
        for r in all_reqs:
            print(f"  [{r['method']}] {r['url']}")

        with open("network_log.json", "w", encoding="utf-8") as f:
            json.dump({'filtered': captured, 'all': all_reqs}, f, ensure_ascii=False, indent=2)
        print("\nLog salvo em network_log.json")

        input("\nAperte ENTER para fechar...")

asyncio.run(main())
