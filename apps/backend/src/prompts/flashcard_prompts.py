# ruff: noqa: E501 — prompt şablonları doğal dil metnidir
"""Flashcard üretim prompt'ları (Yetenek 09)."""

FLASHCARD_BATCH_PROMPT = """Aşağıda bir ders notunun "{topic}" bölümü, anahtar terimleri ve quiz soruları var.

KURALLAR:
1. SADECE sağlanan not bölümü ve kaynaklardan kart üret; kaynaklarda olmayan bilgi EKLEME.
2. MİNİMUM BİLGİ İLKESİ: her kart TEK bir olgu/soru ölçecek.
   - back alanı en fazla 2 cümle, en fazla 25 kelime olacak.
   - Liste, sıralama veya çok adımlı süreç tek karta sığdırılmayacak; her adım ayrı kart olacak.
   - Bir kartın cevabı "ve", "ayrıca" ile ikinci bir olguya bağlanıyorsa kartı ikiye böl.
3. TİPLER:
   - "qa": soru→cevap. Soru, cevabı tahmin ettirmeyecek kadar net olacak.
   - "term": terim→tanım. front yalnızca terim olacak (açıklama cümlesi değil).
   Konu başına 5–15 kart hedefle.
4. BAĞLAM: her kartta cevabın hangi bağlamda geçerli olduğu belirsizse, front'a konuyu belirten
   kısa bir niteleyici ekle (ör. "<konu> bağlamında ..."). Kısaltma kullanacaksan ilk geçtiği kartta
   açılımını yaz.
5. İKİ YÖNLÜLÜK: aynı içerik hem terim→tanım hem tanım→terim yönünden değerliyse iki ayrı kart üret
   (back alanları birebir aynı olmasın; ikinci kartta tanım daha kısa tutulsun).
6. Her kart en az bir atıf taşıyacak (citations alanı); atıf yalnızca ATIF LİSTESİ'ndeki id'lerden seçilecek.
7. Kart içeriği kopyalanabilir bir cevap olmayacak: "şu tanımı tekrarla" gibi akademik olmayan,
   tamamen yüzeysel kartlar üretme. Bir kavramı yalnızca adından ibaret soran kart üretme.
8. Yalnızca JSON döndür ve şemaya birebir uy: {{"cards": [{{"topic": "...", "front": "...", "back": "...", "type": "qa", "citations": [{{"id": 1}}]}}]}}
9. type yalnızca "qa" ya da "term" olabilir.
10. {dil_talimati}

NOT BÖLÜMÜ:
{note_section}

ANAHTAR TERİMLER:
{keywords}

QUIZ SORULARI:
{questions}

ATIF LİSTESİ:
{citations_json}
"""
