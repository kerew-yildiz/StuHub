# Rapor: PWA Otomatik Güncelleme (İş 2) — Doğrulandı + Veri Kaybı Hatası Düzeltildi

**Dal:** `fix/pwa-auto-update` • **Tarih:** 2026-09-18 • **Ortam:** Windows (Git Bash + PowerShell), Python 3.13, Node 22, uv 0.12

---

## 1. Amaç

Railway'de yeni sürüm yayınlandığında kullanıcının Ctrl+Shift+R yapmadan otomatik/güvenli şekilde yeni sürümü alması. Form doluyken asla sessiz/beklenmedik yenileme olmamalı.

## 2. Kök nedenler (özet — kod tarafı bu dalda zaten düzeltilmişti)

1. **Önbellek başlıkları:** `index.html`/`sw.js` tarayıcı HTTP önbelleğine giriyordu → `apps/backend/src/main.py` middleware'i artık kabuk dosyalarına `no-cache, no-store, must-revalidate`, `/assets/*`'a `immutable` veriyor.
2. **Service worker kabuk rotası:** Workbox eklentisinin varsayılan `navigateFallback: 'index.html'` rotası, NetworkFirst navigasyon rotasını gölgelendiriyordu → `vite.config.ts`'de `navigateFallback: null` + tek NetworkFirst rotası (4 sn ağ zaman aşımı, sonra precache kabuğuna düşüş).
3. **Güncelleme denetimi tek seferlikti** → `apps/frontend/src/lib/pwa-update.ts`: 60 sn'de bir + `visibilitychange`'de `/version.json` karşılaştırması; sürüm değiştiyse form boşken sessiz yenileme, form doluyken "Yeni sürüm hazır — Yenile" bildirimi.

## 3. Bu oturumda yapılanlar

### 3.1 Doğrulama (hepsi geçti)

**Önbellek başlıkları** (uvicorn, port 8199):
- `/`, `/sw.js`, `/manifest.webmanifest`, `/version.json` → `no-store` ✅
- `/assets/*.js` → `public, max-age=31536000, immutable` ✅

**Şerit (banner) testi — form doluyken:**
- Eski build (`c2cba38`) yüklü sayfada e-posta alanı dolduruldu; sunucu yeni build (`deadbee`) sunmaya başladı; 60 sn'lik denetim döngüsü bekledi.
- **Sonuç:** Sayfa YENİLENMEDİ (eski build çalışmaya devam etti), form içeriği korundu, ~38 sn sonra "Yeni sürüm hazır" bildirimi + **Yenile** düğmesi göründü. ✅
- **Yenile** düğmesine tıklandı → sayfa yenilendi, çalıştırılan build `0.1.0+deadbee` oldu. ✅
- Ekran görüntüleri: koyu ve açık temada şerit doğru görünüyor (aşağıda).

**Form boşken (otomatik yenileme):**
- Boş form + yeni build → sayfa kullanıcı müdahalesi olmadan, kesintisiz yeni sürüme geçti (deney boyunca defalarca doğal olarak gerçekleşti). ✅

**Service worker / çevrimdışı kabuk:**
- SW aktif ve sayfayı kontrol ediyor (`navigator.serviceWorker.controller`), 93 precache girdisi eksiksiz. ✅
- Üretilen `dist/sw.js` içinde doğrulandı: `stuhub-sayfa-kabugu` rotası, `networkTimeoutSeconds: 4`, `fallbackURL: "index.html"`, `maxEntries: 8`. ✅
- *Sınırlama notu:* Preview webview'i arka plandaki sunucu öldüğünde sekmeyle birlikte kapanıyor; bu yüzden "sunucu kapalıyken gerçek sekme yenilemesi" adımı bu ortamda çalıştırılamadı. Yerine SW'nin çevrimdışı yolu üç kanıtla doğrulandı: (1) precache eksiksizliği, (2) aktif kontrol, (3) sw.js'teki NetworkFirst + zaman aşımı + kabuk yedeği ayarları. Gerçek tarayıcıda DevTools → Network → Offline ile 30 saniyelik son kontrol önerilir (beklenen: uygulama açılır).

### 3.2 Bulunan ve düzeltilen GERÇEK hata: erken odak kör noktası (veri kaybı riski)

**Belirti:** Deneyler sırasında, form DOLUYKEN sayfanın sessizce yenilendiği gözlemlendi.

**Kök neden (kanıtla):** Giriş ekranındaki e-posta alanı, sayfanın ilk odaklanabilir elemanı — tarayıcı yüklenir yüklemez odağı onda. Kullanıcı odayı hiç değiştirmeden yazmaya başlarsa DOM'da `focusin` olayı ÜRETİLMEZ (odak hiç değişmediği için). `pwa-update.ts`'in "kullanıcı bu alana yazdı" tespiti yalnızca `focusin`'e dayandığından, dolu alan haritaya hiç girmiyor ve `kaydedilmemisGirdiVar()` false dönüp **sessiz yenileme kullanıcının yazdığını siliyordu**. Konsol kanıtı: kontrol anında `inputlar = ["test@stuhub.dev", ""]` (form DOLU) ama odak haritası boş.

**Düzeltme (`apps/frontend/src/lib/pwa-update.ts`, iki katman):**
1. **Tohumlama:** Modül başlarken açılışta zaten odaklı olan input/textarea'lar o anki değerleriyle haritaya kaydedilir.
2. **Savunma katmanı (asıl düzeltme):** `kaydedilmemisGirdiVar()` artık haritada kaydı OLMAYAN ama DOLU olan alanı da "kaydedilmemiş girdi" sayar. Yanlış-pozitif (gereksiz bildirim) zararsızdır; yanlış-negatif (sessiz reload) veri kaybettirir — tasarım bu yönde.

**Doğrulama (düzeltmeden sonra):**
- Aynı senaryo tekrarlandı: form dolu → yeni sürüm yayına girdi → **sayfa yenilenmedi** (38+ sn, eski build çalıştı), **form korundu**, şerit çıktı, Yenile çalıştı. ✅

**Yeni testler:** `apps/frontend/src/lib/pwa-update.test.ts` — 7 birim testi (tohumlama, katman 2 savunması, eşik koruması). Bu dosya önceden hiç yoktu.

## 4. Test sonuçları

| Paket | Sonuç |
|---|---|
| Backend `pytest -q` | **385 passed** ✅ |
| Frontend `vitest` | **166 passed** (159 eski + 7 yeni) ✅ |
| `tsc --noEmit` (typecheck) | temiz ✅ |
| `eslint` (lint) | temiz ✅ |
| `npm run build` | başarılı (PWA + version.json) ✅ |
| Backend `ruff check src tests` | temiz ✅ |

## 5. Ekran görüntüleri

Şerit, her iki temada da giriş ekranında doğru konumda ve okunur görünüyor:
- `raporlar/gorseller/pwa-serit-koyu-tema.png` (eklenince) — koyu tema
- `raporlar/gorseller/pwa-serit-acik-tema.png` (eklenince) — açık tema

> Not: Görüntüler otomasyon aracının ekran görüntüsü API'sinden alındı; dosya kaydı tooling'e bağlı olarak el ile kaydedilebilir. Metin doğrulaması DOM'dan yapıldı: `document.body.innerText.includes('Yeni sürüm hazır')` → her iki temada `true`.

## 6. Sade Türkçe özet

PWA güncelleme sistemi uçtan uca doğrulandı. Yeni sürüm çıktığında: form boşsa sayfa kendini sessizce yeniliyor; form doluyken hiçbir şey kaybolmuyor — ekrana "Yeni sürüm hazır" bildirimi geliyor, kullanıcı Yenile'ye bastığında yeni sürüme geçiyor. Test sırasında **gerçek bir hata bulundu ve düzeltildi**: giriş ekranında kullanıcı yazmaya başlarsa (ilk alana otomatik odaklandığı için) sistem "form dolu" olduğunu göremiyor ve yenilerken yazılanları silebiliyordu. Artık dolu alan odak takibinden bağımsız olarak korunuyor. Bu düzeltme için 7 yeni birim testi yazıldı; tüm paketler (385 backend + 166 frontend) yeşil.

## 7. Bıraktığım süreç: YOK

(Test sunucusu (uvicorn, port 8199) kapatıldı; port boş. Açılan tarayıcı/preview sekmeleri araca aittir ve sunucuyla birlikte kapandı.)
