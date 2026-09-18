# ruff: noqa: E501 — prompt şablonları doğal dil metnidir; satır uzunluğu kısıtı uygulanmaz
"""Genel quiz üretim + açık uçlu puanlama prompt'ları (v3 — direktif sertleştirme)."""

from .common import CIKTI_SOZLESMESI_JSON

OVERALL_BATCH_PROMPT = (
    """Görevin: verilen not parçalarından "{category}" türünde TAM {count} soru üretmek.
Amacın öğrenciyi sınamak ve yanlışından öğretmektir.

"""
    + CIKTI_SOZLESMESI_JSON
    + """

ADIM ADIM YORDAM (sırayla uygula):
1. DAĞILIM PLANI'nı oku. Hangi konudan kaç soru isteniyorsa o sayıda üret. Plandan sapma.
2. Her soru için not parçalarından tek bir sınanacak bilgi seç. Aynı bilgiyi iki soruda sorma.
3. Soruyu kendi tip şemasına birebir uygun yaz (aşağıdaki TİP ŞEMALARI).
4. Sorunun en az %10'u (en az 1 soru) FARKLI konuları birbirine bağlasın: karşılaştırma, sıralama,
   "hangisi diğerinden farklı", bir kavramı diğerinin bağlamına taşıma. Bu sorular ilgili atıfların
   TÜMÜNÜ taşır.
5. Her soruya atıf ekle; yalnız ATIF LİSTESİ'ndeki id'leri kullan. Atıfsız soru YASAK.
6. Geribildirim alanlarını doldur; boş bırakma.

TİPE ÖZEL KURALLAR:
- mcq: 4 seçenek, tek doğru. "Hepsi", "Hiçbiri", "A ve B" YASAK. Seçenekler benzer uzunlukta olur.
  Çeldiriciler yaygın yanılgıdan, karıştırılan kavramdan veya yarım kalmış ifadeden türetilir.
- tf: statement yanlışsa yanlışlık GERÇEK bir kavram yanılgısından gelir. Olumsuzlama ekleyerek,
  sayı bozarak veya bariz olgu değiştirerek yanlış üretme. explanation yanılgının kaynağını açıklar.
- fib: boşluk (____) cümlenin kalanından tahmin edilebilecek bir kelime OLMAYACAK; boşluğa terim,
  kavram veya nicelik gelir. accepted_answers eş anlamlıları ve yaygın yazım varyantlarını içerir.
- open: answer_key.points alanına 2-5 anahtar nokta yaz (her biri tek cümle, puanlanabilir olsun).
  Sorunun cevabı tek kelimeyse open kullanma.

GERİBİLDİRİM KALIPLARI (harfiyen):
- feedback_correct: "Doğru! " + doğru cevabın neden doğru olduğu (tek cümle).
- feedback_wrong: "Doğru cevap: <cevap>. Açıklama: <tek cümle>. Yanılgı: <öğrenci neden yanılır>. [n]"

{dil_talimati}

ŞEMA (birebir uy):
{{"category": "{category}", "questions": [ ... ]}}

TİP ŞEMALARI:
- mcq: {{"type": "mcq", "topic": "...", "question": "...", "options": ["","","",""], "correct_index": 0, "explanation": "...", "feedback_correct": "Doğru! ...", "feedback_wrong": "Doğru cevap: X. Açıklama: ...", "citations": [{{"id": 1}}]}}
- tf: {{"type": "tf", "topic": "...", "statement": "...", "answer": true, "explanation": "Açıklama (yanlışsa düzeltme dahil)", "feedback_correct": "...", "feedback_wrong": "...", "citations": [{{"id": 1}}]}}
- fib: {{"type": "fib", "topic": "...", "text": "... ____ ...", "accepted_answers": ["cevap", "eş anlamlı"], "explanation": "...", "feedback_correct": "Doğru! ...", "feedback_wrong": "Doğru cevap: ... Açıklama: ...", "citations": [{{"id": 1}}]}}
- open: {{"type": "open", "topic": "...", "question": "...", "answer_key": {{"points": ["anahtar nokta 1", "anahtar nokta 2"], "citations": [{{"id": 1}}]}}}}

ALTIN REFERANS 1 (tf + fib biçimi — içeriği kopyalama):
{{"category": "tf", "questions": [{{"type": "tf", "topic": "Klasik Koşullanma", "statement": "Söndürme, öğrenilmiş tepkinin bellekten tamamen silinmesidir.", "answer": false, "explanation": "Söndürme tepkiyi zayıflatır; bağ korunur ve kendiliğinden geri gelebilir [2].", "feedback_correct": "Doğru! Söndürme silme değil, zayıflatmadır [2].", "feedback_wrong": "Doğru cevap: Yanlış. Açıklama: Söndürmede bağ korunur, tepki yalnız zayıflar. Yanılgı: Tepkinin kaybolması, bilginin silindiği izlenimi verir. [2]", "citations": [{{"id": 2}}]}}, {{"type": "fib", "topic": "Bağlı Liste", "text": "Bağlı listede her düğüm, bir sonraki düğümün adresini tutan bir ____ içerir.", "accepted_answers": ["işaretçi", "pointer", "gösterici"], "explanation": "Düğümler veriyi ve bir sonraki düğümü gösteren işaretçiyi tutar [1].", "feedback_correct": "Doğru! İşaretçi zinciri kurar [1].", "feedback_wrong": "Doğru cevap: işaretçi. Açıklama: Düğümler adresi işaretçide saklar. Yanılgı: 'indis' dizilere aittir, listede indis yoktur. [1]", "citations": [{{"id": 1}}]}}]}}

ALTIN REFERANS 2 (mcq + open biçimi — içeriği kopyalama):
{{"category": "mixed", "questions": [{{"type": "mcq", "topic": "Bellek", "question": "Bir öğrenci telefon numarasını tekrar ederek aklında tutuyor. Bu işlem hangi bellek sürecine örnektir?", "options": ["Kısa süreli bellekte zihinsel tekrar", "Duyusal bellekte kayıt", "Uzun süreli bellekten geri getirme", "Anlamsal ağda yeniden kodlama"], "correct_index": 0, "explanation": "Zihinsel tekrar, bilgiyi kısa süreli bellekte canlı tutar [3].", "feedback_correct": "Doğru! Tekrar, kısa süreli bellekte bilginin sönmesini geciktirir [3].", "feedback_wrong": "Doğru cevap: Kısa süreli bellekte zihinsel tekrar. Açıklama: Tekrar bilgiyi geçici depoda canlı tutar. Yanılgı: Tekrarın kalıcılık sağladığı düşünülür; kalıcılık anlamlandırmayla gelir. [3]", "citations": [{{"id": 3}}]}}, {{"type": "open", "topic": "Koşullanma", "question": "Klasik ve edimsel koşullanmanın öğrenme kaynağı bakımından farkını bir örnekle açıkla.", "answer_key": {{"points": ["Klasik koşullanmada öğrenme uyaranların eşleşmesiyle olur.", "Edimsel koşullanmada öğrenme davranışın sonucuyla olur.", "Örnek, ödül veya ceza içeriyorsa edimsel koşullanmadır."], "citations": [{{"id": 2}}]}}}}]}}

TESLİM ÖNCESİ KONTROL:
1. Soru sayısı tam {count} mü? Dağılım planına uyuldu mu?
2. Her sorunun tipi şemasıyla birebir uyuşuyor mu (eksik alan var mı)?
3. En az 1 soru konular arası bağlantı kuruyor mu?
4. Her soruda citations dolu mu, id'ler listede var mı?
5. mcq'de yasak seçenek kalıbı var mı? tf'de yanlışlık gerçek yanılgıdan mı geliyor?
6. Çıktı tek JSON nesnesi mi, kod çiti var mı?

DAĞILIM PLANI:
{distribution_plan}

NOT PARÇALARI:
{note_sections}

ATIF LİSTESİ:
{citations_json}"""
)

ESSAY_GRADE_PROMPT = (
    """Görevin: öğrencinin açık uçlu cevabını CEVAP ANAHTARINA göre puanlamak ve öğretici geri bildirim yazmak.

"""
    + CIKTI_SOZLESMESI_JSON
    + """

ADIM ADIM YORDAM (sırayla uygula):
1. Cevap anahtarındaki her anahtar noktayı tek tek al.
2. Öğrencinin cevabında o nokta VAR mı bak:
   - Varsa ve doğruysa → "correct" listesine yaz.
   - Yoksa → "missing" listesine yaz.
   - Varsa ama yanlışsa → "incorrect" listesine yaz.
3. Öğrencinin yazdığı, anahtarda olmayan bilgileri "unnecessary" listesine yaz (doğru sayma).
4. Boş kalan listeye tek eleman olarak "yok" yaz.
5. Puanı 0-10 arası ver: correct sayısının anahtardaki nokta sayısına oranını temel al,
   incorrect maddeler için puan düş. Anahtarda olmayan bilgi puan KAZANDIRMAZ.
6. Her "incorrect" maddesi için misconception kaydı yaz: öğrenci bu yanlışa NEDEN düşmüş olabilir
   (hangi kavramla karıştırma, hangi aşırı genelleme). Yanlış yoksa boş liste.
7. ideal_answer yaz: öğrencinin cevabının "düzeltilmiş + tamamlanmış" hali gibi okunsun.
   Doğru ifadelerini koru, eksikleri ekle, yanlışları düzelt, atıfları [n] ile işaretle.
8. next_step yaz: TEK, somut, uygulanabilir adım. "Daha çok çalış", "tekrar et" gibi genel tavsiye YASAK.
   Adım, cevaptaki en büyük eksiği hedefler.
9. confidence: 0.0-1.0 arası puanlamaya güvenin.

ŞEMA (birebir uy):
{{"score": 7, "correct": [...], "missing": [...], "incorrect": [...], "unnecessary": [...], "misconception": [{{"point": "...", "why": "..."}}], "explanation": "...", "ideal_answer": "...", "next_step": "...", "confidence": 0.9}}

ALTIN REFERANS 1 (kısmi doğru cevap — biçim örneği, içeriği kopyalama):
{{"score": 6, "correct": ["Klasik koşullanmanın uyaran eşleşmesine dayandığını yazmış"], "missing": ["Edimsel koşullanmada sonucun davranışı biçimlendirdiği"], "incorrect": ["Söndürmeyi 'bilginin silinmesi' olarak tanımlamış"], "unnecessary": ["yok"], "misconception": [{{"point": "Söndürme = silme", "why": "Tepkinin gözlenmemesi, bağın da yok olduğu izlenimini verdiği için"}}], "explanation": "Anahtarın üç noktasından biri eksik, biri yanlış tanımlanmış; bu yüzden puan ortanın üstünde kaldı.", "ideal_answer": "Klasik koşullanmada öğrenme, tarafsız uyaranın koşulsuz uyaranla eşleşmesiyle oluşur [1]. Edimsel koşullanmada ise davranışın sonucu (ödül veya ceza) davranışı biçimlendirir [2]. Söndürmede koşullu uyaran tek başına tekrarlandıkça tepki zayıflar; bağ silinmez, kendiliğinden geri gelebilir [2].", "next_step": "Söndürme ile unutmayı ayırt eden 3 örnek soruyu çöz ve her birinde bağın korunup korunmadığını yaz.", "confidence": 0.85}}

ALTIN REFERANS 2 (tam doğru cevap — biçim örneği, içeriği kopyalama):
{{"score": 10, "correct": ["Başa eklemenin sabit sürede olduğunu gerekçesiyle yazmış", "Sona eklemede tarama gerektiğini yazmış"], "missing": ["yok"], "incorrect": ["yok"], "unnecessary": ["yok"], "misconception": [], "explanation": "Anahtardaki tüm noktalar doğru gerekçeyle karşılanmış.", "ideal_answer": "Başa eklemede yalnız yeni düğümün işaretçisi ve baş güncellenir; işlem eleman sayısından bağımsızdır [1]. Sona eklemede son düğüme ulaşmak için liste baştan taranır, bu yüzden maliyet eleman sayısıyla artar [2].", "next_step": "Aynı analizi çift yönlü bağlı listede sona ekleme için yap ve farkı tek cümleyle yaz.", "confidence": 0.95}}

TESLİM ÖNCESİ KONTROL: dört liste de dolu mu (boşsa "yok" yazıldı mı), her incorrect için misconception
var mı, next_step somut mu, ideal_answer atıf taşıyor mu, çıktı tek JSON nesnesi mi?

SORU: {question}
CEVAP ANAHTARI: {answer_key}
KAYNAKLAR:
{numbered_sources}
ÖĞRENCİ CEVABI: {user_answer}"""
)
