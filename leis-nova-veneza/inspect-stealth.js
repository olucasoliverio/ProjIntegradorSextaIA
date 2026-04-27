/**
 * inspect-stealth.js — Inspeciona leismunicipais.com.br usando Chrome real
 * Usa o perfil do Chrome instalado no sistema para bypass do Cloudflare.
 * Execução: node inspect-stealth.js
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// Caminho do Chrome real instalado no sistema
const CHROME_PATH = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  process.env.LOCALAPPDATA + '\\Google\\Chrome\\Application\\chrome.exe',
].find(p => {
  try { fs.accessSync(p); return true; } catch { return false; }
});

console.log('Chrome encontrado:', CHROME_PATH || 'NÃO ENCONTRADO (usando Chromium padrão)');

// Diretório temporário para perfil (separado do perfil real para não corromper)
const PROFILE_DIR = path.join(__dirname, 'chrome-profile');

const URL_LIST = 'https://leismunicipais.com.br/legislacao-municipal/4656/leis-de-nova-veneza?q=&types=28&types=4&types=5&types=35&types=228&types=229&types=230';

(async () => {
  const context = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false,
    executablePath: CHROME_PATH || undefined,
    args: [
      '--profile-directory=Default',
      '--disable-blink-features=AutomationControlled',
      '--no-sandbox',
      '--start-maximized',
    ],
    ignoreDefaultArgs: ['--enable-automation'],
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    viewport: null,
    locale: 'pt-BR',
  });

  const page = await context.newPage();

  // Remove sinais de automação
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
    window.chrome = { runtime: {} };
  });

  console.log('🔍 Abrindo o site...');
  console.log('');
  console.log('⚠️  ATENÇÃO: Se aparecer desafio Cloudflare na janela do browser,');
  console.log('   aguarde ele resolver automaticamente (geralmente < 10s).');
  console.log('   Se não resolver sozinho, clique no checkbox manualmente.');
  console.log('');
  console.log('   O script aguardará até 120s pelo conteúdo.');
  console.log('');

  try {
    await page.goto(URL_LIST, { waitUntil: 'domcontentloaded', timeout: 30000 });
  } catch (e) {
    console.log('⚠️  Timeout no goto, mas continuando...');
  }

  // Aguarda o conteúdo real aparecer (lista de leis)
  console.log('⏳ Aguardando conteúdo da lista...');
  try {
    await page.waitForFunction(
      () => {
        const title = document.title;
        return !title.includes('momento') && !title.includes('Checking') &&
               document.querySelectorAll('a[href]').length > 20;
      },
      { timeout: 120000, polling: 2000 }
    );
    console.log('✅ Cloudflare passou! Conteúdo carregado.');
  } catch (e) {
    console.log('⚠️  Ainda no Cloudflare ou timeout. Tentando continuar...');
  }

  await page.waitForTimeout(3000);

  const title = await page.title();
  const url = page.url();
  console.log('\n📊 Título:', title);
  console.log('🔗 URL:', url);

  if (title.includes('momento') || title.includes('Checking')) {
    console.log('\n❌ Ainda no Cloudflare. Tente rodar o script e resolver o desafio manualmente.');
    await page.waitForTimeout(120000);
  }

  // ===== INSPECIONA A ESTRUTURA =====

  // Total de leis
  const totalText = await page.evaluate(() => {
    const text = document.body.innerText;
    const m = text.match(/[\d.,]+\s*(result|leis?|legislaç)/i);
    return m ? m[0] : null;
  });
  console.log('\n📋 Total encontrado:', totalText);

  // Pega todos os seletores possíveis para itens da lista
  const structure = await page.evaluate(() => {
    const info = {
      title: document.title,
      allClasses: [],
      listItems: {},
      allLinks: [],
      html200: document.documentElement.innerHTML.substring(0, 3000),
    };

    // Coleta classes únicas presentes na página
    document.querySelectorAll('*').forEach(el => {
      if (el.className && typeof el.className === 'string') {
        el.className.split(/\s+/).forEach(c => {
          if (c && !info.allClasses.includes(c)) info.allClasses.push(c);
        });
      }
    });

    // Testa seletores comuns de lista
    const selectors = [
      'li', 'article', '[class*="item"]', '[class*="result"]',
      '[class*="lei"]', '[class*="law"]', '[class*="list"]',
      '.card', '[class*="card"]', 'tr', '.row', '[class*="row"]',
    ];
    for (const sel of selectors) {
      const els = document.querySelectorAll(sel);
      if (els.length > 0 && els.length < 1000) {
        info.listItems[sel] = {
          count: els.length,
          sample: els[0].outerHTML.substring(0, 400),
        };
      }
    }

    // Links que parecem ser de leis
    info.allLinks = Array.from(document.querySelectorAll('a[href]'))
      .map(a => ({ href: a.href, text: (a.innerText || '').trim().substring(0, 100) }))
      .filter(a => a.href.length > 10)
      .slice(0, 30);

    return info;
  });

  console.log('\n🏷️  Classes presentes na página (primeiras 50):');
  console.log(structure.allClasses.slice(0, 50).join(', '));

  console.log('\n📦 Seletores encontrados (com < 1000 matches):');
  for (const [sel, data] of Object.entries(structure.listItems)) {
    console.log(`\n  "${sel}" → ${data.count} elementos`);
    console.log('  Sample:', data.sample.replace(/\s+/g, ' ').substring(0, 300));
  }

  console.log('\n🔗 Links encontrados:');
  structure.allLinks.forEach(l => console.log(`  "${l.text}" → ${l.href}`));

  // Salva o HTML completo
  const fullHTML = await page.content();
  fs.writeFileSync('inspect_full.html', fullHTML);
  console.log('\n💾 HTML completo salvo em inspect_full.html');
  console.log('   Abra no browser para inspecionar a estrutura.');

  console.log('\n⏸️  Browser aberto por mais 60s...');
  await page.waitForTimeout(60000);

  await context.close();
})();
