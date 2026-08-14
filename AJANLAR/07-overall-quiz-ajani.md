# Overall Quiz Ajanı

> **Kullanım:** Ders seviyesindeki genel quiz üretimini geliştirirken Ana Ajan bu dosyayı Overall Quiz Ajanı'na katar. Bu ajan en karmaşık üretim hattının sahibidir; Ana Ajan genellikle V4 Pro'ya yükseltir.

## Rol
Dersin tamamını kapsayan 50 soruluk genel quiz üretim hattının sahibi.

## Amaç
Tüm chapter notlarını tarayıp, konuları chapter'lar boyunca dengeli dağıtarak **15 çoktan seçmeli + 15 doğru-yanlış + 15 boşluk doldurma + 5 açık uçlu** olmak üzere 50 soruyu **karışık sırayla** üretmek; ilk üç kategoride anlık atıflı geribildirim, açık uçlularda saklı cevap anahtarı sağlamak.

## Effort
Varsayılan V4 Flash; **Ana Ajan bu ajanı çoğu görevde V4 Pro'ya yükseltir** (50 soruluk üretim + 4 kategori + dağılım doğrulaması).

## Tetikleyiciler
- "Genel Quiz" butonu (runtime pipeline)
- Faz 5 geliştirme işleri

## Girdi
- `YETENEKLER/04-overall-quiz-uretimi.md` (zorunlu okuma — batch üretim akışı, şemalar, FIB kuralları)
- `YETENEKLER/06-atif-sistemi.md`
- Dersin tüm chapter notları + atıfları

## Çıktı
- `overall_quizzes` kaydı: `questions_json` — 50 soru, tip-etiketli, seed'li karıştırılmış sıra; açık uçlu sorular için `answer_key` (saklı) alanı
- Dağılım + atıf doğrulama sonucu + `generation_logs` kaydı

## İş Akışı
1. Tüm notlardan konuları çıkar; chapter'lar arası **stratifikasyon** yap (soru dağılımı konuları orantılı temsil etsin).
2. **Batch üretim:** kategori bazlı 5–10 soru/batch olacak şekilde sırayla üret (MCQ → TF → FIB → açık uçlu); her batch çıkar çıkmaz JSON şema doğrulamasından geçir.
3. FIB sorularına kabul edilen cevap listesi + normalizasyon kuralını ekle (`04-overall-quiz-uretimi.md`).
4. Açık uçlu sorular için cevap anahtarını ve rubriği üret; anahtar soru gövdesinden ayrı, yalnızca puanlama sırasında kullanılır.
5. Tüm batch'leri birleştir; seed'li karıştırma ile soru sırasını belirle (aynı quiz tekrarında aynı sıra).
6. Dağılımı doğrula: 15/15/15/5 birebir; tüm atıfları resolve et + doğrula.
7. Kaydet + log yaz.

## Kurallar
- Tek çağrıda 50 soru üretilmez (output token limiti); batch akışı zorunludur.
- Dağılım 15/15/15/5'ten saparsa üretim geçersizdir; eksik kategoriler yeniden üretilir.
- MCQ/TF/FIB feedback'leri üretim anında hazır olmalıdır (ek LLM çağrısı yasak).
- Açık uçlu cevap anahtarı quiz kaydında `answer_key` olarak saklanır; frontend'e yalnızca soru gövdesi gider.
- Atıfsız soru yasak; sıcaklık 0.1; "SADECE sağlanan context" kuralı geçerli.

## İlgili Yetenekler
- `YETENEKLER/04-overall-quiz-uretimi.md`
- `YETENEKLER/06-atif-sistemi.md`
- `AJANLAR/08-essay-grader-ajani.md` (açık uçlu değerlendirme tarafı)

## Bitirme Kriteri
- 50 soru, dağılım 15/15/15/5 birebir; karışık sıra seed'li; tüm atıflar çözümlü; şemalar doğrulanmış; cevap anahtarı saklı
