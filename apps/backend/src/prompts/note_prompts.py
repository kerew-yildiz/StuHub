# ruff: noqa: E501 — prompt şablonları doğal dil metnidir; satır uzunluğu kısıtı uygulanmaz
"""Not üretimi prompt şablonları (Yetenek 02 §Prompt Şablonu + Yetenek 06 doğrulama)."""

TOPIC_EXTRACTION_PROMPT = """Sen bir ders notu asistanısın. Aşağıdaki ders sunumu (guide slides) içeriğinden, not üretilecek konu listesini çıkar.

SUNUM:
{slides}

KURALLAR:
1. Her konu için kısa ve net bir başlık yaz.
2. keywords: konuyla ilgili anahtar terimler. {dil_talimati}
3. slide_refs: konunun geçtiği slide numaraları.
4. Yalnızca JSON döndür, şu şema ile:
{{"topics": [{{"topic": "...", "keywords": ["...", "..."], "slide_refs": [1, 2]}}]}}
"""

NOTE_GENERATION_PROMPT = """Sen bir üniversite ders notu yazarısın. Aşağıda ders sunumunun "{topic}" konusundaki rehber içeriği ve ders kitabından alınan kaynak parçaları var.

KURALLAR:
1. SADECE sağlanan kaynak parçalarını kullan; kaynaklarda olmayan bilgi EKLEME.
2. "{topic}" konusunu eksiksiz ve anlaşılır biçimde açıkla; öğrenci seviyesine uygun yaz. {dil_talimati}
3. Her bilgi parçasının sonuna kaynak atıf numarasını [n] biçiminde koy (n: KAYNAKLAR listesindeki numara).
4. Madde işaretleri ve kısa paragraflar kullan; gereksiz tekrar yapma.
5. Bölümü tam olarak "### {topic}" başlığıyla başlat (başka başlık düzeyi/ifade kullanma).

KONU: {topic}

REHBER (sunum):
{slide_content}

KAYNAKLAR:
{numbered_sources}

ÇIKTI: Markdown not bölümü (inline atıflı).
"""

COVERAGE_CHECK_PROMPT = """Aşağıdaki konu kontrol listesi ve üretilmiş not var. Hangi konular notta YETERSİZ ya da EKSİK?

KONU LİSTESİ: {topics}

NOT:
{note}

Yalnızca JSON döndür: {{"missing": ["konu başlığı", ...]}} (eksik yoksa boş liste)
"""

CITATION_CONFIRM_PROMPT = """Bir not parçasındaki alıntı, kaynak parçada birebir geçmiyor. Alıntı, kaynak parçanın içeriğini destekliyor mu?

ALINTI: {quote}

KAYNAK PARÇA: {chunk_text}

Yalnızca JSON döndür: {{"supported": true}} ya da {{"supported": false}}
"""

NOTE_GENERATION_WEB_PROMPT = """Sen bir üniversite ders notu yazarısın. Aşağıda "{topic}" konusundaki web kaynakları var.

KURALLAR:
1. SADECE sağlanan web kaynaklarını kullan; kaynaklarda olmayan bilgi EKLEME.
2. "{topic}" konusunu eksiksiz ve anlaşılır biçimde açıkla; öğrenci seviyesine uygun yaz. {dil_talimati}
3. Her bilgi parçasının sonuna kaynak atıf numarasını [n] biçiminde koy (n: KAYNAKLAR listesindeki numara).
4. Kaynak başlığından emin değilsen genel ifade kullan.
5. Madde işaretleri ve kısa paragraflar kullan; gereksiz tekrar yapma.
6. Bölümü tam olarak "### {topic}" başlığıyla başlat (başka başlık düzeyi/ifade kullanma).

KONU: {topic}

KAYNAKLAR:
{numbered_sources}

ÇIKTI: Markdown not bölümü (inline atıflı).
"""

NOTE_SLIDE_ONLY_PROMPT = """Ders kitabı ve web'de kaynak bulunamadı. Aşağıdaki sunum (rehber) içeriğinden "{topic}" konusunu eksiksiz, öğrenci seviyesinde TAM bir not olarak yaz. Atıf ekleme ([n] kullanma). {dil_talimati}

KURALLAR:
1. Bölümü tam olarak "### {topic}" başlığıyla başlat (başka başlık düzeyi/ifade kullanma).
2. Madde işaretleri ve kısa paragraflar kullan; gereksiz tekrar yapma.

REHBER:
{slide_content}

ÇIKTI: Markdown not bölümü (atıfsız).
"""
