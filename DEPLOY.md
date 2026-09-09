# StuHub — Railway Deploy Kılavuzu

Bu belge StuHub'ı Railway'de üretime almak içindir. Supabase/Lemon Squeezy kurulumu
için önce `KULLANIM-SAAS.md`, ölçekleme gerekçeleri için
`~/.claude/plans/stuhub-scalable-yapmak-sorted-valiant.md` (Rev. 2).

> **Doğrulama durumu.** Bu depodaki Dockerfile bu makinede **derlenip test edilemedi**
> (geliştirme ortamında Docker yok). Backend'in tüm CI adımları (ruff, pyright, 334
> test, bandit, pip-audit) yerelde geçiyor; ama imajın kendisi GitHub Actions'daki
> ilk `docker` job'unda doğrulanacak. Aşağıdaki "İlk deploy kontrol listesi" tam
> olarak bunu adımlıyor.
>
> **Deploy kaynağı: GHCR imajı, Railway build'i değil (2026-09-08 kararı).**
> Railway'in "Deploy from GitHub repo" seçeneği her push'ta Dockerfile'ı kendi
> build kuyruğunda yeniden derler — API ve worker iki ayrı Railway servisi olduğu
> için aynı Dockerfile iki kez, model indirme dahil, baştan derlenir. Bunun yerine
> `.github/workflows/ci.yml`'deki `docker` job'u testler yeşilse imajı BİR KEZ
> derleyip `ghcr.io/kerew-yildiz/stuhub` paketine yayınlar; Railway'deki iki servis
> de (api + worker) aynı imajı çeker. **Not: bu, tek başına "scale" sağlamaz** — Railway
> replikaları image-tabanlı da repo-tabanlı da aynı çalışır; gerçek yatay ölçekleme
> hâlâ Aşama 2'ye (yerel disk bağımlılığının kalkması) bağlı, bkz. `DEVIR.md` §5.3/§6.
> Buradaki asıl kazanç: testler geçmeden imaj hiç yayınlanmaz (CI-gated deploy) ve
> iki servis build'i tekrarlamaz.

---

## 1. Mimari — ne çalışıyor

Tek imaj, iki rol (`STUHUB_ROLE`):

| Rol | Komut | Ne yapar |
|---|---|---|
| `api` (varsayılan) | `uvicorn src.main:app --workers 1` | HTTP API + SPA servisi; `STUHUB_RUN_WORKERS=true` ise arka plan işçilerini de çalıştırır |
| `worker` | `python -m src.worker_main` | Yalnızca indeksleme + feed işçileri, HTTP yok |

**Neden tek imaj (şimdilik):** API'nin ML bağımlılıklarından (torch/sentence-transformers)
kurtulabilmesi için not/quiz üretiminin istek-içi olmaktan çıkıp kuyruğa taşınması gerekir.
Bugün üretim ve sohbet API process'inde çalışıyor ve `retrieval.hybrid_search →
embed_service` zinciriyle embedding modeline ihtiyaç duyuyor. İmaj ayrımı yol haritasının
**Aşama 2** (Arq kuyruğu) adımına bağlıdır; o iş bitmeden ayırmak API'yi çalışmaz kılar.

**En basit başlangıç:** tek servis, `STUHUB_ROLE=api`, `STUHUB_RUN_WORKERS=true`.
Bugünkü davranışın aynısı. Ayrı worker servisi ancak indeksleme yükü API'yi yavaşlatmaya
başladığında gerekir.

**İmaj nereden geliyor:** Railway build etmiyor, çekiyor. `.github/workflows/ci.yml`
`docker` job'u main'e giden her push'ta (testler geçtikten sonra) `ghcr.io/kerew-yildiz/stuhub`
paketine `latest` ve `sha-<kısa-sha>` etiketleriyle push eder. İki Railway servisi
(api, worker) aynı `latest` imajını çeker; hangi rolde çalışacağı yalnızca
`STUHUB_ROLE` ortam değişkeniyle belirlenir — imaj ikisi için de aynıdır.

---

## 2. İlk deploy kontrol listesi

### 2.1 GitHub tarafı — bir kerelik kurulum

1. **GHCR paketini public yap.** İlk `docker` job'u çalışıp `ghcr.io/kerew-yildiz/stuhub`
   paketini oluşturduktan sonra: GitHub → profil → **Packages** → `stuhub` →
   **Package settings** → **Change visibility** → **Public**. İmajın içinde sır yok
   (uygulama sırları Railway env değişkenlerinden gelir, imaja gömülmez — `.dockerignore`
   `.env`'i zaten dışlıyor), yani public yapmak güvenli ve Railway'in Pro plan gerektiren
   private-registry token akışından kurtarır. Private tutmak isterseniz alternatif:
   `read:packages` yetkili bir GitHub PAT (classic) oluşturup Railway'in **Registry
   Credentials** alanına yalnızca token'ı yapıştırın (kullanıcı adı otomatik) — bu Railway
   Pro plan gerektirir.
2. **Repo secret'ları ekleyin** (GitHub → repo → Settings → Secrets and variables →
   Actions): `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. Bunlar Railway env
   değişkenlerinden AYRI — imaj CI'da derlenirken frontend'e gömülür (tarayıcıya giden
   değerler, gizli değil ama build zamanında lazım). `packages: write` izni GitHub
   Actions'ın kendi `GITHUB_TOKEN`'ından geliyor, ekstra bir token gerekmiyor.
3. `main`'e bir push yapın (ya da mevcut son commit'i yeniden çalıştırın) — `docker`
   job'unun yeşil geçtiğini ve `ghcr.io/kerew-yildiz/stuhub:latest`'in Packages
   sekmesinde göründüğünü doğrulayın.

### 2.2 Railway projesi

1. Railway → **New Project → Empty Project**.
2. **Add a Service → Docker Image** → `ghcr.io/kerew-yildiz/stuhub:latest`.
   (GitHub reposunu Railway'e BAĞLAMAYIN — kaynak imaj, repo değil; `railway.json`
   bu yüzden artık okunmuyor, aşağıdaki healthcheck/restart ayarlarını dashboard'dan
   elle girin: Settings → Deploy → Healthcheck Path `/health`, Restart Policy
   `On Failure`, Max Retries `3`.)
3. Aynı imajla ikinci bir servis daha ekleyin (worker) — §1'deki tabloya göre
   `STUHUB_ROLE=worker` ortam değişkeniyle ayrışır.
4. **Region: Europe West (Amsterdam)** — Türkiye kullanıcıları ve Supabase Frankfurt
   projesine en yakın seçenek. ABD bölgesi her istekte ~150ms ekler.
5. **Otomatik güncelleme:** Railway varsayılan olarak `:latest` etiketini periyodik
   yoklamaz; yeni bir imaj push edildiğinde servisin **Deployments** sekmesinden
   **Redeploy** ile elle tetiklenir (ya da Railway CLI/Webhook ile otomatikleştirilir
   — bu depoda henüz kurulmadı, isteğe bağlı bir sonraki adım).

### 2.3 Kalıcı volume (ATLANMAMALI)

Materyal dosyaları ve LanceDB indeksi diskte tutuluyor. Volume bağlanmazsa
**her deploy'da tüm yüklenen materyaller ve vektör indeksi silinir.**

Railway → servis → **Variables → Volumes → Add Volume**, mount path: `/data`.

> Object storage'a taşıma (Supabase Storage) yol haritasının "ölçekten bağımsız"
> maddesi; volume o zamana kadarki geçici çözümdür.

**İzinler — `RAILWAY_RUN_UID` ayarlamayın.** Railway volume'u root olarak mount
ediyor ([docs](https://docs.railway.com/volumes) → "Permissions"); non-root başlayan
bir konteyner `/data`'ya hiç yazamaz. Railway'in önerdiği çözüm `RAILWAY_RUN_UID=0`,
yani her şeyi root çalıştırmak. Bu depo bunun yerine konteyneri root başlatıp
`docker-entrypoint.sh` içinde yalnızca `/data`'yı uygulama kullanıcısına (uid 10001)
devrediyor ve ayrıcalığı hemen bırakıyor. Yani ekstra bir değişken gerekmiyor;
`RAILWAY_RUN_UID` girilirse uygulama gereksiz yere root çalışır.

### 2.4 Ortam değişkenleri

Railway → servis → **Variables**. `.env`'deki değerleri buraya girin (dosyayı
imaja koymayın — `.dockerignore` zaten engelliyor).

**Zorunlu:**

```
DATABASE_URL=postgresql://postgres.<ref>:<şifre>@aws-0-<bölge>.pooler.supabase.com:5432/postgres
VITE_SUPABASE_URL=https://<ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key>
GOOGLE_API_KEY=<...>          # en az bir LLM sağlayıcısı
STUHUB_DATA_DIR=/data
STUHUB_EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

> ⚠️ **`STUHUB_EMBED_MODEL` atlanamaz.** Ayarlanmazsa kod varsayılanı `BAAI/bge-m3`
> devreye girer: 4.3 GB indirme **ve** mevcut indekslerle boyut uyuşmazlığı
> (bge-m3 1024 boyut, MiniLM 384). Uygulama bu durumda sessizce bozulmak yerine
> `VectorDimMismatch` ile durur (`services/vector_store.py`) — ama en baştan doğru
> ayarlamak gerekir. Değer, Dockerfile'da imaja gömülen modelle **birebir aynı** olmalı.

> **Build argümanları artık Railway'de DEĞİL.** `VITE_*` değerleri imaj CI'da
> derlenirken (`docker/build-push-action`, repo secret'larından) gömülüyor —
> §2.1 madde 2. Railway'in Settings → Build → Build Arguments alanı imaj
> kaynağında görünmez/uygulanmaz; yalnızca yukarıdaki **Variables**'a runtime
> için `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY` girmeniz yeterli (frontend
> zaten build'te gömülü değeri kullanıyor, backend'in ayrıca bilmesine gerek yok
> ama tutarlılık için Variables'ta da bulunsun).

**İsteğe bağlı** (varsayılanlar makul): `STUHUB_MAX_UPLOAD_BYTES`,
`STUHUB_INDEXER_CONCURRENCY`, `STUHUB_FEED_TOPUP_BATCH`, `STUHUB_CORS_ORIGINS`,
Lemon Squeezy anahtarları. Tam liste: `.env.example`.

### 2.5 Kaynak boyutlandırma

Bellek tüketiminin ana kalemi embedding modeli (MiniLM-L12-v2, ~460 MB disk,
çalışırken ~600 MB RAM) ve indeksleme sırasındaki batch'ler.

- **Başlangıç: 2 GB RAM / 1 vCPU.** `STUHUB_INDEXER_CONCURRENCY=2` ile güvenli.
- Ses transkripsiyonu (faster-whisper) veya OCR yoğun kullanılacaksa 4 GB'a çıkın.
- `--workers 1` bilinçli: model process-global, her uvicorn worker'ı ayrı kopya yükler.
  Yatay ölçekleme process çoğaltmakla değil, Railway replikasıyla yapılmalı — ve o da
  yol haritası Aşama 2'yi (paylaşımlı depolama) gerektirir.

### 2.6 Şema — ARTIK OTOMATİK (2026-09-08)

`schema_postgres.sql` her açılışta backend tarafından kendisi uygulanır
(`db.apply_pg_schema`, `init_db()`'de çağrılır). Dosyanın tamamı idempotent
(`CREATE TABLE/INDEX IF NOT EXISTS`, policy'ler `DROP`+`CREATE`, seed
`ON CONFLICT DO NOTHING`) olduğu için hedef durumu her boot'ta yeniden ilan etmek
güvenli; rolling deploy'da paralel DDL riskine karşı bir Postgres advisory lock
ile serileştirilir. **Supabase SQL Editor'a elle yapıştırma adımı gerekmiyor.**

Sınır: yalnızca eklemeli şema değişikliklerini kapsar (yeni tablo/kolon/indeks).
Kolon yeniden adlandırma, tip daraltma ya da veri backfill'i gerektiren bir
değişiklik gelirse (bugüne kadar hiç gerekmedi) numaralı bir Postgres migration
listesi eklenmeli — SQLite tarafındaki `_apply_migrations` zaten bu deseni izliyor.

---

## 3. Deploy sonrası doğrulama

Sırayla, hepsi geçmeli:

1. **Sağlık:** `curl https://<domain>/health` → `{"status":"ok","saas_mode":true}`
   `saas_mode` false dönüyorsa `DATABASE_URL` ortam değişkenine ulaşmıyor demektir.
2. **Bağımlılıklar:** `curl https://<domain>/health/deep` → 200 ve `"database":"ok"`.
   `llm_providers_available` en az 1 olmalı; 0 ise anahtar girilmemiş ya da hepsi
   cooldown'da.
3. **SPA:** tarayıcıda `https://<domain>` → giriş ekranı gelmeli.
4. **Auth:** Supabase ile kayıt/giriş → `profiles` tablosunda satır açılmalı.
5. **Kalıcılık (kritik):** bir materyal yükle → indeksleme "done" olsun → Railway'den
   servisi **yeniden başlat** → materyal ve notlar hâlâ duruyor mu? Duruyorsa volume
   doğru bağlanmış; kaybolduysa §2.2 atlanmış.
6. **Üretim:** bir bölüm için not üret → SSE akışı gelmeli, atıflar tıklanabilir olmalı.
7. **İzolasyon:** ikinci bir hesap aç → ilk hesabın derslerini GÖRMEMELİ.

---

## 4. Bilinen sınırlar (deploy'u bloklamaz, ama bilinmeli)

- **Postgres yolu canlıda ilk kez çalışacak.** `pg_compat` katmanı (transaction
  semantiği dahil) yerelde sahte bağlantıyla test edildi; gerçek Postgres'e karşı
  doğrulama bu deploy'dur. İlk gün logları `commit edilmemiş ... geri alındı`
  uyarısı için izlenmeli — çıkarsa bir kod yolu commit'i atlıyor demektir.
- **Yerel disk = tek instance.** Materyaller ve LanceDB volume'da olduğu için ikinci
  replika açılamaz. Yatay ölçekleme Aşama 2'ye (object storage + pgvector) bağlı.
- **Ücretsiz LLM zinciri.** Cooldown platform genelindedir (tüm kiracılar aynı
  operatör anahtarını paylaşır); yoğun kullanımda kalite düşer. Ücretli birincil
  sağlayıcıya geçiş Aşama 2.
- **Rate limiting yok.** Aylık kota dışında istek sınırı yok; tek bir hatalı istemci
  servisi bozabilir. `slowapi` + Redis Aşama 2.
- **Sentry/hata izleme bağlı değil.** Şu an sorunlar yalnızca Railway loglarından
  görülür.

---

## 5. Sorun giderme

| Belirti | Olası neden |
|---|---|
| GitHub Actions'da `docker` job "no space" / çok uzun sürüyor | ML bağımlılıkları + model imajı büyütüyor (~5-8 GB); `ubuntu-latest` runner diski genelde yeterli, sürerse `cache-from/to: type=gha` zaten devrede — tekrar deneyin |
| Railway "Image pull failed" | GHCR paketi hâlâ private (§2.1 madde 1: public yapın ya da Registry Credentials'a `read:packages` token girin — Pro plan gerekir) |
| Yeni push sonrası eski davranış sürüyor | `:latest` imaj güncellendi ama Railway servisi otomatik çekmiyor — Deployments → Redeploy (§2.2 madde 5) |
| Başlangıçta OOM | Bellek 2 GB'ın altında ya da `STUHUB_INDEXER_CONCURRENCY` çok yüksek |
| `VectorDimMismatch` | `STUHUB_EMBED_MODEL` imajdaki modelle uyuşmuyor (§2.4) |
| Deploy sonrası materyaller kayıp | `/data` volume'u bağlanmamış (§2.3) |
| `/health` ok ama `/health/deep` 503 | Supabase bağlantısı yok — Session pooler dizesi mi kullanılıyor? (`KULLANIM-SAAS.md` §2.2) |
| Giriş ekranı yerine boş sayfa | `VITE_*` repo secret'ları CI'da yoktu, imaja boş gömülmüş; secret'ları ekleyip yeniden push edin (§2.1 madde 2) |
| Aynı materyal iki kez indeksleniyor | Beklenmez (`worker_id`/heartbeat koruması); olursa şema §2.6 henüz uygulanmamış olabilir (yeni imaj deploy edilmemiş olabilir) |
