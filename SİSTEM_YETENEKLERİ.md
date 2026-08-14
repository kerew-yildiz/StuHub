# SİSTEM YETENEKLERİ — DeepSeek Harness (DSH) Ajan Kataloğu

> **Kullanım:** Bu dosya, StuHub DS projesinin üzerinde çalıştığı **DeepSeek Harness (DSH)** çalışma zamanının yetenek kataloğu ve ajan kullanım rehberidir. `PROJE_YOL_HARITASI.md` ile birlikte her session başında context'e alınır. Ana Ajan delegasyon yaparken hedef ajanın `AJANLAR/` dosyasına ek olarak bu dosyanın ilgili bölümlerini prompt'a katar.
>
> **Kaynak:** `C:\Users\kerew\deepseek-harness` checkout'unun tam kazısı (`DSH_ARASTIRMA_RAPORU.md`) — sürüm: developer preview. Ayrıntı, kod örneği ve kaynak bağlantıları için rapora bakın; burası ajanların günlük karar referansıdır.

---

## 1. DSH Nedir?

- **DeepSeek Harness (`dsh`)**, DeepSeek AI'ın geliştirdiği açık kaynak (MIT) ajan harness'ıdır. Mimari ilkesi: **"her şey bir plugin'dir"** — model adaptörü, araç kayıt defteri, session log, dosya erişimi, onay politikası, hatta ajan döngüsünün kendisi bile Cordis plugin framework'ü (`@deepseek-ai/cordis`) üzerinde değiştirilebilir bileşenlerdir.
- **İki kullanım yüzü:** (1) `dsh web` — Web GUI (varsayılan `http://127.0.0.1:3080`); (2) `dsh --profile headless "<görev>"` — tek görev çalıştırıp çıkan başsız mod. Ayrıca Python SDK ve JSON-RPC/ACP arayüzleriyle programatik kullanım.
- **Durum:** developer preview — hızlı gelişiyor, uyumluluk kırıcı değişiklikler olabilir. Bu yüzden StuHub DS tarafında DSH'in somut davranışına bağlı kritik işlerde checkout dokümantasyonu (`C:\Users\kerew\deepseek-harness\docs\`) canlı otoritedir.
- **StuHub DS bağlamı:** Projenin 15 ajanı (yol haritası Bölüm 4.1) DSH üzerinde çalışır; Ana Ajan'ın orkestrasyon araçları (subagent, workflow, goal, jobs) DSH yetenekleridir.

## 2. Çalışma Modeli (ajan perspektifinden)

| Kavram | Tanım | Ajan için anlamı |
|--------|-------|------------------|
| **turn** | Kabul edilmiş girdinin bir turu; model ve araçları durana ya da politika kesene kadar sürer; 0+ step içerir | Bir kullanıcı mesajına verilen tüm çalışma tek turdur |
| **step** | 1 model isteği + bu isteğin tetiklediği araç çalıştırmaları | Araç sonuçları sonraki step'in girdisidir |
| **session log** | Append-only `SessionEvent` akışı (JSONL veya SQLite); modelin gördüğü geçmiş bu logdan türetilir | **"Model-visible ⟺ logged" ilkesi:** modele giren her şey logdan yeniden kurulabilir olmalıdır |
| **effect** | `ctx.effect()`/`ctx.on()` ile yapılan her kayıt geri alınabilir | HMR/reload/plugin değişiminde sızıntı olmaz |
| **scope** | Kayıtlar global ya da tek ajana scoped'dur; aynı isimli scoped kayıt globali **gölgeler** (shadowing); lineage (parent/child) veridir, görünürlüğü değiştirmez | Alt ajanlar global araçları miras alır; ajan-bazlı özelleştirme shadowing ile yapılır |
| **waterfall** | Around-middleware olay zinciri; listener `next()` çağırmazsa zincir kısa devre olur (veto) | Politika listener'ları veto edebilir; salt gözlemci bir listener `next()` çağırmalıdır |

**Turn akışı (özet):** `turn/start` → girdi claim → `agent/pre-step` (veto/rewrite hakkı) → `step/start` → `agent/request` → `llm/stream` → `assistant/chunk*` → `tool/call*` → `tools/pre-execute` (onay/politika) → `tools/execute` → `tools/post-execute` → `tool/result*` → `step/end` → (gerekirse yeni step) → `agent/turn-stopping` → `turn/end`. Her aşama plugin'lerin eklemlenebileceği bir uzantı noktasıdır.

## 3. ARAÇ KATALOĞU

> Checkout'un `docs/tool-catalog.md` envanteri (44 araç) + canlı ortamda mevcut varyantlar. Her grup için "nasıl kullanılır" notları StuHub DS pratiğine göre yazılmıştır.

### 3.1 Dosya Sistemi

| Araç | Ne yapar | Kritik kurallar |
|------|----------|-----------------|
| `read` | Satır numaralı dosya okuma (offset/limit) | Metin dosyalarını okumak için kabuk yerine bunu kullan |
| `write` | Dosya oluştur / tamamen değiştir | Mevcut dosyayı önce `read` et; hedefli değişim için `edit` tercih et |
| `edit` | UTF-8 metinde literal değiştirme | `old_string` birebir eşleşmeli; birden fazla eşleşmede `replace_all` |
| `glob` | Yol kalıbıyla dosya keşfi (gitignore dahil) | Kabuk `find` yerine kullan; sonuç değişiklik zamanı sıralıdır |
| `grep` | İçerik arama (ripgrep sözdizimi) | Kabuk `grep`/`rg` yerine kullan |
| `read_image` | PNG/JPEG/WebP/GIF görüntüsünü modele verir | UI/snapshot incelemesi için |
| `str_replace_editor` | Dosya üzerinde çoklu str-replace düzenleyicisi | Büyük refactor'lar için edit'e alternatif |

### 3.2 Kabuk & Terminal

| Araç | Ne yapar | Kritik kurallar |
|------|----------|-----------------|
| `bash` | Bash komutu çalıştırır (state'siz, işlem başına) | `workdir` parametresiyle çalışma dizini ver; `run_in_background: true` ile uzun işler. **Nonzero exit/kill hata DEĞİL sonuçtur:** `exitCode`, `timedOut`, `aborted`, `signal` alanlarını ayrı ayrı oku (timedOut/aborted birbirini dışlar) |
| `pwsh` | PowerShell komutu çalıştırır (Windows) | `cd` yerine `workdir`; her çağrı taze süreçtir — durum kalıcı DEĞİLDİR; nonzero exit kuralı bash ile aynı |
| `terminal_open/send/read/list/close/signal` | Kalıcı PTY oturumu (state korunur) | Uzun ömürlü etkileşimli süreçler (dev server, REPL) için; terminal ajan-owner-scoped'dur; **session başına tek aktif send** vardır (ikincisi bekler) |

### 3.3 Delegasyon & Orkestrasyon

| Araç | Ne yapar | Kritik kurallar |
|------|----------|-----------------|
| `subagent` | Bağımsız bağlamda alt ajan görevi | Prompt kendi kendine yetmeli (konuşmayı görmez); varsayılan arka plan; bağımsız işleri AYNI mesajda birlikte başlat |
| `subagent_fork` | Bu konuşmayı miras alan alt ajan | Tamamlanmış turları görür; devam/inceleme işleri için |
| `send_message` | Aynı alt ajana yeni tur mesajı | Çalışan tur bitince işler; sonuç dönmez, yalnızca teslim onayı |
| `interrupt_agent` | Alt ajanın yürüyen turunu durdurur | Derindeki torun ajanları da durdurabilir; işi bitmiş ajana no-op |
| `list_agents` | Sürebilir alt ajanları durumlarıyla listeler | Bitirme anketi değil hatırlama aracı; bitişler bildirimle gelir |
| `report` | Alt ajanın yapılandırılmış kapanış raporu | Alt ajan tarafında kullanılır |
| `workflow` | Alt ajanları ölçekte orkestre eden JS script motoru | Çok parçalı fan-out için; `agent()`, `pipeline()`, `parallel()`, `phase()`, `log()`; meta JSON, script plain JS |
| `ralph` | Taze-ajan döngüsü (her tur yeni context, workspace = kalıcı bellek) | Yalnızca kullanıcı açıkça Ralph/fresh-agent isterse |
| `create_goal` / `get_goal` / `update_goal` | Aynı session'da uzun soluklu hedef yönetimi | Uzun teslimat hedefi için Ana Ajan kullanır; resume/fork sonrası `update_goal` action: resume ile yeniden silahlanır |
| `job_kill` / `job_list` / `job_output` | Arka plan iş yönetimi (bash/pwsh `run_in_background`) | Başlatılan her job id'sini takip et; bitişler bildirimle gelir, busy-poll yapma. İşin `done` olması "kaynak bırakıldı" demektir (işin bittiği değil); sahip başına eşzamanlı iş sınırı varsayılan 10 |
| `schedule_create/list/delete` | Session'a bağlı zamanlanmış hatırlatıcılar | `every_seconds ≥ 300`; teslim `followup` ile normal turn olarak gelir (at-least-once, tam garanti yok); soğuk session'da çalışmaz, canlanınca devam eder |
| `todo_write` | Yapılandırılmış görev listesi | Liste her çağrıda TAMAMEN değiştirilir; tek satırlık işlerde kullanma |
| `exit_plan_mode` | Plan modunu onaylı planla kapatır | Plan modu yumuşak rehberliktir (enforcement değil); kullanıcıya `#` başlıklı tam markdown plan sun |
| `ask_user_question` | Onay/seçim/eksik bilgi sorusu | Kararlı id'ler kullan; önerilen seçenek ilk sırada + "(Önerilen)". **Yalnız canlı kök ajan sorabilir** — alt ajanlar soramaz (DELEGATED_CALLER); eksik bilgiyi Ana Ajan'a rapor et |
| `skill` | Kayıtlı skill'in tam talimatını yükler | Görev bir skill adıyla eşleşiyorsa önce bunu çağır; skill'ler proje `.dsh/skills`, `.agents/skills`, `~/.agents/skills`, `$DSH_HOME/skills` ve custom dizinlerden keşfedilir |

### 3.4 Bilgi & Web

| Araç | Ne yapar | Kritik kurallar |
|------|----------|-----------------|
| `web_search` | Web'de güncel bilgi arama | Kaynak URL'leri markdown link olarak aktarılmalı; sonuç sayısı varsayılan sınır 8 |
| `web_fetch` | Tek URL'nin içeriğini getirir | **Non-2xx yanıt SONUÇTUR, hata değildir** (`statusCode`+`body` okunur); yalnız HTTP(S), credential reddedilir |
| `session_search` / `session_trace` / `session_event_read` / `session_event_search` / `session_event_trace` | Session log'u üzerinde arama/iz sürme (SQLite FTS dahil) | Geçmiş kararları/kanıtları yeniden bulmak için; varsayılan limit 20, maks 100 |
| `lsp` | Dil sunucusu sorgusu (tanım, referans, hover...) | 4 işlem: goToDefinition/findReferences/goToImplementation/hover; generic JSON-RPC kaçışı YOK |

### 3.5 Çalışma Zamanı Öz-Düzenleme (Cordis araçları)

| Araç | Ne yapar |
|------|----------|
| `cordis_define` / `cordis_undefine` / `cordis_run` / `cordis_stop` | Ajan kendi plugin ağacına plugin tanımlar/çalıştırır/durdurur |
| `cordis_inspect_list` / `cordis_inspect_query` / `cordis_inspect_self` | Bellekteki Cordis ağacını ve servisleri inceler |
| `run_code` | Code Mode taşıma aracı (alt çağrılar pipeline'dan geçer) |

> **Not:** Bu araçlar "ajan kendi çalışma zamanını değiştirir" senaryosu içindir; StuHub DS'te yalnızca açık ihtiyaçta kullanılır (her müdahale session log'a işlenir).

## 4. GÜVENLİK & SANDBOX

- **SandboxMode (dosya-etki politikası):** `read-only` (yalnız gerekli sink'ler, ör. `/dev/null`) · `workspace-write` (workspace kökü + backend'in vaat ettiği temp alan) · `danger-full-access` (kısıt yok — onayla). Ağ ve süreç görünürlüğü bu kelimenin KAPSAMINDA DEĞİLDİR.
- **Enforcement `full` / `partial`:** `partial`, backend'in her dosya etkisini garanti edemediğini bildirir (örn. eski Landlock ABI, Windows ACL boşlukları). Mutlak sınır isteyen işlerde `partial`'a güvenme.
- **Fail-closed:** Confined çalıştırma için uygun backend yoksa `SANDBOX_UNAVAILABLE`; sessiz kısıtsız geçiş asla yasal değildir.
- **Onay akışı:** `tools/pre-execute` waterfall → monotonik guard'lar → `ctx.approval` (cevaplanamazsa deny) → `tools/execute` (timeout/retry/metrics) → tool gövdesi → `tools/post-execute` → `tools/result` (donmuş otoriter sonuç).
- **StuHub DS pratiği:** workspace dışına yazma gerektiren bir komut sandbox'tan reddedilirse `[sandbox: file access denied ...]` gelir — bu politika reddidir, komutu başka yoldan tekrarlama. Yalnızca gerçek bir reddin ardından, AYNI komutu bir kez daha geniş modla (`sandbox_permissions`) + gerekçeyle talep edebilirsin. Windows'ta adlandırılmış pipe üzerinden çıktı yakalama (EPERM) belgelenmiş sınırdır; `stdio: inherit/ignore` ile çalışan işlemler etkilenmez.

## 5. ORKESTRASYON REHBERİ (hangi araç ne zaman)

| Durum | Kullanılacak araç |
|-------|-------------------|
| 1–2 bağımsız, sınırlı görev | `subagent` / `subagent_fork` (arka planda, aynı mesajda birlikte) |
| Çok parçalı fan-out (10+ parça, fazlar, yapılandırılmış sonuçlar) | `workflow` (script ile orchestration) |
| Aynı session'da günler süren teslimat hedefi | `create_goal` + goal turları (Ana Ajan) |
| Kullanıcı "Ralph/fresh-agent döngüsü" isterse | `ralph` (her tur taze context, workspace bellek) |
| Uzun kabuk komutu (build, dev server, test) | `bash`/`pwsh` + `run_in_background` → `job_output`/`job_kill` |
| Çok adımlı iş planını kullanıcıya sunma | plan modu + `exit_plan_mode` |
| İlerleme takibi gereken çok adımlı iş | `todo_write` (tam liste her çağrıda) |
| Eksik bilgi/onay/kritik seçim | `ask_user_question` |

**Alt ajan kuralları (Ana Ajan için bağlayıcı):**
1. Delegasyon prompt'u kendi kendine yetmeli: hedef `AJANLAR/` dosyası + ilgili `YETENEKLER/` dosyaları + bitirme kriteri + bu kataloğun ilgili bölümü.
2. Bağımsız delegasyonlar tek mesajda birlikte başlatılır; sonucu bir sonraki adımı belirleyen görevlerde `run_in_background: false`.
3. Arka plan işin bitişi bildirimle gelir; `list_agents`/`job_list` anket için değil hatırlama içindir. Final cevaptan önce ilgili tüm işler `job_output` ile toplanır.
4. Workflow script'lerinde kötü hook kullanımı (fatal) tüm run'ı öldürür — hook sözleşmelerine birebir uyulur.
5. Goal: yalnızca doğrudan insan isteğiyle oluşturulur; resume/fork sonrası disarm edilmiş goal `update_goal` action: resume ile yeniden silahlanır; `complete` yalnızca hedef gerçekten bittiğinde, `blocked` aynı koşul en az 3 ardışık tur sürdüyse.

**Sınırlar ve tuzaklar:**
- **Alt ajan kullanıcıya soru soramaz** (`ask_user_question` yalnız canlı kök ajanda); eksik bilgi/karar ihtiyacı raporla Ana Ajan'a iletilir.
- **Dosya IO'da timeout yoktur** (`read`/`write`/`edit` iptal edilemez); timeout yalnız süreç destekli araçlarda (bash/pwsh/web/subprocess/glob/grep) anlamlıdır.
- Tool argümanları pipeline'da rewrite edilemez — yalnızca allow/deny/ask kararı verilir; sonuç `tools/result` ile donar.
- `run_code`/Code Mode: araçlar `await tools.<ad>(args)` olarak erişilir; hatalar `ToolCallError`'a çözülür; sub-call'lar parent token taşır.
- Session log append-only'dur: modele giren her şey loglanabilir olmalı ("model-visible ⟺ logged"); chunk'lar filtrelenemez (canonical log).
- Onay akışı fail-closed'dur: tek geçit `allowed-once`; cevaplanamayan onay isteği reddedilir.

## 6. KONFİGÜRASYON & VERİ

- **Harness evi (`$DSH_HOME`):** kullanıcı ayarları, credential'lar ve profiller burada yaşar.
- **`settings.yaml`** — kullanıcı ayarları (provider/model rotaları, `defaultInput` vb.); **`.credentials.yaml`** — API anahtarları (write-only; UI yalnızca redacted tanımlayıcı gösterir).
- **Profiller:** `$DSH_HOME/profiles/<ad>/` — `dsh.profile.bundles` (sıralı bundle listesi) + kullanıcıya ait `cordis.patch.yml`. Katman sırası: bundle'lar (sırayla) → profil patch → ev patch → `--patch` overlay'leri. Sonraki katman satır başına kazanır; patch bir satırın config'ini derin birleştirme yapmadan TÜMDEN değiştirir.
- **Config teftişi:** `dsh --profile web --dump-config` (boot etmeden kompozisyon ağacını basar).
- **Session verisi:** append-only event log (JSONL veya SQLite backend), projection cache, SQLite FTS (session arama), OTEL telemetri — hepsi plugin ile değiştirilebilir backend'lerdir.
- **Model yapılandırması:** Settings → Models (DeepSeek kartı, katalog provider'lar, custom provider — kalıcı Provider ID, `GET /models` ile model keşfi); model değişimi restart istemez, sonraki istekte geçerli olur.

## 7. EKLENTİ GELİŞTİRME (StuHub DS gerektiğinde)

DSH'i genişletmenin üç seviyesi (detay: rapordaki cookbook bölümleri):
1. **Araç ekleme:** `ctx.tools.register(defineTool({...}))` — `parameters` (JSON Schema), tek kanonik `output.schema` değeri, `output.render`, `execute(args)`; args modelden önce doğrulanır; altyapı hatası throw → `isError`.
2. **LLM adapter:** `ctx.llm.registerAdapter(providers, adapter)` — `stream(options): AsyncIterable<StreamChunk>`; chunk sırası `block-start → text-delta*/tool-call-delta* → block-end → usage → finish`; hatalar throw (`LlmError`+kod) veya `finish{kind:'error'}`; `options.signal` her HTTP çağrısına geçirilir.
3. **Plugin/bundle yayını:** bundle = `dsh.bundle.patch` manifestli npm paketi; profil = kullanıcının boot ettiği kompozisyon; `dsh plugin --profile <ad> add/remove <pkg>`.

**StuHub DS sınırı:** Ürün kodumuz (FastAPI/React) DSH plugin'i DEĞİLDİR; DSH yalnızca geliştirme/orkestrasyon katmanıdır. DSH uzantısı ancak Ana Ajan'ın açık kararıyla (ör. özel bir kalite kapısı tool'u) gündeme gelir ve Ücretsizlik Ajanı onayından geçer (DSH MIT'dir — ücretsizlik sözleşmesine uygundur).

## 8. STUHUB DS EŞLEMESİ

| StuHub DS bileşeni | DSH karşılığı / kullanımı |
|--------------------|---------------------------|
| Ana Ajan (orchestrator) | `subagent`/`workflow` delegasyonu, `create_goal`+goal turları, `todo_write`, plan modu |
| Effort kuralı (V4 Pro sabit / Flash + yükseltme) | Workflow faz bazında `provider`/`model` override'ı (`phases[].provider/model`, `agent()` opts); tekil subagent varsayılan seviyede (Flash) çalışır, yükseltme workflow veya Settings→Models rotasıyla yapılır — prompt metni çalışma modelini değiştirmez |
| Kalite kapısı | `pwsh` (pytest/vitest/lint/audit) + `report` kanıtları; `exit_plan_mode` onay akışı |
| Indexer (arka plan işleri) | `bash`/`pwsh` + `run_in_background` + `job_*` araçları |
| Ücretsizlik Ajanı denetimi | `web_search` + `read`/`grep` (bağımlılık taraması) |
| Session yaşam döngüsü (yol haritası 4.5) | Goal turları + checkpoint'te session log + `PROJE_YOL_HARITASI.md` güncellemesi |
| Kullanıcı onayı gerektiren kararlar | `ask_user_question`; sandbox genişletme yalnız gerçek reddin ardından |

**Bağlayıcı kurallar (özet):**
- Session başında okuma sırası: `PROJE_YOL_HARITASI.md` → bu dosya → durum tespiti. Bu sıra bozulmaz.
- Modelin gördüğü her bilgi loglanabilir olmalı; "model-visible ⟺ logged" ilkesi prompt tasarımında gözetilir (uzun context'ler session log ve compaction'a tabidir).
- Sandbox politikası ihlali komut hatası değildir; tekrarlanmaz, yalnızca tek seferlik, dar kapsamlı ve gerekçeli genişletme talep edilir.
- DSH developer preview olduğundan, davranışta şüphede `C:\Users\kerew\deepseek-harness\docs\` canlı referanstır.
