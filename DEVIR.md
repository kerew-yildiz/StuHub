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

Yol haritasının **Aşama 0'ı (lansman öncesi kod blokajları) tamamlandı** ve Railway
deploy dosyaları yazıldı; **hiçbir şey commit edilmedi** ve Docker imajı hiç
derlenmedi — sıradaki iş bu ikisi.

Doğrulama durumu: **backend 334 test, frontend 64 test, ikisi de 0 başarısız**;
ruff/pyright/bandit/pip-audit temiz.

(Oturum başındaki temel çizgi: backend 304 geçiyor / 2 başarısız, frontend 62 geçiyor /
1 başarısız, ruff 16 hata, pyright 114 hata.)

---

## 2. ⛔ Devam etmeden önce bilinmesi ZORUNLU olan iki şey

### 2.1 Depo ile çalışma ağacı ayrışmış — deploy'u bloklar

```
101 izlenmeyen (untracked) dosya
 67 değişmiş izlenen dosya
```

İzlenmeyenler arasında **uygulamanın çalışması için gereken kod** var:
`src/routers/exams.py`, `src/routers/feed.py`, `src/services/feed_service.py`,
`src/workers/feed_topup.py`, 20+ frontend bileşeni, 20+ test dosyası.

Railway GitHub'dan deploy ettiği için, bu haliyle push edilirse **imaj eksik kodla
derlenir ve uygulama ayağa kalkmaz.** Deploy'dan önce bunlar commit edilmeli.

Bu iş kullanıcı onayı beklediği için bilerek yapılmadı. `.env` ve `data/`
`.gitignore`'da, yani sır sızma riski yok.

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

### 5.4 `_stream_test3.py`

`apps/backend/_stream_test3.py` kullanıcının debug scratch dosyası; 5 lint hatası var.
Şu an untracked olduğu için CI görmüyor, ama **commit edilirse `ruff check .` düşer.**
Silinmeli ya da `.gitignore`'a eklenmeli. Dosya sahibinin kararı, dokunulmadı.

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

1. **Commit + push** (§2.1). Deploy'u bloklayan tek şey.
2. **İlk Railway deploy'u** — `DEPLOY.md` adım adım anlatıyor. Kritik noktalar:
   `/data` volume'u, `STUHUB_EMBED_MODEL`, `VITE_*` build argümanları, EU-West bölgesi.
   Deploy sonrası 7 adımlık doğrulama listesi `DEPLOY.md` §3'te.
3. **Postgres migration runner** (yol haritası "ölçekten bağımsız" madde 1) — Postgres
   şeması hâlâ elle uygulanıyor; `0011` migration'ının SQL karşılığı `DEPLOY.md` §2.5'te.
4. **Sentry + object storage** (aynı bölüm, madde 2-3).
5. **Aşama 2** — pgvector (ANN indeksi + SQL-tarafı top-k; port değil yeniden yazım),
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
