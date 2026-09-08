# StuHub — SaaS Kurulum Kılavuzu

Bu belge StuHub'ı **çok kiracılı (multi-tenant) SaaS** modunda çalıştırmak içindir —
Supabase, auth ve Lemon Squeezy kurulumu. Yerel/tek-kullanıcı kurulum için `KULLANIM.md`
yeterli.

> **Bu belge kurulumu anlatır, üretime almayı değil.** Railway'e deploy için
> **[`DEPLOY.md`](./DEPLOY.md)**; projenin güncel durumu, bilinen tuzaklar ve sıradaki
> işler için **[`DEVIR.md`](./DEVIR.md)**.

Açık ürün kararları (dosya depolama, KVKK/gizlilik, farklılaşma) için:
`🏰 300-Projects/StuHub/KARAR-SAAS-GECISI.md`.

---

## 1. SaaS modu nasıl açılır

Backend, `.env`'deki `DATABASE_URL` doluysa otomatik olarak SaaS moduna geçer
(`src/config.py` → `Settings.saas_mode`). Boşsa bugünkü gibi yerel/SQLite modda,
auth'suz çalışmaya devam eder — iki mod aynı kod tabanını paylaşır, dallanma yoktur.

## 2. Supabase kurulumu

1. [supabase.com](https://supabase.com) → yeni proje aç.
2. **Project Settings → Database → Connection string → Session pooler** sekmesinden
   bağlantı dizesini kopyala → `.env`'de `DATABASE_URL`.
   Format: `postgresql://postgres.<proje-ref>:<şifre>@aws-0-<bölge>.pooler.supabase.com:5432/postgres`
   > ⚠️ **Direct connection (`db.<proje-ref>.supabase.co`) DEĞİL, Session pooler kullanın.**
   > Direct connection yalnızca IPv6 üzerinden çalışır; çoğu geliştirme/hosting ortamı
   > (bu makine dahil) IPv6 rotası olmadığı için `OSError: Network is unreachable` verir.
3. **SQL Editor** → yeni sorgu → `apps/backend/sql/schema_postgres.sql`'in tüm içeriğini
   yapıştır → çalıştır. 22 tablo (profiles/plans/subscriptions + 19 tenant-scoped içerik
   tablosu) + RLS politikaları oluşur.
4. **Kimlik doğrulama — iki olası yöntem, kod ikisini de destekler:**
   - **Yeni projeler (varsayılan):** Supabase artık access token'ları **asimetrik anahtarla
     (ES256/JWKS)** imzalıyor, ayrıca bir "JWT Secret" ayarı YOKTUR. Bu durumda
     `SUPABASE_JWT_SECRET`'i boş bırakabilirsiniz — backend `VITE_SUPABASE_URL`'den
     `{url}/auth/v1/.well-known/jwks.json` uç noktasını otomatik keşfedip kullanır.
   - **Eski projeler:** **Project Settings → JWT Settings → Legacy JWT Secret** varsa
     `.env`'de `SUPABASE_JWT_SECRET`'e yapıştırın (HS256 yedek doğrulama yolu).
5. **Project Settings → API** → "Project URL" → `VITE_SUPABASE_URL`, "anon public" key →
   `VITE_SUPABASE_ANON_KEY`.

## 3. Lemon Squeezy kurulumu

1. [lemonsqueezy.com](https://lemonsqueezy.com) → mağaza aç (gerçek/erişilebilir bir domain
   isteyebilir — statik bir Vercel/Netlify deploy'u bu kontrolü geçmek için yeterlidir).
2. **Test modunu açık tutun** (sandbox) — gerçek para geçmez.
3. Bir "Pro" ürünü/varyantı oluşturun → variant ID'yi `.env`'de `LEMONSQUEEZY_PRO_VARIANT_ID`'ye
   yazın; ayrıca Supabase SQL Editor'da eşlemeyi kaydedin:
   ```sql
   UPDATE plans SET lemonsqueezy_variant_id = '<variant-id>' WHERE name = 'pro';
   ```
4. **Settings → API** → API key → `LEMONSQUEEZY_API_KEY`; aynı sayfada Store ID →
   `LEMONSQUEEZY_STORE_ID`.
5. **Settings → Webhooks** → yeni webhook: URL = `https://<backend-domain>/api/billing/webhook`,
   olaylar: `subscription_created`, `subscription_updated`, `subscription_cancelled`,
   `subscription_expired`. Signing secret → `.env`'de `LEMONSQUEEZY_WEBHOOK_SECRET`
   (**40 karakteri geçmemeli** — Lemon Squeezy'nin API'si daha uzununu reddeder).
   > Backend henüz kalıcı bir yerde barınmıyorsa (geliştirme aşaması), geçici test için
   > `cloudflared tunnel --url http://localhost:8000` ile bir public URL açılabilir —
   > hesapsız "quick tunnel" modu, her başlatmada URL değişir, yalnızca test amaçlıdır.

## 4. `.env` — SaaS bölümü özeti

`.env.example`'daki `── SaaS ──` bloğunu doldurun: `DATABASE_URL`, `SUPABASE_JWT_SECRET`
(genelde boş), `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `LEMONSQUEEZY_API_KEY`,
`LEMONSQUEEZY_STORE_ID`, `LEMONSQUEEZY_WEBHOOK_SECRET`, `LEMONSQUEEZY_PRO_VARIANT_ID`.

> `VITE_` önekli iki değişken hem backend'de (JWKS URL türetmek için) hem frontend'de
> (Supabase JS istemcisi için) okunur — `apps/frontend/vite.config.ts`'teki `envDir: '../../'`
> ayarı sayesinde frontend de kök `.env`'i okur, ayrı bir `apps/frontend/.env` gerekmez.

## 5. İlk yönetici (admin) hesabı

`/api/settings` (LLM sağlayıcı anahtarları, global ayarlar) yalnızca `profiles.is_admin = true`
olan kiracıya açıktır — SaaS modunda hiçbir kullanıcı varsayılan olarak admin değildir.
Kendi hesabınızı (signup olduktan sonra) admin yapmak için Supabase SQL Editor'da:

```sql
UPDATE profiles SET is_admin = true WHERE email = '<sizin-e-postanız>';
```

## 6. Kiracı izolasyonu — nasıl çalışır

- Her içerik tablosunda `tenant_id` (UUID, `profiles.id`'ye referans) var; her sorgu
  uygulama katmanında bu kolonla filtrelenir (`src/auth.py` `get_tenant_id` +
  router'lardaki `AND tenant_id = ?` filtreleri).
- RLS (Row-Level Security) `schema_postgres.sql`'de ikinci savunma katmanı olarak
  etkinleştirilmiştir — uygulama kendi anahtarlarıyla bağlandığından (service-level,
  RLS'i bypass eden rol) birincil izolasyon uygulama koduna dayanır; RLS yalnızca
  Supabase Studio/doğrudan SQL erişimi gibi yan kanallara karşı ek güvencedir.
- Yerel/test modda `tenant_id` her zaman sabit `"local"` değerini alır — auth yoktur,
  bugünkü tek-kullanıcı davranış birebir korunur.

## 7. Bilinen sınırlar / açık işler

- **Dosya depolama:** materyal dosyaları hâlâ sunucu diskine yazılıyor
  (`materials.filepath`); object storage (S3/Supabase Storage) kararı verilmedi.
- **Ücretsiz LLM sağlayıcı zinciri geçicidir** — tüm kiracılar aynı operatör anahtarlarını
  paylaşıyor (Gemini → OpenRouter → Groq → Cerebras → GitHub Models). Kullanıcı sayısı arttıkça
  kota/maliyet operatöre yıkılır; kalıcı ücretli plan/anahtar modeline geçiş ayrı bir karar.
- **KVKK/GDPR gizlilik sözleşmesi metni yazılmadı.**
- **Hosting kararı verildi: Railway.** Konteyner dosyaları (`Dockerfile`, `railway.json`,
  `docker-entrypoint.sh`) yazıldı ama **henüz canlıya alınmadı** ve imaj hiç derlenmedi —
  adımlar ve doğrulama listesi `DEPLOY.md`'de.
- **Yerel disk = tek instance.** Materyaller ve LanceDB indeksi sunucu diskinde olduğu için
  ikinci bir replika açılamaz; yatay ölçekleme object storage + pgvector geçişine bağlı.
- **Postgres şeması elle uygulanıyor** — SQLite tarafındaki otomatik migration runner'ın
  Postgres karşılığı yok. Yeni migration'ların SQL karşılığı ilgili dosyanın başında yorum
  olarak tutulur (örn. `sql/migrations/0011_indexing_jobs_worker.sql`).
- **Rate limiting yok** — aylık kota dışında istek sınırı bulunmuyor.

## 8. Sorun Giderme

| Belirti | Kök neden / çözüm |
|---|---|
| `Network is unreachable` (DB bağlantısı) | Direct connection kullanılmış olabilir — Session pooler'a geçin (bkz. §2.2). |
| `InvalidAlgorithmError` / token doğrulanamıyor | Proje JWKS (ES256) kullanıyor ama `SUPABASE_JWT_SECRET` HS256 ile zorlanmaya çalışılıyor olabilir — `VITE_SUPABASE_URL` doğru mu kontrol edin, JWKS otomatik keşfedilir. |
| `pydantic.ValidationError: created_at ... expected string` | `pg_compat.py`'nin `_Row` sarmalayıcısı devre dışı kalmış/bozulmuş olabilir — asyncpg `datetime` döner, ISO string'e çevrilmesi gerekir. |
| `/api/settings` her zaman 403 | Hesabınız admin değil — bkz. §5. |
| Webhook secret kaydedilmiyor, `422` | Lemon Squeezy webhook secret'ı 40 karakteri geçemez. |
| Not/quiz üretimi çok uzun sürüyor | Ücretsiz sağlayıcı zinciri çok adımlı (konu çıkarımı + konu başına üretim + kapsama/atıf doğrulama, her biri ayrı LLM çağrısı); Gemini kotası dolup OpenRouter'a düşülürse (~30-50sn/çağrı) toplam süre birkaç dakikaya çıkabilir — sayfadan ayrılmadan bekleyin. |
| İlk materyal indeksleme çok yavaş | Embedding modeli ilk kullanımda indirilir — tek seferlik, sonraki indekslemeler hızlıdır. Üretim imajında model gömülü olduğu için bu yalnızca yerel kurulumda görülür. |
| `VectorDimMismatch` hatası | `STUHUB_EMBED_MODEL`, indeksin kurulduğu modelden farklı. Kodun varsayılanı `BAAI/bge-m3` (1024 boyut), kullanılan model `paraphrase-multilingual-MiniLM-L12-v2` (384 boyut) — ortam değişkeni ayarlanmadıysa bu hata çıkar. Bkz. `DEVIR.md` §5.1. |
| Loglarda `commit edilmemiş ... geri alındı` | Bir kod yolu `commit()` çağırmayı atlamış. `pg_compat` artık gerçek transaction kullanıyor; commit edilmeyen yazım kapanışta geri alınır. Bkz. `DEVIR.md` §5.2. |
