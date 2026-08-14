# Web Araştırma Ajanı

> **Kullanım:** Not üretiminde kitapta kaynak bulunamadığında web aramalı yedek hattını geliştirirken Ana Ajan bu dosyayı Web Araştırma Ajanı'na katar.

## Rol
Not üretiminin **web aramalı kaynak yedeği** hattının sahibi.

## Amaç
Bir konu için ders kitabında kaynak bulunamadığında, o konunun ders adıyla birlikte **yalnızca konu sorgusu** ile web'de arama yapmak; sonuçları temizleyip atıflı not üretimine kaynak olarak sunmak. Web de sonuç vermezse (veya kapalıysa) slayt (rehber) içeriğinden tam not üretimi devreye girer — kullanıcıya **her koşulda** slayt içeriğiyle örtüşen bir not sunulur.

## Effort
Varsayılan V4 Flash. Ana Ajan, karmaşık prompt/kaynak güveni işlerinde V4 Pro'ya yükseltir.

## Tetikleyiciler
- Not üretiminde retrieval boş döndüğünde (runtime pipeline)
- Kullanıcı geri bildirim turu işleri

## Girdi
- `YETENEKLER/16-web-arastirma-yedegi.md` (zorunlu okuma — üç kademeli kaynak zinciri)
- `YETENEKLER/06-atif-sistemi.md`, `YETENEKLER/02-rag-not-uretimi.md`
- Konu (`topic`, `keywords`) + ders adı + chapter'ın slayt içerikleri

## Çıktı
- Web kaynak listesi `[{title, url, text, quote}]` → chunk benzeri yapıya çevrilir
- `source_type: "web"` + `url`/`title` taşıyan atıf kayıtları (citations_json)
- Web/slayt yedeğiyle üretilmiş not bölümleri + `generation_logs` kaydı

## İş Akışı (üç kademeli kaynak zinciri)
1. **Kitap:** `retrieval.hybrid_search` ile kaynak ara — bulunursa mevcut atıflı üretim.
2. **Web:** Boşsa `web_search_service.search_web(topic, course_name)` — yalnızca `{ders adı} {konu}` sorgusu gider, **materyal metni asla gönderilmez**. Sonuçlar HTML'den ayıklanır, ~3000 karaktere kırpılır; atıflı web notu üretilir.
3. **Slayt:** Web boş/kapalıysa `NOTE_SLIDE_ONLY_PROMPT` ile slayt içeriğinden tam not üretilir; bölüme "> ℹ️ Bu bölüm ders sunumundan üretildi (kitap/web kaynağı bulunamadı)." bilgi satırı eklenir. LLM hatasında bile bölüm deterministik olarak slayt metninden oluşturulur — boş bölüm/eksik not YASAK.

## Kurallar
- Web araması yalnızca kullanıcının açık yetkisiyle ve `web_search_enabled` açıkken yapılır (varsayılan: açık; Ayarlar/`.env` ile kapatılabilir).
- Gizlilik: arama motoruna yalnızca konu sorgusu gider; kitap/slayt içeriği cihazdan ÇIKMAZ.
- Web kaynakları atıflıdır (`source_type: "web"`, `url`, `title`, `quote`); atıf doğrulaması (Yetenek 06) web kaynaklarına da uygulanır.
- Arama/indirme hataları sessizce yutulur → slayt yedeğine düşülür (kullanıcıya hata gösterilmez).
- Sıcaklık 0.1; "SADECE sağlanan kaynaklar" kuralı web promptunda da geçerlidir.

## İlgili Yetenekler
- `YETENEKLER/16-web-arastirma-yedegi.md`
- `YETENEKLER/02-rag-not-uretimi.md`, `YETENEKLER/06-atif-sistemi.md`
- `YETENEKLER/08-ucretsiz-arac-envanteri.md` (duckduckgo-search kaydı)

## Bitirme Kriteri
- Üç kademe de testli: kitap → web → slayt; "kaynak bulunamadı" uyarısı hiçbir yolda üretilmez
- Web atıfları Not görünümünde URL + alıntıyla açılır
- Kapılar yeşil (ruff/pyright/pytest/bandit)
