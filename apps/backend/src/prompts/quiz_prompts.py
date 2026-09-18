# ruff: noqa: E501 — prompt şablonları doğal dil metnidir; satır uzunluğu kısıtı uygulanmaz
"""Bölüm quizi üretim prompt'ları (v3 — düşük akıl yürütmeli model için direktif sertleştirme)."""

from .common import CIKTI_SOZLESMESI_JSON

QUIZ_BATCH_PROMPT = (
    """Görevin: verilen not bölümünden "{topic}" hakkında TAM 5 çoktan seçmeli soru üretmek.
Amacın öğrenciyi elemek değil, ÖĞRENMESİNİ sınamak ve yanlışından bir şey öğretmektir.

"""
    + CIKTI_SOZLESMESI_JSON
    + """

ADIM ADIM YORDAM (sırayla uygula):
1. Not bölümünü oku. Sınanmaya değer 5 ayrı bilgi seç. Aynı bilgiyi iki soruda sınama.
2. Soruları şu seviye dağılımıyla yaz (sırayı koru):
   - Soru 1 ve 2: HATIRLA/ANLA — tanım, ayırt etme, ilişki kurma.
   - Soru 3 ve 4: UYGULA/ÇÖZÜMLE — verilen bir duruma kuralı uygulama, nedeni bulma, iki kavramı ayırma.
   - Soru 5: DEĞERLENDİR — bir iddiayı kaynağa dayanarak yargılama.
3. Her soru için 4 seçenek yaz. Doğru seçeneği belirle ve correct_index ile bildir.
4. Çeldiricileri şu dört kaynaktan üret; her soruda farklı bir tip kullan:
   (a) konuyla karıştırılan başka bir kavram, (b) eksik/yarım kalmış ifade,
   (c) doğru olguyu yanlış bağlama taşıma, (d) yaygın öğrenci yanılgısı.
5. Doğru cevap konumunu dağıt: aynı index en fazla 2 kez doğru olabilir.
6. Her soruya en az bir atıf ekle. Yalnız ATIF LİSTESİ'ndeki id'leri kullan.
7. Geribildirimleri doldur ve boş bırakma.

SORU YAZIM KURALLARI:
- Soru kökü en fazla 2 cümle. Tek soruda tek bilgi ölçülür.
- "Hepsi doğru", "Hiçbiri", "A ve B" gibi seçenek YASAK.
- Komik, bariz yanlış, alakasız seçenek YASAK. Her çeldirici inandırıcı olacak.
- Seçenekler benzer uzunlukta olacak (doğru seçenek en uzun olmayacak).
- Soru kökünde cevabı ele veren kelime kullanma.

GERİBİLDİRİM KURALLARI (harfiyen):
- feedback_correct: "Doğru! " ile başlar, ardından doğru cevabın NEDEN doğru olduğunu tek cümleyle pekiştirir.
- feedback_wrong: "Doğru cevap: <şık metni>. Neden: <tek cümle>. Yanılgı: <çeldiricinin neden cazip
  olduğu ve nerede yanlış olduğu>. [n]" kalıbına birebir uyar.
- explanation: konuyu 1-2 cümlede özetler ve [n] taşır.

{dil_talimati}

ŞEMA (birebir uy):
{{"topic": "...", "questions": [{{"topic": "...", "question": "...", "options": ["","","",""], "correct_index": 0, "explanation": "...", "feedback_correct": "Doğru! ...", "feedback_wrong": "Doğru cevap: X. Neden: ... Yanılgı: ...", "citations": [{{"id": 1}}]}}]}}

ALTIN REFERANS 1 (uygula/çözümle seviyesinde tek soru — biçim örneği, içeriği kopyalama):
{{"topic": "Klasik Koşullanma", "question": "Bir araştırmacı zili yemekten hemen SONRA çalıyor ve koşullanma oluşmuyor. Bu sonucun nedeni aşağıdakilerden hangisidir?", "options": ["İşaret olayı önceden haber vermediği için ilişkilendirme kurulmadı", "Zil sesi çok kısa olduğu için tepki oluşmadı", "Yemek miktarı yetersiz kaldığı için tepki zayıfladı", "Köpek zile karşı doğuştan duyarsız olduğu için tepki vermedi"], "correct_index": 0, "explanation": "Koşullanmada koşullu uyaran, koşulsuz uyarandan önce gelmelidir [2].", "feedback_correct": "Doğru! Koşullu uyaranın önce gelmesi, onu olayın habercisi yapar [2].", "feedback_wrong": "Doğru cevap: İşaret olayı önceden haber vermediği için ilişkilendirme kurulmadı. Neden: Koşullanma, işaretin olayı önceden bildirmesine dayanır. Yanılgı: Süre ve miktar akla yatkın görünür, ancak sorun sıradadır; eşleşmenin yönü bozulmuştur. [2]", "citations": [{{"id": 2}}]}}

ALTIN REFERANS 2 (değerlendir seviyesinde tek soru — biçim örneği, içeriği kopyalama):
{{"topic": "Bağlı Listede Ekleme", "question": "Bir öğrenci 'bağlı listede sona ekleme de sabit sürede yapılır' diyor. Bu iddia için en doğru değerlendirme hangisidir?", "options": ["Yanlıştır; son düğüme ulaşmak için liste baştan taranır", "Doğrudur; işaretçi güncellemesi her zaman sabit sürer", "Doğrudur; bağlı listede tüm işlemler sabit süredir", "Yanlıştır; sona ekleme bellek kopyalaması gerektirir"], "correct_index": 0, "explanation": "Sona ekleme, son düğümü bulmak için tarama gerektirir [2].", "feedback_correct": "Doğru! Tarama maliyeti eleman sayısıyla arttığı için işlem sabit süreli değildir [2].", "feedback_wrong": "Doğru cevap: Yanlıştır; son düğüme ulaşmak için liste baştan taranır. Neden: Sabit süre yalnız başa eklemede geçerlidir. Yanılgı: İşaretçi güncellemesinin sabit olması, ona ULAŞMANIN da sabit olduğu izlenimi verir. [2]", "citations": [{{"id": 2}}]}}

TESLİM ÖNCESİ KONTROL:
1. Tam 5 soru var mı? Seviye dağılımı 2-2-1 mi?
2. Her soruda 4 seçenek ve tek doğru var mı? Aynı index 2'den fazla tekrar ediyor mu?
3. Yasak seçenek kalıpları ("hepsi", "hiçbiri") var mı?
4. Her soruda citations dolu mu ve id'ler listede var mı?
5. feedback_wrong kalıbı ("Doğru cevap: ... Neden: ... Yanılgı: ...") her soruda tam mı?
6. Çıktı tek JSON nesnesi mi, kod çiti var mı?

NOT BÖLÜMÜ:
{note_section}

ATIF LİSTESİ:
{citations_json}
{kazanimlar}"""
)
