# Yetenek 08 — Ücretsiz Araç Envanteri

> **Sahibi:** Ücretsizlik Ajanı (`AJANLAR/03-ucretsizlik-ajani.md`). Bu dosya, projede kullanılan her aracın lisans/maliyet kaydı ve denetim prosedürüdür.

## Kural

**Tüm araçlar ücretsiz ve açık kaynak olmalıdır.** Tek istisna ailesi: **LLM çıkarımı** — kullanıcı kararıyla yerel LLM çalıştırılmaz; LLM gerektiren görevlerde ücretli API kullanımına izin verilir (birincil: DeepSeek chat API). Diğer tüm araçlar ücretsiz/açık kaynak kalır (`PROJE_YOL_HARITASI.md` Bölüm 7).

## Onaylı Araç Envanteri

| Araç | Amaç | Lisans | Maliyet | Alternatif (gerekirse) |
|------|------|--------|---------|------------------------|
| DeepSeek Harness (dsh) | Geliştirme/orkestrasyon çalışma zamanı (15 ajan) | MIT | Ücretsiz | — |
| React 18 + TypeScript + Vite | Frontend | MIT | Ücretsiz | — |
| Tailwind CSS | Stil | MIT | Ücretsiz | — |
| Zustand | State yönetimi | MIT | Ücretsiz | — |
| FastAPI | Backend API | MIT | Ücretsiz | — |
| SQLite + aiosqlite | Veritabanı | Public Domain | Ücretsiz | — |
| LanceDB | Vektör DB | Apache-2.0 | Ücretsiz | FAISS (Apache-2.0) |
| DeepSeek chat API | LLM çıkarımı (birincil sağlayıcı) | **İstisna (kullanıcı onaylı)** | Kullanım bazlı | OpenAI uyumlu alternatif sağlayıcı (yalnızca kullanıcı onayıyla) |
| openai (Python SDK) | DeepSeek API istemcisi | Apache-2.0 | Ücretsiz | httpx ile elle |
| sentence-transformers + bge-m3 | Embedding (**LLM değildir** — yerelde kalır) | MIT | Ücretsiz (yerel) | multilingual-e5-small (Apache-2.0) — uzak embedding API'si YASAK |
| pymupdf | PDF metin çıkarımı | AGPL-3.0 | Ücretsiz | pdfplumber (MIT) — dağıtım hedeflenirse zorunlu değişim |
| marker-pdf | OCR yedeği | GPL-3.0 (kişisel yerel kullanımda kabul) | Ücretsiz | Tesseract (Apache-2.0) — dağıtımda zorunlu değişim |
| python-pptx | PPTX metin çıkarımı | MIT | Ücretsiz | — |
| LibreOffice headless | PPTX→PDF render | MPL-2.0 | Ücretsiz | Yok → metin fallback |
| pdfjs-dist | PDF sayfa render (pop-up) | Apache-2.0 | Ücretsiz | — |
| GitHub Actions | CI | Ücretsiz tier | Ücretsiz | — |
| ruff / pyright / pytest | Backend QA | MIT | Ücretsiz | — |
| eslint / tsc / vitest / playwright | Frontend QA | MIT/Apache-2.0 | Ücretsiz | — |
| bandit / pip-audit / pnpm audit | Güvenlik tarama | Apache-2.0/ISC | Ücretsiz | — |
| gitleaks / trufflehog | Sırlar tarama | MIT | Ücretsiz | — |

## Yasak Liste (özet — tam metin yol haritası Bölüm 7'de)

- LLM dışı ücretli SaaS/API'ler (vektör DB bulutları, auth SaaS, hosting, monitoring)
- Onay kaydı olmayan ücretli LLM sağlayıcı kullanımı
- Kullanım-bazlı ücretlendirme (LLM çıkarımı hariç)

## Denetim Prosedürü

1. **Tarama:** `package.json`, `pyproject.toml`, `uv.lock`, `requirements*.txt` içindeki her bağımlılığı listele.
2. **Kontrol:** Her servisin lisansını ve fiyatlandırma sayfasını doğrula (web_search).
3. **Karar:** Ücretsiz/open-source ve lisansı uygunsa envantere ekle (ONAY). Değilse ücretsiz alternatif ara → spike görevle doğrula → envanteri ve yol haritasını güncelle. Alternatif yoksa RED + Ana Ajan'a rapor.
4. **Kayıt:** Her araç değişimini `PROJE_YOL_HARITASI.md` Bölüm 2.1 + Bölüm 15'e (Sürüm Geçmişi) işle.
5. **Maliyet gözetimi:** `generation_logs`'u faz geçişlerinde denetle; token israfı/verimsiz prompt deseni tespit edersen Ana Ajan'a optimizasyon görevi öner. Uyarı kriteri: aynı içerik için tekrarlanan tam yeniden üretimler, batch'siz dev çağrılar, gereksiz yüksek `max_tokens`.

## İstisna Kaydı (LLM Çıkarımı)

| Alan | Kayıt |
|------|-------|
| Kapsam | LLM gerektiren tüm görevler: ürün çıkarımı (not/quiz/puanlama) + geliştirme sırasındaki LLM ihtiyaçları |
| Sınır | Yerel LLM (Ollama/GGUF) çalıştırılmaz (kullanıcı kararı); embedding modeli LLM değildir, yerelde kalır |
| Onay | Kullanıcı kararı (bu oturum) |
| Yönetim | `generation_logs` + maliyet bekçiliği; prompt verimliliği denetimi |
| Alternatif | OpenAI uyumlu başka sağlayıcı yalnızca kullanıcı onayıyla; istisna kaydına işlenir |

## Kabul Kriterleri
- Her bağımlılık bu envanterde kayıtlı ve onaylı
- Envanter ile gerçek bağımlılık dosyaları birebir (denetim geçer)
- LLM istisnası dışında ücretli araç yok
