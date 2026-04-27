/**
 * inspect.js — Inspeciona a estrutura HTML do leismunicipais.com.br
 * Roda HEADFUL (com janela visível) para passar pelo Cloudflare manualmente.
 * Execução: node inspect.js
 */
const { chromium } = require('playwright');
const fs = require('fs');

const URL_LIST = 'https://leismunicipais.com.br/legislacao-municipal/4656/leis-de-nova-veneza?q=&types=28&types=4&types=5&types=35&types=228&types=229&types=230';

(async () => {
  const browser = await chromium.launch({
    headless: false,
    args: [
      '--disable-blink-features=AutomationControlled',
      '--no-sandbox',
      '--start-maximized',
    ],
  });

  const context = await browser.newContext({
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 900 },
    locale: 'pt-BR',
  });

  const page = await context.newPage();

  // Remove navigator.webdriver flag
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });

  console.log('🔍 Abrindo página de listagem...');
  console.log('⚠️  Se aparecer desafio Cloudflare, resolve manualmente na janela do browser!');

  // Navega sem esperar networkidle (evita timeout em sites pesados)
  await page.goto(URL_LIST, { waitUntil: 'domcontentloaded', timeout: 60000 });

  // Aguarda a lista de leis carregar — espera por qualquer elemento com links
  console.log('⏳ Aguardando conteúdo carregar (até 60s)...');
  try {
    await page.waitForFunction(
      () => document.querySelectorAll('a[href*="/lei"]').length > 5,
      { timeout: 60000 }
    );
    console.log('✅ Conteúdo carregado!');
  } catch {
    console.log('⚠️  Timeout esperando links /lei — tentando continuar mesmo assim...');
  }

  await page.waitForTimeout(2000);

  console.log('\n📊 Título da página:', await page.title());
  console.log('🔗 URL atual:', page.url());

  // Busca texto com total de resultados
  const totalText = await page.evaluate(() => {
    const body = document.body.innerText;
    const m = body.match(/[\d.,]+\s*(result|leis?|legisl|legislaç)/i);
    return m ? m[0] : 'não encontrado';
  });
  console.log('📋 Total mencionado:', totalText);

  // Inspeciona candidatos a selector de item de lista
  const listInfo = await page.evaluate(() => {
    const candidates = [
      'li.result-item', '.result-item', '.law-item', '.lei-item',
      'article', '.list-item', '.listagem li', '.search-results li',
      '.results-list li', 'ul > li', '.listagem-leis li',
      '[class*="lei"]', '[class*="result"]', '[class*="item"]',
    ];
    const out = {};
    for (const sel of candidates) {
      const els = document.querySelectorAll(sel);
      if (els.length > 0) {
        out[sel] = {
          count: els.length,
          html: els[0].outerHTML.substring(0, 600),
        };
      }
    }
    return out;
  });

  console.log('\n🏷️  Seletores com resultados:');
  for (const [sel, info] of Object.entries(listInfo)) {
    console.log(`\n  "${sel}" → ${info.count} elementos`);
    if (info.count < 50) console.log('  HTML:', info.html.replace(/\s+/g, ' '));
  }

  // Links de leis
  const links = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a[href]'))
      .map(a => ({ href: a.href, text: a.innerText?.trim().substring(0, 100) || '' }))
      .filter(a => a.href.includes('/lei'))
      .slice(0, 15);
  });
  console.log('\n🔗 Links de leis (primeiros 15):');
  links.forEach(l => console.log(`  "${l.text}" → ${l.href}`));

  // Paginação
  const paging = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('[class*="pag"] a, [class*="page"] a, nav a, .next, .prev'))
      .slice(0, 10)
      .map(el => ({ tag: el.tagName, cls: el.className, text: el.innerText?.trim(), href: el.href || '' }));
  });
  console.log('\n📄 Paginação:');
  paging.forEach(p => console.log(`  ${p.tag}.${p.cls} → "${p.text}" → ${p.href}`));

  // Salva HTML completo para análise offline
  const html = await page.content();
  fs.writeFileSync('inspect_output.html', html);
  console.log('\n💾 HTML completo salvo em inspect_output.html');

  console.log('\n⏸️  Browser aberto por mais 60s para você inspecionar manualmente...');
  await page.waitForTimeout(60000);

  await browser.close();
  console.log('✅ Concluído.');
})();
