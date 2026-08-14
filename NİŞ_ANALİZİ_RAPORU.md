# StuHub — Niş, Rakip ve Arayüz Analizi Raporu

> **Amaç:** StudyFetch (studyfetch.com) ve Mindgrasp (app.mindgrasp.ai) referans alınarak, "ders materyali yükle → AI not / flashcard / quiz / asistan" nişindeki uygulamaların envanteri, sundukları özelliklerin tek listede toplanması, arayüz tasarım örneklemi ve StuHub için geliştirme önerileri.
>
> **Durum:** ✅ Tamamlandı — 30 uygulama kataloğu, iki anchor derin incelemesi, birleşik özellik listesi, 13 uygulamalık arayüz örneklemi ve StuHub geliştirme önerileri dahil.

---

## 1. Niş Tanımı

StuHub'ın bulunduğu niş, **"AI destekli çalışma / ders içeriği üretim platformları"**dır. Ortak iş akışı:

1. Kullanıcı çalışma materyalini yükler: **PDF (kitap, ders notu), sunum (PPTX), video (YouTube), ses kaydı (ders), web sayfası**
2. AI materyali işler: özetler, not üretir, **flashcard** ve **quiz/practice test** üretir, **çalışma rehberi** çıkarır
3. Kullanıcı çalışır: flashcard'larla tekrar eder (spaced repetition), quiz çözer, **materyalle sohbet eder** (RAG chat), denemelerini AI'a değerlendirtir

Nişin alt kümeleri: (a) doküman→çalışma içeriği platformları, (b) ders/ses kaydından not çıkaranlar, (c) flashcard/quiz uygulamaları, (d) AI öğretmen/chat platformları, (e) hepsi bir arada platformlar.

**StuHub'ın konumu:** (a) kümesinde, yerel-öncelikli (local-first), gizlilik odaklı, Türkçe bir uygulama.

---

## 2. StuHub'ın Mevcut Durumu (Baseline)

Kaynak: `README.md`, `PROJE_YOL_HARITASI.md`, `KULLANIM.md`, `YETENEKLER/` (1.0 teslim edilmiş durum).

### 2.1 Mevcut Özellikler

| Alan | Özellik |
|------|---------|
| Organizasyon | Dönem → Ders → Chapter hiyerarşisi; ders metadata'sı (hoca vb.) |
| Materyal | Kitap PDF + hoca sunumu (PDF/PPTX) yükleme; yerel vektör indeksleme (LanceDB + bge-m3) |
| Not | Guide slides rehberli, kitap taramalı (hibrit RAG), konu bazlı map-reduce, **atıflı** not üretimi (stream) |
| Atıf | Inline `[1]` `[2]` atıfları; tıklanınca kaynak parça pop-up'ı (PDF sayfası / slide) |
| Bölüm Quiz | Konu başına 5 çoktan seçmeli; anında atıflı açıklamalı geri bildirim |
| Genel Quiz | 55 soru (20 MCQ + 15 D/Y + 15 boşluk + 5 açık uçlu); açık uçlular rubrikle 0–10 otomatik puanlanır, doğru/eksik/yanlış/gereksiz analizi + ideal cevap |
| Maliyet | `generation_logs` ile her LLM çağrısı izlenir |
| Export | Not → PDF (var); Anki/MD yok (yol haritası Bölüm 13'te planlı) |
| Ayarlar | Kullanıcının kendi DeepSeek API anahtarı; model seçimi |

### 2.2 Teknoloji & Felsefe

- **Stack:** React 18 + TS + Vite + Tailwind + Zustand · FastAPI + SQLite · LanceDB · yerel embedding (bge-m3) · DeepSeek API (BYO anahtar)
- **Farklılaşan ilkeler:** localhost'ta çalışır, hesap/telemetri/analitik yok, veri tamamen yerel, Türkçe UI, ücretsiz/açık kaynak araçlar zorunlu (tek istisna: LLM çıkarımı)
- **Mevcut arayüz dili** (`YETENEKLER/07-stil-rehberi.md`): nötr gri + tek mavi vurgu (#2563eb), Inter, 4px boşluk ölçeği, 6/10/12px radius, tek seviye gölge, karanlık/aydınlık tema, tek soruluk quiz ekranı, boş durum mikro-metinleri

### 2.3 Yol Haritasında Açık / Planlı Maddeler

- Açık sorular: auth/çoklu cihaz (opsiyonel sync), Anki/PDF/MD export, mobil companion
- Genişletilebilirlik noktaları: yeni quiz tipleri, yeni export formatları, Cmd+K arama/komut paleti, yeni diller, yeni dosya tipleri (DOCX/EPUB), alternatif LLM sağlayıcıları, opsiyonel bulut sync

---

## 3. Rakip Uygulama Kataloğu (30 Uygulama)

> Yöntem: yinelenen aramalar ("StudyFetch alternatives", "apps like Mindgrasp", "best AI study tools 2025", "AI flashcard generator from PDF", "AI quiz maker from documents", "AI lecture note taker") + karşılaştırma sayfaları. Fiyatlar araştırma tarihindeki halka açık planlardır.

### 3.1 Doküman → Çalışma İçeriği Platformları (StuHub'ın doğrudan kümesi)

| Uygulama | URL | Platform | Fiyat | Çekirdek özellikler |
|----------|-----|----------|-------|---------------------|
| **StudyFetch** | studyfetch.com | Web, iOS, Android, Chrome eklentisi | Ücretsiz kredi + ~$11.99/ay | PDF/sunum/Word/ses/YouTube yükleme; AI not & özet; flashcard & quiz; çalışma rehberi; pratik sınav ("Exam" modu) + notlandırma; materyalinden eğitilen chat öğretmeni (Sparky/Riley) |
| **Mindgrasp** | mindgrasp.ai | Web, iOS, Android | 5 gün deneme; ~$8.99–19.99/ay | PDF/Word/PPT/YouTube/ses yükleme; özet+not+flashcard; açıklamalı quiz üretimi; belgeden yanıt veren Q&A chat; atıf desteği; web sayfası özetleme |
| **TurboLearn AI** | turbolearn.ai | Web, iOS, Android | Ücretsiz kredi + ~$12/ay | Ders/ses/PDF/slayt/YouTube → zaman damgalı notlar; flashcard & quiz; spaced repetition; AI chat; kurs dashboard'u |
| **Notedly AI** | notedly.ai | Web | Ücretsiz sınırlı + ~$8/ay | PDF/URL/metin → bölüm bölüm not; flashcard & quiz; YouTube özeti; kurs bazlı organizasyon |
| **Algor Education** | algoreducation.com | Web, Android | Ücretsiz + ~$8/ay | AI **kavram haritası/zihin haritası** üretimi; PDF/fotoğraf/metinden özet + flashcard; harita düzenleme/iş birliği |
| **NoteGPT** | notegpt.io | Web, iOS, Chrome eklentisi | Ücretsiz + kredi paketleri | YouTube (zaman damgalı), PDF, web özeti; flashcard & quiz; zihin haritası; not kütüphanesi + arama |
| **Studyable** | studyable.app | Web, iOS | Ücretsiz + Pro | Not → flashcard/quiz/pratik test; **AI essay notlandırma**; AI öğretmen chat; adım adım ödev yardımı |

### 3.2 Ders/Ses Kaydından Not Çıkaranlar

| Uygulama | URL | Platform | Fiyat | Çekirdek özellikler |
|----------|-----|----------|-------|---------------------|
| **Otter.ai** | otter.ai | Web, iOS, Android | Ücretsiz 300 dk/ay; Pro ~$16.99/ay | Canlı ders transkripsiyonu; AI özet + aksiyon maddeleri; konuşmacı tanıma; OtterPilot otomatik kayıt; transkript arama; PDF/Word export |
| **Fireflies.ai** | fireflies.ai | Web, iOS, Android, Chrome | Ücretsiz 800 dk; Pro ~$10/kullanıcı/ay | Kayıt + transkripsiyon; AI ders notu/özet; görev çıkarımı; aranabilir kütüphane; takvim/LMS entegrasyonları |
| **Speak.AI** | speakai.co | Web, iOS, Android | Deneme; kota bazlı; öğrenci planları var | Çok dilli ses/video transkripsiyonu; özet + bölümleme; kayıtlar arası içgörü arama; transkript senkronlu medya oynatıcı |
| **Voicenotes** | voicenotes.com | Web, iOS, Android | Ücretsiz; Pro $14.99/ay | Ses → anlık transkripsiyon; AI özet + ana çıkarımlar; ses kaydından görev çıkarımı; çok dilli |
| **Granola** | granola.ai | macOS (iOS eşlikçi), Web | Ücretsiz; **öğrencilere 12 ay ücretsiz** | Bilgisayardaki dersi dinler; kişisel tarzında AI not taslağı; özet + aksiyon maddeleri; şablon biçimlendirme |

### 3.3 Flashcard / Quiz Uygulamaları

| Uygulama | URL | Platform | Fiyat | Çekirdek özellikler |
|----------|-----|----------|-------|---------------------|
| **Quizlet** | quizlet.com | Web, iOS, Android | Ücretsiz; Plus ~$7.99/ay (yıllık) | Flashcard + Learn/Test/Match modları; **Magic Notes** (not/PDF → kart); **Q-Chat** AI öğretmen; milyonlarca paylaşımlı set; spaced repetition; çevrimdışı mobil |
| **Anki** | apps.ankiweb.net | Masaüstü ücretsiz, iOS $24.99, Android ücretsiz | Tek seferlik | Altın standart spaced repetition (SM-2); tamamen çevrimdışı; eklentiler (AI kart üreticileri dahil); AnkiWeb senkron; medya destekli kartlar |
| **Knowt** | knowt.com | Web, iOS, Android, Chrome | Büyük ölçüde ücretsiz; opsiyonel Pro | Quizlet setlerini tek tıkla import; PDF/not/YouTube'dan AI kart + not + quiz; spaced repetition; D/Y + eşleştirme + serbest yanıt modları |
| **RemNote** | remnote.com | Web, masaüstü, iOS, Android | Ücretsiz; Pro ~$8/ay | Not + flashcard tek bilgi tabanında; PDF/ders → otomatik kart; AI kart üretimi; spaced repetition; Anki tarzı export |
| **Brainscape** | brainscape.com | Web, iOS, Android | Ücretsiz; Pro abonelik | Güven dereceli akıllı flashcard; AI kart üretimi; dev paylaşımlı deste kütüphanesi; ilerleme analitiği; çevrimdışı |
| **StudySmarter** | studysmarter.de/.co.uk/.us | Web, iOS, Android | Ücretsiz çekirdek; Premium | Not → AI set/kart/quiz; spaced repetition; 1M+ paylaşımlı set; çalışma planı + analitik; AI açıklama + chat |
| **Quizgecko** | quizgecko.com | Web, iOS, Android, Chrome | Ücretsiz; Plus $9/ay | Metin/PDF/URL/videodan quiz + kart + not; çoklu soru tipi; canlı çok oyunculu oyunlaştırılmış quiz; Excel/PDF/LMS export |
| **Quizizz** | quizizz.com | Web, iOS, Android, Chrome | Ücretsiz; okul planları | Doküman/PDF/slayt/URL → interaktif quiz ve ders; canlı çok oyunculu + ödev modu; 20M+ soru bankası; mastery raporları |
| **Gizmo** | gizmo.ai | Web, iOS, Android | Ücretsiz; Pro | **Magic Import** (PDF/not/YouTube → kart); spaced repetition; deste üzerinden AI öğretmen; mastery takibi |
| **Wisdolia** | wisdolia.com | Chrome eklentisi | Ücretsiz; premium | Herhangi bir web sayfası/PDF/YouTube'dan tek tıkla flashcard; spaced repetition; Anki/Notion'a export |

### 3.4 AI Öğretmen / Chat Platformları

| Uygulama | URL | Platform | Fiyat | Çekirdek özellikler |
|----------|-----|----------|-------|---------------------|
| **Khanmigo** | khanmigo.ai | Web, iOS, Android | Öğretmenlere ücretsiz; ~$4/ay | Sokratik tarz yönlendirmeli chat; ipuçlu adım adım çözüm; quiz üretimi; essay geri bildirimi; Khan Academy müfredatına bağlı |
| **Synthesis Tutor** | synthesis.com/tutor | Web, iOS, Android | ~$70/ay aile planı | Gerçek zamanlı uyarlanabilir AI matematik öğretmeni; interaktif dersler; ilerleme raporları |
| **Socratic** | socratic.org | iOS, Android | **Tamamen ücretsiz** | Fotoğraflanan soru → AI açıklama; matematikte adım adım çözüm; video/görsel kaynaklar; OCR |
| **ChatPDF** | chatpdf.com | Web, iOS, Android | Ücretsiz 2 PDF/gün; Plus ~$5/ay | Herhangi bir PDF ile chat; **atıflı, kaynak referanslı yanıtlar**; otomatik özet; çok belgeli konuşma; çok dilli |
| **AskYourPDF** | askyourpdf.com | Web, Chrome | Ücretsiz kredi; ücretli paketler | Atıflı belge chat'i; özet; PDF'ten AI flashcard + soru üretimi; belge kütüphanesi |
| **AskSia** | asksia.ai | Web, iOS, Android, Windows | Freemium | Adım adım ödev açıklaması; PDF/not → Q&A + özet; quiz üretimi; görsel soru çözme; Windows masaüstü uygulaması |

### 3.5 Hepsi Bir Arada Platformlar (Geniş Küme)

| Uygulama | URL | Platform | Fiyat | Çekirdek özellikler |
|----------|-----|----------|-------|---------------------|
| **Course Hero** | coursehero.com | Web, iOS, Android | Abonelik; yükleme karşılığı kilit açma | 30M+ yüklenmiş ders dokümanı; AI ödev yardımı + öğretmen chat; ders kitabı çözümleri; flashcard + çalışma rehberi; uzman Q&A |
| **StudyX** | studyx.ai | Web, iOS, Android | Freemium (AI kredisi) | Fotoğraf/OCR ödev çözücü; çok dersli AI chat; essay/yazım yardımı; doküman yükleme + Q&A; sınav hazırlık araçları |

### 3.6 Katalog Kaynakları

[ToolChase — StudyFetch alternatives](https://toolchase.com/alternatives/studyfetch/) · [SourceForge — Study Fetch alternatives](https://sourceforge.net/software/product/Study-Fetch/alternatives) · [Dupple — best AI study tools](https://dupple.com/learn/best-ai-study-tools) · [ToolRadar — best AI study tools](https://toolradar.com/guides/best-ai-study-tools) · [LaxuAI — 10 best study apps](https://laxuai.com/best-study-apps) · [RightAIChoice — Mindgrasp](https://rightaichoice.com/tools/mindgrasp) · [Quizlet review — PCMag](https://me.pcmag.com/en/education/19970/quizlet) · [The Verge — Quizlet Q-Chat](https://www.theverge.com/2023/8/9/23826191/quizlet-generative-ai-chatgpt-education)

---

## 4. Anchor İncelemesi: StudyFetch & Mindgrasp

> Kaynak: ~40 hedefli web araması (Ocak 2026 anlık görüntüsü). Fiyatlar üçüncü taraf inceleme sitelerinden; resmi sayfalardan teyit edilmelidir.

### 4.1 StudyFetch (studyfetch.com)

**Özellikler:**
- **Girdi:** PDF, Word, PPT, görsel, YouTube/video, slayt→not; sınıf başına çoklu kaynak paketleme
- **Üretim:** AI not + özet, çalışma rehberi, quiz, flashcard, pratik sınav (exam), **essay notlandırıcı**; "Learn Engine" uyarlanabilir katman + yeniden tasarlanan çalışma planı
- **Çalışma modları:** Flashcard/quiz/pratik test + **Arcade oyunları** + Mini Apps; spaced repetition başlık özelliği değil (rakipler buna karşı konumlanıyor)
- **AI öğretmen:** **Spark.E** — materyalden eğitilen sohbet öğretmeni; **yönlendirmeli (Socratic) chat modları**; **SMS ile erişim**; **Wolfram ortaklığı** ile gelişmiş matematik
- **Mobil:** iOS + Android aktif; **API/geliştirici dokümanları** (LMS köprüsü yok, DIY entegrasyon)
- **Büyüme:** TikTok/Snapchat yaratıcı içerik motoru (1B+ görüntülenme, 225+ hesap); ~$10M+ ARR / 1M+ kullanıcı iddiası

**Fiyat:** Kredi bazlı model; ücretsiz katman ~50 kredi (çabuk tükeniyor); ücretli ~**$9–16/ay** (yıllık faturalamada), kademeler kredi miktarına göre.

**İnceleme dengesi:** Güçlü: hızlı/kaliteli not üretimi, Spark.E farkı, düzenlenebilir notlar, mobil. Şikayetler: **krediler hızlı yanıyor** (ücretsiz katman gerçek kullanıma yetmiyor — Reddit'te "bedava alternatif var mı" konuları), niş/teknik içerikte tutarlılık sorunları, mobil hatalar ve abonelik/fatura sürtünmesi. Trustpilot ~3.9/5 (bölgesel 3.5–4.2).

### 4.2 Mindgrasp (mindgrasp.ai)

**Özellikler:**
- **Girdi:** PDF, Word, PPT, kitap, eski sınavlar, web içeriği; **YouTube/video özetleme**; **ders özetleme**; **ses transkripsiyonu**; Kindle export akışları
- **Üretim:** Çalışma rehberi, flashcard, quiz, pratik test, özet, not; **AI Grader** (essay); **Homework Helper**
- **Chat:** Yüklenen her belge/video ile sohbet — **atıflı yanıtlar**
- **Mobil:** iOS güçlü; Android zayıf. Şirket: Apricot AI (Columbia, MD)
- **SEO:** Düzinelerce bölüm-özel açılış sayfası (kimya, sosyal hizmet, veteriner hemşirelik, klinik psikoloji...); öğrenci + **çalışan profesyonel** çift hedef kitle

**Fiyat:** Sınırlı ücretsiz deneme; 3 kademe ~**$9.99–24.99/ay** (yıllıkta ~%40–50 indirim); kota = yükleme/sayfa limitleri.

**İnceleme dengesi:** Güçlü: **transkripsiyon-öncelikli girdi** (ders/ses/video) sınıfının en iyisi; geniş girdi tipi; tam çalışma döngüsü (rehber + test + grader). Şikayetler: **Trustpilot bölgesel çok karışık** (bazı sayfalar 3.8, bazıları 2.0–2.7 — fatura/iptal sürtünmesi, hatalı transkripsiyon), **not/özet export'unda eksikler** (kendi Canny panosunda), uzun belgelerde kalite varyansı, Android geride.

### 4.3 Karşılaştırma Tablosu

| Boyut | StudyFetch | Mindgrasp |
|-------|-----------|-----------|
| Çekirdek kavram | AI öğrenme platformu + kişisel AI öğretmen (Spark.E) | Belge/ders/video için AI not tutucu + çalışma asistanı |
| Girdi | PDF, DOC, slayt, YouTube, video | + **ses/ders, kitap, eski sınav** |
| Üretim | Not, özet, rehber, quiz, flashcard, pratik test, essay grader | Aynı + AI Grader, Homework Helper |
| AI öğretmen | **Spark.E**: materyal hafızalı, yönlendirmeli mod, Wolfram, SMS | Belge/video chat'i (atıflı) — daha az "öğretmen" markalı |
| Çalışma modları | + Arcade oyunları, Mini Apps | Standart set; oyunlaştırma az |
| Mobil | iOS + Android aktif | iOS güçlü, Android zayıf |
| Ücretsiz katman | ~50 kredi (çabuk biter) | Sınırlı deneme |
| Fiyat (bildirilen) | Kredi bazlı ~$9–16/ay (yıllık) | 3 kademe ~$9.99–24.99/ay |
| Trustpilot | ~3.9/5 | Bölgesel karışık (3.8 ↔ 2.0–2.7) |
| Zayıflıklar | Kredi ekonomisi; fatura/mobil şikayetleri; LMS yok | Fatura/iptal şikayetleri; **export eksik**; Android zayıf |

**Özet dersler:** StudyFetch'i seçtiren **öğretmen deneyimi** (Spark.E), Mindgrasp'ı seçtiren **transkripsiyon gücü**. İkisinin de ortak zayıflığı: **export eksiklikleri, şeffaf olmayan kredi/kota ekonomisi ve atıf derinliğinin chat dışında zayıf kalması** — StuHub'ın tam da güçlü olduğu alanlar.

---

## 5. Birleşik Özellik Listesi (Nişin Ortak Özellikleri)

> 30 uygulamanın özellikleri tek listede birleştirildi. **StuHub durumu** sütunu: ✅ var · 🟡 kısmen/planlı (yol haritası Bölüm 13) · ❌ yok.

### 5.1 İçerik Alma (Ingestion)

| Özellik | Sunan uygulamalar | StuHub |
|---------|-------------------|--------|
| PDF yükleme | StudyFetch, Mindgrasp, TurboLearn, Notedly, Algor, NoteGPT, Studyable, Knowt, RemNote, Gizmo, ChatPDF, AskYourPDF, AskSia, Course Hero, StudyX | ✅ |
| Sunum (PPT) yükleme | StudyFetch, Mindgrasp, TurboLearn, NoteGPT, Knowt, Gizmo, AskSia | ✅ |
| Word/metin yapıştırma | Mindgrasp, Studyable, Algor, Knowt, RemNote, Quizgecko, StudySmarter, AskSia, StudyX | ❌ (planlı: DOCX — Bölüm 13/5) |
| YouTube video → içerik | StudyFetch, Mindgrasp, TurboLearn, Notedly, NoteGPT, Knowt, Gizmo, Wisdolia, Quizgecko | ❌ |
| Ses kaydı/ders transkripsiyonu | Mindgrasp, TurboLearn, Otter, Fireflies, Speak.AI, Voicenotes, Granola | ❌ |
| Canlı ders kaydı | Otter, Fireflies, Speak.AI, Granola, TurboLearn | ❌ |
| Fotoğraf/OCR → içerik | Socratic, AskSia, StudyX, Course Hero, KardsAI | ❌ |

### 5.2 AI İçerik Üretimi

| Özellik | Sunan uygulamalar | StuHub |
|---------|-------------------|--------|
| AI özet | StudyFetch, Mindgrasp, TurboLearn, Notedly, Algor, NoteGPT, ChatPDF, AskYourPDF, AskSia, Otter, Fireflies, Speak.AI, Voicenotes, Granola, Quizgecko, StudyX | 🟡 (not içinde kısmen) |
| AI not üretimi | StudyFetch, Mindgrasp, TurboLearn, Notedly, NoteGPT, Knowt, StudySmarter, Otter, Fireflies, Speak.AI, Voicenotes, Granola | ✅ (atıflı, RAG) |
| Flashcard üretimi | StudyFetch, Mindgrasp, TurboLearn, Notedly, Studyable, Knowt, RemNote, Brainscape, StudySmarter, Quizgecko, Gizmo, Wisdolia, AskYourPDF, Quizlet, StudyX | ❌ |
| Quiz üretimi | StudyFetch, Mindgrasp, TurboLearn, Notedly, Studyable, Knowt, StudySmarter, Quizgecko, Quizizz, AskSia, AskYourPDF, Khanmigo, StudyX | ✅ (bölüm + 55 soruluk genel) |
| Çalışma rehberi | StudyFetch, Course Hero, StudySmarter, Notedly, Algor | 🟡 (not ~ rehber) |
| Pratik sınav (exam) | StudyFetch, Studyable, Knowt, Khanmigo, Course Hero | 🟡 (genel quiz) |
| Kavram/zihin haritası | Algor, NoteGPT | ❌ |
| Essay/ödev notlandırma | Studyable, Khanmigo, StudyX | 🟡 (açık uçlu puanlama — essay'e genellenebilir) |
| Adım adım ödev çözümü | Socratic, AskSia, StudyX, Course Hero, Synthesis | ❌ |

### 5.3 AI Etkileşim

| Özellik | Sunan uygulamalar | StuHub |
|---------|-------------------|--------|
| Belge üzerinden Q&A chat | StudyFetch, Mindgrasp, TurboLearn, AskSia, ChatPDF, AskYourPDF, StudyX, NoteGPT | ❌ |
| Yönlendirmeli AI öğretmen | StudyFetch (Sparky), Khanmigo, Synthesis, Gizmo, Studyable, Quizlet (Q-Chat), StudySmarter | ❌ |
| **Atıflı yanıtlar** (yanıt → kaynak pasaj) | Mindgrasp, ChatPDF, AskYourPDF, NotebookLM, StudyFetch, Monic | ✅ (notlarda; chat'te yok) |

### 5.4 Çalışma Mekanikleri

| Özellik | Sunan uygulamalar | StuHub |
|---------|-------------------|--------|
| Spaced repetition | Anki, Knowt, RemNote, Brainscape, Quizlet, StudySmarter, Gizmo, Wisdolia, TurboLearn | ❌ |
| Güven dereceli tekrar (Again/Hard/Good/Easy) | Brainscape, Knowt, Quizlet, OmniSets, KardsAI | ❌ |
| Oyunlaştırılmış quiz modları | Quizizz, Quizlet, StudySmarter, Knowt, Shiken | ❌ |
| Paylaşımlı içerik kütüphanesi | Quizlet, Anki, Knowt, Brainscape, StudySmarter, Course Hero, Quizizz | ❌ (local-first gereği kısıtlı alan) |
| Streak / günlük hedef / XP | Quizlet, StudyFetch, Shiken, OmniSets | ❌ |
| İlerleme/mastery göstergesi | Quizlet, Monic, Knowt, TurboLearn, Brainscape | ❌ |

### 5.5 Platform & Dağıtım

| Özellik | Sunan uygulamalar | StuHub |
|---------|-------------------|--------|
| Tarayıcı eklentisi | StudyFetch, NoteGPT, Fireflies, Wisdolia, Quizgecko, Quizizz, Knowt, AskYourPDF | ❌ |
| Mobil uygulama | 28/30 uygulama | ❌ (planlı: mobil companion — Bölüm 10/6) |
| Çoklu cihaz senkron | Quizlet, Anki, Knowt, RemNote, Course Hero... | 🟡 (opsiyonel sync — Bölüm 13/7) |
| LMS entegrasyonu | StudyFetch, Mindgrasp, Fireflies, Speak.AI, Quizgecko | ❌ |
| Ücretsiz katman | 28/30 uygulama | ✅ (tamamen yerel; yalnız kendi API anahtarın) |
| Export (Anki/PDF/MD) | Knowt, RemNote, Wisdolia, Anki, Otter | 🟡 (PDF not var; Anki/MD planlı) |
| Çok dilli destek | Speak.AI, ChatPDF, NoteGPT, Voicenotes, Mindgrasp | 🟡 (Türkçe güçlü; çok dil planlı — Bölüm 13/4) |
| Yerel-öncelikli / gizlilik (hesap yok, veri cihazda) | Anki (kısmen), Granola (kısmen) | ✅ **StuHub'ın temel farkı** |

### 5.6 Niş Okuması: En Yaygın 10 Özellik

1. **PDF'ten içerik üretimi** — nişin giriş bileti (30/30'e yakın)
2. **AI özet + not** — neredeyse herkes
3. **Flashcard üretimi + spaced repetition** — 15+ uygulama
4. **Quiz/pratik test üretimi** — 13+ uygulama
5. **Belge üzerinden chat (RAG chat)** — 8+ uygulama; nişin en hızlı yayılan kalıbı
6. **Atıflı/kaynaklı yanıtlar** — güven satan farklılaştırıcı (NotebookLM öncü)
7. **YouTube video → içerik** — 9 uygulama
8. **Ses/ders kaydı → not** — 7 uygulama
9. **Essay/ödev değerlendirme** — 3+ uygulama
10. **Streak/oyunlaştırma katmanı** — elde tutma motoru

**StuHub'ın boşluk haritası:** Flashcard + spaced repetition, belge chat'i, YouTube/ses girdisi, streak/progress katmanı ve mobil en büyük boşluklar; atıflı üretim, quiz kalitesi (55 soruluk çok tipli + açık uçlu otomatik puanlama) ve yerel-öncelikli gizlilik ise StuHub'ın en güçlü kartları.

---

## 6. Arayüz Tasarım Örneklemi

> Yöntem: App Store/Google Play ekran görüntüsü sayfaları, resmi yardım dokümanları ve ürün incelemeleri tasarım kanıtı olarak önceliklendirildi. Renkler pazarlama/mağaza materyalinden aktarılan "ton"lardır (doğrulanmış hex değil).

### 6.1 Uygulama Bazlı Tasarım Kartları

| Uygulama | Renk | Stil | İç arayüz düzeni | Ayırt edici UI |
|----------|------|------|------------------|----------------|
| **StudyFetch** | Mor/menekşe vurgu, koyu indigo tonlar | Temiz SaaS, yuvarlak kartlar; pazarlamada gradyan "AI magic" | Sol sidebar + belge/not merkezi + Sparky chat paneli; set ızgarası + set başına ilerleme | **Sparky** AI avatar (kalıcı chat rayı); **Spaced Learning Hub** (streak'li günlük tekrar takvimi) |
| **Mindgrasp** | Lacivert + mor/mavi gradyan; özellik başına renk (mavi=not, mor=quiz) | Minimal, profesyonel EdTech; yoğun bilgi | Solda yükleme kuyruğu/belge listesi; belge başına **sekmeler: AI Notes, Summaries, Flashcards, Quizzes, AI Tutor**; chat atıf numaralarıyla kaynak gösterir | Tek yükleme → 5 araçlı sekmeli çalışma alanı; atıf çapalı "Ask AI" yan paneli |
| **NotebookLM** | Material 3 nötr gri/beyaz + Google mavisi | Sakin, editoryal, aşırı minimal; oyunlaştırma yok | Üç bölme: sol **kaynak kütüphanesi**, orta chat/kanvas, sağ notlar; üretilen çıktılar kart olarak açılır | **Numaralı inline atıflı, kaynak-temelli yanıtlar** (tıklayınca kaynak pasaj vurgulanır); Audio Overviews; Eyl 2025'ten beri Flashcards & Quizzes |
| **Quizlet** | Indigo **#4255FF** + mor ikincil + sarı vurgu | Oyuncu, yuvarlak, renkli, oyunlaştırılmış; sektörün "öğrenci dostu" referansı | Set sayfası hub'dır — üstte **mod sekmeleri: Flashcards, Learn, Test, Match, Q-Chat**; sınıf klasörleri; streak sayaçları | Tek içerik üzerinde çoklu çalışma modu sekmeleri; **Q-Chat** AI öğretmen |
| **Knowt** | Indigo/mor, beyaz zemin | Minimal, hafif oyuncu; düşük görsel gürültü | Klasör/set dashboard'u; çevirmeli flashcard + **Again/Hard/Good/Easy** tekrar butonları; AI notlar stillenmiş markdown | Quizlet/PDF/YouTube'dan otomatik set import; AI practice test üretimi |
| **TurboLearn** | Turkuaz vurgu + çok koyu slate | Temiz, hızlı-ürün hissi; mobilde koyu kartlar + camgöbeği vurgu | Yükle → **Notes (stillenmiş markdown), Flashcards (kaydırma destesi), Quizzes**; belge başına ilerleme özet kartı | Sihirli yükleme akışı + işleme animasyonu; soru bazlı açıklamalı quiz sonuç ekranı |
| **Coconote** | Mor/pembe gradyan + sıcak vurgular | Dost canlısı, yuvarlak, tüketici uygulaması; TikTok doğumlu | Ses/video/PDF yükle → **renk kodlu yapılandırılmış notlar** + anahtar terim kutusu; çalışma rehberi + quiz | **Renk kodlu not sistemi** (konu başına renk, nottan quize tutarlı taşınır) — nişte gerçekten farklı bir kimlik |
| **Studyable** | Mavi/indigo + beyaz | Temiz, chat-öncelikli mobil; yuvarlak mesaj balonları | **Chat-öncelikli öğretmen ekranı** ana yüzeydir; flashcard kaydırmalı; essay inceleme ekranı | AI **essay notlandırma + satır içi açıklamalar** |
| **Monic.ai** | Koyu indigo + mavi→mor gradyan vurgular | Koyu-mod AI ürünü estetiği; yoğun dashboard | Kurs/kütüphane sidebar'ı; belge çalışma alanı sekmeleri: **Notes, Flashcards, Quizzes, Summary**; materyalden beslenen AI chat | Anında notlamalı quiz kurucu; kurs başına **mastery/ilerleme dashboard'u** |
| **Wisdolia** | Yeşil/teal + beyaz | Fonksiyonel, minimal; ürün bir **Chrome uzantısı** (kompakt overlay) | Okuma sayfası üzerinde açılan flashcard destesi; sağ çekmece: kart çevir + doğru/yanlış + "daha fazla üret" | **Bağlam içi flashcard üretimi** (okurken/izlerken kartlar gelir — sıfır bağlam değişimi) |
| **OmniSets** | Mor/indigo + beyaz, gradyansız | Temiz, fonksiyonel, sakin | **Klasör + alt klasör ağacı sidebar**; set başına mod sekmeleri: Flashcards, Learn, Write, Test, Match-benzeri oyunlar, Quiz Mode; **StudyPlans** takvimi | Klasör/alt klasör organizasyonu (nişte nadir); otomatik tekrar planlayıcı takvim görünümü |
| **KardsAI** | Canlı mor + beyaz kartlar | Mobil-öncelikli, yuvarlak, oyuncu; kart çevirme merkezde | Deste listesi → çevirme + kaydırma + doğru/yanlış; üretim ekranında kaynak tipi seçici (PDF/fotoğraf/metin/konu) | **Fotoğraftan (OCR) flashcard üretimi**; ana ekranda "günün kartı" beslemesi |
| **Shiken** | Koyu tema + neon lime + mor | Cesur, enerjik, oyun estetiği; XP/leaderboard/avatar | 11 soru tipli quiz motoru; **Shiken Chat** öğretmen; her katmanda XP/streak/leaderboard | **Oyunlaştırılmış onboarding** (hedef/ilgi sorar, akışı kişiselleştirir); canlı çok oyunculu quizler |

### 6.2 Ortak Tasarım Desenleri (Top 10)

1. **"Yükle → araç sekmeleri" belge çalışma alanı** — tek kaynak; Notlar/Flashcard/Quiz/Özet sekmelerine yayılır *(Mindgrasp, Monic, TurboLearn, StudyFetch, Coconote)*
2. **Öz-değerlendirmeli flashcard çevirme** (Again/Hard/Good/Easy ya da ✓/✗) → spaced repetition *(Knowt, Quizlet Learn, OmniSets, KardsAI, Wisdolia)*
3. **Tek içerik üzerinde çalışma modu sekmeleri** — Flashcards | Learn | Test | Match *(Quizlet, OmniSets, Knowt, StudyFetch)*
4. **Belge yanında AI öğretmen chat paneli** — yan ray (StudyFetch Sparky, Mindgrasp) veya ana yüzey (Studyable, Shiken, NotebookLM) *(13 uygulamanın neredeyse tümü)*
5. **Kaynak-temelli yanıtlar + inline atıflar** — kaynak pasaja giden numaralı çipler *(NotebookLM kanonik, Mindgrasp, StudyFetch, Monic)*
6. **Streak, günlük hedef ve ilerleme çubukları** — elde tutma katmanı *(Quizlet, StudyFetch Spaced Learning Hub, Shiken XP, OmniSets StudyPlans)*
7. **Sol sidebar IA: klasör/set dashboard'u + çalışma kartları ızgarası** *(OmniSets alt klasörlerle, Quizlet, Knowt, Monic, StudyFetch)*
8. **Set başına ilerleme halkası / mastery göstergesi** *(Quizlet, Monic, Knowt, TurboLearn)*
9. **SaaS açılış yığını: hero mockup → özellik bölümleri → sosyal kanıt → fiyatlandırma** + docs/blog hub'ı *(tüm web uygulamaları)*
10. **Persona/onboarding kişiselleştirme** — başta konu/hedef sorar, akışı şekillendirir *(Shiken kanonik, Quizlet, StudyFetch)*

### 6.3 Baskın Renk Aileleri

- **Indigo/mor ailesi (nişin varsayılanı):** Quizlet (#4255FF + mor), StudyFetch, Knowt, Monic, OmniSets, KardsAI, Coconote, Mindgrasp — mor "çalışma/AI-sihri" olarak okunuyor
- **Nötr/Material ailesi:** NotebookLM (beyaz/gri + Google mavisi) — güven sinyali veren anti-marka
- **Turkuaz/camgöbeği:** TurboLearn — hız/teknoloji aykırısı
- **Lime/yeşil + koyu oyun ailesi:** Shiken, Wisdolia — enerji/büyüme
- Ürün arayüzünde baskın desen: **açık zemin + tek doygun vurgu** (pazarlama gradyan kullansa bile)

### 6.4 Navigasyon / Bilgi Mimarisi Gelenekleri

- Dashboard-öncelikli + sol sidebar: klasörler → setler → set detayı → mod sekmeleri. **Set/dosya atomik birimdir**
- Belge-öncelikli çalışma alanları (NotebookLM, Mindgrasp, Monic): kaynak listesi → üretilen içerikler bölme/sekme olarak; üç bölmeli düzen yükseliyor
- Mobil alt sekmeler: Home / Decks / Create / Profile — **oluşturma belirgin merkez aksiyonu**
- Sayfa navigasyonu yerine **mod değiştirme** (çalışma arayüzleri set içinde sekmedir)
- Oyunlaştırma katmanı aynı içeriği sarmalar, değiştirmez (Shiken, StudyFetch)

### 6.5 StuHub'un Ödünç Alabilecekleri (8 Somut Fikir)

1. **Dönem → Ders → Notebook klasör ağacı sidebar'ı** — OmniSets'in klasör/alt klasör deseni, StuHub hiyerarşisine birebir oturur
2. **Atıf çipli AI notlar** — NotebookLM tarzı numaralı çipler; tıklayınca sağ şeritte kaynak pasaj vurgulanır. StuHub'ın "atıflı not" özelliğinin doğal evrimi
3. **Quiz → gözden geçirme döngüsü** — her bölüm/genel quiz sonunda yanlış yapılan sorular atıflı nota bağlanır (Mindgrasp/NotebookLM temellendirmesi + Quizlet test-review UX'i)
4. **Notebook düzeyinde çalışma modu sekmeleri** — Notlar | Flashcard | Bölüm Quiz | Genel Quiz sekmeleri; 55 soruluk genel quiz ayrı bir "özellik adası" olmaktan çıkar
5. **Güven dereceli flip kartlar (Again/Hard/Good/Easy)** — Knowt/Quizlet Learn deseni; spaced repetition yerel kalır (bulut planlama yok), ilerleme cihazda saklanır
6. **Açık nötr zemin + tek doygun vurgu** — nişin varsayılanı olan indigo/mor tek vurgu rengi; karanlık mod opsiyonel tema olarak kalır
7. **Yerel streak + günlük hedef halkası** — dashboard'da küçük ilerleme halkası/streak çipi (StudyFetch, Quizlet); leaderboard yok — kişisel kalır, minimal estetiğe uyar
8. **3 adımlı Türkçe onboarding** — "Bu dönem hangi dersleri alıyorsun?" sohbet tonuyla Dönem/Ders ağacını anında kurar (Shiken dersi)

**Önerilen görsel çıpa:** NotebookLM'in sakin üç sütunu + Quizlet/OmniSets'in mod sekmesi hub'ı + tek mor vurgu = minimal, yerel-öncelikli, güvenilir ve yine de net biçimde "AI destekli" okunan bir arayüz.

**Ekran görüntüsü referansları (örneklem):** [StudyFetch App Store](https://apps.apple.com/cz/app/studyfetch-make-learning-easy/id6663574866) · [StudyFetch Google Play](https://play.google.com/store/apps/details?id=com.studyfetch.mobile.v2&hl=en_IN) · [Mindgrasp App Store](https://apps.apple.com/dk/app/mindgrasp/id1638182014) · [TurboLearn App Store](https://apps.apple.com/us/app/turbolearn-ai-note-taker/id6502794561) · [Coconote App Store](https://apps.apple.com/us/app/coconote-ai-note-taker/id6479320349) · [Studyable App Store](https://apps.apple.com/us/app/studyable-ai-study-help/id6448214477) · [KardsAI App Store](https://apps.apple.com/us/app/kardsai-instant-flashcards/id6462700482) · [Shiken App Store](https://apps.apple.com/us/app/shiken-quizzes-study-tools/id1481436914) · [Knowt App Store](https://apps.apple.com/si/app/knowt-ai-flashcards-notes/id6463744184) · [OmniSets yardım dokümanları](https://help.omnisets.com/quickstart) · [NotebookLM flashcards/quizzes](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-app-quizzes-flashcards/)

---

## 7. StuHub Geliştirme Önerileri

### 7.1 Stratejik Okuma (Konumlanma)

Nişin tamamı **bulut + abonelik/kredi ekonomisi** üzerine kurulu: StudyFetch'te "krediler hızla yanıyor", Mindgrasp'ta fatura/iptal şikayetleri, her ikisinde export eksiklikleri. StuHub'ın üç yapısal avantajı bu şikayetlerin **tam üstüne** oturuyor:

1. **Maliyet:** BYO DeepSeek anahtarı = abonelik yok, kredi limiti yok (kullanım başına kuruş mertebesi — `KULLANIM.md` Bölüm 4). Bu, pazarlama mesajı olarak da kullanılabilir.
2. **Atıf derinliği:** Rakipler atfı yalnızca chat yanıtlarında gösterir; StuHub **üretim çıktısının kendisinde** (not + quiz açıklamaları) inline atıf + kaynak pop-up sunuyor. Bu, nişin en güçlü güven sinyalidir (NotebookLM deseni).
3. **Gizlilik:** 30 uygulamanın hiçbiri tam yerel değil. "Verin cihazında kalır" tek başına bir satış argümanıdır.

Strateji: **"Rakiplerin eksik bıraktığı şeyler"** üzerine oyna (export, şeffaf maliyet, atıf, yerellik) ve **nişin standartlarına** en ucuz şekilde yetiş (flashcard, chat, streak). Türkçe öncelikli olmak, İngilizce-öncelikli nişte bir boşluk.

### 7.2 Kısa Vade (1–2 Hafta — Yüksek Etki / Düşük Maliyet)

| # | Öneri | Kanıt (rakip/desen) | StuHub'a uyarlama | Mevcut altyapı |
|---|-------|---------------------|-------------------|----------------|
| 1 | **Flashcard üretimi + yerel spaced repetition** | Nişin en yaygın özelliği: 15+ uygulama (Knowt, Quizlet, Anki, Gizmo, Wisdolia...); StuHub'da tamamen yok | Chapter notlarından + quiz verilerinden kart üret (soru-cevap + anahtar terim); SQLite'ta SM-2 benzeri yerel zamanlama; **Again/Hard/Good/Easy** dörtlüsü (Bölüm 6.5/5) | Chapter Quiz Ajanı'nın şema/prompt kalıbı + `notes`/`topics_json` kayıtları |
| 2 | **"Materyale Sor" — belge chat'i** | Nişin en hızlı yayılan kalıbı (8+ uygulama); NotebookLM kanonik, Mindgrasp/StudyFetch takip ediyor | Hibrit retrieval zaten var; **yanıtlar zorunlu atıflı** ("SADECE context" kuralı + atıf doğrulama) → NotebookLM tarzı tıklanabilir kaynak çipleri (Bölüm 6.5/2) | `rag_service` + `citations_ledger` + SSE altyapısı |
| 3 | **Notebook düzeyinde çalışma modu sekmeleri** | Quizlet/OmniSets deseni (Bölüm 6.2/3): Notlar \| Flashcard \| Bölüm Quiz \| Genel Quiz | 55 soruluk genel quiz "ayrı özellik adası" olmaktan çıkar; tek ekran = tek çalışma birimi | Frontend `NotebookPage` yeniden düzenleme (yeni rota yok) |
| 4 | **Anki + Markdown export** | StudyFetch/Mindgrasp'ın export şikayetleri + Knowt/RemNote/Wisdolia'nın Anki export'u; yol haritası Bölüm 13/2'de zaten planlı | `export_service.py`'ye Anki (.apkg) ve MD ekle; flashcard çıktısının doğal tüketicisi | Mevcut `export_service.py` + PDF export kalıbı |
| 5 | **Streak + günlük hedef halkası (yerel)** | Quizlet/StudyFetch/Shiken deseni; leaderboard YOK (kişisel kalır — Bölüm 6.5/7) | Dashboard kartına küçük ilerleme halkası; veri SQLite'ta, bulut yok | `quiz_attempts`/`notes` kayıtlarından türetilir |
| 6 | **3 adımlı Türkçe onboarding + klasör ağacı sidebar** | Shiken onboarding dersi (Bölüm 6.2/10) + OmniSets klasör/alt klasör deseni (Bölüm 6.5/1) | "Bu dönem hangi dersleri alıyorsun?" → Dönem/Ders ağacını sohbet tonuyla kurar; sol ray = Dönem→Ders→Chapter | `TermsPage` + form bileşenleri |

### 7.3 Orta Vade (v2)

| # | Öneri | Kanıt | Uyarlama / Not |
|---|-------|-------|----------------|
| 7 | **Essay/ödev değerlendirici** | Studyable, Mindgrasp (AI Grader), Khanmigo; StudyFetch'te de var | StuHub'ın Essay Grader Ajanı **zaten var** (açık uçlu puanlama: rubrik + doğru/eksik/yanlış/gereksiz + ideal cevap). Tek eksik: "ödev yükle → değerlendir" genel akışı. Neredeyse sıfır maliyetli büyük özellik |
| 8 | **YouTube video → içerik** | 9 uygulama; StudyFetch'in "youtube-to-notes" ve Mindgrasp'ın video özetleme sayfaları bu talebin kanıtı | Yerel `yt-dlp` (Unlicense) ile transkript/alt yazı çek → indeksle → mevcut not/quiz hattı. Ücretsizlik sözleşmesine uygun; kişisel kullanımda yaygın pratik |
| 9 | **Ses/ders kaydı → not** | Mindgrasp'ın temel farkı; Otter/Fireflies kümesi; Granola öğrencilere 12 ay ücretsiz veriyor | **faster-whisper** (MIT) ile yerel transkripsiyon — bulut yok, gizlilik korunur; çıktı indekslenip not/quiz üretimine girer. Yerel LLM değil, yerel STT — ücretsizlik sözleşmesine uygun |
| 10 | **Çalışma rehberi / chapter özeti görünümü** | StudyFetch study-guide-maker, Mindgrasp ai-study-guide-maker; Algor/NoteGPT'de görsel haritalar | Mevcut not üretiminin yan ürünü: chapter özeti + anahtar terim listesi + (opsiyonel) kavram haritası görünümü |
| 11 | **Mobil erişim (PWA veya yerel ağ)** | 28/30 uygulama mobil; yol haritası Bölüm 10/6 "mobil companion" | Tam native yerine: **PWA** (Vite tabanlı, ucuz) veya telefonun aynı ağdan localhost'a erişimi; veri hâlâ bilgisayarda kalır |
| 12 | **Yönlendirmeli (Sokratik) chat modu** | Spark.E "guided chatting" + Khanmigo'nun Sokratik tarzı — doğrudan cevap yerine ipucu | "Materyale Sor" içinde mod seçici: **Doğrudan yanıt / Sınav modu (bana soru sor)**. Atıf zorunluluğu devam eder |

### 7.4 Uzun Vade

| # | Öneri | Not |
|---|-------|-----|
| 13 | **Opsiyonel bulut sync** (yol haritası Bölüm 13/7) | Feature flag arkasında; çok cihaz talebi için |
| 14 | **Yeni dosya tipleri: DOCX, EPUB, fotoğraf (OCR)** | Yol haritası Bölüm 13/5; OCR için yerel **Tesseract** (Apache-2.0) — KardsAI'nin fotoğraftan kart üretimi deseni |
| 15 | **Çok dilli not üretimi** | Yol haritası Bölüm 13/4; bge-m3 zaten çok dilli — prompt dili değişimi yeterli |
| 16 | **Paylaşım/paket export (dönem arşivi)** | StudyFetch/Mindgrasp'ta export acısı kanıtlandı; "tüm dönemi tek dosyada dışa aktar" StuHub'ı ayrıştırır |

### 7.5 Öncelik Matrisi (Etki × Maliyet)

```
Yüksek etki ┌──────────────────────────────┬──────────────────┐
            │ 1 Flashcard+SR  2 Materyale Sor │ 7 Essay Grader   │
            │ 3 Mod sekmeleri 4 Export      │ 8 YouTube 9 Ses  │
            │ 5 Streak        6 Onboarding  │ 12 Sokratik mod  │
            ├──────────────────────────────┼──────────────────┤
Düşük etki  │ 10 Özet/rehber               │ 13 Sync 14 OCR   │
            │ 11 PWA                        │ 15 Çok dil 16 Paket│
            └──────────────────────────────┴──────────────────┘
                 Düşük maliyet                Yüksek maliyet
```

**Önerilen sıra:** 2 (Materyale Sor) → 1 (Flashcard+SR) → 4 (Export) → 3+5+6 (UI paketi) → 7 → 8/9 → 11.

### 7.6 Bilinçli Olarak Yapılmaması Gerekenler

- **Paylaşımlı içerik kütüphanesi / sosyal katman** — local-first ve gizlilik felsefesiyle çelişir; nişin "milyonlarca set" oyuncularıyla rekabet edilmez
- **Leaderboard / çok oyunculu oyunlaştırma** — kişisel çalışma aracı kimliğine aykırı; streak/kişisel hedef yeterli (Bölüm 6.5/7)
- **LMS entegrasyonları** — yerel ürünün kullanıcısı buna ihtiyaç duymaz; StudyFetch bile ancak API ile DIY sunuyor
- **Kredi/kota ekonomisi** — rakiplerin en çok şikayet aldığı desen; StuHub'ın BYO-key modeli üstünlüktür, korunmalı
- **Yerel LLM çalıştırma** — yol haritası Bölüm 7'de kullanıcı kararıyla kapsam dışı; dokunma

---

## 8. Kaynaklar

**Anchor ürünler:**
- [StudyFetch — Spark.E AI tutor](https://www.studyfetch.com/features/sparke) · [StudyFetch — Arcade](https://sso.studyfetch.com/features/arcade) · [StudyFetch — guided chatting](https://sso.studyfetch.com/blog/meet-guided-chatting-on-studyfetch) · [StudyFetch — Wolfram ortaklığı](https://sso.studyfetch.com/blog/studyfetch-partners-with-wolfram-to-add-advanced-math-tools-to-ai-tutor-spark-e) · [StudyFetch — essay grading](https://sso.studyfetch.com/docs/tutorial-doc-format/essaygrading) · [StudyFetch App Store](https://apps.apple.com/cz/app/studyfetch-make-learning-easy/id6663574866) · [mspoweruser StudyFetch incelemesi](https://mspoweruser.com/studyfetch-ai-review/)
- [Mindgrasp — AI Study Guide Maker](https://www.mindgrasp.ai/ai-study-guide-maker) · [Mindgrasp — AI Grader](https://www.mindgrasp.ai/ai-grader) · [Mindgrasp — ders özetleyici](https://www.mindgrasp.ai/ai-summarizer/lecture) · [Mindgrasp — ses transkripsiyonu](https://www.mindgrasp.ai/ai-transcriber/audio-to-text-transcriber) · [Mindgrasp App Store](https://apps.apple.com/us/app/mindgrasp/id1638182014) · [Unite.AI Mindgrasp incelemesi](https://www.unite.ai/mindgrasp-ai-review/) · [Mindgrasp Canny (export sorunları)](https://mindgrasp.canny.io/feature-requests/p/problem-exporting-notes-and-summaries)
- Trustpilot: [StudyFetch](https://www.trustpilot.com/review/studyfetch.com) · [Mindgrasp](https://www.trustpilot.com/review/mindgrasp.ai)

**Katalog / karşılaştırma sayfaları:**
- [ToolChase — StudyFetch alternatives](https://toolchase.com/alternatives/studyfetch/) · [SourceForge — Study Fetch alternatives](https://sourceforge.net/software/product/Study-Fetch/alternatives) · [Dupple — best AI study tools](https://dupple.com/learn/best-ai-study-tools) · [ToolRadar — best AI study tools](https://toolradar.com/guides/best-ai-study-tools) · [LaxuAI — 10 best study apps](https://laxuai.com/best-study-apps) · [RightAIChoice — Mindgrasp](https://rightaichoice.com/tools/mindgrasp) · [RightAIChoice — StudyFetch](https://rightaichoice.com/tools/study-fetch) · [Quizlet — PCMag](https://me.pcmag.com/en/education/19970/quizlet) · [The Verge — Quizlet Q-Chat](https://www.theverge.com/2023/8/9/23826191/quizlet-generative-ai-chatgpt-education) · [Granola — öğrenci programı](https://www.granola.ai/students)

**Arayüz / tasarım kaynakları:**
- [NotebookLM flashcards/quizzes (blog.google)](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-app-quizzes-flashcards/) · [9to5Google — NotebookLM Studio redesign](https://9to5google.com/2025/08/06/notebooklm-studio-redesign/) · [Quizlet marka renkleri](https://pickcoloronline.com/brands/quizlet/) · [Quizlet — Refero style guide](https://styles.refero.design/style/528eb1d4-8508-4dc6-87b4-c7b92d648dac) · [Knowt — flashcard mode dokümanı](https://intercom.help/knowt/en/articles/10298062-how-can-i-use-the-flashcard-mode) · [OmniSets yardım dokümanları](https://help.omnisets.com/quickstart) · [Shiken — soru tipleri](https://help.shiken.ai/en/articles/7889375-what-types-of-questions-can-i-create) · [Shiken onboarding vaka çalışması](https://www.lightningux.design/projects/improving-shikens-onboarding-experience) · [Coconote TikTok büyüme analizi](https://www.socialgrowthengineers.com/259m-views-200k-mrr-coconote-ais-shared-playbook-for-tiktok-reels) · [StudyFetch yeni görünüm blog'u](https://sso.studyfetch.com/blog/studyfetch-has-a-new-look)
- Ekran görüntüsü örneklemi (App Store sayfaları): [StudyFetch](https://apps.apple.com/cz/app/studyfetch-make-learning-easy/id6663574866) · [TurboLearn](https://apps.apple.com/us/app/turbolearn-ai-note-taker/id6502794561) · [Coconote](https://apps.apple.com/us/app/coconote-ai-note-taker/id6479320349) · [Studyable](https://apps.apple.com/us/app/studyable-ai-study-help/id6448214477) · [KardsAI](https://apps.apple.com/us/app/kardsai-instant-flashcards/id6462700482) · [Shiken](https://apps.apple.com/us/app/shiken-quizzes-study-tools/id1481436914) · [Knowt](https://apps.apple.com/si/app/knowt-ai-flashcards-notes/id6463744184)

---

> **Yöntem notu:** Bu rapor, üç paralel web araştırması ajanının çıktıları (30 uygulama kataloğu, iki anchor derin incelemesi, 13 uygulamanın arayüz örneklemi) ve StuHub kod tabanı/`PROJE_YOL_HARITASI.md`/`YETENEKLER/` incelemesi birleştirilerek üretilmiştir. Fiyatlar araştırma tarihindeki halka açık planlardır ve değişebilir; renkler pazarlama materyalinden aktarılan tonlardır.
