/**
 * inspect-manual.js
 * Abre o site, você resolve o Cloudflare manualmente, aperta Enter, e o script inspeciona.
 * 
 * Execução: node inspect-manual.js
 */
const { chromium } = require('playwright');
const fs = require('fs');
const readline = require('readline');

const URL_LIST = 'https://leismunicipais.com.br/legislacao-municipal/4656/leis-de-nova-veneza?q=&types=28&types=4&types=5&types=35&types=228&types=229&types=230';

function waitForEnter(msg) {
  return new Promise(resolve => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    rl.question(msg, () => { rl.close(); resolve(); });
  });
}

(async () => {
  console.log('🚀 Iniciando Chromium...');

  const context = await chromium.launchPersistentContext(
    __dirname + '/chrome-profile-inspect',
    {
      headless: false,
      args: [
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--start-maximized',
      ],
      ignoreDefaultArgs: ['--enable-automation'],
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
      viewport: null,
      locale: 'pt-BR',
    }
  );

  const page = await context.newPage();

  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    window.chrome = { runtime: {} };
  });

  console.log('🌐 Abrindo o site...\n');
  try {
    await page.goto(URL_LIST, { waitUntil: 'domcontentloaded', timeout: 30000 });
  } catch {}

  console.log('====================================================');
  console.log('  SE APARECER O CLOUDFLARE NA JANELA DO BROWSER:');
  console.log('  Aguarde ele resolver (geralmente automático ~5s).');
  console.log('  Se aparecer checkbox, clique nele.');
  console.log('====================================================\n');

  await waitForEnter('Quando a LISTA DE LEIS aparecer, aperte ENTER aqui: ');

  console.log('\n🔍 Inspecionando página...');
  await page.waitForTimeout(2000);

  const title = await page.title();
  const url = page.url();
  console.log('📊 Título:', title);
  console.log('🔗 URL:', url);

  // Inspeciona a estrutura
  const data = await page.evaluate(() => {
    const info = {
      totalText: null,
      classes: [],
      listItems: {},
      links: [],
      paging: [],
      bodyText: document.body.innerText.substring(0, 2000),
    };

    // Total
    const bodyText = document.body.innerText;
    const m = bodyText.match(/[\d.,]+\s*(result|lei|legislaç)/i);
    info.totalText = m ? m[0] : null;

    // Classes únicas
    info.classes = [...new Set(
      [...document.querySelectorAll('*')]
        .map(el => el.className)
        .filter(c => typeof c === 'string')
        .flatMap(c => c.split(/\s+/))
        .filter(Boolean)
    )].slice(0, 150);

    // Seletores de lista
    const sels = [
      'li', 'article', 'tr', '.card', '[class*="item"]', '[class*="result"]',
      '[class*="lei"]', '[class*="law"]', '[class*="card"]', '[class*="row"]',
      'ul > li', 'ol > li',
    ];
    for (const sel of sels) {
      const els = document.querySelectorAll(sel);
      if (els.length >= 2 && els.length <= 300) {
        info.listItems[sel] = {
          count: els.length,
          html: els[0].outerHTML.substring(0, 600),
          text: (els[0].innerText || '').substring(0, 200),
        };
      }
    }

    // Links
    info.links = Array.from(document.querySelectorAll('a[href]'))
      .map(a => ({ href: a.href, text: (a.innerText || '').trim().substring(0, 120) }))
      .filter(a => a.href.includes('leismunicipais') || a.href.includes('/lei'))
      .slice(0, 30);

    // Paginação
    const pagSels = [
      '[class*="pag"] a', '[class*="page"] a', 'nav a',
      'a[rel="next"]', 'a[rel="prev"]', '.next a', '.prev a',
      '[aria-label="próxima"]', '[aria-label="next"]',
    ];
    const pagEls = [];
    for (const sel of pagSels) {
      document.querySelectorAll(sel).forEach(el => {
        pagEls.push({ sel, text: (el.innerText || '').trim(), href: el.href || '', cls: el.className });
      });
    }
    info.paging = pagEls.slice(0, 15);

    return info;
  });

  console.log('\n📋 Total de leis:', data.totalText || 'não encontrado');
  console.log('\n🏷️  Classes presentes (primeiras 150):');
  console.log(data.classes.join(' | '));

  console.log('\n📦 Seletores de lista encontrados:');
  for (const [sel, info] of Object.entries(data.listItems)) {
    console.log(`\n  "${sel}" → ${info.count} elementos`);
    console.log('  Texto:', info.text.replace(/\n/g, ' | ').substring(0, 200));
    console.log('  HTML:', info.html.replace(/\s+/g, ' ').substring(0, 400));
  }

  console.log('\n🔗 Links encontrados:');
  data.links.forEach(l => console.log(`  "${l.text}" → ${l.href}`));

  console.log('\n📄 Elementos de paginação:');
  data.paging.forEach(p => console.log(`  [${p.sel}] "${p.text}" [${p.cls}] → ${p.href}`));

  console.log('\n📝 Primeiros 2000 chars do texto da página:');
  console.log(data.bodyText.replace(/\n+/g, '\n'));

  // Salva HTML completo
  const html = await page.content();
  fs.writeFileSync('inspect_full.html', html);
  console.log('\n💾 HTML completo salvo em inspect_full.html');

  await waitForEnter('\nAperte ENTER para fechar o browser: ');
  await context.close();
  console.log('✅ Concluído.');
})();
