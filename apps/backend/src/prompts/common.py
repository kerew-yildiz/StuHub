# ruff: noqa: E501 — prompt şablonları doğal dil metnidir; satır uzunluğu kısıtı uygulanmaz
"""Ortak prompt yardımcıları (v3 — düşük akıl yürütmeli model için direktif sertleştirme).

TASARIM NOTU (2026-09-18):
Hedef model `deepseek-v4.1-flash` DÜŞÜK akıl yürütme kipinde çalışır. Böyle bir model
"iyi yaz", "uygun biçimde açıkla" gibi soyut talimatları güvenilir biçimde yorumlayamaz;
karar bırakılan her yer sapma üretir. Bu nedenle tüm şablonlar şu üç ilkeyle yazılır:

1. KARAR BIRAKMA: bölüm adları, sıraları, madde sayıları, kelime bütçeleri sabit verilir.
2. YORDAM VER: model "önce şunu yap, sonra şunu yap" biçiminde adım adım yönlendirilir.
3. ALTIN REFERANS: her şablonda iki tam örnek çıktı bulunur; model taklit ederek üretir.

BRACE KURALI: bu sabitler `.format()` uygulanan şablonlara gömülür. Bu yüzden metinde geçen
süslü parantezler ÇİFT yazılır (`{{` / `}}`); format sonrası tek parantez olarak görünürler.
"""

from __future__ import annotations

# ── Eski sabitler (geriye uyumluluk) ────────────────────────────────────
KAYNAK_DISI_BILGI_YASAGI = (
    "SADECE sağlanan kaynak parçalarını kullan; kaynaklarda olmayan bilgi EKLEME."
)

ATIF_LISTESI_KURALI = (
    "[n] numaraları yalnızca aşağıda verilen kaynak listesinden olacak; "
    "listede olmayan numara KULLANMA."
)

# ── ÇIKTI SÖZLEŞMELERİ ──────────────────────────────────────────────────
# 2026-09-18 üretim hatası: model yanıtı kod çitiyle sarılı bir JSON zarfı olarak döndü
# (içerik "content" anahtarının içinde, satır sonları kaçış dizisi olarak). Zarf çözülmeden
# kullanıcıya basıldı. Aşağıdaki sözleşmeler bu hata sınıfını kaynağında keser.

CIKTI_SOZLESMESI_MARKDOWN = """ÇIKTI SÖZLEŞMESİ (İHLALİ HATADIR):
- Yanıtın TAMAMI düz Markdown metindir. İlk karakter diyez (#) işaretidir.
- Kod çiti KULLANMA: üç ters tırnak işareti (ve json etiketli hali) YASAK. Tek bir tane bile yazma.
- JSON YAZMA. Süslü parantez, anahtar-değer yapısı, "content" adlı zarf alanı KULLANMA.
- Satır sonu için gerçek satır sonu kullan; ters bölü + n dizisini metne YAZMA.
- Markdown öncesi/sonrası açıklama, selamlama, "İşte notunuz" gibi cümle YAZMA.
- Yanıtın ilk satırı istenen başlık, son satırı istenen son bölümdür; fazlası yoktur."""

CIKTI_SOZLESMESI_JSON = """ÇIKTI SÖZLEŞMESİ (İHLALİ HATADIR):
- Yanıtın TAMAMI TEK bir JSON nesnesidir: açan süslü parantezle başlar, kapatanla biter.
- Kod çiti KULLANMA: üç ters tırnak işareti (ve json etiketli hali) YASAK.
- JSON öncesi/sonrası açıklama, başlık, yorum satırı YAZMA.
- Şemada olmayan alan EKLEME; şemadaki alanların tamamını doldur.
- Metin alanlarında gerçek Türkçe cümle yaz; alan değerini ikinci bir JSON nesnesine sarma.
- Son alandan sonra virgül bırakma; tırnakları kapat."""

# ── ÜSLUP VE ÖĞRENME İLKELERİ ───────────────────────────────────────────

DIDAKTIK_USLUP = """ÜSLUP KURALLARI (her cümlede uygula):
1. Öğretmen gibi yaz: önce fikri söyle, sonra açıkla, sonra örnekle. Sırayı bozma.
2. Her yeni terimi ilk geçtiği yerde tanımla. Tanımsız terim bırakma.
3. Cümleler kısa olsun: en fazla 25 kelime. Uzun cümleyi ikiye böl.
4. Soyut ifadeyi somutla: "önemlidir" yerine NEDEN önemli olduğunu yaz.
5. Doğrudan öğrenciye hitap et ("...dikkat et", "...karıştırma"). Resmî mesafe koyma.
6. Bir olguyu iki kez anlatma. Tekrar yerine yeni bilgi ver."""

YASAK_IFADELER = """YASAK İFADELER (tek bir tanesini bile kullanma):
- "Bu bölümde ... ele alınmaktadır/anlatılmaktadır", "Aşağıda ... verilmiştir"
- "Sunumda ... listelenmiştir", "Slayt N'de ...", "[Slide N]", "Yukarıda görüldüğü gibi"
- "Önemli bir konudur", "dikkat çekicidir", "büyük rol oynar" (içi boş değer cümleleri)
- "Umarım faydalı olur", "Başarılar", "İşte ...", "Elbette", "Tabii ki"
- Kaynakta geçmeyen sayı, tarih, isim, oran (uydurma YASAK)."""

OGRENME_ISKELETI = """ÖĞRENME İSKELETİ (etkili öğrenmenin sırası — bu sırayı DEĞİŞTİRME):
1. BAĞLAM: konu nereye oturuyor, öğrenci bunu neyin üstüne koyacak.
2. TANIM: kavramın ne olduğu, sade tek cümlelik karşılığıyla birlikte.
3. MEKANİZMA: nasıl işliyor, neden böyle oluyor (neden-sonuç zinciri).
4. ÖRNEK: tek somut örnek üstünde kavramın çalıştığını gösterme.
5. AYIRT ETME: en çok karıştırılan komşu kavramdan ayrılma noktası.
6. GERİ ÇAĞIRMA: öğrencinin kendi kendini sınadığı sorular (cevaplarıyla).
7. SIKIŞTIRMA: tek satırlık hatırlatıcılar."""

KAYNAK_ROL_AYRIMI = """KAYNAKLARIN ROL AYRIMI (karıştırma):
- REHBER (ders sunumu/slaytlar) KAPSAMI belirler: hangi kavramlar, hangi sırayla, ne derinlikte
  işlenecek. Sınavın sınırı budur. Rehberde olmayan konuyu ANLATMA.
- KAYNAKLAR (ders kitabı taraması) İÇERİĞİ verir: tanım, mekanizma, örnek, sayı, ayrıntı.
  Her bilgi cümlesi buradan gelir. Kaynak numaralarını METNE YAZMA (bkz. ATIF YASAĞI).
- Yani: rehber NE anlatılacağını, kaynaklar NASIL anlatılacağını söyler.
- Rehberde geçen ama kaynaklarda karşılığı olmayan kavramı yalnızca adıyla an, uydurma açıklama yazma."""

ATIF_YASAGI = """ATIF YASAĞI (İHLALİ HATADIR):
1. Metin içinde [1], [2], ⟨3⟩ biçiminde NUMARA İŞARETİ KULLANMA. Tek bir tane bile yazma.
2. KAYNAKLAR listesindeki numaralar sana içeriği sunmak içindir; numaraları metne TAŞIMA.
3. Kaynakça, kaynak listesi, "Kaynaklar" başlıklı bölüm EKLEME; not yalnız öğretici metinden oluşur.
4. Kaynağı olmayan bilgiyi YAZMA (uydurma yasaktır) — ama yazdığın her cümle ÇIPLAK akar:
   numara işareti olmadan."""


def dil_talimati(not_dili: str, *, json_sema: bool = True) -> str:
    """Ayarlanan üretim dili için prompt talimatı (tr/en/auto).

    `json_sema=False`: MARKDOWN üreten promptlar için (not bölümleri). Varsayılan
    metindeki "JSON anahtar adları şemada verildiği gibi İngilizce kalacak" cümlesi
    JSON şemalı çağrılar için yazılmıştır; markdown not promptuna girince model notu
    JSON zarfına sarıyordu (2026-09-18 vakası: İngilizce anahtarlı {"content": "..."}
    zarfı ham olarak kaydedildi). Markdown promptlarında bu cümle GEÇMEZ.
    """
    if not_dili == "en":
        return "Tüm çıktıları İngilizce yaz."
    if not_dili == "auto":
        return "Çıktı dilini kaynak içeriğin diliyle eşleştir (kaynak Türkçeyse Türkçe yaz)."
    if not json_sema:
        return "Tüm çıktıları Türkçe yaz."
    return "Tüm çıktıları Türkçe yaz. JSON anahtar adları şemada verildiği gibi İngilizce kalacak."


def kazanimlar_blok(kazanimlar: str) -> str:
    """Müfredat/kazanım metnini prompt'a eklenecek bölüm bloğuna çevirir."""
    if not kazanimlar.strip():
        return ""
    return (
        "\nKAZANIMLAR (müfredat hedefleri — bu hedefleri karşılayan içeriği ÖNE AL, "
        "hedefle ilgisiz ayrıntıyı kısa tut):\n" + kazanimlar + "\n"
    )
