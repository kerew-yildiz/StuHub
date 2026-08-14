# StuHub — Rakip UI/UX Analizi

> **Amaç:** "AI destekli çalışma / ders içeriği üretim platformları" nişindeki 10 rakip uygulamanın **güncel** arayüz tasarımını (görsel kimlik, bilgi mimarisi, ayırt edici desenler, oyunlaştırma, mobil) web araştırmasıyla incelemek ve StuHub için somut, ödünç alınabilir tasarım çıkarımları üretmek.
>
> **Kapsam (öncelik sırası):** StudyFetch, Mindgrasp, NotebookLM, Quizlet, Knowt, Coconote, TurboLearn AI, Algor Education, Studyable, OmniSets.
>
> **Durum:** ✅ Tamamlandı — 10 rakip için UI/UX kartı, nişin ortak tasarım desenleri, renk/tipografi akımları ve StuHub çıkarımları dahil.

---

## 1. Giriş ve Yöntem

### 1.1 Neden bu analiz

`NİŞ_ANALİZİ_RAPORU.md` nişin **özellik envanterini** (30 uygulama) ve **iki anchor derin incelemesini** (StudyFetch & Mindgrasp) çıkarmıştı; arayüz için 13 uygulamalık bir özet örneklem (Bölüm 6) içeriyordu. Bu belge onun üstüne inşa edilir ve farkı şudur: **özellik değil, salt arayüz/deneyim katmanına** odaklanır; her rakip için görsel kimlik → bilgi mimarisi → ayırt edici desen → oyunlaştırma → mobil sırasını ayrı ayrı belgeler. Amaç, StuHub'ın frontend ajanına (`AJANLAR/13-frontend-gelistirici-ajani.md`) ve Stil Ajanı'na (`YETENEKLER/07-stil-rehberi.md`) girdi sağlamaktır.

### 1.2 Yöntem ve Kaynaklar

- **Birincil kaynaklar:** Resmi yardım dokümanları ve ürün blogları (StudyFetch blog, OmniSets Docs, Quizlet Help, Google NotebookLM blog/support, Algor Education Help Center).
- **Tasarım kanıtı:** App Store / Google Play ekran görüntüsü sayfaları, tasarım vitrin siteleri (ScreensDesign), marka/renk katalogları (Brandfetch, PickColorOnline).
- **İkincil/inceleme:** Unite.AI, Fritz.ai, EducationalAppStore, aiseekertools, daidu.ai, ToolMage, Coda One gibi ürün incelemeleri; NotebookLM'in "Designing NotebookLM" tarzı tasarım yazıları.
- **Güncel durum doğrulaması:** Coconote'un Quizlet tarafından satın alınması (2025), NotebookLM'in Flashcards/Quizzes ve yeni görünümü, StudyFetch'in Learn Engine + Mini-Apps + Spaced Learning Hub duyuruları.

> **Yöntem notu:** Renkler, şirketler nadiren resmi hex paylaştığı için **pazarlama/mağaza materyalinden aktarılan "ton"lardır** (doğrulanmış hex değildir); tipografi çoğu rakip için belgelenmediğinden **gözleme dayalı** sınıflandırmadır. Bu belge `NİŞ_ANALİZİ_RAPORU.md` ile çelişmeyecek biçimde, onun "ton" atıflarını tekrarlar ve derinleştirir.

### 1.3 Temel Kaynak Listesi (özet)

- StudyFetch: [Spark.E](https://www.studyfetch.com/features/sparke) · [Spaced Learning Hub](https://sso.studyfetch.com/blog/meet-the-spaced-learning-hub) · [Learn Engine](https://sso.studyfetch.com/blog/the-learn-engine) · [Mini-Apps](https://sso.studyfetch.com/blog/mini-apps-on-studyfetch) · [Study Plan redesign](https://sso.studyfetch.com/blog/study-plan-redesign) · [Brandfetch](https://brandfetch.com/studyfetch.com)
- Mindgrasp: [App Store](https://apps.apple.com/cy/app/mindgrasp/id1638182014) · [Unite.AI incelemesi](https://www.unite.ai/mindgrasp-ai-review/) · [EducationalAppStore](https://www.educationalappstore.com/website/mindgrasp-ai) · [Canny özellik talepleri](https://mindgrasp.canny.io/feature-requests/p/feature-rich-list)
- NotebookLM: [Yeni görünüm + premium (blog.google)](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-new-features-december-2024/) · [Interface Panels (LibGuides UPRM)](https://libguides.uprm.edu/notebooklm/interface_panels) · [Designing NotebookLM](https://liduos.com/posts/designing-notebooklm)
- Quizlet: [Features (dev.to)](https://dev.to/john_dusty_6e163a86b84/quizlet-app-features-that-drive-60m-users-and-what-founders-can-learn-3ohe) · [Answer Streaks (Help)](https://help.quizlet.com/hc/en-ca/articles/40011154960653-Studying-with-Answer-Streaks) · [ScreensDesign](https://screensdesign.com/showcase/quizlet-study-with-flashcards)
- Knowt: [App Store](https://apps.apple.com/us/app/knowt-ai-flashcards-notes/id6463744184) · [Fritz.ai incelemesi](https://fritz.ai/knowt-ai-review/)
- Coconote: [ScreensDesign](https://screensdesign.com/showcase/coconote-ai-note-taker) · [TikTok büyüme analizi](https://www.socialgrowthengineers.com/259m-views-200k-mrr-coconote-ais-shared-playbook-for-tiktok-reels) · [Quizlet'e satış (RevenueCat podcast)](https://metacast.app/podcast/sub-club-by-revenuecat/DlWjuiPD/bootstrapped-to-6-7m-arr-and-an-exit-to-quizlet-in-2-years-brett-bauman-and-zack-hargett-coconote/EsSaMxJe)
- TurboLearn: [App Store](https://apps.apple.com/us/app/turbolearn-ai-note-taker/id6502794561) · [Google Play](https://play.google.com/store/apps/details?id=ai.turbolearn) · [ToolMage](https://www.toolmage.com/en/tool/turbo/) · [Coda One incelemesi](https://www.codaone.ai/tools/turbolearn-ai/)
- Algor Education: [Concept Map Generator](https://www.algoreducation.com/en/ai-concept-map-generator) · [Mind Map Generator](https://www.algoreducation.com/en/ai-mind-map-generator) · [aiseekertools incelemesi](https://aiseekertools.com/tools/algoreducation-com) · [Help Center](https://www.algoreducation.com/en/help-center)
- Studyable: [aiseekertools incelemesi](https://aiseekertools.com/tools/studyable-app) · [SourceForge](https://sourceforge.net/app/studyable/web-app/) · [App Store](https://apps.apple.com/us/app/studyable-ai-study-help/id6448214477)
- OmniSets: [Quickstart](https://help.omnisets.com/quickstart) · [Study Mode](https://help.omnisets.com/guides/study-mode) · [StudyPlans](https://help.omnisets.com/guides/studyplans) · [aiseekertools incelemesi](https://aiseekertools.com/tools/omnisets-ai)

---

## 2. Rakip Başına UI/UX Kartları

### 2.0 Özet Tablo

| Uygulama | Renk paleti | Tipografi | Düzen / IA | Ayırt edici desenler | Oyunlaştırma | Mobil |
|----------|-------------|-----------|-----------|----------------------|--------------|-------|
| **StudyFetch** | Mor/menekşe vurgu + koyu indigo; pazarlamada gradyan "AI-sihri" | İnsancıl sans (SaaS varsayılanı) | Sol sidebar → set ızgarası → belge çalışma alanı; kalıcı Sparky chat rayı | Sparky AI avatarı; Spaced Learning Hub (streak'li tekrar takvimi); mod seçici | Streak + günlük hedef; Arcade oyunları; Mini-Apps | iOS + Android aktif |
| **Mindgrasp** | Lacivert + mor/mavi gradyan; özellik başına renk (mavi=not, mor=quiz) | Nötr profesyonel sans | Sol belge kuyruğu → belge başına **5 sekmeli çalışma alanı** | Tek yükleme → çok araçlı sekmeler; atıf çapalı "Ask AI" yan paneli | Zayıf (streak yok) | iOS güçlü, Android zayıf |
| **NotebookLM** | Material 3 nötr gri/beyaz + Google mavisi (anti-marka) | Google Sans / ürün sans | **Üç bölme:** sol kaynak kütüphanesi · orta chat/kanvas · sağ notlar | Numaralı inline atıf → kaynak pasaj vurgusu; Audio Overviews; Flashcards/Quizzes | Yok (bilinçli) | Web + mobil uygulama |
| **Quizlet** | Indigo **#4255FF** + mor ikincil + sarı vurgu | Yuvarlak/oyuncu sans | Set sayfası hub; üstte **mod sekmeleri** (Flashcards/Learn/Test/Match/Q-Chat); sınıf klasörleri | Tek içerik üzerinde çoklu mod; Q-Chat AI öğretmen; cevap streak'i | Streak + günlük hedef + mastery; Match oyunu; rozetler | iOS + Android (çevrimdışı) |
| **Knowt** | Indigo/mor + beyaz zemin (düşük gürültü) | Temiz sans | Klasör/set dashboard → çevirmeli flashcard | **Again/Hard/Good/Easy** tekrar; Quizlet setlerini tek tık import; AI notlar stillenmiş markdown | Spaced repetition + mastery göstergesi (hafif) | iOS + Android + Chrome |
| **Coconote** | Mor/pembe gradyan + sıcak vurgular (TikTok doğumlu kimlik) | Dost canlısı yuvarlak sans | Ses/video/PDF yükle → renk kodlu yapılandırılmış not + anahtar terim kutusu | **Renk kodlu not sistemi** (konu başına renk, not→quize taşınır) | Hafif (kota/plan) | Mobil-öncelikli; App Store |
| **TurboLearn** | Turkuaz/camgöbeği vurgu + çok koyu slate | Temiz, hızlı-ürün sans | Yükle → Notes / Flashcards / Quizzes sekmeleri | **Sihirli yükleme akışı + işleme animasyonu**; soru açıklamalı quiz sonuç ekranı | Streak (hafif); belge başına ilerleme kartı | iOS + Android (koyu tema) |
| **Algor Education** | Teal/yeşil marka + **çok renkli harita düğümleri** | EdTech sakin sans | Yükle → **kavram haritası kanvası** + yan panel (özet/flashcard) | **Kavram haritası görünümü** (düzenlenebilir, iş birliği); otomatik düzen/outline | Yok / çok hafif | Web + Android |
| **Studyable** | Mavi/indigo + beyaz | Chat-baloncuklu sans | **Chat-öncelikli öğretmen ekranı** ana yüzey | AI essay notlandırma + satır içi açıklamalar; kaydırmalı flashcard | Zayıf | iOS (chat-öncelikli) |
| **OmniSets** | Mor/indigo + beyaz, gradyansız | Sakin fonksiyonel sans | **Klasör + alt klasör ağacı sidebar**; set başına mod sekmeleri + **StudyPlans takvimi** | Klasör/alt klasör organizasyonu; otomatik tekrar planlayıcı takvim | Spaced repetition planı (leaderboard yok, kişisel) | Web-öncelikli |

### 2.1 StudyFetch (studyfetch.com)

- **Görsel kimlik:** Baskın **mor/menekşe** vurgu + **koyu indigo** zeminler; pazarlama/landing'de "AI-sihri"ni çağrıştıran **mor→mavi gradyanlar**. Ürün içi yüzeyler temiz SaaS: yuvarlak kartlar, tek seviye gölge, set başına ilerleme çubuğu. ([Brandfetch — studyfetch.com](https://brandfetch.com/studyfetch.com), [yeni görünüm blog'u](https://sso.studyfetch.com/blog/studyfetch-has-a-new-look))
- **Bilgi mimarisi:** Solda **sidebar** (sınıf/set listesi) → orta alan **set ızgarası** → set açılınca **belge çalışma alanı**. Kalıcı **Sparky chat rayı** sağda veya altta açılır; içerik üretimi ile konuşma aynı bağlamda kalır.
- **Ayırt edici desenler:**
  - **Sparky AI avatarı** — materyalden eğitilen, kalıcı/erişilebilir chat öğretmeni; "guided chatting" (yönlendirmeli/Sokratik) mod seçici.
  - **Spaced Learning Hub** — streak'li, günlük tekrar içeren çalışma takvimi (rakiplere karşı konumlandıkları spaced repetition katmanı).
  - **Çalışma modu seçici** — Flashcard / Quiz / Pratik test / Arcade / Mini-Apps aynı set içinde.
- **Oyunlaştırma:** Streak + günlük hedef göstergesi; **Arcade oyunları** ve **Mini-Apps** (Learn Engine üstünde uyarlanabilir katman).
- **Mobil:** iOS + Android aktif; alttan sekmeli navigasyon, kart çevirme + quiz modları taşınmış. (bkz. [StudyFetch App Store](https://apps.apple.com/cz/app/studyfetch-make-learning-easy/id6663574866))

### 2.2 Mindgrasp (mindgrasp.ai)

- **Görsel kimlik:** **Lacivert** taban + **mor/mavi gradyan**; özellik başına renk kodlaması (mavi = not, mor = quiz, vb.). Minimal, profesyonel EdTech hissi; yoğun bilgi ama düzenli kartlar. ([App Store](https://apps.apple.com/cy/app/mindgrasp/id1638182014), [Unite.AI](https://www.unite.ai/mindgrasp-ai-review/))
- **Bilgi mimarisi:** Solda **yükleme kuyruğu / belge listesi**; seçilen belge için üstte **sekmeler: AI Notes · Summaries · Flashcards · Quizzes · AI Tutor**. Tek yükleme → 5 araçlı sekmeli çalışma alanı.
- **Ayırt edici desenler:**
  - **"Tek yükleme → çok araçlı sekmeli çalışma alanı"** nişin en net örneği.
  - **Atıf çapalı "Ask AI" yan paneli** — yanıtlar numaralı atıflarla kaynak pasaja gider.
  - **AI Grader / Homework Helper** — essay değerlendirme akışı.
- **Oyunlaştırma:** Zayıf; streak/XP katmanı yok (işlevsel EdTech kimliği).
- **Mobil:** iOS güçlü, Android zayıf (şikayet konusu); masaüstü web birincil yüzey.

### 2.3 NotebookLM (notebooklm.google.com)

- **Görsel kimlik:** **Material 3 nötr gri/beyaz + Google mavisi**; sakin, editoryal, aşırı minimal. Oyunlaştırma bilinçli olarak yok — "anti-marka" güven sinyali. ([Designing NotebookLM](https://liduos.com/posts/designing-notebooklm))
- **Bilgi mimarisi:** **Üç bölmeli düzen:** sol **kaynak kütüphanesi** · orta **chat/kanvas** · sağ **notlar/studio**. Üretilen çıktılar (not, sesli genel bakış, quiz, flashcard) kart olarak açılır. ([Interface Panels — LibGuides UPRM](https://libguides.uprm.edu/notebooklm/interface_panels))
- **Ayırt edici desenler:**
  - **Numaralı inline atıf** — yanıt içindeki çipler tıklanınca ilgili kaynak pasaj vurgulanır (nişin kanonik atıf deseni).
  - **Audio Overviews** (iki sunuculu podcast tarzı sesli özet) ve **Flashcards/Quizzes** (Eyl 2025'ten beri).
  - **Kaynak-temelli, "sadece kaynaklardan" yanıt** ilkesi — atıf güveni merkezde.
- **Oyunlaştırma:** Yok.
- **Mobil:** Web + mobil uygulama; mobilde tek kolonlu sadeleşme, atıf davranışı korunur. ([Yeni görünüm + premium — blog.google](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-new-features-december-2024/))

### 2.4 Quizlet (quizlet.com)

- **Görsel kimlik:** Indigo **#4255FF** ana renk + **mor** ikincil + **sarı** vurgu; oyuncu, yuvarlak, renkli — nişin "öğrenci dostu" görsel referansı. (bkz. [PickColorOnline — Quizlet](https://pickcoloronline.com/brands/quizlet/))
- **Bilgi mimarisi:** **Set sayfası = hub.** Üstte **mod sekmeleri: Flashcards · Learn · Test · Match · Q-Chat**; solda sınıf/klasör yapısı; streak sayaçları başlıkta.
- **Ayırt edici desenler:**
  - **Tek içerik üzerinde çoklu çalışma modu sekmeleri** (nişin standart deseni Quizlet'ten gelir).
  - **Q-Chat** — setten beslenen AI öğretmen sohbeti.
  - **Cevap streak'i (Answer Streaks)** — doğru cevap serisi görsel/onay. ([Answer Streaks — Help](https://help.quizlet.com/hc/en-ca/articles/40011154960653-Studying-with-Answer-Streaks))
- **Oyunlaştırma:** Streak + günlük hedef + mastery halkaları + Match oyunu + rozetler; en olgun oyunlaştırma katmanı. ([Features — dev.to](https://dev.to/john_dusty_6e163a86b84/quizlet-app-features-that-drive-60m-users-and-what-founders-can-learn-3ohe))
- **Mobil:** iOS + Android; **alt sekme düzeni** (Home / Library / Create / Profile), kart çevirme = dokunmatik tap, Learn'de kaydırma; çevrimdışı.

### 2.5 Knowt (knowt.com)

- **Görsel kimlik:** **Indigo/mor + beyaz zemin**; minimal, hafif oyuncu, düşük görsel gürültü. AI notlar **stillenmiş markdown** olarak sunulur. ([App Store](https://apps.apple.com/us/app/knowt-ai-flashcards-notes/id6463744184))
- **Bilgi mimarisi:** Klasör/set **dashboard** → set açılınca **çevirmeli flashcard** ekranı → altta tekrar butonları.
- **Ayırt edici desenler:**
  - **Again / Hard / Good / Easy dörtlüsü** — güven dereceli self-report tekrarı (spaced repetition motoruna bağlı).
  - **Quizlet setlerini tek tık import** — onboarding'in ana çekişi.
  - PDF/not/YouTube'dan AI kart + not + quiz üretimi; D/Y + eşleştirme + serbest yanıt modları. (bkz. [Fritz.ai incelemesi](https://fritz.ai/knowt-ai-review/))
- **Oyunlaştırma:** Hafif; mastery/ilerleme göstergesi + spaced repetition planı.
- **Mobil:** iOS + Android + Chrome; mobilde kart çevirme + dörtlü tekrar butonu aynı.

### 2.6 Coconote (coconote.com)

- **Görsel kimlik:** **Mor/pembe gradyan + sıcak vurgular**; dost canlısı, yuvarlak, tüketici uygulaması estetiği. TikTok doğumlu, duygu-odaklı bir kimlik. ([ScreensDesign](https://screensdesign.com/showcase/coconote-ai-note-taker))
- **Bilgi mimarisi:** Ses/video/PDF yükle → **renk kodlu yapılandırılmış not** (konu blokları) + **anahtar terim kutusu**; yandan çalışma rehberi + quiz.
- **Ayırt edici desenler:**
  - **Renk kodlu not sistemi** — her konu/başlık kendi rengini alır ve bu renk **not → quiz → flashcard** arasında tutarlı taşınır (nişte gerçekten farklılaşan kimlik öğesi).
  - "Hiçbir detayı kaçırma" App Store hook'u — müşteri dilini aynalayan konumlama. ([BetterLaunch playbook](https://www.betterlaunch.co/playbooks/coconote-quizlet-8))
- **Oyunlaştırma:** Hafif (kota/plan); esas çekiş "çalışmaya değil üretkenliğe" odaklı.
- **Mobil:** Mobil-öncelikli; App Store'da güçlü. **Güncel:** 2025'te **Quizlet tarafından satın alındı** (~$6.7M ARR'ye) — renk kodlu not kimliği Quizlet portföyüne girdi. ([RevenueCat podcast](https://metacast.app/podcast/sub-club-by-revenuecat/DlWjuiPD/bootstrapped-to-6-7m-arr-and-an-exit-to-quizlet-in-2-years-brett-bauman-and-zack-hargett-coconote/EsSaMxJe))

### 2.7 TurboLearn AI (turbolearn.ai)

- **Görsel kimlik:** **Turkuaz/camgöbeği** vurgu + **çok koyu slate** zemin; temiz, "hızlı ürün" hissi. Mobilde koyu kartlar + camgöbeği vurgu. ([App Store](https://apps.apple.com/us/app/turbolearn-ai-note-taker/id6502794561), [ToolMage](https://www.toolmage.com/en/tool/turbo/))
- **Bilgi mimarisi:** Yükle → belge başına **Notes (stillenmiş markdown) · Flashcards (kaydırma destesi) · Quizzes** sekmeleri; belge başına ilerleme özet kartı.
- **Ayırt edici desenler:**
  - **Sihirli yükleme akışı + işleme animasyonu** — dosya düşürünce ilerleme/kademe animasyonu ile "AI çalışıyor" geri bildirimi (bekleme kaygısını yönetir).
  - **Soru bazlı açıklamalı quiz sonuç ekranı** — her yanıt için gerekçe.
- **Oyunlaştırma:** Hafif streak + belge başına ilerleme kartı.
- **Mobil:** iOS + Android; koyu tema + kaydırmalı flashcard destesi. ([Google Play](https://play.google.com/store/apps/details?id=ai.turbolearn))

### 2.8 Algor Education (algoreducation.com)

- **Görsel kimlik:** **Teal/yeşil** marka rengi + **çok renkli kavram haritası düğümleri** (her dal farklı renk). EdTech sakinliği ile görsel öğrenme vurgusu birleşir. ([Concept Map Generator](https://www.algoreducation.com/en/ai-concept-map-generator), [aiseekertools](https://aiseekertools.com/tools/algoreducation-com))
- **Bilgi mimarisi:** Yükle (PDF/fotoğraf/metin) → **kavram haritası kanvası** ana yüzey + yan panelde özet/flashcard; harita **düzenlenebilir** ve **iş birliğine açık**.
- **Ayırt edici desenler:**
  - **Kavram/zihin haritası görünümü** — metin yerine grafik bilgi organizasyonu (nişte nadir; NoteGPT dışında az örnek).
  - **AI Outline / otomatik düzen** — harita düğümlerini otomatik yerleştirir, kullanıcı sürükleyip düzenler. ([AI Mind Map Generator](https://www.algoreducation.com/en/ai-mind-map-generator), [Help Center](https://www.algoreducation.com/en/help-center))
- **Oyunlaştırma:** Yok / çok hafif.
- **Mobil:** Web + Android uygulama; mobilde harita okuma/gezinme sadeleştirilmiş.

### 2.9 Studyable (studyable.app)

- **Görsel kimlik:** **Mavi/indigo + beyaz**; temiz, chat-öncelikli mobil estetiği; yuvarlak mesaj balonları. ([SourceForge](https://sourceforge.net/app/studyable/web-app/), [aiseekertools](https://aiseekertools.com/tools/studyable-app))
- **Bilgi mimarisi:** **Chat-öncelikli öğretmen ekranı ana yüzeydir**; flashcard kaydırmalı; essay inceleme ekranı ayrı.
- **Ayırt edici desenler:**
  - **AI essay notlandırma + satır içi açıklamalar** — metin üstünde gerekçeli geri bildirim (StuHub'ın açık uçlu puanlamasının doğal akrabası).
  - Chat'i ana yüzey yapma kararı (not/flashcard ikincil).
- **Oyunlaştırma:** Zayıf.
- **Mobil:** iOS; chat-öncelikli tasarım mobille doğal uyumlu. ([App Store](https://apps.apple.com/us/app/studyable-ai-study-help/id6448214477))

### 2.10 OmniSets (omnisets.com)

- **Görsel kimlik:** **Mor/indigo + beyaz, gradyansız**; temiz, fonksiyonel, sakin. ([Quickstart](https://help.omnisets.com/quickstart))
- **Bilgi mimarisi:** **Klasör + alt klasör ağacı sidebar** (nişte nadir) → set başına **mod sekmeleri: Flashcards · Learn · Write · Test · Match-benzeri oyunlar · Quiz Mode** → **StudyPlans** takvim görünümü.
- **Ayırt edici desenler:**
  - **Klasör/alt klasör organizasyonu** — hiyerarşik IA (StuHub'ın Dönem→Ders→Chapter ağacına birebir oturur).
  - **StudyPlans** — otomatik tekrar planlayıcı **takvim** görünümü. ([StudyPlans](https://help.omnisets.com/guides/studyplans), [Study Mode](https://help.omnisets.com/guides/study-mode))
  - **Adaptive/AI destekli** — spaced repetition'ı planlar, kullanıcı güven dereceleriyle besler.
- **Oyunlaştırma:** Kişisel (spaced repetition planı + ilerleme); leaderboard yok.
- **Mobil:** Web-öncelikli; mobilde klasör ağacı ve modlar korunur.

---

## 3. Ortak Tasarım Desenleri (Nişin UI Normları)

> Nişin tekrarlayan arayüz normları; `NİŞ_ANALİZİ_RAPORU.md` Bölüm 6.2'deki "Top 10"u genişletir ve salt-UI gözünden yeniden yazar.

1. **"Yükle → araç sekmeleri" belge çalışma alanı** — Tek kaynak; Notlar / Flashcard / Quiz / Özet sekmelerine yayılır. *(Mindgrasp kanonik; TurboLearn, StudyFetch, Coconote)*
2. **Tek içerik üzerinde çalışma modu sekmeleri** — Flashcards | Learn | Test | Match. Set/not defteri atomik birimdir; mod değiştirme sayfa navigasyonunun yerini alır. *(Quizlet kanonik; OmniSets, Knowt, StudyFetch)*
3. **Öz-değerlendirmeli kart çevirme** — Again/Hard/Good/Easy ya da ✓/✗ → spaced repetition'ı besler. *(Knowt, Quizlet Learn, OmniSets, KardsAI, Wisdolia)*
4. **Belge yanında AI chat paneli** — yan ray (StudyFetch Sparky, Mindgrasp Ask AI) veya ana yüzey (Studyable, NotebookLM, Shiken). Chat, üretim çıktısından ayrılmaz.
5. **Kaynak-temelli yanıt + numaralı inline atıf** — tıklanınca kaynak pasaj vurgulanır. *(NotebookLM kanonik; Mindgrasp, StudyFetch, Monic)*
6. **Streak / günlük hedef / ilerleme çubuğu** — elde tutma katmanı; neredeyse her zaman **kişisel**, leaderboard'lu değil. *(Quizlet, StudyFetch Spaced Learning Hub, OmniSets StudyPlans, TurboLearn)*
7. **Sol sidebar IA: klasör → set dashboard + çalışma kartı ızgarası** — *(OmniSets alt klasörlerle; Quizlet, Knowt, Monic, StudyFetch)*
8. **Set başına ilerleme halkası / mastery göstergesi** — *(Quizlet, Monic, Knowt, TurboLearn)*
9. **Üç bölmeli "kaynak → çalışma → çıktı" düzeni** — kaynak listesi sol, chat/kanvas orta, notlar/çıktı sağ. *(NotebookLM kanonik; Mindgrasp/Monic belge sekmeleriyle varyant)*
10. **Yükleme/işleme animasyonu ve ilerleme geri bildirimi** — AI'nın "çalışıyor" hissini veren kademeli animasyon/progress bar. *(TurboLearn en belirgin; StudyFetch, Mindgrasp)*
11. **Persona/onboarding kişiselleştirme** — başta konu/hedef sorar, akışı ve içeriği şekillendirir. *(Shiken kanonik; Quizlet, StudyFetch)*
12. **Boş durum + birincil eylem mikro-metni** — "henüz X yok → ilk X'ini oluştur" kalıbı; SaaS açılışta hero mockup → özellik → sosyal kanıt → fiyat yığını. *(tüm web uygulamaları)*

---

## 4. Renk / Tipografi Akımları Özeti

### 4.1 Renk aileleri

- **Indigo/mor ailesi (nişin varsayılanı):** Quizlet `#4255FF` + mor, StudyFetch, Knowt, OmniSets, Coconote, Mindgrasp — mor "çalışma/AI-sihri" olarak okunuyor.
- **Nötr/Material ailesi:** NotebookLM (beyaz/gri + Google mavisi) — güven sinyali veren anti-marka.
- **Turkuaz/camgöbeği:** TurboLearn — hız/teknoloji aykırısı.
- **Teal/yeşil + çok renkli görsel:** Algor Education — görsel öğrenme (harita düğümleri çok renkli).
- **Lime/yeşil + koyu oyun:** Shiken, Wisdolia — enerji/büyüme (geniş küme).
- **Ürün içi baskın desen:** **açık zemin + tek doygun vurgu**; gradyanlar pazarlama/landing'de yoğun, ürün içinde ise kenar durumlarına (logo, boş durum, AI anları) saklanır.

### 4.2 Tipografi akımları

- Neredeyse tamamı **geometric/humanist sans-serif**; belgelenmiş istisnalar: NotebookLM **Google Sans**, StuHub tarafı Inter (mevcut rehber).
- Quizlet/Coconote **yuvarlak/oyuncu** sans; Mindgrasp/Studyable **nötr profesyonel** sans; NotebookLM **editoryal sakin** sans.
- Hiyerarşi normu: başlık 600–700, gövde 400, vurgu 500; geniş satır aralığı (gövde ~1.5).
- Çoğu rakip tipografiyi **belgelemez** — ayırt edici tipografi yerine **renk** ile kimlik kurarlar (tek istisna kısmen Google Sans'ın güven hissi).

### 4.3 Yüzey / şekil / hareket normları

- Kartlar: **8–16px radius**, tek seviye düşük-opaklık gölge; kenarlıklar 1px düşük kontrast (StuHub'ın mevcut 6/10/12px ölçeğiyle uyumlu).
- Geçişler 150–200ms; animasyon **yalnızca** geri bildirim/ilerleme/onboarding amaçlı (AI "işleme" anları hariç).
- Karanlık mod: StudyFetch/TurboLearn koyu-indigo/slate tema; çoğu rakip açık zemin öncelikli.

---

## 5. StuHub İçin Çıkarımlar

> Bu bölüm `NİŞ_ANALİZİ_RAPORU.md` Bölüm 6.5 (8 fikir) ve 7 (öneriler) ile **uyumludur**, çelişmez; onları salt-UI gözünden somutlaştırır. StuHub'ın mevcut arayüz dili (nötr gri + tek mavi `#2563eb`, Inter, 4px ölçeği, 6/10/12px radius, tek seviye gölge, tek soruluk quiz, boş durum mikro-metinleri — `YETENEKLER/07-stil-rehberi.md`) temel alınır; aşağıdakiler bu dili zenginleştiren, **gizlilik/yerellik ve minimal estetikle çelişmeyen** ödünçlerdir.

1. **Not defterini "araç sekmeleri hub"ına dönüştür** — Mindgrasp/TurboLearn deseni: tek ders/not defteri içinde **Notlar · Flashcard · Bölüm Quiz · Genel Quiz** sekmeleri. 55 soruluk genel quiz "ayrı özellik adası" olmaktan çıkar (mevcut rapor öneri #3'ün UI karşılığı).
2. **NotebookLM tarzı numaralı atıf çipleri** — StuHub'ın mevcut inline `[1]` atfını **tıklanabilir çip** haline getir; tıklayınca sağ şeritte kaynak pasaj vurgulansın (mevcut pop-up'ın üç-bölmeli evrimi; rapor öneri #2).
3. **Güven dereceli flip kartlar (Again/Hard/Good/Easy)** — Knowt/Quizlet Learn deseni; spaced repetition yerel (SQLite) kalır, ilerleme cihazda saklanır (rapor öneri #5). Kart çevirme, StuHub'ın "tek soru/ekran" quiz kalıbına uyumludur.
4. **"Materyale Sor" chat paneli** — belge yanında açılan yan ray; **yanıtlar zorunlu atıflı** (NotebookLM/Mindgrasp deseni; rapor öneri #2). Chat, not ekranından bağımsız açılır, atıf davranışı korunur.
5. **Kademeli "AI çalışıyor" işleme animasyonu** — TurboLearn deseni; StuHub'ın mevcut "Notların hazırlanıyor… (3/7 konu)" metnini **progress bar + konu kademesi animasyonuyla** güçlendir (stil rehberinin "spinner tek başına kullanılmaz" kuralıyla birebir uyumlu).
6. **Yerel streak + günlük hedef halkası** — dashboard'da küçük ilerleme halkası/streak çipi; **leaderboard yok** (kişisel kalır; rapor öneri #7 ve Bölüm 7.6'nın "leaderboard yapma" kararıyla tutarlı).
7. **Klasör ağacı sidebar + "mod sekmeleri"** — OmniSets'in klasör/alt klasör deseni StuHub'ın Dönem→Ders→Chapter hiyerarşisine birebir oturur (rapor öneri #1).
8. **Renk kodlu konu kimliği (ölçülü)** — Coconote'un "konu başına renk, not→quize taşınır" fikri; StuHub'da **dekoratif değil işlevsel** kullanılır: chapter'lar arası ayrım ve quiz'de konu kaynağını işaretleme. Stil rehberinin "renk işlevseldir" ilkesine uyar; **tek vurgu rengi** korunur.
9. **3 adımlı Türkçe onboarding** — Shiken/StudyFetch deseni: "Bu dönem hangi dersleri alıyorsun?" sohbet tonuyla Dönem/Ders ağacını anında kurar (rapor öneri #8).
10. **"Tek soru/ekran" quiz'i koru, ama sonuç ekranına açıklama döngüsü ekle** — TurboLearn'in soru-bazlı açıklamalı sonuç ekranı; StuHub'ın anında atıflı geri bildirimi zaten var, üstüne "yanlışlar → ilgili nota git" bağlantısı (rapor öneri #3).

**Önerilen görsel çıpa (mevcut raporla aynı):** NotebookLM'in sakin üç sütunu + Quizlet/OmniSets'in mod sekmesi hub'ı + tek doygun vurgu = minimal, yerel-öncelikli, güvenilir ama net biçimde "AI destekli" okunan bir arayüz. StuHub'ın mevcut mavi `#2563eb` vurgusu korunur; istenirse nişin varsayılanı olan **indigo/mora** yaklaştırılabilir (rapor Bölüm 6.3'teki niş normu) — ancak bu bir kimlik kararıdır, işlev değişikliği değildir.

---

## 6. Kaynaklar

**Resmi ürün blogları / yardım dokümanları:**
- StudyFetch: [Spark.E](https://www.studyfetch.com/features/sparke) · [Spaced Learning Hub](https://sso.studyfetch.com/blog/meet-the-spaced-learning-hub) · [Learn Engine](https://sso.studyfetch.com/blog/the-learn-engine) · [Mini-Apps](https://sso.studyfetch.com/blog/mini-apps-on-studyfetch) · [Study Plan redesign](https://sso.studyfetch.com/blog/study-plan-redesign) · [Guided Chatting](https://sso.studyfetch.com/blog/meet-guided-chatting-on-studyfetch)
- Mindgrasp: [Canny özellik talepleri](https://mindgrasp.canny.io/feature-requests/p/feature-rich-list)
- NotebookLM: [Yeni görünüm + premium (blog.google)](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-new-features-december-2024/) · [Interface Panels (LibGuides UPRM)](https://libguides.uprm.edu/notebooklm/interface_panels)
- Quizlet: [Answer Streaks (Help)](https://help.quizlet.com/hc/en-ca/articles/40011154960653-Studying-with-Answer-Streaks)
- OmniSets: [Quickstart](https://help.omnisets.com/quickstart) · [Study Mode](https://help.omnisets.com/guides/study-mode) · [StudyPlans](https://help.omnisets.com/guides/studyplans)
- Algor Education: [AI Concept Map Generator](https://www.algoreducation.com/en/ai-concept-map-generator) · [AI Mind Map Generator](https://www.algoreducation.com/en/ai-mind-map-generator) · [Help Center](https://www.algoreducation.com/en/help-center)

**Tasarım / marka kanıtı:**
- [Brandfetch — StudyFetch](https://brandfetch.com/studyfetch.com) · [PickColorOnline — Quizlet](https://pickcoloronline.com/brands/quizlet/) · [ScreensDesign — Quizlet](https://screensdesign.com/showcase/quizlet-study-with-flashcards) · [ScreensDesign — Coconote](https://screensdesign.com/showcase/coconote-ai-note-taker) · [Designing NotebookLM](https://liduos.com/posts/designing-notebooklm)

**İnceleme / ikincil:**
- [Unite.AI — Mindgrasp](https://www.unite.ai/mindgrasp-ai-review/) · [EducationalAppStore — Mindgrasp](https://www.educationalappstore.com/website/mindgrasp-ai) · [Fritz.ai — Knowt](https://fritz.ai/knowt-ai-review/) · [Fritz.ai — TurboLearn](https://fritz.ai/turbolearn-ai-review/) · [aiseekertools — Algor Education](https://aiseekertools.com/tools/algoreducation-com) · [aiseekertools — Studyable](https://aiseekertools.com/tools/studyable-app) · [aiseekertools — OmniSets](https://aiseekertools.com/tools/omnisets-ai) · [ToolMage — TurboLearn](https://www.toolmage.com/en/tool/turbo/) · [Coda One — TurboLearn](https://www.codaone.ai/tools/turbolearn-ai/) · [dev.to — Quizlet features](https://dev.to/john_dusty_6e163a86b84/quizlet-app-features-that-drive-60m-users-and-what-founders-can-learn-3ohe)

**App Store / Google Play (ekran görüntüsü kanıtı):**
- [StudyFetch App Store](https://apps.apple.com/cz/app/studyfetch-make-learning-easy/id6663574866) · [Mindgrasp App Store](https://apps.apple.com/cy/app/mindgrasp/id1638182014) · [Knowt App Store](https://apps.apple.com/us/app/knowt-ai-flashcards-notes/id6463744184) · [TurboLearn App Store](https://apps.apple.com/us/app/turbolearn-ai-note-taker/id6502794561) · [TurboLearn Google Play](https://play.google.com/store/apps/details?id=ai.turbolearn) · [Studyable App Store](https://apps.apple.com/us/app/studyable-ai-study-help/id6448214477)

**Güncel durum / pazar:**
- [Coconote → Quizlet satın alımı (RevenueCat podcast)](https://metacast.app/podcast/sub-club-by-revenuecat/DlWjuiPD/bootstrapped-to-6-7m-arr-and-an-exit-to-quizlet-in-2-years-brett-bauman-and-zack-hargett-coconote/EsSaMxJe) · [Coconote TikTok büyüme analizi](https://www.socialgrowthengineers.com/259m-views-200k-mrr-coconote-ais-shared-playbook-for-tiktok-reels) · [Coconote BetterLaunch playbook](https://www.betterlaunch.co/playbooks/coconote-quizlet-8)

---

> **Durum:** ✅ Analiz tamamlandı — 10 rakip, 5 bölüm, 40+ kaynak URL. Bu belge `NİŞ_ANALİZİ_RAPORU.md`'nin arayüz katmanı genişletmesidir; özellik kararları için o rapor, görsel/deneyim kararları için bu belge ve `YETENEKLER/07-stil-rehberi.md` birlikte otoritedir.
