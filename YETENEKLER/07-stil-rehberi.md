# Yetenek 07 — Stil Rehberi

> **Sahibi:** Stil Ajanı (`AJANLAR/02-stil-ajani.md`). Bu dosya uygulamanın görsel dilinin **tek otoritesidir**. Hiçbir UI bu rehberle çelişemez.
>
> **Aktif şema:** Şema 5 — "Renkli Not Defteri" (`TASARIM_SEMALARI.md`; kullanıcı seçimi). İlham: Coconote'un renk kodlu not kimliği + Algor'un görsel organizasyonu.

## Görsel Dil İlkeleri

**Net → Anlaşılır → Minimalist → Şık.** Somut karşılıkları:

1. **Net:** Bilgi hiyerarşisi belirgin; her ekranda tek birincil eylem; tipografi kontrastı güçlü.
2. **Anlaşılır:** Türkçe, kısa mikro-metinler; boş durumlar ve hata mesajları ne yapılacağını söyler; jargon yok.
3. **Minimalist:** Süs yok, gereksiz animasyon yok, gölge az ve amaçlı; boşluk cömert; renk **işlevseldir** — ders renk kodu bilgi taşır, dekorasyon değildir.
4. **Şık:** Tutarlı token kullanımı, dengeli kompozisyon, rafine detaylar (odak halkaları, geçişler).

## Tasarım Tokenları

### Renk
- CSS variables ile tanımlanır (`apps/frontend/src/styles/theme.css`); aydınlık/karanlık iki tema.
- **Zemin/yüzey:** sıcak kağıt ailesi (aydınlık: krem zemin + beyaz yüzey; karanlık: sıcak taş tonları).
- **Vurgu:** tek mavi (birincil eylem) + semantik renkler (başarı, hata, uyarı, bilgi).
- **Ders renk paleti (hue):** 6 ton — çivit, çam, bordo, amber, turkuaz, erik. Her tonun üç token'ı vardır: `--stuhub-hue-<id>` (nokta/şerit), `-text` (WCAG AA güvenli metin varyantı), `-soft` (yüzey üstü yumuşak zemin). Aydınlıkta koyu, karanlıkta açık varyantlar kullanılır.
- **Anahtar terim kutusu:** `--stuhub-callout-bg` / `--stuhub-callout-border` (sıcak amber zeminli).
- Kontrast: metin/zemin oranı WCAG 2.1 AA (normal metin ≥ 4.5:1, büyük metin ≥ 3:1). Hue renkleri metinde yalnızca `-text` varyantıyla kullanılır.
- Hardcoded renk (`#fff`, `bg-blue-500` gibi) **yasaktır**; bileşenler yalnızca token'ları kullanır. Dinamik hue değerleri `src/lib/courseColors.ts` yardımcılarıyla CSS değişkeni olarak uygulanır (inline `style` yalnızca bu dinamik değişkenler içindir).

### Ders Rengi Sistemi (hue)
- Palet tanımı ve atama kuralı: `src/lib/courseColors.ts` (tek kaynak; hex değerleri `theme.css`'tedir).
- Atama: dersin `metadata_json.hue` alanı (CourseForm'daki renk seçicisiyle yazılır); yoksa `course.id % 6` ile kararlı varsayılan.
- Kullanım yerleri: Sidebar ders noktası, ders kartı sol şeridi + rozet, chapter satırı sol şeridi, not bölüm başlığı şeridi, flashcard üst şeridi + konu çipi, kart/quiz listesi sol şeritleri.
- Kural: hue **şerit/nokta/çip** olarak kullanılır; buton dolguları ve büyük yüzeyler hue ile boyanmaz (mavi vurgu korunur).

### Tipografi
- Sistem font yığını (Inter varsayılan; Türkçe karakter destekli).
- Ölçek: 12/14/16/18/20/24/30/36 px; satır yüksekliği 1.5 (gövde), 1.2 (başlık).
- Ağırlık hiyerarşisi: başlık 600, gövde 400, vurgu 500.

### Boşluk ve Şekil
- Boşluk ölçeği: 4px taban (4/8/12/16/24/32/48/64).
- Radius: 10px (`rounded-sm`), 14px (`rounded-md`), 16px (`rounded-lg`) — yumuşak "defter" köşeleri.
- Kenarlıklar 1px, düşük kontrastlı; kart gölgeleri tek seviye, düşük opaklık (gerekliyse).

### Hareket
- Geçişler 150–200ms, ease-out; animasyon yalnızca geribildirim/ilerleme amaçlı.

## Bileşen Kalıpları

| Bileşen | Kural |
|---------|-------|
| Sekme çubuğu (TabBar) | **Pill mod değiştirici:** 1px çerçeveli, p-1 yüzey; aktif sekme `accent/10` zemin + accent metin; alt çizgi yok |
| Dönem kartı (TermCard) | Ad + tarih aralığı; hover'da hafif yüzey değişimi |
| Ders kartı / Chapter satırı | Sol 4px hue şerit + ders adı yanında hue noktası |
| Ders formu (CourseForm) | Tek sütun, etiket üstte; **ders rengi seçici** (6 yuvarlak swatch, radiogroup semantiği); hata mesajı alan altında |
| Not görüntüleyici (NoteViewer) | Okunabilir sütun (~68ch); bölüm başlıkları sol 4px hue şeritli; atıflar vurgu renginde tıklanabilir; `blockquote` → **anahtar terim kutusu** (amber callout zemini + sol kenarlık) |
| Not yüzeyi | Not `<details>` içinde gösterilmez — doğrudan görünür yüzey (sol hue şeritli kart) |
| Atıf pop-up'ı (CitationPopup) | Modal; PDF/slide içerik + kapatma; odak tuzağı (bkz. `06-atif-sistemi.md`) |
| Flashcard oynatıcı (FlashcardPlayer) | Kart üstü 4px hue şerit; konu çipi hue `-soft`/`-text`; Again/Hard/Good/Easy semantik renkli; tekrar ilerleme çubuğu |
| Quiz oynatıcı (QuizPlayer) | Tek soru/ekran; seçenekler tam genişlik; anında feedback kartı (yeşil/kırmızı semantik); ilerleme çubuğu |
| Boş durumlar | Kısa başlık + tek cümle yönerge + birincil eylem butonu |
| Yükleme/ilerleme | Durum metni + progress bar; sonsuz spinner tek başına kullanılmaz |

## Mikro-metin Örnekleri (Türkçe)

- Boş dönem listesi: "Henüz dönem yok" / "İlk dönemini oluştur"
- Not üretiliyor: "Notların hazırlanıyor… (3/7 konu tamamlandı)"
- Quiz yanlış cevap: "Doğru cevap: X. Neden?" (açıklama atıflı)
- Hata: "Bir şeyler ters gitti. Tekrar dene." + teknik olmayan ayrıntı
- Ders rengi seçici yardımı: "Notlarda, kartlarda ve listede bu renk şerit olarak kullanılır."

## Uygulama Kuralları

- Tailwind + CSS variables; tokenlar `theme.css`'te tanımlanır.
- Bileşenler `components/` altında; sayfa bazlı stil dosyası yazılmaz.
- Tema: varsayılan sistem temasını izle; kullanıcı değiştirebilir (Ayarlar). Aydınlık tema "sıcak kağıt", karanlık tema sıcak taş tonlarıdır; hue token'larının iki temada da AA güvenli varyantı vardır.
- Her yeni bileşen bu rehbere kaydedilir (Stil Ajanı günceller).

## Kabul Kriterleri
- Hardcoded renk/boşluk değeri yok (denetim: grep ile token dışı renk aranır); inline `style` yalnızca `hue*Var()` yardımcılarının döndürdüğü CSS değişkenleri için kullanılır
- WCAG 2.1 AA kontrast (axe-core denetimi); hue metinleri yalnızca `-text` varyantıyla
- Türkçe mikro-metinler eksiksiz; İngilizce artık metin yok
- Aydınlık VE karanlık temada ders renkleri ayırt edilebilir (hue çift varyantlı)
