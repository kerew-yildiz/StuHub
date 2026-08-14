# Yetenek 06 — Atıf Sistemi (Doğrulama + İnteraktif Pop-up)

> **Sahipleri:** Tüm üretim ajanları (04-08) üretim tarafında; frontend tarafında Stil Ajanı. Bu dosya, atıf veri modelinin, doğrulama adımının ve interaktif pop-up davranışının sözleşmesidir.

## Amaç
Üretilen her AI çıktısındaki atıfların gerçek kaynaklara işaret etmesini garanti etmek ve kullanıcı atfa tıkladığında kaynağın ilgili bölümünü pop-up penceresinde göstermek.

## 1. Atıf Veri Modeli

```json
{
  "id": 1,
  "source_type": "textbook | slides | note",
  "source_id": 12,
  "page": 41,
  "slide": null,
  "chunk_id": "chk_12_41_1",
  "quote": "Kaynak metinden kısa alıntı (fallback gösterimi için)"
}
```

- `source_type=textbook` → `page` zorunlu, `slide` null.
- `source_type=slides` → `slide` zorunlu, `page` null.
- `source_type=note` → dosya render'ı yok; pop-up ilgili not bölümünün metnini (`quote`) gösterir.
- `chunk_id` → `citations_ledger` üzerinden tam metne çözümlenir.
- Metin içi gösterim: `[1]`, `[2]`, ... (sıralı; üretim sırasında atanır).

## 2. Üretim Sonrası Doğrulama Adımı (her üretimde zorunlu)

1. Çıktıdaki tüm `[n]` işaretlerini topla; `citations_json` ile birebir eşleştir (fazla/eksik atıf = bulgu).
2. Her atfın `quote`'u ile `chunk_id`'nin tam metni arasında **fuzzy substring eşleşmesi** yap (normalize: küçük harf, noktalama temizliği, Türkçe karakter korunur).
3. Eşik altında kalan atıflar için **LLM onay çağrısı**: "Bu alıntı şu kaynak parçasında geçiyor mu?" — evet/hayır; hayırsa atıf geçersizdir.
4. Geçersiz atıf bulunursa ilgili üretim adımı yeniden çalıştırılır (atıf düzeltme iterasyonu).
5. Kalite kapısı: **0 çözümsüz atıf; çözümlenme oranı ≥ %80** (yol haritası Bölüm 12).

## 3. İnteraktif Pop-up (CitationPopup)

### Davranış
- Atıf `[n]` tıklanabilir bağlantıdır; tıklandığında modal açılır.
- Modal içeriği kaynak tipine göre:
  - **textbook:** PDF'nin ilgili sayfası render edilir (pdfjs `pdfjs-dist`; dosya `/api/materials/{id}/file` üzerinden Range destekli servis edilir); `quote` terimi sayfada **vurgulanır** (pdfjs text layer arama).
  - **slides:** Dönüştürülmüş PDF render dosyasından ilgili slide sayfası gösterilir; LibreOffice dönüşümü yoksa slide metni biçimli metin olarak gösterilir (fallback).
  - **note:** ilgili not bölümünün metni (`quote`) gösterilir (dosya render'ı yoktur).
- Render hatası (dosya silinmiş, sayfa aralığı dışı vb.) → `quote` metin alıntısı fallback gösterilir + "sayfa <n>" etiketi.

### Erişilebilirlik
- Modal: odak tuzağı, Esc ile kapanma, başlık (`aria-labelledby`), klavye ile atıf odağı (Tab ile gezilebilir, Enter/Space ile açılır).
- Vurgu rengi kontrast kurallarına uyar (stil rehberi).

## 4. Kaynak Erişim API Sözleşmesi

- `GET /api/materials/{id}/file` — Range destekli (HTTP 206); pdfjs için zorunlu.
- `GET /api/citations/{chunk_id}` — chunk tam metni + sayfa/slide metadata'sı.

## 5. Chat Yanıtları İçin Atıf Kuralları (`10-materyale-sor.md`)

- Chat yanıtındaki her `[n]` kimliği, **yanıt üretilmeden önce verilen kaynak listesinden** (1..n) olmalıdır.
- **Tanımsız kimlik = ret:** listede olmayan `n` tespit edilirse yanıt reddedilir ve tek üretimle düzeltilir (deterministik doğrulama; LLM çağrısı yok).
- Kaynak listesi `source_type` taşır (`textbook`/`slides`/`audio`/`note`); atıf çipi tıklanınca **mevcut kaynak pop-up'ı** (Bölüm 3) açılır. Render'ı olmayan tiplerde (`audio`/`note`) `quote` + zaman damgası/sayfa etiketi fallback gösterilir.
- Retrieval boşsa atıf içeren yanıt üretilemez; "kaynak bulunamadı" mesajı döner.

## Hata Modları
| Durum | Davranış |
|-------|----------|
| Atıf chunk'a çözümlenemiyor | Üretim yeniden çalıştırılır (doğrulama adımı) |
| PDF sayfası render edilemiyor | Metin alıntısı fallback |
| Materyal dosyası silinmiş | "Kaynak dosya bulunamadı" + metin alıntısı |
| Modal açıkken yeni render isteği | İptal + yeni sayfa yüklenir (yarış durumu yasak) |
| Chat yanıtında tanımsız `[n]` | Yanıt reddi + tek üretim (deterministik doğrulama) |

## Kabul Kriterleri
- Her üretim doğrulama adımından geçmiş (0 çözümsüz atıf)
- Pop-up her kaynak tipi için çalışır; fallback yolu testli
- Klavye + ekran okuyucu erişimi sağlanmış
