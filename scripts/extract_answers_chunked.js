/**
 * Scrapes correct answers from the official BAMF online test portal.
 *
 * Usage:
 *   node scripts/extract_answers_chunked.js <state> <start> <end> [outFile]
 *
 * Examples:
 *   node scripts/extract_answers_chunked.js "Nordrhein-Westfalen" 1 300 ./answers_general.json
 *   node scripts/extract_answers_chunked.js "Bayern" 1 10 ./state_answers_Bayern.json
 *
 * <state>   – German state name as shown in the BAMF dropdown (e.g. "Bayern")
 * <start>   – first question number (inclusive)
 * <end>     – last question number (inclusive)
 * [outFile] – output path (default: ./answers_<state>_<start>_<end>.json)
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const state = process.argv[2] || 'Nordrhein-Westfalen';
const start = Number(process.argv[3] || '1');
const end   = Number(process.argv[4] || '300');
const out   = process.argv[5] || path.join(
  process.cwd(),
  `answers_${state.replace(/[^a-zA-Z0-9]+/g, '_')}_${start}_${end}.json`
);

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

  async function openCatalog() {
    await page.goto('https://oet.bamf.de/ords/oetut/f?p=514:1:0', { waitUntil: 'networkidle' });
    await page.selectOption('#P1_BUL_ID', { label: state });
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'networkidle' }),
      page.locator('input[value="Zum Fragenkatalog"]').click(),
    ]);
  }

  async function gotoQuestion(n) {
    if (n === 1) return;
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'networkidle' }),
      page.selectOption('#P30_ROWNUM', { label: String(n) }),
    ]);
  }

  async function extractCurrent(n) {
    const errText = await page.locator('body').innerText();
    if (/Leider ist ein Fehler aufgetreten/i.test(errText)) {
      throw new Error('error page');
    }
    return await page.evaluate((n) => {
      const clean = (s) => (s || '').replace(/\s+/g, ' ').replace(/\u00a0/g, ' ').trim();
      const answerRows = [...document.querySelectorAll('td[headers="ANTWORT"]')].map((td, idx) => {
        const tr = td.closest('tr');
        const correct = !!tr?.querySelector('span[style*="color:green"]') || /richtige Antwort/.test(tr?.innerText || '');
        return { idx, text: clean(td.innerText), correct };
      });
      const imageUrl = document.querySelector('img[src*="show_pag_bild"]')?.src || null;
      const topLine = [...document.body.innerText.split('\n').map(s => s.trim()).filter(Boolean)]
        .find(x => /^Aufgabe\s+\d+\s+von\s+310$/i.test(x)) || null;
      return {
        number: n,
        topLine,
        options: answerRows.map(r => r.text),
        correctIndex: answerRows.findIndex(r => r.correct),
        imageUrl,
      };
    }, n);
  }

  let results = [];
  if (fs.existsSync(out)) {
    results = JSON.parse(fs.readFileSync(out, 'utf-8'));
  }
  const done = new Set(results.map(r => r.number));

  for (let n = start; n <= end; n++) {
    if (done.has(n)) { console.log(`Skip ${n} (already done)`); continue; }
    let attempts = 0;
    while (attempts < 4) {
      attempts++;
      try {
        await openCatalog();
        await gotoQuestion(n);
        const item = await extractCurrent(n);
        if (item.correctIndex < 0 || item.options.length !== 4) {
          throw new Error('bad extraction');
        }
        results.push(item);
        results.sort((a, b) => a.number - b.number);
        fs.writeFileSync(out, JSON.stringify(results, null, 2));
        console.log(`Saved ${n}/${end} for ${state}`);
        break;
      } catch (e) {
        console.error(`Failed ${state} ${n} attempt ${attempts}: ${e.message}`);
        await sleep(1200 * attempts);
        if (attempts >= 4) {
          await browser.close();
          process.exit(1);
        }
      }
    }
  }

  await browser.close();
  console.log(`Done: ${state} ${start}–${end} → ${out}`);
})();
