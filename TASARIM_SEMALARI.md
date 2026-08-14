# StuHub — 5 Alternatif Design Şeması

> **Bağlam:** `NİŞ_ANALİZİ_RAPORU.md` (Bölüm 6: Arayüz Tasarım Örneklemi) ve `RAKIP_UIUX_ANALIZI.md` temel alınarak hazırlandı.
> **Amaç:** 5 farklı görsel/deneyimsel yön önerisi. Bunlardan **biri seçilecek** ve seçilen şemaya göre StuHub'ın UI/UX optimizasyonu yapılacak.
> **Ortak ilke (tüm şemalarda korunur):** Yerel-öncelikli, gizlilik odaklı, Türkçe mikro-metinler, WCAG 2.1 AA kontrast, tema token'ları (hardcoded renk yok).

---

## 0. Mevcut Durum (Baseline Anlık Görüntüsü)

Seçim yaparken "neler değişecek"i görmek için mevcut arayüzün özeti:

| Boyut | Mevcut durum |
|-------|--------------|
| Kimlik | Nötr gri + tek mavi vurgu (#2563eb); Inter; `rounded-sm` (6px) her yerde; ince kenarlıklar |
| Düzen | Sol 256px sidebar (Dönem→Ders→Chapter ağacı) + üst başlık çubuğu + 5xl içerik sütunu |
| Dashboard | Streak halkası kartı + dönem kartları listesi + onboarding sihirbazı |
| Notebook | 4 sekme (Notlar/Kartlar/Quiz/Rehber); not `<details>` içinde; flashcard ve quiz setleri `<details>` listelerinde |
| AI öğeleri | Chat paneli (Doğrudan/Sokratik/Sınav modları, atıflı) yalnızca ders sayfasında; atıf çipleri `[n]` |
| Üretim | Sağ-alt sabit "küresel üretim paneli" (iş + ilerleme çubuğu) |
| Kimlik sorunları | Görsel farklılaşma yok; sekme/boş durum/eylem butonları jenerik; AI yetenekleri görsel olarak "gömülü" kalıyor |

---

## Şema 1 — "Sakin Güven" (NotebookLM evrimi)

**İlham:** NotebookLM'in editoryal sakinliği + StuHub'ın mevcut mavi kimliğinin evrimi. En düşük riskli, en tutarlı yol.

**Kimlik:** Açık zemin (#fafafa), beyaz yüzey, tek mavi vurgu (korunur), 1px düşük kontrast kenarlık, gölge neredeyse yok. Tipografi Inter; başlıklar `tracking-tight`, gövde 16px, okuma sütunu ~68ch. Radius 8/12/16. İkon seti ince çizgi (lucide tarzı).

**Düzen:**
```
┌─────────┬───────────────────────────────┬──────────────┐
│ SIDEBAR │  SEKME: Notlar|Kartlar|Quiz|Rehber  │              │
│ Dönemler │                               │  BAĞLAM RAYI  │
│  ▸ Ders  │   ┌────────────────────────┐  │  · Atıf [1]   │
│    ▸ Ch. │   │  Not içeriği (68ch)    │  │  · Kaynak     │
│ Ayarlar  │   │  [1][2] atıf çipleri   │  │  · Materyale  │
│          │   └────────────────────────┘  │    Sor (mini) │
└─────────┴───────────────────────────────┴──────────────┘
```

**Ekran kartları:** Dashboard'da sakin istatistik şeridi (streak, üretilen not, çözülen quiz) + dönem kartları; Notebook'ta üç bölmeli çalışma alanı (sol: materyal listesi, orta: içerik, sağ: atıf/bağlam rayı); tıklanan `[n]` çipi sağ rayı açıp kaynak pasajı vurgular.

**Değişenler:** Sekme çubuğu alt çizgiden **pill mod değiştiriciye** döner; not `<details>` yerine gerçek içerik yüzeyi olur; boş durumlara minimal glifler; sidebar 240px'e iner + ikonlar.

**Artılar:** Gizlilik/güven konumlanmasını en güçlü yansıtır; mevcut token sistemiyle en ucuz geçiş; nişte NotebookLM "güven" kodunu taşır.
**Eksiler:** "Jenerik SaaS" riski; kişilik/marka akılda kalıcılığı düşük.
**Efor:** Düşük–orta (token genişletme + 2 sayfa yeniden düzenleme).

---

## Şema 2 — "AI Arkadaş" (StudyFetch / Studyable)

**İlham:** StudyFetch'in Spark.E'si ve Studyable'ın chat-öncelikli arayüzü. AI asistan görsel olarak **merkezde**.

**Kimlik:** Açık zemin + **mor vurgu** (#7c3aed; hover #6d28d9); AI öğelerinde indigo→mor gradyan; asistan mesajları yumuşak mor zemin balonlarında; "Stu" adlı yerel asistan avatarı (basit geometrik, dosya ikonu konsepti). Radius 10/14/20.

**Düzen:** Chat-first:
```
┌─────────┬──────────────────────────────┬──────────────────┐
│ SIDEBAR │   Aktif içerik (not/kart/quiz) │  STU ASİSTAN     │
│         │                              │  ┌────────────┐  │
│         │                              │  │ Avatar +   │  │
│         │                              │  │ "Bugün ne  │  │
│         │                              │  │ çalışalım?"│  │
│         │                              │  └────────────┘  │
│         │  Öneri çipleri: [Kart üret]  │  · chat geçmişi  │
│         │  [Zayıf konunu tekrar et]    │  · Doğrudan/     │
│         │                              │    Sokratik/     │
│         │                              │    Sınav modu    │
└─────────┴──────────────────────────────┴──────────────────┘
```

**Ekran kartları:** Her sayfada sağda daraltılabilir asistan rayı; notebook'ta "Stu önerdi" çipleri (AI aksiyon önerileri); quiz sonunda asistan analizi ("3. konu zayıf — kart öneriyorum"); onboarding'de asistanla sohbet ederek dönem kurulumu.

**Değişenler:** ChatPanel kalıcı sağ raya terfi eder; AI üretim butonları gradyan "sihir" stiline kavuşur; üretim paneli asistan balonu biçimini alır.

**Artılar:** Nişin en hızlı yayılan kalıbını yakalar; "AI destekli" algısı anında; mevcut chat altyapısı hazır.
**Eksiler:** İçerik ile asistan arasında dikkat rekabeti; en çok iş; mor kimlik nişin "default" rengi (farklılaşma zayıflar); gizlilik mesajı daha fazla vurgulanmalı ("Stu senin cihazında").
**Efor:** Yüksek (kalıcı ray + öneri sistemi + avatar kimliği).

---

## Şema 3 — "Öğrenci Oyun Alanı" (Quizlet / Knowt)

**İlham:** Quizlet'in indigo kimliği + Knowt'un taktil kartları. Öğrenciye anında tanıdık, eğlenceli, elde tutma odaklı.

**Kimlik:** Indigo birincil **#4255FF**, mor ikincil, sarı vurgu (#FFCD1F) ikonik; beyaz zemin üstünde kalın kenarlıklı, gölgeli büyük kartlar; radius 16/20/24; başlıklar 700; büyük tipografi; konfeti/çizim benzeri mikro animasyonlar (quiz bitişi).

**Düzen:** Mod sekmeleri hub:
```
┌─────────┬──────────────────────────────────────┐
│ SIDEBAR │  ( Kart | Quiz | Notlar | Rehber )    │
│         │  ┌────────────────────────────────┐  │
│         │  │          FLASHCARD             │  │
│         │  │   (kocaman, çevirmeli, 3D)     │  │
│         │  └────────────────────────────────┘  │
│         │  [Yine] [Zor] [İyi] [Kolay]  ← BÜYÜK │
│         │  ┌─ mastery çubuğu ──────────────┐  │
└─────────┴──────────────────────────────────────┘
```

**Ekran kartları:** Dashboard büyük renkli kart ızgarası (dönem başına ilerleme halkası + XP çipi); flashcard tam sahne flip kart + devasa Again/Hard/Good/Easy butonları; quiz'de puan patlaması + yanlış soruların tekrar listesi; streak alev animasyonlu çip.

**Değişenler:** Token paleti indigo ailesine geçer; kart/buton boyutları büyür; oyunlaştırma katmanı görsel olarak öne çıkar (kişisel; leaderboard yine YOK); `rounded-sm` tamamen kalkar.

**Artılar:** Öğrenci kitlesine anında "ev sahibi" hissi; tekrar/quiz döngüsünü (StuHub'ın çekirdeği) en iyi sahneleyen şema; nişin referans kodu.
**Eksiler:** "Ciddi ders notu" algısı zayıflayabilir; minimalist stil rehberiyle en çok çatışan şema; dekoratif öğeler disiplin gerektirir.
**Efor:** Orta–yüksek (token değişimi + oynatıcı ekranları + mikro animasyonlar).

---

## Şema 4 — "Gece Kütüphanesi" (Monic / Shiken koyu estetik)

**İlham:** Monic.ai'nin koyu indigo + gradyan estetiği; Shiken'in cesur koyu teması. Karanlık-öncelikli, konsantrasyon odaklı.

**Kimlik:** Koyu zemin (#0f1117), yüzey (#1a1d27), yumuşak ışımalı odak durumları; vurgu indigo→mor gradyan (#6366f1 → #8b5cf6); semantik renkler neonlaştırılır (success #34d399, error #f87171); radius 10/14; cam efekti (hafif blur + transparan) yalnızca üst düzey panellerde.

**Düzen:** Aynı iskelet, + **Odak Modu**:
```
┌─────────┬──────────────────────────────────────┐
│ SIDEBAR │   Not okuma (Odak Modu)              │
│ (koyu)  │   ┌──────────────────────────────┐   │
│         │   │  içerik; chrome soluk/gizli  │   │
│         │   └──────────────────────────────┘   │
│         │   [F] Odak Modu aç/kapa · 4'te 1 hız │
└─────────┴──────────────────────────────────────┘
```

**Ekran kartları:** Varsayılan tema koyu (açık tema seçenek olarak kalır); dashboard'da gradyan vurgulu streak halkası; quiz oynatıcısı tam ekran, soluk arka planlı; üretim paneli alt kısımda ince gradyan çubuk.

**Değişenler:** Tema önceliği ters çevrilir (koyu default); token'lara gradyan çiftleri eklenir; Odak Modu (fullscreen + soluk chrome + kısayol) yeni bileşen; odak halkaları ışımalı olur.

**Artılar:** Nişte görsel ayrışma (rakiplerin çoğu açık zemin); uzun çalışma seanslarına uygun; "AI ürünü" estetiği güçlü.
**Eksiler:** Koyu-öncelik her kullanıcıya hitap etmez; gradyan disiplini (stil rehberi "süs yok" ilkesiyle gerilim); PDF/ekran görüntüsü kontrastına dikkat gerekir.
**Efor:** Orta (mevcut dark theme genişletilir + Odak Modu + gradyan tokenları).

---

## Şema 5 — "Renkli Not Defteri" (Coconote / Algor)

**İlham:** Coconote'un renk kodlu not sistemi (nişte gerçekten farklı kimlik) + Algor'un zihin haritası görünümü. Sıcak, düzenleyici, "defter" hissi.

**Kimlik:** Sıcak kağıt zemini (#faf7f2), mürekkep metin (#1f2937); **ders başına otomatik renk ataması** (6–8 tonluk palet: çivit, çam, bordo, amber, turkuaz, erik); not bölüm başlıkları ve anahtar terim kutuları konu renginde; radius 10/14; yumuşak renkli kenarlıklar.

**Düzen:**
```
┌─────────┬──────────────────────────────────────┐
│ SIDEBAR │  ● Fizik (çivit)  · Ders renkli nokta │
│  ● Mat  │  ┌────────────────────────────────┐  │
│  ● Fiz  │  │ § 3.1 Başlık  (çivit şerit)    │  │
│         │  │   metin...                     │  │
│         │  │  ⬒ ANAHTAR TERİM: X (amber kutu)│  │
│         │  └────────────────────────────────┘  │
└─────────┴──────────────────────────────────────┘
```

**Ekran kartları:** Sidebar'da her dersin renk noktası; kartlar ve quiz'ler üretildikleri konunun rengini miras alır (not → kart → quiz tutarlı renk akışı); dönem kartlarında ders renk şeritleri; rehber sekmesinde renk kodlu kavram haritası önizlemesi.

**Değişenler:** Tek vurgu rengi yerine "doku bazlı" renk sistemi (vurgu mavi kalır, ama konu renkleri ikincil eksen olur); not görüntüleyici yapılandırılmış bölüm/kutu render'ı kazanır; sidebar renk noktaları.

**Artılar:** Nişte nadir ve akılda kalıcı kimlik; çok dersli kullanımda organizasyonu gerçekten kolaylaştırır; not→kart→quiz akışını görselleştirir.
**Eksiler:** Renk sistemi yönetimi karmaşık (token disiplini şart); 8+ ders olduğunda tonlar yakınlaşabilir; erişilebilirlik (renk körlüğü) için desen/nokta eşlikçileri gerekir.
**Efor:** Orta–yüksek (renk atama motoru + not render + sidebar).

---

## Karşılaştırma Matrisi

| Kriter | 1 Sakin Güven | 2 AI Arkadaş | 3 Oyun Alanı | 4 Gece Kütüphanesi | 5 Renkli Defter |
|--------|:---:|:---:|:---:|:---:|:---:|
| Gizlilik/güven sinyali | ★★★★★ | ★★★ | ★★ | ★★★★ | ★★★★ |
| "AI destekli" algısı | ★★★ | ★★★★★ | ★★★ | ★★★★ | ★★ |
| Farklılaşma (nişte) | ★★ | ★★★ | ★★★ | ★★★★ | ★★★★★ |
| Çalışma döngüsü sahnelemesi | ★★★★ | ★★★★ | ★★★★★ | ★★★★ | ★★★★ |
| Uygulama eforu | Düşük–Orta | Yüksek | Orta–Yüksek | Orta | Orta–Yüksek |
| Stil rehberiyle uyum | ★★★★★ | ★★★ | ★★ | ★★★ | ★★★ |
| Risk | En düşük | Orta | Orta | Orta | Orta |

## Şemaların Somut Token Setleri (uygulamaya hazır özet)

> Her şema için varsayılan (aydınlık) tema değerleri. Karanlık varyantlar uygulama aşamasında aynı ilkeyle türetilir.

### Şema 1 — Sakin Güven
| Token | Değer |
|-------|-------|
| bg / surface / border | `#fafafa` / `#ffffff` / `#e8e8ec` |
| text / secondary | `#1a1a1f` / `#5f5f66` |
| accent / hover / on | `#2563eb` / `#1d4ed8` / `#ffffff` (mevcut korunur) |
| radius | 8 / 12 / 16 |
| gölge | yalnızca modal: `0 4px 16px rgb(0 0 0 / .06)` |
| Öne çıkan detay | pill mod değiştirici, atıf rayı, 68ch okuma sütunu |

### Şema 2 — AI Arkadaş
| Token | Değer |
|-------|-------|
| bg / surface / border | `#fafaff` / `#ffffff` / `#e9e7f5` |
| text / secondary | `#1c1a2b` / `#5c5871` |
| accent / hover / on | `#7c3aed` / `#6d28d9` / `#ffffff` |
| gradyan (AI öğeleri) | `linear-gradient(135deg, #6366f1, #8b5cf6)` |
| asistan balonu zemini | `#f3efff` |
| radius | 10 / 14 / 20 |
| Öne çıkan detay | kalıcı sağ asistan rayı, "Stu" avatarı, öneri çipleri |

### Şema 3 — Öğrenci Oyun Alanı
| Token | Değer |
|-------|-------|
| bg / surface / border | `#f6f7fb` / `#ffffff` / `#e2e8f0` (kalın 1.5px) |
| text / secondary | `#1e1b4b` / `#52525b` |
| accent / hover / on | `#4255ff` / `#3646d6` / `#ffffff` |
| ikincil (mor) / vurgu (sarı) | `#a855f7` / `#ffcd1f` |
| radius | 16 / 20 / 24 |
| gölge | kart: `0 2px 0 0 #e2e8f0` + hover `-translate-y-0.5` |
| Öne çıkan detay | dev flip kart, 4'lü güven butonları, konfeti bitişi |

### Şema 4 — Gece Kütüphanesi
| Token | Değer |
|-------|-------|
| bg / surface / border | `#0f1117` / `#1a1d27` / `#2a2f3d` |
| text / secondary | `#eef0f6` / `#9aa1b5` |
| accent gradyanı | `linear-gradient(135deg, #6366f1, #8b5cf6)`; hover `#818cf8` |
| success / error | `#34d399` / `#f87171` |
| radius | 10 / 14 |
| Öne çıkan detay | koyu default, ışımalı odak, Odak Modu (F kısayolu) |

### Şema 5 — Renkli Not Defteri
| Token | Değer |
|-------|-------|
| bg / surface / border | `#faf7f2` (sıcak kağıt) / `#ffffff` / `#ece5d8` |
| text / secondary | `#1f2937` (mürekkep) / `#6b7280` |
| accent / hover / on | `#2563eb` (mavi ana eylem korunur) |
| ders renk paleti (6 ton) | çivit `#4f46e5` · çam `#15803d` · bordo `#b91c1c` · amber `#d97706` · turkuaz `#0e7490` · erik `#9333ea` |
| radius | 10 / 14 |
| Öne çıkan detay | ders renk noktaları, renk şeritli bölüm başlıkları, anahtar terim kutuları |

## Önerilen Okuma

- **Güvenli, hızlı ve yerel-öncelikli kimliği koruyarak ilerlemek** istersen: **Şema 1** (evrimsel) ya da **Şema 4** (kimlik kazanımı).
- **Nişin AI kalıbını en güçlü şekilde sahnelemek** istersen: **Şema 2**.
- **Öğrenci kitlesine anında tanıdık + tekrar/quiz motorunu öne çıkarmak** istersen: **Şema 3**.
- **Nişte gerçekten ayırt edici bir kimlik** istersen: **Şema 5** (Coconote kanıtı).

## Seçim Sonrası Plan (Tüm Şemalarda Ortak UX İyileştirmeleri)

Hangi şema seçilirse seçilsin şunlar da yapılacak:
1. Token sisteminin genişletilmesi (seçilen palet + radius + gölge + odak halkaları) — `theme.css`
2. Sekme çubuğu → pill mod değiştirici; not `<details>` → gerçek yüzey; boş durum + mikro-metin iyileştirmeleri
3. Sidebar ağacı: ikonlar, aktif durum çipi, daha sıkı hiyerarşi
4. Atıf çiplerinin ve üretim panelinin seçilen kimliğe uyarlanması
5. Mobil üst bar düzeni iyileştirmesi
6. `YETENEKLER/07-stil-rehberi.md` güncellemesi (yeni token'lar tek otoriteye işlenir)
7. WCAG AA kontrast doğrulaması + hardcoded renk denetimi (grep)

---

> **Durum:** Şema seçimi bekleniyor — kullanıcı 1–5 arasından birini seçecek.
