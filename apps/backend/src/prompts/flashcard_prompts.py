# ruff: noqa: E501 — prompt şablonları doğal dil metnidir; satır uzunluğu kısıtı uygulanmaz
"""Flashcard üretim prompt'ları (v3 — düşük akıl yürütmeli model için direktif sertleştirme)."""

from .common import CIKTI_SOZLESMESI_JSON

FLASHCARD_BATCH_PROMPT = (
    """Görevin: verilen not bölümünden aralıklı tekrar (spaced repetition) kartları üretmek.
Kart, öğrencinin bilgiyi HATIRLAMASINI zorlayan küçük bir sınama birimidir; özet değildir.

"""
    + CIKTI_SOZLESMESI_JSON
    + """

ADIM ADIM YORDAM (sırayla uygula):
1. Not bölümünü oku. Ezberlenmesi gereken tekil olguları listele (tanım, ayrım, sıra, koşul, sonuç).
2. Her olgu için TEK kart yaz. Konu başına 5-15 kart üret; daha azı eksik, daha fazlası gereksizdir.
3. Kart tipini seç:
   - "term": front YALNIZ terimdir (cümle değil), back tanımdır.
   - "qa": front tam bir sorudur, back kısa cevaptır.
4. Her kartın back alanını en fazla 2 cümle ve 25 kelime yaz. Uzunsa kartı böl.
5. Her karta en az bir atıf ekle; yalnız ATIF LİSTESİ'ndeki id'leri kullan.
6. Kartları not bölümündeki işleniş sırasına göre diz.

MİNİMUM BİLGİ İLKESİ (ihlal etme):
- Bir kart TEK bir şey sorar. Cevap "ve", "ayrıca", "bunun yanında" ile ikinci olguya bağlanıyorsa kartı ikiye böl.
- Liste, sıralama veya çok adımlı süreç tek karta sığdırılmaz; her adım ayrı karttır.
- Cevabı paragraf olan kart YASAK.

BAĞLAM VE NETLİK:
- Cevabın hangi bağlamda geçerli olduğu belirsizse front'a niteleyici ekle: "<konu> bağlamında ...".
- Kısaltmanın ilk geçtiği kartta açılımını yaz.
- Sorunun cevabı soru metninden tahmin edilebiliyorsa soruyu yeniden yaz.

İKİ YÖNLÜLÜK:
- Bir kavram hem terim→tanım hem tanım→terim yönünden değerliyse İKİ ayrı kart üret.
- İkinci kartın back alanı birinciyle birebir aynı olmayacak; daha kısa yazılacak.

YASAK KART TİPLERİ:
- "Şu tanımı tekrarla" gibi yüzeysel kart.
- Yalnız kavramın adını soran kart ("X nedir?" karşılığı tek kelime olan kart hariç tutulur).
- Notta geçmeyen bilgiyi soran kart.

{dil_talimati}

ŞEMA (birebir uy):
{{"cards": [{{"topic": "...", "front": "...", "back": "...", "type": "qa", "citations": [{{"id": 1}}]}}]}}
type yalnızca "qa" veya "term" olabilir.

ALTIN REFERANS 1 (biçim örneği — içeriği kopyalama):
{{"cards": [{{"topic": "Klasik Koşullanma", "front": "Koşullu uyaran", "back": "Eşleşme sonucu tepki doğurmaya başlayan, başlangıçta tarafsız olan uyaran.", "type": "term", "citations": [{{"id": 1}}]}}, {{"topic": "Klasik Koşullanma", "front": "Klasik koşullanmada koşullu uyaranın zamanlaması neden önemlidir?", "back": "Koşulsuz uyarandan önce gelmelidir; aksi halde olayın habercisi olmaz ve ilişkilendirme kurulmaz.", "type": "qa", "citations": [{{"id": 2}}]}}, {{"topic": "Klasik Koşullanma", "front": "Söndürme sırasında koşullu tepkiye ne olur?", "back": "Koşullu uyaran tek başına tekrarlandıkça tepki zayıflar.", "type": "qa", "citations": [{{"id": 2}}]}}]}}

ALTIN REFERANS 2 (biçim örneği — içeriği kopyalama):
{{"cards": [{{"topic": "Bağlı Listede Ekleme", "front": "Baş düğüm", "back": "Bağlı listenin ilk düğümü; listeye erişim buradan başlar.", "type": "term", "citations": [{{"id": 1}}]}}, {{"topic": "Bağlı Listede Ekleme", "front": "Bağlı listede başa ekleme neden sabit sürededir?", "back": "Yalnız yeni düğümün işaretçisi ve baş güncellenir; diğer düğümlere dokunulmaz.", "type": "qa", "citations": [{{"id": 2}}]}}, {{"topic": "Bağlı Listede Ekleme", "front": "Bağlı liste ile diziyi soruda ayırt eden ipucu nedir?", "back": "\"Kaydırma\" geçiyorsa dizi, \"işaretçi\" geçiyorsa bağlı listedir.", "type": "qa", "citations": [{{"id": 3}}]}}]}}

TESLİM ÖNCESİ KONTROL:
1. Kart sayısı 5-15 arasında mı?
2. Her back alanı 25 kelimeyi aşıyor mu? Aşıyorsa böl.
3. İki olgu tek kartta birleşmiş mi?
4. Her kartta citations dolu mu ve id'ler listede var mı?
5. type değerleri yalnız "qa" veya "term" mi?
6. Çıktı tek JSON nesnesi mi, kod çiti var mı?

NOT BÖLÜMÜ:
{note_section}

ANAHTAR TERİMLER:
{keywords}

QUIZ SORULARI (aynı bilgiyi tekrar sormamak için incele):
{questions}

ATIF LİSTESİ:
{citations_json}"""
)
