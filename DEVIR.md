# StuHub — Devir Notu (2026-09-08)

Bu dosya, deploy hazırlığı çalışmasının bulunduğu noktayı devralacak kişi/ajan için
kaydeder. **Önce bunu, sonra `DEPLOY.md`'yi, sonra yol haritasını oku.**

| Belge | Ne içerir | Güncellik |
|---|---|---|
| **DEVIR.md** (bu dosya) | Ne yapıldı, ne kaldı, tuzaklar | Güncel |
| `DEPLOY.md` | Railway deploy adımları + doğrulama listesi | Güncel |
| `~/.claude/plans/stuhub-scalable-yapmak-sorted-valiant.md` (Rev. 2) | Ölçekleme yol haritası (100 → 100k kullanıcı) | **Aşama 0 kısmı eskidi** — bkz. §3 |
| `KULLANIM-SAAS.md` | Supabase / Lemon Squeezy kurulumu | Güncel |
| `README.md` | Genel bakış, iki çalışma modu, mimari, belge haritası | Güncel |
| `KULLANIM.md` | **Yerel mod** kurulumu ve kullanımı | Güncel |

---

## 1. Tek cümlelik durum

Yol haritasının **Aşama 0'ı (lansman öncesi kod blokajları) tamamlandı**, Railway
deploy dosyaları yazıldı, ilk gerçek deploy'u kıracak bir **volume izin hatası**
bulunup düzeltildi, **Postgres migration runner** eklendi (elle şema yapıştırma
adımı kalktı), **deploy kaynağı Railway build'inden GHCR imajına çevrildi**
(Kerem'in talebi, CI-gated + iki servis tek imaj paylaşıyor — bkz. `DEPLOY.md` §1) ve
**her şey commit edilip `origin/main`'e push edildi** (2026-09-08,
`8644a7b..4a51131`, 9 commit). Docker imajı hâlâ hiç derlenmedi/push edilmedi —
sıradaki iş **Kerem'in kendisinin yapması gereken kurulum** (GitHub secret'ları
§2.1 + Railway proje/volume/env §2.2-2.4 — bkz. `DEPLOY.md` §2).

**Devralan ajan için not:** bu turun sonunda `apps/backend/src/services/quiz_generator.py`
ve komşu dosyalarda (frontend `QuizPlayer.tsx`/`OnboardingWizard.tsx` silinmiş,
yeni `SavedQuestionsPage`/migration `0012` beliriyor) **kullanıcının kendi
editöründe sürmekte olan ayrı, büyük bir refactor** vardı — bu devir notuna
dokunmadı. O çalışma bitmeden `pytest` collection'ı kırık olabilir
(`generate_quiz_stream` tanımsız); bu §6'daki deploy işiyle ilgisizdir, karıştırma.

Bu turun BAŞINDA bağımsız doğrulanan temel çizgi: **backend 334 test, frontend
65/66** (1 flaky Mermaid testi izole koşuda geçti — bkz. §5.4b); ruff/pyright/
bandit temiz. Yukarıdaki not nedeniyle şu an tam paket koşulamıyor.

(Oturum başındaki temel çizgi: backend 304 geçiyor / 2 başarısız, frontend 62 geçiyor /
1 başarısız, ruff 16 hata, pyright 114 hata.)

---

## 2. ⛔ Devam etmeden önce bilinmesi ZORUNLU olan iki şey

### 2.1 ~~Depo ile çalışma ağacı ayrışmış~~ — ÇÖZÜLDÜ (2026-09-08)

169 dosya altı commit'te toplanıp push edildi; çalışma ağacı temiz, `origin/main`
ile senkron. Bölme: depo hijyeni → özellik seti → Aşama 0 düzeltmeleri → deploy
altyapısı → satır sonu sabitleme.

Bu sırada iki artık temizlendi: `.claude/worktrees/` altında **2.13 GB'lık kayıtlı
bir git worktree** (main ile aynı commit, kendine ait commit'i yok) ve `.impeccable/`
önbelleği — ikisi de artık `.gitignore`'da. `apps/backend/_stream_test3.py` de yok
sayılıyor (commit edilseydi CI'daki `ruff check .` düşerdi).

### 2.2 Bu ortamda doğrulanamayan iki şey

- **Docker yok** → `Dockerfile` hiç derlenmedi. İlk Railway build'i onun testidir.
- **Postgres yok** → `pg_compat`'in yeni transaction katmanı sahte asyncpg bağlantısıyla
  test edildi (çağrı sırası doğrulandı), gerçek sunucuya karşı değil. İlk canlı deploy
  bunun da testidir; logda `commit edilmemiş ... geri alındı` uyarısı çıkarsa bir kod
  yolu `commit()` çağırmayı atlıyor demektir.

---

## 3. ⚠️ Yol haritasında (Rev. 2) DÜZELTİLMESİ gereken iki varsayım

Rev. 2 planı kod okunarak yazılmıştı; uygulama sırasında iki maddesi yanlış çıktı.
**Plan dosyası bu iki noktada güncellenmedi — oraya bakan biri yanlış iş yapar.**

### 3.1 "API imajını ML bağımlılıklarından ayır" (Aşama 0-13) — ŞU AN YAPILAMAZ

Plan, API'nin torch/sentence-transformers'a ihtiyacı olmadığını varsayıyordu. Gerçek:
not üretimi ve sohbet **API process'inde** çalışıyor ve `retrieval.hybrid_search →
embed_service` zinciriyle embedding modeline ihtiyaç duyuyor. Ayırmak API'yi çalışmaz
hale getirir.

→ **İmaj ayrımı, üretimin kuyruğa taşınmasına (Aşama 2 / Arq) bağlıdır.**
Şimdilik tek imaj + iki rol (`STUHUB_ROLE=api|worker`) yapıldı.

### 3.2 Bellek tablosu yanlıştı — ayrım o kadar acil değil

Plan "model 2.2 GB, 2 worker = 5 GB RAM, OOM" diyordu. Ölçüldü:

| Model | Boyut |
|---|---|
| `BAAI/bge-m3` (kodun varsayılanı, `embed_service.DEFAULT_MODEL`) | **4.3 GB** |
| `paraphrase-multilingual-MiniLM-L12-v2` (`.env`'de gerçekte kullanılan) | **458 MB** |

Gerçek ihtiyaç **~2 GB RAM**, 5 GB değil.

Bu fark bir mayın da ortaya çıkardı (bkz. §5.1): kod varsayılanı 1024 boyutlu,
kullanılan model 384 boyutlu.

---

## 4. Bu oturumda yapılanlar

Numaralar yol haritası Rev. 2'nin Aşama 0 maddeleridir.

| # | İş | Doğrulayan test |
|---|---|---|
| 0-A1 | `/api/citations/{chunk_id}` kiracılar arası sızıntısı kapatıldı; arama tüm kiracıların tablolarını taramak yerine tek satır sorgusuna indi | `tests/test_citations_router.py` (8 test) |
| 0-A3 | `pg_compat.commit()` no-op'tu → gerçek transaction (tembel başlatma, `close()`'da rollback + uyarı logu) | `tests/test_pg_compat.py` (12 test) |
| 0-A4 | Yükleme boyutu limiti (`STUHUB_MAX_UPLOAD_BYTES`, 200 MB) + yarım dosya temizliği | `tests/test_materials.py` |
| 0-B5 | `_last_call` global dict → `ContextVar` (eşzamanlı isteklerde yanlış model etiketi yazılıyordu) | mevcut `test_llm_service.py` |
| 0-B6 | Cooldown tek JSON blob + oku-değiştir-yaz → sağlayıcı başına atomik satır (lost update giderildi); eski blob geriye dönük okunuyor | `test_llm_service.py` |
| 0-B7 | `_apply_table_config` her LLM çağrısında 2 DB round-trip + global `settings` mutasyonu yapıyordu → TTL'li (30 sn) önbellek, mutasyon yok | `test_llm_service.py`, `test_settings.py` |
| 0-C8 | `hybrid_search` senkron çağrılıyordu (event loop'u blokluyordu) → `asyncio.to_thread` | `test_note_generator.py`, `test_chat_service.py` |
| 0-C9 | Yükleme, dosya yazma boyunca DB havuz bağlantısı tutuyordu → bağlantı kısa tutuldu | `test_materials.py` |
| 0-C10 | İndekslemede backpressure yoktu (sınırsız `create_task`) → `STUHUB_INDEXER_CONCURRENCY` (varsayılan 2) | `test_indexing.py` |
| 0-C11 | `recover_stale_jobs` tüm `processing` işleri körlemesine geri alıyordu → `worker_id` + `heartbeat_at`, yalnızca bayat işler kurtarılıyor | `test_indexing.py` |
| 0-C12 | `feed_topup` tüm aktif dersleri seri geziyordu → `STUHUB_FEED_TOPUP_BATCH` + ilerleyen imleç | `test_feed.py` |
| 0-D14 | CORS middleware yoktu → `STUHUB_CORS_ORIGINS` ile koşullu | — |
| ek | Embedding boyut uyuşmazlığı koruması (`VectorDimMismatch`) | `test_vector_store_schema.py` |
| ek | `/health/deep` eklendi; `/health` kasıtlı olarak ucuz bırakıldı + regresyon testi | `test_health.py` (5 test) |
| ek | CI yeşile çekildi: ruff 16→0, pyright 114→0, bandit 9→0 | — |
| ek | Frontend `GuideView.test.tsx` timeout'u düzeltildi (Mermaid render ~12 sn) | `npm test` 64/64 |
| ek | Belgelerdeki bayat bilgiler temizlendi: `README.md`, `KULLANIM.md`, `KULLANIM-SAAS.md` (bkz. §8) | — |

### Deploy dosyaları (yeni)

`Dockerfile` · `docker-entrypoint.sh` · `.dockerignore` · `railway.json` ·
`apps/backend/src/worker_main.py` · `DEPLOY.md` ·
`apps/backend/sql/migrations/0011_indexing_jobs_worker.sql`

### Pyright 114 → 0 nasıl oldu (tekrar etmemek için)

Hataların çoğu **iki kök nedenden** geliyordu, 114 ayrı sorundan değil:
1. `LLMProvider.extra_params: dict[str, str]` → `create(**extra_params)` ile açılınca
   pyright her keyword'ü `str`e karşı deniyordu (64 hata). `dict[str, Any]` yapıldı.
2. `pg_compat._Row.__getitem__`'in dönüş tipi yazılmamıştı → `Any | str` çıkarsanıyor
   ve her `row["x"]` erişiminden yayılıyordu (36 hata). `-> Any` yazıldı.

### Bandit hakkında

9 bulgunun tamamı **B608 yanlış pozitifi** — susturulmadan önce tek tek okundu.
SQL'e giren metin ya `?` içeren modül sabiti ya da bir sayıdan üretilen `?, ?, ?`
dizisi; kullanıcı verisi her zaman parametreyle geçiyor. Gerekçeli `# nosec B608`
eklendi. **Gerçek bir enjeksiyon bulunsaydı susturulmaz, düzeltilirdi.**

### Devralma turu (2026-09-08, ikinci oturum)

Temel çizgi bağımsız olarak doğrulandı — **334 test, ruff temiz, pyright 0, bandit
exit 0** — ve devralınan kararlar kodla karşılaştırıldı. Doğru çıkanlar: `pg_compat`
transaction katmanı, `/api/citations` kiracı sahipliği kontrolü, koşullu CORS,
ucuz `/health`. Üç gerçek sorun bulundu ve düzeltildi:

| # | Bulgu | Düzeltme |
|---|---|---|
| 1 | **`USER stuhub` + Railway volume = deploy'da yazma hatası.** Railway volume'u root olarak mount ediyor; non-root başlayan konteyner `/data`'ya hiç yazamaz (materyal, SQLite, LanceDB). İlk deploy'da ölürdü. | Konteyner root başlıyor, entrypoint yalnızca `/data`'yı uid 10001'e devredip `setpriv` ile ayrıcalığı bırakıyor. `setpriv` yoksa uyarıp root devam ediyor (boot kırılmıyor). `USER` direktifi kaldırıldı. |
| 2 | `railway.json`'daki `startCommand` ENTRYPOINT'i exec form'da eziyordu (aynı komut olduğu için zararsızdı, ama ENTRYPOINT değişirse sessizce ayrışırdı). | Kaldırıldı; ENTRYPOINT tek otorite. |
| 3 | Git for Windows **system** seviyesinde `core.autocrlf=true`; taze bir Windows klonunda `docker-entrypoint.sh` CRLF olur ve imaj shebang hatasıyla açılmaz. | `.gitattributes` ile `.sh`/Dockerfile LF'e sabitlendi. (Depodaki mevcut blob'lar zaten LF'ti, `git ls-files --eol` ile doğrulandı.) |

Entrypoint mantığı (root tespiti → devir → ayrıcalık bırakma → rol seçimi) stub'lu
bir harness ile 5 senaryoda davranışsal olarak doğrulandı. **Gerçek `chown`/`setpriv`
semantiği değil, kontrol akışı doğrulandı** — Docker hâlâ yok.

**Ardından: Postgres migration runner eklendi.** `schema_postgres.sql`'in tamamı
zaten idempotent olduğu tespit edildi (26/26 tablo `CREATE TABLE IF NOT EXISTS`,
22/22 indeks `CREATE INDEX IF NOT EXISTS`, policy'ler `DROP`+`CREATE`, seed
`ON CONFLICT DO NOTHING`) — yani numaralı bir migration listesi yazmaya gerek
kalmadan `db.apply_pg_schema()` (yeni fonksiyon, `db.py`) her açılışta dosyayı
yeniden uygulayacak şekilde `init_db()`'ye bağlandı. Paralel DDL'e karşı bir
Postgres advisory lock (`pg_advisory_lock`/`unlock`) ile serileştirildi. Sahte
bağlantıyla iki test eklendi (`tests/test_db.py`): çağrı sırası (lock → şema →
unlock) ve hata durumunda kilidin yine de bırakıldığı. `DEPLOY.md` §2.5 ve
`KULLANIM-SAAS.md` elle-yapıştırma adımları kaldırılarak güncellendi.

**Not:** bu turda `apps/backend/src/services/quiz_generator.py` üzerinde
kullanıcının kendi editöründe aktif/yarım kalmış bir refactor bulundu (working
tree'de `M`, `generate_quiz_stream` henüz tanımsız — `tests/conftest.py` import'ta
patlıyor). Dokunulmadı; tam arka arkaya `pytest` bu yüzden şu an koşulamıyor,
`apply_pg_schema` doğrudan Python ile (conftest'i atlayarak) ayrıca doğrulandı.

---

## 5. Yeni ajanın bilmesi gereken tuzaklar

### 5.1 `STUHUB_EMBED_MODEL` atlanamaz

Kod varsayılanı `BAAI/bge-m3` (1024 boyut, 4.3 GB); `.env` ve Dockerfile
`paraphrase-multilingual-MiniLM-L12-v2` (384 boyut) kullanıyor. Ortam değişkeni
unutulursa 4.3 GB iner **ve mevcut indekslerle boyut uyuşmaz**. Artık sessizce
bozulmak yerine `VectorDimMismatch` fırlıyor (`services/vector_store.py`,
`services/retrieval.py`). Dockerfile'a gömülen model ile runtime değeri **aynı olmalı**.

### 5.2 Transaction semantiği değişti — sessiz veri kaybı riski

`pg_compat.commit()` artık gerçekten commit ediyor; `close()` commit edilmemiş yazımı
**geri alıyor**. Doğru davranış, ama `commit()` çağırmayı unutan bir kod yolu artık
veri kaybeder. Bu yüzden geri alma **uyarı logluyor**. Canlıda ilk gün
`commit edilmemiş %d yazma ifadesi geri alındı` araması yapılmalı.

SQLite yolu aynı sözleşmeyi zaten uyguluyordu, bu yüzden 334 testin geçmesi bu
disiplinin test edilen yollarda mevcut olduğunu gösteriyor — **ama pg_compat
yalnızca `saas_mode`'da devrede ve testler SQLite'ta koşuyor.**

### 5.3 Yerel disk = tek instance

Materyaller (`data/materials/`) ve LanceDB (`data/lancedb/`) yerel diskte. Railway'de
`/data`'ya **kalıcı volume bağlanmazsa her deploy'da silinir**. İkinci replika
açılamaz — yatay ölçekleme Aşama 2'ye (object storage + pgvector) bağlı.

### 5.4b Frontend testleri zamanlamaya duyarlı (flake riski)

`src/components/GuideView.test.tsx` Mermaid'i gerçekten çiziyor (mock yok); jsdom'da
~12 sn sürüyor ve vitest'in 5 sn'lik varsayılanını aşıyordu — bu teste 30 sn timeout
verildi. Yüklü makinede **başka testler de** timeout'a takılabiliyor: art arda üç
çalıştırmada sırasıyla `63 test / 1 başarısız`, `64 test / 1 başarısız`, `64 test /
0 başarısız` sonuçları alındı.

Tek seferlik bir başarısızlık gördüğünde **önce tekrar çalıştır**. Kalıcı hale gelirse
kalıcı çözüm Mermaid'i test ortamında mock'lamak ya da vitest `testTimeout`'unu global
olarak yükseltmektir. Şu anki doğrulanmış durum: **64 test, 0 başarısız.**

### 5.4 ~~`_stream_test3.py`~~ — ÇÖZÜLDÜ (2026-09-08)

Kullanıcının debug scratch dosyası (5 lint hatası) `.gitignore`'a alındı — dosya
diskte duruyor ama izlenmiyor. Ruff varsayılan olarak `.gitignore`'a saygı
duyduğu için CI'ın çalıştırdığı `ruff check .` artık temiz geçiyor (doğrulandı).

### 5.5 Bekleyen soru — model kimlikleri

Kullanıcı bir model kademelendirme kuralı verdi ve "tüm projede uygula" dedi:

> Hız gereken (interaktif) işlerde düşük-efor hızlı model; kullanıcının beklemesi
> gerekmeyen, arka planda buffer'lanabilen işlerde yüksek-efor model. Örnek: quiz
> kaydırmada buffer'da yüksek-efor üretim varsa o gösterilir, buffer boşsa hızlı
> model üretimi gösterilir.

Kural mimari olarak sağlam ve soyutlama olarak kurulabilir. **Ancak kullanıcının
verdiği `Gemini 3.8 Flash` ve `GPT 5.6 Luna` isimleri doğrulanamadı** (bu asistanın
bilgisi Mayıs 2026'da kesiliyor; bu isimler daha yeni olabilir ya da yanlış
hatırlanmış olabilir). **Tam model ID'leri kullanıcıdan alınmadan koda yazılmamalı —
tahmin edilmemeli.** Soyutlama şimdi kurulup slotlar mevcut ücretsiz modellerle
doldurulabilir, ücretli modeller sonra config'den takılır.

---

## 6. Sıradaki iş (öncelik sırasıyla)

1. **İlk deploy'u tamamla** — sırayla `DEPLOY.md` §2.1 (GitHub repo secret'ları
   `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY` + GHCR paketini public yapma),
   §2.2 (Railway'de iki servis: api + worker, aynı `ghcr.io/kerew-yildiz/stuhub:latest`
   imajından), §2.3 (`/data` volume'u), §2.4 (env değişkenleri, `STUHUB_EMBED_MODEL`
   dahil). Deploy sonrası 7 adımlık doğrulama listesi `DEPLOY.md` §3'te. Bu aynı
   zamanda Dockerfile'ın, `pg_compat`'in VE `apply_pg_schema`'nın gerçek Postgres'e
   karşı ilk testi.
2. ~~Postgres migration runner~~ **ÇÖZÜLDÜ (2026-09-08).** `db.apply_pg_schema` her
   açılışta `schema_postgres.sql`'i uyguluyor (idempotent, advisory lock'lu). Ayrıntı
   ve sınır (yalnızca eklemeli değişiklikler) `DEPLOY.md` §2.6'da.
3. **Sentry + object storage** (aynı yol haritası bölümü, madde 2-3).
4. **Aşama 2** — pgvector (ANN indeksi + SQL-tarafı top-k; port değil yeniden yazım),
   Redis + Arq kuyruğu, ücretli LLM kademelendirmesi (§5.5), rate limiting.
   Bu iş bittiğinde §3.1'deki imaj ayrımı da mümkün hale gelir.

Kalan tek Aşama 0 maddesi **0-A2** (vektör namespace'inde `tenant_id` yok) — pgvector
geçişinde doğal olarak kapanacağı için ayrıca yapılmadı; şu an izolasyon `/api/citations`
düzeltmesiyle uygulama katmanında sağlanıyor.

---

## 7. Doğrulama komutları

```bash
cd apps/backend
uv run ruff check .        # NOT: "." CI ile aynı; _stream_test3.py yüzünden düşebilir (§5.4)
uv run ruff check src/ tests/
uv run pyright
uv run pytest -q
uv run bandit -q -r src
uv run pip-audit
```

Frontend:

```bash
cd apps/frontend
npm test           # 64 test geçmeli (~60-90 sn; flake için bkz. §5.4b)
npm run lint && npm run typecheck && npm run build
```

Beklenen: ruff temiz (src/ tests/), pyright 0 hata, backend 334 test, frontend 64 test,
bandit exit 0.

---

## 8. Belge temizliği (bu oturumda yapıldı)

Yeni bir ajanın yanlış bağlam çekmemesi için belgelerdeki bayat bilgiler düzeltildi:

| Nerede | Neydi | Ne oldu |
|---|---|---|
| `README.md` | "Backend: FastAPI + SQLite" | İki mod tablosu: SQLite (yerel) / Postgres-Supabase (SaaS) |
| `README.md` | "Embedding: bge-m3" | Gerçekte kullanılan MiniLM-L12-v2 + boyut uyuşmazlığı uyarısı |
| `README.md` | LLM zinciri 4 sağlayıcı, "Gemini 2.5 Flash" | 5 sağlayıcı, Gemini 3.1 Flash Lite (kaynak: `llm_providers.py`) |
| `README.md` | "306 pytest (1 bilinen hata)" · "30 vitest" | 334 pytest / 64 vitest, ikisi de 0 başarısız |
| `README.md` | "Hesap yok, tüm veri yerel" (koşulsuz) | Moda göre ayrıştırıldı; SaaS için ayrı gizlilik maddeleri |
| `README.md` | Dağıtım/hosting bilgisi yok | Railway satırı + belge haritası eklendi |
| `KULLANIM.md` | "StuHub **tamamen yerel** çalışan bir uygulamadır" | "Bu belge **yerel modu** anlatır" + diğer belgelere yönlendirme |
| `KULLANIM-SAAS.md` | "Kalıcı backend hosting'i yapılmadı" | Railway kararı + gerçek kalan sınırlar (tek instance, elle şema, rate limit yok) |
| `KULLANIM-SAAS.md` | Sorun giderme tablosu eksik | `VectorDimMismatch` ve commit-rollback uyarısı satırları eklendi |

**Değiştirilmeyen ve hâlâ doğru olan:** özellik listeleri, kurulum adımları, Supabase/
Lemon Squeezy kurulum akışı, mevcut sorun giderme satırları.
