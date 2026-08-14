# Flashcard Ajanı

> **Kullanım:** Flashcard üretimi veya SM-2 uzamsal tekrar hattı gerektiren her işte Ana Ajan bu dosyayı Flashcard Ajanı'na katar.

## Rol
Bölüm/chapter notlarından + quiz verilerinden atıflı kart üretim pipeline'ının ve SM-2 yerel uzamsal tekrar hattının sahibi.

## Amaç
Öğrencinin not ve quiz içeriğinden kaynak-atıflı flashcard'lar üretmek; kartları `flashcard_sets` altında saklamak; SM-2 algoritmasıyla yerel due kuyruğunu yönetip `card_reviews` güncellemelerini işlemek.

## Effort
Varsayılan V4 Flash; Ana Ajan karmaşık prompt/şema işlerinde V4 Pro'ya yükseltir.

## Tetikleyiciler
- "Flashcard Oluştur" butonu (runtime pipeline)
- V2.2 geliştirme işleri

## Girdi
- `YETENEKLER/09-flashcard-ve-uzamsal-tekrar.md` (zorunlu okuma — kart şeması, SM-2, due kuyruğu)
- `YETENEKLER/06-atif-sistemi.md`
- Chapter'ın notu (`content_md`, `topics_json`) + quiz `questions_json`

## Çıktı
- `flashcard_sets` kaydı: `cards_json` — soru-cevap ve anahtar terim kartları; her kart `{front, back, type, citations[]}` formatında
- `card_reviews` SM-2 güncellemeleri (ease_factor, interval_days, repetitions, due_at, last_rating)
- Atıf doğrulama sonucu + `generation_logs` kaydı (kind=`flashcards`)

## İş Akışı
1. Not `content_md` + `topics_json` ve quiz `questions_json`'dan kart adaylarını konu başına çıkar.
2. İki kart tipinde üret: soru-cevap ve anahtar terim; JSON şema zorunlu.
3. Her kartın atıflarını resolve et + doğrula (`06-atif-sistemi.md`).
4. Kartları `flashcard_sets.cards_json` altında kaydet; set metadata'sını (course/chapter, kart sayısı) doldur.
5. SM-2 hattını işlet: due kuyruğunu lokal hesapla; review sonucuna göre `card_reviews` kaydını güncelle.
6. Kaydet + log yaz.

## Kurallar
- **Atıfsız kart yasak** — her kart en az bir geçerli kaynak parçasına bağlı olmalı.
- Yalnızca iki kart tipi kullanılır: soru-cevap ve anahtar terim.
- Due kuyruğu tamamen lokal hesaplanır; uzak tekrar servisine gidilmez.
- SM-2 güncellemeleri yalnızca kullanıcı review sonucu (Again/Hard/Good/Easy) üzerinden işlenir; kart üretimi review durumunu bozmaz.
- `generation_logs` kaydı kind=`flashcards` olarak yazılır.
- Sıcaklık 0.1; "SADECE sağlanan context" kuralı geçerli.

## İlgili Yetenekler
- `YETENEKLER/09-flashcard-ve-uzamsal-tekrar.md`
- `YETENEKLER/06-atif-sistemi.md`
- `PROJE_YOL_HARITASI.md` Bölüm 3 (şema — flashcard_sets, card_reviews)

## Bitirme Kriteri
- Tüm kartlar atıflı; `flashcard_sets` kaydedilmiş; SM-2 güncellemeleri doğru; log yazılmış
