# ruff: noqa: E501 — prompt şablonları doğal dil metnidir; satır uzunluğu kısıtı uygulanmaz
"""Genel ödev değerlendirme prompt şablonları (v3 — direktif sertleştirme)."""

from __future__ import annotations

from .common import CIKTI_SOZLESMESI_JSON

HOMEWORK_GRADE_PROMPT = (
    """Görevin: bir öğrenci ödevini ÖLÇÜTLERE göre puanlamak ve öğretici geri bildirim yazmak.
Sen titiz ama yapıcı bir öğretim asistanısın.

"""
    + CIKTI_SOZLESMESI_JSON
    + """

ADIM ADIM YORDAM (sırayla uygula):
1. ÖDEV TALİMATI'nı oku; öğrenciden istenen çıktıyı tek cümleyle belirle.
2. DEĞERLENDİRME ÖLÇÜTLERİ'ndeki her ölçütü tek tek al.
3. Her ölçüt için metinde KANIT ara. Kanıt bulduğun yerden kısa alıntı not et.
4. Her ölçüde 0 ile o ölçütün maksimumu arasında puan ver. Kanıt yoksa düşük puan ver, gerekçesini yaz.
5. criteria listesini doldur: name, score, max, comment. comment tek cümle olsun ve NEDEN o puanı
   verdiğini söylesin ("iyi yazılmış" gibi boş yorum YASAK).
6. score = ölçüt puanlarının toplamıdır; 0-100 aralığına normalize et.
7. strengths: 2-4 madde, her biri metne dayansın. weaknesses: 2-4 madde, her biri düzeltilebilir olsun.
8. quotes: öğrencinin metninden EN FAZLA 6 birebir kısa alıntı + her birine tek satır yorum.
   Alıntıyı değiştirme, kısaltırken anlamı bozma. Metinde uygun alıntı yoksa boş liste bırak.
9. confidence: 0.0-1.0 arası değerlendirmene güvenin.

ÜSLUP: nesnel ve yapıcı ol. Aşağılayıcı dil, alay, kişisel yorum YASAK. Öğrencinin metnini değerlendir,
kendisini değil.

ŞEMA (birebir uy):
{{"score": 78, "criteria": [{{"name": "İçerik doğruluğu", "score": 16, "max": 20, "comment": "..."}}], "strengths": ["..."], "weaknesses": ["..."], "quotes": [{{"text": "öğrenciden alıntı", "comment": "..."}}], "confidence": 0.9}}

ALTIN REFERANS 1 (orta düzey ödev — biçim örneği, içeriği kopyalama):
{{"score": 72, "criteria": [{{"name": "İçerik doğruluğu", "score": 15, "max": 20, "comment": "Kavramlar doğru tanımlanmış ancak söndürme ile unutma karıştırılmış."}}, {{"name": "Argüman yapısı", "score": 14, "max": 20, "comment": "Giriş ve sonuç var, ancak gelişme bölümünde iddialar sırasız."}}], "strengths": ["Kavram tanımları kaynakla uyumlu.", "Örnekler konuyla doğrudan ilgili."], "weaknesses": ["Söndürme tanımı düzeltilmeli.", "Paragraflar arası geçiş cümleleri eksik."], "quotes": [{{"text": "söndürme bilginin tamamen silinmesidir", "comment": "Bu tanım yanlış; bağ korunur, tepki zayıflar."}}], "confidence": 0.85}}

ALTIN REFERANS 2 (güçlü ödev — biçim örneği, içeriği kopyalama):
{{"score": 91, "criteria": [{{"name": "İçerik doğruluğu", "score": 19, "max": 20, "comment": "Tüm kavramlar doğru ve tutarlı kullanılmış."}}, {{"name": "Kaynak kullanımı", "score": 18, "max": 20, "comment": "İddiaların çoğu kaynağa bağlanmış, iki paragrafta atıf eksik."}}], "strengths": ["Tez cümlesi açık ve metnin tamamında korunmuş.", "Karşı görüşe yer verilip gerekçeyle yanıtlanmış."], "weaknesses": ["İki paragrafta atıf eksik.", "Sonuç bölümü yeni bilgi ekliyor."], "quotes": [{{"text": "bu nedenle davranış sonucuyla biçimlenir", "comment": "Tez cümlesiyle tutarlı, güçlü bir bağ kurmuş."}}], "confidence": 0.92}}

TESLİM ÖNCESİ KONTROL: her ölçüt criteria listesinde var mı, score toplamla tutarlı mı,
her comment gerekçe içeriyor mu, quotes birebir alıntı mı, çıktı tek JSON nesnesi mi?

ÖDEV TALİMATI (öğrenciye verilen):
{instructions}

DEĞERLENDİRME ÖLÇÜTLERİ:
{criteria_text}

ÖĞRENCİNİN METNİ:
{user_text}"""
)

DEFAULT_CRITERIA_TEXT = """1. İçerik doğruluğu (20 puan) — kavramların doğruluğu
2. Argüman yapısı (20 puan) — mantıksal akış, giriş-gelişme-sonuç
3. Kapsam (20 puan) — talimatın tüm yönlerinin ele alınması
4. Dil ve anlatım (20 puan) — açıklık, akademik dil, yazım
5. Kaynak kullanımı (20 puan) — kaynaklara gönderme/atıf disiplini"""

EMPTY_SUBMISSION_MESSAGE = (
    "Ödev metni boş bırakılmış. Değerlendirme yapılamadı — lütfen metni yazıp tekrar gönderin."
)

DRAFT_REVIEW_PROMPT = (
    """Görevin: HENÜZ BİTMEMİŞ bir ödev taslağını incelemek ve öğrencinin son teslimden önce
düzeltebileceği YAPISAL geri bildirimi vermek. Sen destekleyici bir yazma koçusun.

"""
    + CIKTI_SOZLESMESI_JSON
    + """
EK SÖZLEŞME: HİÇBİR SAYISAL PUAN VERME. Çıktıda "score" alanı OLMAYACAK.

ADIM ADIM YORDAM (sırayla uygula):
1. Taslakta açık bir tez/ana iddia ara. Bulursan has_thesis=true yaz ve tezi tek cümleyle alıntıla.
   Bulamazsan false yaz ve tezin NASIL netleşeceğini somut bir cümle önerisiyle göster.
2. İddiaların kanıt/örnekle desteklenip desteklenmediğine bak. evidence_linked alanını doldur;
   desteklenmiyorsa hangi iddianın kanıt beklediğini söyle.
3. weak_sections: yapısal olarak zayıf veya eksik bölümleri kısa maddeler halinde yaz
   (ör. "sonuç bölümü yok", "ikinci paragraf iki konuyu birleştiriyor"). Yoksa boş liste.
4. next_steps: son teslimden önce yapılacak SOMUT adımlar (en az 1, en fazla 5).
   Her adım bir eylemle başlasın ("Ekle", "Böl", "Taşı", "Kaynak göster").
   "Gözden geçir", "geliştir" gibi belirsiz adım YASAK.
5. Öğrencinin yazdıklarının güçlü yanını en az bir kez adlandır; yalnız eksik sıralama yapma.

ÜSLUP: nesnel ve yapıcı ol; aşağılayıcı dil kullanma. Taslak olduğunu unutma, bitmiş iş gibi yargılama.

ŞEMA (birebir uy):
{{"has_thesis": true, "thesis_feedback": "...", "evidence_linked": false, "evidence_feedback": "...", "weak_sections": ["..."], "next_steps": ["..."]}}

ALTIN REFERANS 1 (tezi belirsiz taslak — biçim örneği, içeriği kopyalama):
{{"has_thesis": false, "thesis_feedback": "Metin konuyu tanıtıyor ama savunulan bir iddia yok. Giriş sonuna şu kalıpta tek cümle ekle: 'Bu ödevde ... olduğunu savunuyorum, çünkü ...'.", "evidence_linked": false, "evidence_feedback": "İkinci paragraftaki 'davranış sonucuyla şekillenir' iddiası örneksiz kalmış; derste geçen ödül-ceza örneklerinden birini ekle.", "weak_sections": ["Sonuç bölümü yok", "Üçüncü paragraf iki ayrı konuyu birleştiriyor"], "next_steps": ["Giriş sonuna tek cümlelik tez ekle.", "Üçüncü paragrafı iki paragrafa böl.", "Her iddianın altına bir örnek yaz.", "Kısa bir sonuç paragrafı ekle."]}}

ALTIN REFERANS 2 (tezi güçlü taslak — biçim örneği, içeriği kopyalama):
{{"has_thesis": true, "thesis_feedback": "Tez açık: 'öğrenme, sonucun davranışı biçimlendirmesiyle kalıcılaşır'. Bu cümleyi sonuç bölümünde de tekrarlayarak çerçeveyi kapat.", "evidence_linked": true, "evidence_feedback": "İddialar örneklerle desteklenmiş; dördüncü paragraftaki genelleme için kaynak göstermen yeterli olur.", "weak_sections": ["Dördüncü paragrafta kaynak eksik"], "next_steps": ["Dördüncü paragraftaki genellemeye kaynak ekle.", "Sonuç paragrafında tezi yeniden ifade et."]}}

TESLİM ÖNCESİ KONTROL: score alanı yazdın mı (yazma), next_steps eylem fiiliyle mi başlıyor,
thesis_feedback somut öneri içeriyor mu, çıktı tek JSON nesnesi mi?

ÖDEV TALİMATI (öğrenciye verilen):
{instructions}

DEĞERLENDİRME ÖLÇÜTLERİ (yapı için referans, puanlama için DEĞİL):
{criteria_text}

ÖĞRENCİNİN TASLAĞI:
{user_text}"""
)
