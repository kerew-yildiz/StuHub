# Yetenek 07 — Stil Rehberi

> **Sahibi:** Stil Ajanı (`AJANLAR/02-stil-ajani.md`). Bu dosya uygulamanın görsel dilinin **tek otoritesidir**. Hiçbir UI bu rehberle çelişemez.

## Görsel Dil İlkeleri

**Net → Anlaşılır → Minimalist → Şık.** Somut karşılıkları:

1. **Net:** Bilgi hiyerarşisi belirgin; her ekranda tek birincil eylem; tipografi kontrastı güçlü.
2. **Anlaşılır:** Türkçe, kısa mikro-metinler; boş durumlar ve hata mesajları ne yapılacağını söyler; jargon yok.
3. **Minimalist:** Süs yok, gereksiz animasyon yok, gölge az ve amaçlı; boşluk cömert; renk işlevseldir (dekoratif değil).
4. **Şık:** Tutarlı token kullanımı, dengeli kompozisyon, rafine detaylar (odak halkaları, geçişler).

## Tasarım Tokenları

### Renk
- CSS variables ile tanımlanır; aydınlık/karanlık iki tema.
- Palet: nötr gri ailesi (zemin, yüzey, kenarlık, metin) + tek vurgu rengi (birincil eylem) + semantik renkler (başarı, hata, uyarı, bilgi).
- Kontrast: metin/zemin oranı WCAG 2.1 AA (normal metin ≥ 4.5:1, büyük metin ≥ 3:1).
- Hardcoded renk (`#fff`, `bg-blue-500` gibi) **yasaktır**; yalnızca tokenlar kullanılır.

### Tipografi
- Sistem font yığını (Inter varsayılan; Türkçe karakter destekli).
- Ölçek: 12/14/16/18/20/24/30/36 px; satır yüksekliği 1.5 (gövde), 1.2 (başlık).
- Ağırlık hiyerarşisi: başlık 600, gövde 400, vurgu 500.

### Boşluk ve Şekil
- Boşluk ölçeği: 4px taban (4/8/12/16/24/32/48/64).
- Radius: 6px (küçük), 10px (kart), 12px (modal).
- Kenarlıklar 1px, düşük kontrastlı; kart gölgeleri tek seviye, düşük opaklık.

### Hareket
- Geçişler 150–200ms, ease-out; animasyon yalnızca geribildirim/ilerleme amaçlı.

## Bileşen Kalıpları

| Bileşen | Kural |
|---------|-------|
| Dönem kartı (TermCard) | Ad + tarih aralığı; hover'da hafif yüzey değişimi |
| Formlar (CourseForm, ChapterForm) | Tek sütun, etiket üstte; hata mesajı alan altında |
| Not görüntüleyici (NoteViewer) | Okunabilir sütun genişliği (~68ch); atıflar vurgu renginde tıklanabilir |
| Atıf pop-up'ı (CitationPopup) | Modal; PDF/slide içerik + kapatma; odak tuzağı (bkz. `06-atif-sistemi.md`) |
| Quiz oynatıcı (QuizPlayer) | Tek soru/ekran; seçenekler tam genişlik; anında feedback kartı (yeşil/kırmızı semantik renk); ilerleme çubuğu |
| Boş durumlar | Kısa başlık + tek cümle yönerge + birincil eylem butonu |
| Yükleme/ilerleme | Durum metni + progress bar; sonsuz spinner tek başına kullanılmaz |

## Mikro-metin Örnekleri (Türkçe)

- Boş dönem listesi: "Henüz dönem yok" / "İlk dönemini oluştur"
- Not üretiliyor: "Notların hazırlanıyor… (3/7 konu tamamlandı)"
- Quiz yanlış cevap: "Doğru cevap: X. Neden?" (açıklama atıflı)
- Hata: "Bir şeyler ters gitti. Tekrar dene." + teknik olmayan ayrıntı

## Uygulama Kuralları

- Tailwind + CSS variables; tokenlar `theme.css`'te tanımlanır.
- Bileşenler `components/` altında; sayfa bazlı stil dosyası yazılmaz.
- Tema: varsayılan sistem temasını izle; kullanıcı değiştirebilir (Ayarlar).
- Her yeni bileşen bu rehbere kaydedilir (Stil Ajanı günceller).

## Kabul Kriterleri
- Hardcoded renk/boşluk değeri yok (denetim: grep ile token dışı renk aranır)
- WCAG 2.1 AA kontrast (axe-core denetimi)
- Türkçe mikro-metinler eksiksiz; İngilizce artık metin yok
