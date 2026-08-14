# Yetenek 16 — Web Araştırma Yedeği (Not Üretimi Kaynak Zinciri)

> **Sahibi:** Web Araştırma Ajanı (`AJANLAR/20-web-arastirma-ajani.md`). Bu dosya, not üretiminde kaynak bulunamadığında devreye giren üç kademeli kaynak zincirinin sözleşmesidir.

## Amaç
Not üretiminde her konu için bir kaynak garanti etmek: (1) ders kitabı (mevcut retrieval), (2) web araması (kullanıcı yetkili), (3) slayt/rehber içeriği. **Kullanıcıya her koşulda slayt içeriğiyle örtüşen bir not sunulur** — "eksik not" davranışı yasaktır.

## Kademe 1 — Kitap (mevcut)
- `retrieval.hybrid_search(course_id, topic, keywords)` ile kaynak ara.
- Chunk bulundu → mevcut `NOTE_GENERATION_PROMPT` ile atıflı üretim (değişmez).

## Kademe 2 — Web Arama
- Koşul: kademe 1 boş VE `web_search_enabled` açık (settings tablosu `web_search_enabled` → env `STUHUB_WEB_SEARCH_ENABLED` → varsayılan true).
- Sorgu: **yalnızca** `"{ders adı} {konu}"` — materyal metni asla gönderilmez.
- Araç: `duckduckgo_search` (MIT, anahtarsız, ücretsiz) → `DDGS().text(query, max_results=3)` → `{title, href, body}`.
- Kaynak hazırlama: her sonuç için `href` güvenli şema kontrolüyle (yalnız http/https) indirilir, HTML etiketleri ayıklanır, ~3000 karaktere kırpılır; indirme başarısızsa `body` (snippet) kullanılır. `quote` = metnin ilk 240 karakteri.
- Üretim: `NOTE_GENERATION_WEB_PROMPT` ile stream (kind=`note_generation_web`); atıflar `[n]`; her kaynak `[n] (Web: {title})` etiketli.
- Atıf kaydı: `{"id": n, "source_type": "web", "source_id": null, "page": null, "slide": null, "chunk_id": "web-{n}", "url": ..., "title": ..., "quote": ...}`; `chunk_text` (dahili doğrulama) = kaynak metni. Atıf doğrulaması (Yetenek 06) web kaynaklarına da uygulanır.

## Kademe 3 — Slayt (Rehber) Yedeği
- Koşul: web kapalı ya da boş.
- Üretim: `NOTE_SLIDE_ONLY_PROMPT` ile slayt içeriğinden **tam** not (kind=`note_generation_slide_only`); atıf yok.
- Bölüm başına bilgi satırı (zorunlu):
  `> ℹ️ Bu bölüm ders sunumundan üretildi (kitap/web kaynağı bulunamadı).`
- LLM hatası durumunda bile bölüm deterministik olarak slayt metninden oluşturulur (`### {topic}` + slayt içeriği + bilgi satırı) — boş bölüm yasak.

## Hata Modları
| Durum | Davranış |
|-------|----------|
| Retrieval boş | Kademe 2'ye geç (web) |
| Web araması hatası/boş/import yok | Kademe 3'e geç (slayt); kullanıcıya hata GÖSTERİLMEZ |
| Web kapalı (`web_search_enabled=false`) | Kademe 3'e geç |
| LLM web/slayt üretimi başarısız | Deterministik slayt bölümü + bilgi satırı |
| Web kaynak indirmesi zaman aşımı | snippet'e düş (body) |

## Gizlilik Sözleşmesi
- Web'e yalnızca konu sorgusu gider; kitap/slayt içeriği cihazdan çıkmaz.
- Bu, Ücretsizlik Sözleşmesi'nin kayıtlı istisnalarına eklenir (LLM çıkarımı gibi — kullanıcı yetkisiyle).
- `duckduckgo_search` kaydı `YETENEKLER/08-ucretsiz-arac-envanteri.md`'dedir.

## Kabul Kriterleri
- Üç kademe testli; "kaynak bulunamadı (uyarılı not)" çıktısı hiçbir yolda üretilmez
- Web atıfları URL + alıntıyla görüntülenir (fetch'siz)
- Kapılar: ruff/pyright/pytest/bandit yeşil
