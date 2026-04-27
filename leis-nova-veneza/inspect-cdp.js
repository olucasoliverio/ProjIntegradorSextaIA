/**
 * inspect-cdp.js — Conecta ao Chrome REAL já aberto via CDP
 * 
 * PASSO 1: Feche todo Chrome aberto.
 * PASSO 2: Abra o Chrome manualmente com este comando no terminal:
 *   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --no-first-run --no-default-browser-check
 * PASSO 3: No Chrome aberto, acesse o site manualmente e passe o Cloudflare.
 * PASSO 4: Rode este script: node inspect-cdp.js
 */
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  console.log('🔌 Conectando ao Chrome via CDP na porta 9222...');
  console.log('');
  console.log('Certifique-se de que:');
  console.log('1. Chrome foi aberto com --remote-debugging-port=9222');
  console.log('2. Você acessou o site e passou pelo Cloudflare manualmente');
  console.log('');

  let browser;
  try {
    browser = await chromium.connectOverCDP('http://localhost:9222');
  } catch (e) {
    console.error('❌ Erro ao conectar:', e.message);
    console.error('');
    console.error('Abra o Chrome com:');
    console.error('"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222 --no-first-run');
    process.exit(1);
  }

  console.log('✅ Conectado ao Chrome!');

  // Pega a aba ativa (ou cria uma nova)
  const contexts = browser.contexts();
  console.log(`📋 Contextos encontrados: ${contexts.length}`);

  let page;
  for (const ctx of contexts) {
    const pages = ctx.pages();
    for (const p of pages) {
      const url = p.url();
      if (url.includes('leismunicipais')) {
        page = p;
        console.log('✅ Aba do leismunicipais encontrada:', url);
        break;
      }
    }
    if (page) break;
  }

  if (!page) {
    // Usa a primeira aba disponível
    const ctx = contexts[0] || await browser.newContext();
    const pages = ctx.pages();
    page = pages[0] || await ctx.newPage();
    console.log('ℹ️  Navegando para o site na aba atual...');
    await page.goto(
      'https://leismunicipais.com.br/legislacao-municipal/4656/leis-de-nova-veneza?q=&types=28&types=4&types=5&types=35&types=228&types=229&types=230',
      { waitUntil: 'domcontentloaded', timeout: 30000 }
    );

    // Aguarda Cloudflare resolver (o usuário pode ajudar)
    console.log('⏳ Aguardando Cloudflare resolver (até 120s)...');
    try {
      await page.waitForFunction(
        () => !document.title.includes('momento') && document.querySelectorAll('a[href]').length > 20,
        { timeout: 120000, polling: 2000 }
      );
    } catch {
      console.log('⚠️  Timeout — continuando mesmo assim...');
    }
  }

  await page.waitForTimeout(2000);

  const title = await page.title();
  const url = page.url();
  console.log('\n📊 Título:', title);
  console.log('🔗 URL:', url);

  if (title.includes('momento')) {
    console.log('\n❌ Ainda no Cloudflare. Tente passar manualmente na janela do Chrome.');
    console.log('   Aguardando 120s...');
    await page.waitForTimeout(120000);
  }

  // ===== INSPECIONA A ESTRUTURA =====
  const data = await page.evaluate(() => {
    const info = {
      totalText: (() => {
        const m = document.body.innerText.match(/[\d.,]+\s*(result|lei|legislaç)/i);
        return m ? m[0] : null;
      })(),
      classes: [...new Set(
        [...document.querySelectorAll('*')]
          .map(el => el.className)
          .filter(c => typeof c === 'string' && c.trim())
          .flatMap(c => c.split(/\s+/))
          .filter(Boolean)
      )].slice(0, 100),
      listItems: {},
      links: Array.from(document.querySelectorAll('a[href]'))
        .map(a => ({ href: a.href, text: (a.innerText || '').trim().substring(0, 120) }))
        .filter(a => a.href.length > 10)
        .slice(0, 40),
      paging: Array.from(document.querySelectorAll('[class*="pag"] a, [class*="page"] a, nav a, .next, .prev, [rel="next"], [rel="prev"]'))
        .map(el => ({ text: (el.innerText || '').trim(), href: el.href || '', cls: el.className }))
        .slice(0, 10),
    };

    // Testa seletores de lista
    for (const sel of ['li', 'article', 'tr', '.card', '[class*="item"]', '[class*="result"]', '[class*="lei"]', '[class*="card"]']) {
      const els = document.querySelectorAll(sel);
      if (els.length > 1 && els.length < 500) {
        info.listItems[sel] = { count: els.length, html: els[0].outerHTML.substring(0, 500) };
      }
    }

    return info;
  });

  console.log('\n📋 Total:', data.totalText);
  console.log('\n🏷️  Classes (primeiras 100):');
  console.log(data.classes.join(', '));
  console.log('\n📦 Seletores de lista:');
  for (const [sel, info] of Object.entries(data.listItems)) {
    console.log(`\n  "${sel}" → ${info.count} itens`);
    console.log('  HTML:', info.html.replace(/\s+/g, ' ').substring(0, 300));
  }
  console.log('\n🔗 Links:');
  data.links.forEach(l => console.log(`  "${l.text}" → ${l.href}`));
  console.log('\n📄 Paginação:');
  data.paging.forEach(p => console.log(`  "${p.text}" [${p.cls}] → ${p.href}`));

  const html = await page.content();
  fs.writeFileSync('inspect_full.html', html);
  console.log('\n💾 HTML salvo em inspect_full.html');

  await browser.close();
  console.log('✅ Concluído.');
})();
