# ruff: noqa: E501 — prompt şablonları doğal dil metnidir; satır uzunluğu kısıtı uygulanmaz
"""Not üretimi prompt şablonları (v3 — düşük akıl yürütmeli model için direktif sertleştirme)."""

from .common import (
    ATIF_KURALLARI,
    CIKTI_SOZLESMESI_JSON,
    CIKTI_SOZLESMESI_MARKDOWN,
    DIDAKTIK_USLUP,
    KAYNAK_ROL_AYRIMI,
    OGRENME_ISKELETI,
    YASAK_IFADELER,
)

TOPIC_EXTRACTION_PROMPT = (
    """Görevin: ders sunumunu okuyup NOT ÜRETİLECEK KONU LİSTESİNİ çıkarmak.

"""
    + CIKTI_SOZLESMESI_JSON
    + """

ADIM ADIM YORDAM (sırayla uygula, atlama):
1. Sunumu baştan sona oku. Her slaytın hangi kavramı öğrettiğini belirle.
2. Aynı kavramı işleyen ardışık slaytları TEK konuda birleştir.
3. Bir konu 8'den fazla yeni terim içeriyorsa VEYA slaytların yarısından fazlasına yayılıyorsa,
   onu anlamlı alt konulara BÖL. Bağımsız iki kavramı tek konuda BİRLEŞTİRME.
4. Her konuya en fazla 8 kelimelik başlık yaz. Başlık konunun kendisi olsun ("Giriş", "Bölüm 2",
   "Genel Bakış" gibi içi boş başlık YASAK).
5. Her konu için 3-8 anahtar terim seç: öğrencinin sınavda görmesi en muhtemel terimler.
6. Her konu için karıştırılması muhtemel konu başlıklarını yaz (aynı derste benzer isimli,
   benzer süreçli veya zıt işlevli konular). Yoksa boş liste bırak.
7. Konunun geçtiği slayt numaralarını yaz.
8. Konuları sunumdaki İŞLENİŞ SIRASINA göre diz. Alfabetik veya rastgele sıralama YASAK.

{dil_talimati}

ŞEMA (birebir uy):
{{"topics": [{{"topic": "...", "keywords": ["...", "..."], "slide_refs": [1, 2], "confusable_with": ["..."]}}]}}

ALTIN REFERANS 1 (psikoloji dersi — biçim örneği, içeriği kopyalama):
{{"topics": [{{"topic": "Freud'un Psikoseksüel Gelişim Evreleri", "keywords": ["oral evre", "anal evre", "fallik evre", "libido", "saplanma"], "slide_refs": [4, 5, 6], "confusable_with": ["Erikson'un Psikososyal Evreleri"]}}, {{"topic": "Savunma Mekanizmaları", "keywords": ["bastırma", "yansıtma", "yer değiştirme", "ego"], "slide_refs": [7, 8], "confusable_with": ["Başa Çıkma Stratejileri"]}}]}}

ALTIN REFERANS 2 (veri yapıları dersi — biçim örneği, içeriği kopyalama):
{{"topics": [{{"topic": "Bağlı Listede Ekleme ve Silme", "keywords": ["düğüm", "işaretçi", "baş düğüm", "O(1) ekleme"], "slide_refs": [11, 12], "confusable_with": ["Dizide Ekleme ve Silme"]}}, {{"topic": "Yığın ve Kuyruk Farkı", "keywords": ["LIFO", "FIFO", "push", "pop"], "slide_refs": [13], "confusable_with": ["Öncelik Kuyruğu"]}}]}}

SUNUM:
{slides}
{kazanimlar}"""
)

NOTE_GENERATION_PROMPT = (
    """Görevin: "{topic}" konusunu bir üniversite öğrencisine ÖĞRETEN bir ders notu bölümü yazmak.
Sen deneyimli bir öğretim görevlisisin. Amacın bilgi listelemek değil, öğrenciyi anlatarak öğretmek.

"""
    + CIKTI_SOZLESMESI_MARKDOWN
    + """

"""
    + KAYNAK_ROL_AYRIMI
    + """

"""
    + OGRENME_ISKELETI
    + """

ZORUNLU BÖLÜM DÜZENİ (bu başlıkları BİREBİR, bu sırayla yaz; başka başlık ekleme, atlama):

### {topic}

**Ne işe yarar?**
- 2-3 cümle. Konunun ne olduğunu ve öğrencinin bunu neden öğrendiğini söyle. Her cümle [n] taşır.

**Kavramlar**
- 3-8 madde. Her madde şu kalıpta: "**Terim** — tanım (tek cümle). Sade karşılığı: <günlük dille
  tek cümle>. [n]"
- Madde 3 satırı geçerse ikiye böl. Tanımsız terim bırakma.

**Neden böyle?**
- 2-4 madde. Her madde "Neden ...?" sorusuyla başlar, hemen altında tek paragraflık cevap verir ve [n] taşır.
- Cevap neden-sonuç zinciri kurar ("çünkü ... bu yüzden ...").
- Kaynaklarda cevabı olmayan soruyu YAZMA.

**Sık karıştırılanlar**
- 1-3 madde. Kalıp: "**A** ile **B**: <fark tek cümle>. Ayırt etmek için: <5 saniyede uygulanacak
  tek test>. [n]"
- Kaynaklarda karşılaştırma yoksa bu bölümü tek satır "Bu konuda karışan ikili yok." yaz.

**Örnek üzerinden**
- Tek somut örnek. 3-5 cümle. Örneği adım adım yürüt ve kavramın nerede devreye girdiğini göster. [n]

**Kendini sına**
- TAM 3 soru. Her soru ayrı madde. Sorular "neden", "ne olurdu", "hangisi farklı", "sırala" tipinde olur.
- Yalnızca "... nedir?" biçiminde soru YASAK.
- Her sorunun hemen altına "**Cevap:** ..." satırı yaz (1-2 cümle, [n] taşır).

**Hatırlatıcı**
- 3-5 madde. Her madde TEK satır, en fazla 15 kelime, ezberlenecek çekirdek bilgi. Atıf koyma.

UZUNLUK BÜTÇESİ: toplam 400-700 kelime. Bütçeyi aşma, yarısında da bırakma.

"""
    + DIDAKTIK_USLUP
    + """

"""
    + YASAK_IFADELER
    + """

"""
    + ATIF_KURALLARI
    + """

{dil_talimati}

ALTIN REFERANS 1 (yalnız BİÇİM örneğidir; konusu farklıdır, içeriğini KOPYALAMA):
### Klasik Koşullanma
**Ne işe yarar?**
- Klasik koşullanma, tarafsız bir uyaranın tepki doğuran bir uyaranla eşleşerek tepki üretir hale gelmesidir [1].
- Öğrenmenin en temel biçimidir; korku, iştah ve alışkanlık davranışlarının nasıl kurulduğunu açıklar [2].
**Kavramlar**
- **Koşulsuz uyaran** — doğuştan tepki doğuran uyarandır. Sade karşılığı: öğrenmeye gerek olmadan etkileyen şey. [1]
- **Koşullu uyaran** — eşleşme sonucu tepki doğurmaya başlayan tarafsız uyarandır. Sade karşılığı: sonradan anlam kazanan işaret. [1]
**Neden böyle?**
- Neden eşleşme tek başına yetmez?
  Çünkü tarafsız uyaranın koşulsuz uyarandan ÖNCE ve ona yakın zamanda gelmesi gerekir; sıra bozulursa beyin iki olayı ilişkilendirmez, bu yüzden koşullanma kurulmaz [2].
**Sık karıştırılanlar**
- **Klasik koşullanma** ile **edimsel koşullanma**: klasikte tepki uyaranla, edimselde sonuçla öğrenilir. Ayırt etmek için: davranışın ardından ödül/ceza varsa edimseldir. [3]
**Örnek üzerinden**
- Zil sesi başta anlamsızdır. Zil her yemekten hemen önce çalınır. Birkaç tekrardan sonra köpek zili duyunca salya üretir. Salya artık zile verilmiş öğrenilmiş tepkidir [1].
**Kendini sına**
- Zil yemekten SONRA çalınsaydı koşullanma neden kurulmazdı?
  **Cevap:** Çünkü işaret, olayı önceden haber vermez; beyin ilişkilendirme kuramaz [2].
- Aşağıdakilerden hangisi edimsel koşullanmadır: ödülle artan davranış mı, işaretle gelen tepki mi?
  **Cevap:** Ödülle artan davranış edimseldir; sonuç davranışı biçimlendirir [3].
- Söndürme sırasında ne olur?
  **Cevap:** Koşullu uyaran tek başına tekrarlanır ve öğrenilmiş tepki zamanla zayıflar [2].
**Hatırlatıcı**
- Önce işaret, sonra olay: sıra bozulursa öğrenme olmaz.
- Klasik = uyaran eşleşmesi, edimsel = sonuç.
- Söndürme tepkiyi siler değil, zayıflatır.

ALTIN REFERANS 2 (yalnız BİÇİM örneğidir; konusu farklıdır, içeriğini KOPYALAMA):
### Bağlı Listede Ekleme
**Ne işe yarar?**
- Bağlı liste, her düğümün bir sonrakini işaret ettiği bir veri yapısıdır [1].
- Araya eleman eklemeyi, diziyi kaydırmadan yapmayı sağlar; bu yüzden sık değişen koleksiyonlarda tercih edilir [2].
**Kavramlar**
- **Düğüm** — veriyi ve bir sonraki düğümün adresini tutan birimdir. Sade karşılığı: içinde hem eşya hem sonraki durağın adresi olan kutu. [1]
- **Baş düğüm** — listenin ilk düğümüdür. Sade karşılığı: zincirin ilk halkası. [1]
**Neden böyle?**
- Neden başa ekleme O(1)'dir?
  Çünkü yalnızca yeni düğümün işaretçisi baş düğüme çevrilir ve baş güncellenir; diğer düğümlere dokunulmaz, bu yüzden işlem eleman sayısından bağımsızdır [2].
**Sık karıştırılanlar**
- **Bağlı liste** ile **dizi**: dizide elemanlar bitişik bellekte, listede dağınıktır. Ayırt etmek için: soruda "kaydırma" geçiyorsa dizi, "işaretçi" geçiyorsa listedir. [3]
**Örnek üzerinden**
- Listede 5 → 9 → 12 var. Başa 3 eklenecek. Yeni düğüm 3 oluşturulur, işaretçisi 5'e çevrilir, baş artık 3'tür. Hiçbir eleman yer değiştirmez [2].
**Kendini sına**
- Sona ekleme neden başa eklemeden yavaştır?
  **Cevap:** Son düğüme ulaşmak için liste baştan taranır; bu tarama eleman sayısıyla artar [2].
- Diziyle bağlı liste arasındaki temel fark nedir?
  **Cevap:** Dizide bellek bitişiktir, listede düğümler işaretçilerle bağlanır [3].
- Baş düğümün işaretçisi kaybolursa ne olur?
  **Cevap:** Listenin geri kalanına erişilemez, tüm zincir kopar [1].
**Hatırlatıcı**
- Başa ekleme sabit sürede biter.
- Sona ekleme tarama gerektirir.
- Baş düğüm kaybolursa liste kaybolur.

TESLİM ÖNCESİ KONTROL (yazdıktan sonra kendi metnini denetle, hatalıysa düzelt):
1. Yedi bölüm başlığının hepsi var mı ve sırası doğru mu?
2. "Kendini sına" altında tam 3 soru ve 3 "**Cevap:**" satırı var mı?
3. Her bilgi cümlesi [n] taşıyor mu? Listede olmayan numara var mı?
4. Kod çiti, JSON, süslü parantez veya ters bölü + n dizisi var mı? Varsa sil.
5. Yasak ifadelerden biri geçiyor mu? Geçiyorsa cümleyi yeniden yaz.
6. Toplam 400-700 kelime aralığında mı?

KONU: {topic}

REHBER (ders sunumu — kapsamı belirler):
{slide_content}

KAYNAKLAR (ders kitabı taraması — içeriği verir):
{numbered_sources}
{kazanimlar}"""
)


COVERAGE_CHECK_PROMPT = (
    """Görevin: üretilmiş notu iki açıdan DENETLEMEK ve kusurları listelemek. Not yazmıyorsun, denetliyorsun.

"""
    + CIKTI_SOZLESMESI_JSON
    + """

ADIM ADIM YORDAM:
1. KONU LİSTESİ'ndeki her başlığı tek tek al. Notta o başlığa ait bölüm var mı bak.
2. Bölüm yoksa VEYA bölüm 3 cümleden kısaysa VEYA yalnız tanım verip mekanizma/örnek vermiyorsa,
   başlığı "missing" listesine yaz.
3. Sonra her bölümü şu altı bozukluk için denetle; bulduğun her bozukluğu "structure_issues" listesine yaz:
   a) "Kendini sına" bölümü yok, boş ya da cevapları yazılmamış.
   b) Sorulardan biri yalnızca "... nedir?" biçiminde (tekrar ettiren, düşündürmeyen).
   c) Atıfsız bilgi cümlesi var ([n] taşımayan iddia).
   d) Tek cümlede 3'ten fazla yeni kavram var (bilişsel yük).
   e) Aynı bilgi üç kez tekrarlanmış.
   f) Sunumu anlatan ifade var ("sunumda", "slaytta", "[Slide N]").
4. Kusur bulamazsan ilgili listeyi BOŞ bırak. Kusur uydurma.

ŞEMA (birebir uy):
{{"missing": ["konu başlığı", ...], "structure_issues": [{{"topic": "...", "issue": "kısa açıklama"}}]}}

ALTIN REFERANS 1 (kusur bulunan durum):
{{"missing": ["Savunma Mekanizmaları"], "structure_issues": [{{"topic": "Klasik Koşullanma", "issue": "Kendini sına sorularının cevapları yazılmamış"}}, {{"topic": "Bellek Türleri", "issue": "iki paragrafta aynı tanım tekrar ediliyor"}}]}}

ALTIN REFERANS 2 (kusursuz durum):
{{"missing": [], "structure_issues": []}}

KONU LİSTESİ: {topics}

NOT:
{note}"""
)

CITATION_CONFIRM_PROMPT = (
    """Görevin: bir alıntının kaynak parça tarafından DESTEKLENİP desteklenmediğine karar vermek.

"""
    + CIKTI_SOZLESMESI_JSON
    + """

KARAR KURALI (harfiyen uygula):
1. Alıntının taşıdığı İDDİA, kaynak parçada aynı anlamda geçiyorsa true yaz.
2. Kelimeler farklı ama anlam aynıysa true yaz (birebir eşleşme aranmaz).
3. Kaynak parça iddiayı kısmen destekliyor ama bir koşulu/sayıyı değiştiriyorsa false yaz.
4. İddia kaynakta hiç geçmiyorsa false yaz. Tahmin yürütme, genel bilgine başvurma.

ŞEMA: {{"supported": true}} veya {{"supported": false}}

ALTIN REFERANS 1: alıntı "Zil sesi öğrenilmiş tepki doğurur", kaynak "koşullu uyaran eşleşme sonrası tepki üretir" → {{"supported": true}}
ALTIN REFERANS 2: alıntı "Süreç üç evreden oluşur", kaynak "süreç beş evreden oluşur" → {{"supported": false}}

ALINTI: {quote}

KAYNAK PARÇA: {chunk_text}"""
)

NOTE_GENERATION_WEB_PROMPT = (
    """Görevin: "{topic}" konusunu öğreten bir ders notu bölümü yazmak. Elinde ders kitabı yok;
yalnız web kaynakları var. Sen deneyimli bir öğretim görevlisisin.

"""
    + CIKTI_SOZLESMESI_MARKDOWN
    + """

ZORUNLU BÖLÜM DÜZENİ (birebir bu başlıklar, bu sıra):
### {topic}
**Ne işe yarar?** (2-3 cümle, her cümle [n])
**Kavramlar** (3-8 madde; "**Terim** — tanım. Sade karşılığı: ... [n]")
**Neden böyle?** (2-3 madde; "Neden ...?" sorusu + tek paragraf cevap + [n])
**Örnek üzerinden** (tek somut örnek, 3-5 cümle, [n])
**Kendini sına** (TAM 3 soru, her birinin altında "**Cevap:** ..." [n])
**Hatırlatıcı** (3-5 tek satır, en fazla 15 kelime, atıfsız)

UZUNLUK BÜTÇESİ: 350-600 kelime.

"""
    + DIDAKTIK_USLUP
    + """

"""
    + YASAK_IFADELER
    + """

"""
    + ATIF_KURALLARI
    + """
EK KURAL: web kaynağının başlığından emin değilsen kaynağı yine [n] ile an, adını uydurma.

{dil_talimati}

ALTIN REFERANS 1 (biçim örneği — içeriği kopyalama):
### Fotosentez Işık Evresi
**Ne işe yarar?**
- Işık evresi, güneş ışığını hücrenin kullanabileceği kimyasal enerjiye çevirir [1].
- Bu evre olmadan karbon bağlanması için gerekli enerji üretilemez [2].
**Kavramlar**
- **Tilakoit zar** — ışık evresinin gerçekleştiği zar yapısıdır. Sade karşılığı: enerji üretiminin yapıldığı atölye. [1]
**Neden böyle?**
- Neden su parçalanır?
  Çünkü kopan elektronlar klorofilin kaybettiği elektronun yerini doldurur; bu yüzden zincir kesintisiz işler [2].
**Örnek üzerinden**
- Yaprağa ışık düşer, tilakoit zarda elektronlar uyarılır, su parçalanır ve oksijen açığa çıkar [1].
**Kendini sına**
- Işık kesilirse karanlık evre neden bir süre sonra durur?
  **Cevap:** Çünkü karanlık evrenin kullandığı enerji taşıyıcıları ışık evresinde üretilir [2].
- Açığa çıkan oksijen nereden gelir?
  **Cevap:** Parçalanan su moleküllerinden gelir [1].
- Klorofilin görevi nedir?
  **Cevap:** Işığı soğurup elektronları uyarır [1].
**Hatırlatıcı**
- Işık evresi enerji üretir, karanlık evre onu harcar.
- Oksijenin kaynağı sudur.

ALTIN REFERANS 2 (biçim örneği — içeriği kopyalama):
### Enflasyon Nedenleri
**Ne işe yarar?**
- Enflasyon, genel fiyat düzeyinin sürekli artmasıdır [1].
- Nedenini bilmek, hangi politikanın işe yarayacağını seçmeyi sağlar [2].
**Kavramlar**
- **Talep enflasyonu** — toplam talebin üretimi aşmasıyla oluşur. Sade karşılığı: mal az, para çok. [1]
- **Maliyet enflasyonu** — girdi fiyatlarının artmasıyla oluşur. Sade karşılığı: üretim pahalılaşır, fiyat yükselir. [2]
**Neden böyle?**
- Neden faiz artışı talebi kısar?
  Çünkü borçlanma pahalılaşır, harcama ertelenir; bu yüzden talep baskısı azalır [2].
**Örnek üzerinden**
- Petrol fiyatı yükselir, nakliye maliyeti artar, market fiyatları da artar. Talep değişmese bile fiyatlar yükselir [2].
**Kendini sına**
- Maliyet enflasyonunda faiz artışı neden yetersiz kalır?
  **Cevap:** Çünkü sorun talepte değil, girdi maliyetindedir [2].
- Hangisi talep enflasyonu işaretidir: üretim kapasitesi doluyken artan harcama mı, petrol zammı mı?
  **Cevap:** Kapasite doluyken artan harcama talep enflasyonudur [1].
- Fiyat artışı tek seferlikse buna enflasyon denir mi?
  **Cevap:** Denmez; enflasyon sürekli artış gerektirir [1].
**Hatırlatıcı**
- Talep enflasyonu: para çok, mal az.
- Maliyet enflasyonu: girdi pahalı.
- Tek seferlik artış enflasyon değildir.

TESLİM ÖNCESİ KONTROL: altı başlık tam mı, 3 soru + 3 cevap var mı, her bilgi cümlesi [n] taşıyor mu,
kod çiti, JSON veya süslü parantez var mı, kelime bütçesi tutuyor mu?

KONU: {topic}

KAYNAKLAR (web):
{numbered_sources}
{kazanimlar}"""
)

NOTE_SLIDE_ONLY_PROMPT = (
    """Görevin: "{topic}" konusunu YALNIZ ders sunumundan öğreten bir not bölümü yazmak.
Ders kitabı ve web kaynağı bulunamadı. Bu yüzden ATIF KULLANMAYACAKSIN.

"""
    + CIKTI_SOZLESMESI_MARKDOWN
    + """
EK SÖZLEŞME: [n] biçiminde atıf YAZMA. Köşeli parantezli numara kullanma.

ZORUNLU BÖLÜM DÜZENİ (birebir bu başlıklar, bu sıra):
### {topic}
**Ne işe yarar?** (2-3 cümle)
**Kavramlar** (3-8 madde; "**Terim** — tanım. Sade karşılığı: ...")
**Neden böyle?** (2-3 madde; "Neden ...?" sorusu + tek paragraf cevap)
**Örnek üzerinden** (tek somut örnek, 3-5 cümle; sunumda örnek yoksa sunumdaki bilgiyle
  tutarlı, uydurma sayı içermeyen bir günlük hayat örneği kur)
**Kendini sına** (TAM 3 soru, her birinin altında "**Cevap:** ...")
**Hatırlatıcı** (3-5 tek satır, en fazla 15 kelime)

UZUNLUK BÜTÇESİ: 300-550 kelime.

SUNUMU DEĞİL KONUYU ANLAT:
- Sunum maddelerini olduğu gibi kopyalama. Her maddeyi tanım + neden-sonuç + örnek içeren
  açıklamaya çevir. Çıplak madde listesi bırakma.
- Sunumda olmayan teknik ayrıntı, sayı, tarih, isim UYDURMA.

"""
    + DIDAKTIK_USLUP
    + """

"""
    + YASAK_IFADELER
    + """

{dil_talimati}

ALTIN REFERANS 1 (biçim örneği — içeriği kopyalama):
### Proje Yönetiminde Kapsam
**Ne işe yarar?**
- Kapsam, projede nelerin yapılacağını ve nelerin yapılmayacağını belirler.
- Kapsam netleşmezse ekip aynı işi farklı anlar ve teslim tarihi kayar.
**Kavramlar**
- **Kapsam bildirimi** — projenin sınırlarını yazılı olarak tanımlayan belgedir. Sade karşılığı: neyin dahil olduğunu söyleyen sözleşme.
- **Kapsam kayması** — onay alınmadan işin büyümesidir. Sade karşılığı: sessizce eklenen işler.
**Neden böyle?**
- Neden kapsam kayması bütçeyi bozar?
  Çünkü her ek iş zaman ve kişi gerektirir; plan sabit kalırken yük arttığı için maliyet aşılır.
**Örnek üzerinden**
- Ekip bir mobil uygulama sözü verir. Müşteri sonradan web sürümü ister. Onay alınmadan iş eklenir ve teslim iki ay gecikir.
**Kendini sına**
- Kapsam bildirimi neden yalnız "yapılacaklar" listesi değildir?
  **Cevap:** Yapılmayacakları da yazar; sınır ancak iki taraflı tanımla netleşir.
- Kapsam kaymasının ilk işareti nedir?
  **Cevap:** Onaysız eklenen küçük taleplerin birikmesidir.
- Kapsam ile hedef aynı şey midir?
  **Cevap:** Değildir; hedef sonucu, kapsam işin sınırlarını tanımlar.
**Hatırlatıcı**
- Kapsam neyin dışarıda olduğunu da söyler.
- Onaysız her ek iş kapsam kaymasıdır.

ALTIN REFERANS 2 (biçim örneği — içeriği kopyalama):
### Hücre Zarının Yapısı
**Ne işe yarar?**
- Hücre zarı, hücrenin içini dışından ayırır ve madde geçişini denetler.
- Bu denetim olmadan hücre iç dengesini koruyamaz.
**Kavramlar**
- **Fosfolipit çift katman** — zarın temel iskeletidir. Sade karşılığı: su seven başlar dışta, su sevmeyen kuyruklar içte duran çift sıra.
- **Zar proteini** — geçiş ve tanıma görevini üstlenir. Sade karşılığı: zarın kapıları ve kimlik okuyucuları.
**Neden böyle?**
- Neden yağda çözünen maddeler zardan kolay geçer?
  Çünkü zarın iç kısmı yağ benzeri kuyruklardan oluşur; benzer yapı benzerini geçirdiği için bu maddeler taşıyıcıya gerek duymaz.
**Örnek üzerinden**
- Oksijen küçük ve yağda çözünür, doğrudan geçer. Glikoz iridir ve taşıyıcı protein ister. Aynı zar iki maddeye farklı davranır.
**Kendini sına**
- Zar neden "seçici geçirgen" diye adlandırılır?
  **Cevap:** Bazı maddeleri geçirip bazılarını engellediği için.
- Taşıyıcı protein olmasaydı hücre ne kaybederdi?
  **Cevap:** Büyük ve suda çözünen maddeleri alamaz, beslenemezdi.
- Kuyrukların içte durması neyi sağlar?
  **Cevap:** Su ile temasını azaltır ve zarın kararlı kalmasını sağlar.
**Hatırlatıcı**
- Zar seçici geçirgendir.
- Küçük ve yağda çözünenler serbest geçer.
- Büyük moleküller taşıyıcı ister.

TESLİM ÖNCESİ KONTROL: altı başlık tam mı, 3 soru + 3 cevap var mı, hiç [n] kullandın mı (kullanma),
sunumu anlatan ifade var mı, kelime bütçesi tutuyor mu?

REHBER (ders sunumu):
{slide_content}
{kazanimlar}"""
)
