#!/usr/bin/env node
/**
 * Rehberli tur ADIM GEÇİŞİ animasyon ölçümü — muse/tur.mjs S2 protokolünün aynısı:
 * her "İleri" tıklamasından sonra 600 ms boyunca 100 ms aralıkla
 * `document.getAnimations()` örneklenir; animasyonlar yalnız `.tour-popover` /
 * `.tour-overlay` ve alt ağacından sayılır (`animasyonVar = tekil animasyon > 0`),
 * ayrıca popover konum serisi (+ anchor halkası ::after geçişi) kaydedilir.
 *
 * Neden harness: bu koşum dev sunucu/backend GEREKTİRMEZ (localhost'a istek yok).
 * Gerçek `TourOverlay` esbuild ile paketlenir, `tur-gecis-harness.tsx` sahnesiyle
 * dosya:// üzerinden gerçek Chromium'da koşar. Stil kaynağı theme.css'tir
 * (`:root` token'ları + tur kuralları metinden birebir alınır).
 *
 * Kullanım (WSL):
 *   node apps/frontend/scripts/tur-gecis-olcum.mjs --etiket=sonra --bekle=animasyonlu
 *   node apps/frontend/scripts/tur-gecis-olcum.mjs --etiket=sonra-reduced --hareket=reduced --bekle=animasyonsuz
 *
 * Çıkış kodu: 0 PASS, 1 FAIL (beklenti tutmadı), 2 ortam hatası.
 */
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const BURASI = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(BURASI, '..')
const ARG = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const [k, v = '1'] = a.replace(/^--/, '').split('=')
    return [k, v]
  }),
)
const ETIKET = ARG.etiket ?? 'olcum'
const CIKTI = path.resolve(ARG.cikti ?? path.join('/tmp/tur-olcum', ETIKET))
const HAREKET = ARG.hareket ?? 'normal'
// animasyonlu: hepsinde animasyon olmalı | animasyonsuz: hiçbirinde olmamalı | yok: beklenti yok
const BEKLE = ARG.bekle ?? 'yok'
const GECIS_MS = 600
const ORNEK_ARALIK_MS = 100

function chromeBul() {
  if (ARG.chrome) return ARG.chrome
  const kalip = path.join(os.homedir(), '.cache/puppeteer/chrome/*/chrome-linux64/chrome')
  const adaylar = fs.globSync(kalip).filter((p) => fs.existsSync(p)).sort()
  if (!adaylar.length) throw new Error(`denetimli tarayıcı bulunamadı: ${kalip}`)
  return adaylar[adaylar.length - 1]
}

/** Playwright paketi depo kökünde değil: master_worker_system/uiux/node_modules altında. */
function playwrightBul() {
  if (ARG.playwright) return ARG.playwright
  let dizin = BURASI
  for (let i = 0; i < 6; i += 1) {
    const aday = path.join(dizin, 'master_worker_system/uiux/node_modules/playwright/index.mjs')
    if (fs.existsSync(aday)) return aday
    dizin = path.dirname(dizin)
  }
  throw new Error('playwright bulunamadı (--playwright=<yol> ile verilebilir)')
}

/** theme.css'ten ölçüm için gereken stilleri birebir alır (kopya değil, metin). */
function stilCikar() {
  const tema = fs.readFileSync(path.join(FRONTEND, 'src/styles/theme.css'), 'utf8')
  const kokBloklari = tema.match(/:root\s*\{[^}]*\}/g) ?? []
  if (!kokBloklari.length) throw new Error('theme.css: :root token bloğu bulunamadı')
  const kurallar = [
    /\.tour-overlay \{[^}]*\}/,
    /\.tour-popover \{[^}]*\}/,
    /\[data-tour-id\] \{[^}]*\}/,
    /\[data-tour-id\]::after \{[^}]*\}/,
    /\[data-tour-id\]\.tour-target::after \{[^}]*\}/,
  ].map((re) => {
    const m = tema.match(re)
    if (!m) throw new Error(`theme.css: kural bulunamadı ${re}`)
    return m[0]
  })
  return [...kokBloklari, ...kurallar].join('\n')
}

/** Sahne iskeleti: Tailwind yardımcı sınıfları YOK — yalnız okunur PNG için sade biçim. */
const SAHNE_CSS = `
html, body { margin: 0; height: 100%; background: #0b0b0b; color: #e8e8e8;
  font: 14px/1.5 system-ui, "Segoe UI", sans-serif; }
h2 { margin: 8px 0 0; font-size: 17px; }
.tour-popover p { margin: 8px 0 0; color: #b9b9b9; }
.tour-popover .eyebrow { margin: 0; font-size: 11px; letter-spacing: .12em; color: #8f8f8f; }
.tour-popover .btn-primary { padding: 6px 12px; border: 0; border-radius: 8px; background: #e8e8e8;
  color: #101010; font-weight: 600; font: inherit; }
.tour-popover .glass-panel-subtle { padding: 6px 12px; border: 1px solid #333; border-radius: 8px;
  background: #1b1b1b; color: #cfcfcf; font: inherit; }
.tour-popover > div { display: flex; align-items: center; justify-content: space-between; margin-top: 18px; }
`

async function paketle() {
  const esbuild = (await import(pathToFileURL(path.join(FRONTEND, 'node_modules/esbuild/lib/main.js')).href)).default
  const cikti = path.join(CIKTI, 'harness.js')
  esbuild.buildSync({
    entryPoints: [path.join(BURASI, 'tur-gecis-harness.tsx')],
    outfile: cikti,
    bundle: true,
    format: 'iife',
    platform: 'browser',
    target: 'chrome120',
    jsx: 'automatic',
    define: { 'process.env.NODE_ENV': '"production"' },
    logLevel: 'silent',
  })
  fs.writeFileSync(
    path.join(CIKTI, 'harness.html'),
    `<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>tur-gecis-olcum</title>
<style>${stilCikar()}\n${SAHNE_CSS}</style></head><body><div id="kok"></div>
<script src="./harness.js"></script></body></html>`,
  )
  return pathToFileURL(path.join(CIKTI, 'harness.html')).href
}

/** Sayfa içi anlık okuma — muse'un animasyon eşlemesiyle birebir aynı alanlar. */
function anlikOku() {
  const pop = document.querySelector('.tour-popover')
  const kap = document.querySelector('.tour-overlay')
  const esles = (x) => {
    const t = x.effect && x.effect.target
    if (!t) return false
    return t === pop || t === kap || (pop && pop.contains(t)) || (kap && kap.contains(t))
  }
  const map = (x) => {
    let sure = '?'
    try {
      const d = x.effect.getComputedTiming().duration
      sure = typeof d === 'number' ? Math.round(d) : String(d)
    } catch {
      /* süre okunamadı */
    }
    const t = x.effect.target
    return {
      ad: x.animationName || x.transitionProperty || (x.constructor && x.constructor.name) || '',
      sure,
      playState: x.playState,
      hedef: (t.tagName || '').toLowerCase() + '.' + String(t.className || '').split(' ')[0],
      sahte: x.effect.pseudoElement || '',
    }
  }
  const hepsi = document.getAnimations ? document.getAnimations() : []
  const r = pop ? pop.getBoundingClientRect() : null
  const ilerleme = pop ? (pop.innerText.match(/(\d+)\s*\/\s*(\d+)/) || [])[0] : ''
  return {
    animasyonlar: hepsi.filter(esles).map(map),
    halkalar: hepsi.filter((x) => esles(x) === false && x.effect && x.effect.pseudoElement === '::after').map(map),
    konum: r ? { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) } : null,
    adim: ilerleme ?? '',
    hedef: document.querySelector('.tour-target')?.getAttribute('data-tour-id') ?? '',
    acik: Boolean(pop),
  }
}

const tekil = (liste) => {
  const gorulen = new Set()
  const cikti = []
  for (const x of liste) {
    const k = `${x.ad}|${x.sure}|${x.hedef}|${x.sahte}`
    if (!gorulen.has(k)) {
      gorulen.add(k)
      cikti.push(x)
    }
  }
  return cikti
}

/** Popover konum serisi: ardışık tekrarlar atılır (geçiş eğrisi görünür). */
const konumSerisi = (liste) => {
  const cikti = []
  for (const k of liste) {
    const son = cikti[cikti.length - 1]
    if (!son || son.x !== k.x || son.y !== k.y) cikti.push(k)
  }
  return cikti
}

async function gecisOrnekle(page, sureMs = GECIS_MS) {
  const bas = Date.now()
  const animasyonlar = []
  const halkalar = []
  const konumlar = []
  const adimlar = []
  while (Date.now() - bas < sureMs) {
    const s = await page.evaluate(anlikOku)
    animasyonlar.push(...s.animasyonlar)
    halkalar.push(...s.halkalar)
    if (s.konum) konumlar.push(s.konum)
    adimlar.push(s.adim)
    await page.waitForTimeout(ORNEK_ARALIK_MS)
  }
  const tekilAnim = tekil(animasyonlar)
  return {
    animasyonVar: tekilAnim.length > 0,
    ornekSayisi: animasyonlar.length,
    animasyonlar: tekilAnim.slice(0, 8),
    sureler: [...new Set(tekilAnim.map((x) => x.sure))],
    konumSerisi: konumSerisi(konumlar),
    halkaVar: tekil(halkalar).length > 0,
    halkalar: tekil(halkalar).slice(0, 4),
    adimSerisi: [...new Set(adimlar)],
  }
}

async function main() {
  fs.mkdirSync(CIKTI, { recursive: true })
  const sayfaUrl = await paketle()
  const { chromium } = await import(pathToFileURL(playwrightBul()).href)
  const tarayici = await chromium.launch({
    executablePath: chromeBul(),
    headless: true,
    args: ['--no-sandbox', '--force-device-scale-factor=1'],
  })
  const baglam = await tarayici.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    reducedMotion: HAREKET === 'reduced' ? 'reduce' : 'no-preference',
  })
  const page = await baglam.newPage()
  await page.goto(sayfaUrl)
  await page.waitForSelector('.tour-popover button.btn-primary')

  // Açılış probe'u: ilk yerleşim animasyonsuz olmalı (viewport ortasından süzülme yok).
  const acilis = await gecisOrnekle(page, 450)

  const gecisler = []
  const adimlar = []
  for (let i = 1; i <= 30; i += 1) {
    const durum = await page.evaluate(anlikOku)
    if (!durum.acik) break
    adimlar.push({ adim: i, ilerleme: durum.adim, hedef: durum.hedef, konum: durum.konum })
    await page.screenshot({ path: path.join(CIKTI, `${ETIKET}-tur-adim-${i}.png`) })
    await page.waitForTimeout(650)
    const ileri = page.locator('.tour-popover button.btn-primary').first()
    if (!(await ileri.count())) break
    const oncekiKonum = durum.konum
    await ileri.click({ timeout: 3000 })
    // Örnekleme ile eşzamanlı: geçişin ortasından PNG (t≈70-160 ms)
    const ornekleme = gecisOrnekle(page)
    await page.waitForTimeout(70)
    await page.screenshot({ path: path.join(CIKTI, `${ETIKET}-gecis-${i}-orta.png`) })
    const gecis = await ornekleme
    const kapandi = !(await page.evaluate(anlikOku)).acik
    const kayit = {
      adim: i,
      animasyonVar: gecis.animasyonVar,
      ornekSayisi: gecis.ornekSayisi,
      sureler: gecis.sureler,
      animasyonlar: gecis.animasyonlar,
      konumSerisi: gecis.konumSerisi,
      oncekiKonum,
      halkaVar: gecis.halkaVar,
      halkalar: gecis.halkalar,
      adimSerisi: gecis.adimSerisi,
      kapandi,
    }
    gecisler.push(kayit)
    await page.waitForTimeout(300)
    if (kapandi) break
  }

  const kapanisDisi = gecisler.filter((g) => !g.kapandi)
  const animasyonlu = kapanisDisi.filter((g) => g.animasyonVar).length
  const tutarli = animasyonlu === 0 || animasyonlu === kapanisDisi.length
  const hepsiAnimasyonlu = kapanisDisi.length > 0 && animasyonlu === kapanisDisi.length
  const hepsiAnimasyonsuz = animasyonlu === 0
  const halkaTutarli = kapanisDisi.every((g) => g.halkaVar)

  const ozet = {
    etiket: ETIKET,
    hareket: HAREKET,
    tarayici: tarayici.version(),
    adimSayisi: adimlar.length,
    acilis: {
      animasyonVar: acilis.animasyonVar,
      sureler: acilis.sureler,
      animasyonlar: acilis.animasyonlar,
      konumSerisi: acilis.konumSerisi,
    },
    gecisSayisi: kapanisDisi.length,
    animasyonluGecis: `${animasyonlu}/${kapanisDisi.length}`,
    tutarli,
    hepsiAnimasyonlu,
    hepsiAnimasyonsuz,
    halkaTutarli,
    adimlar,
    gecisler,
  }
  fs.writeFileSync(path.join(CIKTI, `${ETIKET}-olcum.json`), JSON.stringify(ozet, null, 1))

  console.log(
    `\n[${ETIKET}] AÇILIŞ: animasyon=${acilis.animasyonVar ? 'VAR' : 'yok'} konum serisi ${acilis.konumSerisi.map((k) => `${k.x},${k.y}`).join(' → ') || '(yok)'}`,
  )
  console.log(`[${ETIKET}] tarayıcı=${ozet.tarayici} hareket=${HAREKET} adım=${adimlar.length} geçiş=${kapanisDisi.length}`)
  console.log('adım | hedef | animasyon | süreler | konum serisi | halka | kapandı')
  for (const g of gecisler) {
    const seri = g.konumSerisi.map((k) => `${k.x},${k.y}`).join(' → ') || '(yok)'
    console.log(
      `${g.adim} | ${(g.adimSerisi.join('/') || '-')} | ${g.animasyonVar ? 'VAR' : 'yok'} | [${g.sureler.join(',')}] | ${seri} | ${g.halkaVar ? 'var' : 'yok'} | ${g.kapandi}`,
    )
  }
  console.log(
    `SONUÇ: animasyonlu=${ozet.animasyonluGecis} tutarlı=${tutarli} hepsiAnimasyonlu=${hepsiAnimasyonlu} hepsiAnimasyonsuz=${hepsiAnimasyonsuz} halkaTutarli=${halkaTutarli}`,
  )

  const beklentiTutar =
    BEKLE === 'animasyonlu' ? hepsiAnimasyonlu : BEKLE === 'animasyonsuz' ? hepsiAnimasyonsuz : tutarli
  console.log(`BEKLENTİ(${BEKLE}): ${beklentiTutar ? 'PASS' : 'FAIL'}`)
  await tarayici.close()
  process.exit(beklentiTutar ? 0 : 1)
}

main().catch((e) => {
  console.error('[tur-gecis-olcum] HATA:', e.message)
  process.exit(2)
})
