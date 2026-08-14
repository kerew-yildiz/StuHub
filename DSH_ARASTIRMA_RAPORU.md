# DEEPSEEK HARNESS (DSH) — KAPSAMLI ARAŞTIRMA RAPORU

> **Meta:** Bu rapor, yerel DeepSeek Harness (DSH) checkout'unun (developer preview, paket sürümü `0.1.0-rc.5`) sistematik kazısıyla üretilmiştir. Yöntem: çekirdek dokümanlar, alt sistem dokümanları, paket README/package.json'ları, cookbook'lar ve kullanıcı rehberleri ilk elden + paralel araştırma ajanlarıyla tarandı; ayrıca web'deki güncel haber/kaynaklar doğrulandı. Amaç: harness'ın ne olduğu, içindeki her bileşenin ne işe yaradığı, nasıl kullanıldığı ve neler yapabildiği. Bu raporun ajan-prompt karşılığı `SİSTEM_YETENEKLERİ.md` dosyasındadır; ikisi birlikte StuHub DS belkemiği dokümanlarına bağlanmıştır.

---

## 1. YÖNETİCİ ÖZETİ

**DeepSeek Harness (`dsh`)**, DeepSeek AI'ın geliştirdiği, **"her şey plugin'dir" (everything is a plugin)** ilkesine dayanan açık kaynak (MIT) **ajan harness'ıdır**. Cordis plugin framework'ü üzerinde kuruludur; model adaptöründen araç kayıt defterine, session logundan onay politikasına ve ajan döngüsünün kendisine kadar her şey değiştirilebilir bir plugin'dir.

**Ne yapabilir (özet):**
- Ajanları **Web GUI** (`dsh web`, varsayılan `http://127.0.0.1:3080`) üzerinden çalıştırır: workspace seçimi, model/provider yönetimi, session'lar, onay akışları, plan modu, goal takibi, arka plan iş listesi, skill'ler, terminal'ler.
- **Headless** modda (`dsh --profile headless "<görev>"`) tek görev çalıştırıp sonucu basar.
- **Python SDK + JSON-RPC/ACP** ile programatik ajan çalıştırma sunar.
- Ajanlara **44 model-facing araç** verir: dosya sistemi (read/write/edit/glob/grep/read_image), kabuk (bash/pwsh/terminal), delegasyon ve orkestrasyon (subagent/subagent_fork/workflow/ralph/goal/jobs/schedule/todo/plan), web (search/fetch), session sorgulama, LSP, skill yükleme ve **kendi çalışma zamanını düzenleme** (cordis_* araçları).
- **Çoklu LLM sağlayıcı** destekler: DeepSeek (native adaptör), pi-ai üzerinden OpenAI uyumlu özel uçlar, Anthropic, Bedrock/Vertex/Azure/Codex; model değişimi restart gerektirmez.
- **Sandbox** ile dosya-etki izolasyonu (read-only / workspace-write / danger-full-access; Linux bwrap+Landlock, macOS Seatbelt, Windows ACL).
- **Eklenti ekosistemi**: npm (`@deepseek-ai/dsh-*`) üzerinden tool/LLM adaptörü/bundle yayınlanır; `dsh plugin` ile profillere kurulur.

**Durum:** *Developer preview* — hızla değişiyor, uyumluluk kırıcı değişiklikler taahhüt ediliyor. Ağustos 2026 itibarıyla kamuya açık beta ("对标 Claude Code/Claude Cowork" — ithome haberleri) ve npm'de yayında.

**StuHub DS için anlamı:** DSH, StuHub DS'in ürün kodu değil **geliştirme/orkestrasyon katmanıdır**. Ürünün 15 ajanı DSH üzerinde çalışır; Ana Ajan'ın subagent/workflow/goal orkestrasyonu, paralellik ve kalite kapısı pratikleri DSH yeteneklerine dayanır.

---

## 2. DIŞ DÜNYA VE KURULUM

### 2.1 Topluluk ve yayın durumu
- Repo: [github.com/deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness); lisans MIT; üçüncü taraf bildirimleri `THIRD_PARTY_NOTICES.md`.
- Geri bildirim: GitHub Discussions; eklenti keşfi için `dsh-plugin` GitHub topic'i; Discord topluluğu.
- Basın/uygulama testleri: "DeepSeek Harness 公测" (public beta) — [ithome haberi](https://www.ithome.com/0/989/446.htm), [zhidx incelemesi](https://www.zhidx.com/p/584897.html). Claude Code/Claude Cowork ile kıyaslanıyor; npm üzerinde eklenti ekosistemi açılmış durumda ([@why913/dshx](https://www.npmjs.com/package/@why913/dshx) gibi topluluk paketleri mevcut).

### 2.2 Kurulum ve çalıştırma

```sh
# npm üzerinden (Node.js gerekli):
npx @deepseek-ai/dsh web          # Web UI → http://127.0.0.1:3080

# Kaynaktan (repo checkout'u):
git clone https://github.com/deepseek-ai/deepseek-harness.git
cd deepseek-harness
pnpm install && pnpm run build
pnpm dsh web                       # kaynak çalıştırma (tsx/esm hook'u)
```

Önkoşullar: **Node.js 22.19+ / 24+**, pnpm (repo 11.7.0 pin'ler, corepack ile). Gerçek API testleri/demolar `DEEPSEEK_API_KEY` (+ opsiyonel `DEEPSEEK_BASE_URL`) ister; anahtar yoksa keyless testler kendi kendini atlar.

### 2.3 `dsh` CLI — giriş modları ve profiller

| Komut | Amaç |
|---|---|
| `dsh --profile <ad>` | Adlandırılmış profili boot eder (`$DSH_HOME/profiles/<ad>`) |
| `dsh --profile headless "görev"` | Tek taze session çalıştırır, final cevabı basar, çıkar |
| `dsh web` | `--profile web` kısa yolu |
| `dsh plugin --profile <ad> <pnpm args>` | Profilin plugin'lerini pnpm'e yönlendirerek yönetir |

- **Profil** = `package.json` (dış plugin bağımlılıkları + `dsh.profile.bundles` sıralı listesi) + kullanıcıya ait `cordis.patch.yml`. `web` ve `headless` şablonlardan ilk kullanımda otomatik kurulur.
- **Katman sırası:** boş kök → bundle'lar (listelenen sırada) → profil patch → `$DSH_HOME/cordis.patch.yml` → `--patch` overlay'leri. Sonraki katman satır başına kazanır; patch bir satırın config'ini **tümden** değiştirir (deep-merge yok).
- Teşhis: `dsh --profile web --dump-config` (boot etmeden kompozisyon ağacını basar), `--dump-default-config`.
- Launcher yalnız kendi bayraklarını ayrıştırır; ilk tanımadığı token'dan itibaren her şey profilin uygulamasına gider (örn. `dsh --profile web --port 8080`).

### 2.4 Geliştirme komutları (repo)

```sh
pnpm install            # workspace + lefthook + merge driver
pnpm run build          # tsc host → tsdown host → tsc client → tsdown client → build:web
pnpm run test           # vitest unit
pnpm run test:coverage  # CI kapısı: packages/*/*/src başına %100 satır
pnpm run test:e2e       # gerçek API testleri (anahtar yoksa kendi kendini atlar)
pnpm run test:snapshot  # keyless ACP/headless replay
pnpm run typecheck / lint / duplication / hygiene / doc-sync
pnpm run check:windows-wine  # yalnız bilinen Windows arızası tanısında (wine ister)
pnpm dsh --profile headless "task"   # tek görev (anahtar gerekli)
pnpm run demo:cordis / demo:acp      # öz-düzenleme ve ACP demoları
```

---

## 3. MİMARİ

### 3.1 Cordis — beş fikir

Cordis, DSH'in altındaki (vendored) plugin framework'üdür (`@deepseek-ai/cordis`, `@deepseek-ai/cosmokit`, `@deepseek-ai/schemastery` vendored ve re-scope edilmiştir — bkz. `docs/rescope.md`):

1. **Plugin, Service'i gerçekleyen nesnedir** — opsiyonel `inject` + `apply(ctx)` alanlı fonksiyon, nesne veya `Service` alt sınıfı.
2. **Context bir servis deposudur** — servisler `ctx.<key>` (örn. `ctx.tools`, `ctx.llm`, `ctx.sessions`) anahtarını sahiplenir; tüketiciler somut implementasyonu import etmez.
3. **Bağımlılık `inject` ile bildirilir** — yüklenme sırası dosya sırasından değil servis gereksinimlerinden gelir; eksik servis varsa plugin `PENDING` durumunda bekler (meşru).
4. **Tip güvenli event'ler** — declaration-merging ile bildirilir; dispatch moduna göre `emit` / `waterfall` / `parallel` / `serial` ile yayınlanır.
5. **Kayıtlar geri alınabilir effect'lerdir** — `ctx.effect()` / `ctx.on()`; reload/HMR/teardown ters sırada, sızıntısız çözer.

**Dispatch modları:** `emit` (gözlem, sıralı, beklenmez, dönüş yok) · `waterfall` (around-middleware: listener `next()` çağırmazsa kısa devre/veto; değer `next()` dönüşüyle yayılır) · `parallel` (hepsi paralel, beklenir) · `serial` (sıralı, beklenir, dönüş var). Mod, event'in kamusal sözleşmesinin parçasıdır (`@mode` etiketiyle belgelenir).

**Plugin yaşam döngüsü (fiber):** `PENDING → LOADING → ACTIVE → UNLOADING → DISPOSED` (hata: `FAILED`, yüksek sesle). `ctx.plugin(child)` alt fiber üretir; `fiber.dispose()` kayıtları kaldırır, altları recursive unload eder, async temizlik bitince resolve eder. Config değişimi HMR ile hot-replace olur.

### 3.2 Profiller, bundle'lar ve katmanlar

- **Bundle** — Cordis config satırları + kodu dağıtan npm paketi; manifest: `package.json` içinde `"dsh": { "bundle": { "patch": "./cordis.patch.yml" } }`.
- **Profil** — Harness evinde saklanan adlandırılmış kompozisyon; `dsh.profile.bundles` listesi + kullanıcı patch'i.
- **Yerleşik bundle'lar:** `@deepseek-ai/dsh-base` (her profilin ilk katmanı: model adaptörleri, araçlar, persistence, sandbox, onay, ayarlar, credential'lar, telemetri), `dsh-web-app` (tarayıcı uygulaması), `dsh-headless` (sunucusuz tek seferlik runner).
- Kurulumdan çözülürler; dış bundle'lar `dsh plugin --profile <ad> add <pkg>` ile gelir (GitHub'dan kurulumda build scripti çalışmadığı için `prepare` scripti + pnpm `allowBuilds` izni gerekir).

### 3.3 Çekirdek paketler ve `ctx` anahtarları

| Paket | Sahibi olduğu şey | ctx anahtarı |
|---|---|---|
| `core/session` | Append-only `SessionEvent` log + bellek-içi store | `ctx.sessions` |
| `core/system-prompt` | Prompt bölümü + tool-schema derleme | `ctx.systemPrompt` |
| `core/tools` | Scoped tool registry + korumalı çalıştırma hattı | `ctx.tools` |
| `core/agent` | `Agent` arayüzü, canlı registry, `agent/*` event'leri | `ctx.agents` |
| `core/agent-loop` | Varsayılan sürücü (değiştirilebilir) | `ctx.agentLoop` |
| `core/scope` | Ajan-bazlı scoped-kayıt ilkeli | (kütüphane) |
| `llm/llm` | Mesaj/stream sözlüğü + adaptör seam'i | `ctx.llm` |

### 3.4 Event alanları

- **Session event'leri** — kalıcı gerçekler, loga eklenir, `session/event` ile yayınlanır. (Reload sonrası yaşaması gereken her şey.)
- **Agent event'leri** (`agent/*`) — canlı `Agent` taşır: inbox, step, status, request, validation, continuation. (Uçuş halindeki işi gözlemle/kes.)
- **Capability event'leri** (`fs/*`, `tools/*`, `telemetry/*`) — policy/adaptör'ü seam'e bağlar.
- Üretici/tüketici matrisi: `docs/event-producer-consumer.md` (generated).

### 3.5 Turn/step akışı

**Step** = 1 model isteği + tetiklediği araç çağrıları. **Turn** = kabul edilmiş girdinin bir turu (0+ step).

```
turn/start → girdi claim → agent/pre-step (waterfall: reject | enter) → step/start
→ user/message → agent/request → llm/stream → assistant/chunk* → assistant/message
→ tool/call* → tools/pre-execute → tools/execute → tools/post-execute → tool/result*
→ step/end → (yeni girdi varsa sonraki step) → agent/turn-stopping → turn/end
```

`turn/*`, `step/*`, `user/message`, `assistant/*`, `tool/*` **kalıcı** event'tir; `agent/pre-step`, `agent/request`, `llm/stream`, üç `tools/*` event'i **waterfall**'dır; `agent/turn-stopping` **serial**'dir. İptal/hata kurtarma: `agent/request-error` waterfall'ı retry aksiyonu döndürebilir.

### 3.6 Session log ve "model-visible ⟺ logged"

Session log, modelin gördüğü bağlamın **kaynağıdır**: `deriveMessages()` model geçmişini logdan türetir; `assistant/chunk` ham kayıtları replay ve UI doğruluğunu korur. Fork, resume, transcript, telemetri, persistence hep bu akıştan türer. **Runtime invariant:** modele giren her şey logdan yeniden kurulabilir olmalıdır — yeni model-visible girdi = yeni session event = `SessionEventMap` genişletme.

**Event zarfı:** `{ type, seq (monotonic), time (epoch ms), data, ignorable? }`; surface tipleri ayrıca `sourceEventSeqs`/`surfaceOp` taşır. **Surface** = LLM mesajı üreten (`user/message`, `assistant/message`, `tool/result`); **log-only** = kalıcı ama derived history'ye katkısız. `SESSION_FORMAT_VERSION = 0` (pre-release, uyumluluk garantisi yok). `ignorable: true` bilinmeyen tipi güvenle atlatır; aksi halde okuyucu oturumu reddeder.

### 3.7 Capability seam'leri

**Seam** = 3 rollü değiştirilebilir yetenek: **Service Definition** (arayüz, `ctx.<key>` sahibi) + **Service Provider** (implementasyon) + **Consumer** (çoğu model-facing araç). Tek rol seam değildir. Kanonik örnek `packages/shell`: `dsh-shell` (SD) / `dsh-bash-local`, `dsh-bash-sandbox` (provider) / `dsh-tool-bash` (consumer). Seam'ler sayesinde tek provider değişimi tüm ürünü taşır: fs ve subprocess aynı execution world'ünü paylaştığından uzak sandbox'a işaret etmek Bash + PTY + LSP'yi birlikte taşır.

Tam seam listesi: `ctx.attachments, ctx.llm, ctx.sessionPersistence, ctx.settings, ctx.credentials, ctx.sessionTelemetry, ctx.storage, ctx.sessionQuery, ctx.sessionTitle, ctx.skills, ctx.subprocess, ctx.shell, ctx.terminals, ctx.sandbox, ctx.approval, ctx.codeRuntime, ctx.fs, ctx.compaction, ctx.subagents, ctx.jobs, ctx.web, ctx.spillStore, ctx.directoryPicker, ctx.workflowEngine, ctx.lsp`.

### 3.8 Scope ve lineage (ajan-bazlı kayıt)

- Kayıt **global** ya da tek ajana **scoped**'dur; iki seviye, düz — subagent'lara miras YOK.
- **Shadowing:** scoped kayıt aynı adlı global ikizini o scope için gölgeler (ajan-başına persona/tool varyantı mekanizması).
- **Restriction:** `tools.restrict` global seti bir scope için filtreler (kesişim); filtrelenen tool prompt'ta da yoktur, çalışmayı da reddeder.
- **Setup window:** `CreateAgentOptions.setup` — ajan/session publish olmadan önceki kompozisyon penceresi.
- **Lineage:** parent/child gerçekleri veri olarak taşınır (`parentSession`, `delegationDepth`, `subagentDepth`) — görünürlüğü etkilemez.

### 3.9 Terminoloji (glossary'den seçmeler)

**turn / step / round** (round = goal round veya Ralph attempt gibi dış politika iterasyonu) · **goal** (`active/paused/blocked/complete`, goal-round cap; aktivasyon `armed/disarmed` — resume/fork sonrası insan onaylı resume gerekir) · **human command** (slash komutu, `ctx.commands`, model mesajı değil; `/goal` komutu) · **Ralph loop** (immutable hedefe foreground fresh-agent turları; her tur taze child session — parent/önceki tur seed'i yok; cross-round durum workspace + Ralph handoff ile taşınır).

### 3.10 "Yeni davranış nereye gider" (extension haritası)

| Hedef | Mekanizma |
|---|---|
| Yeni model sağlayıcı | `ctx.llm`'e adapter kaydet |
| Yeni model-facing yetenek | `ctx.tools`'a kaydet (şema prompt derlemesine katılır) |
| Tek session'a farklı yetenek seti | Agent preset (+ servis satırına `isolate` realm) |
| Shell çalıştırma | `ctx.shell` backend'i |
| Kalıcı terminal | `ctx.terminals` backend + `dsh-tool-terminal` |
| İnsan komutu | `ctx.commands` |
| Arka plan iş | `ctx.jobs` + `job_*` araçları |
| Dosya erişimi/politikası | `ctx.fs` provider / `fs/*` event'leri |
| Süreç hapsi | `ctx.sandbox` backend |
| Request/tool/turn yakalama | `agent/*` ve `tools/*` event'leri |
| Modele bağlam ekleme | `agent.inject()` (sonraki isteğe iner) |
| UI/editor entegrasyonu | `ctx.agents` + `session/event` |
| Web Chat node'u | `ConversationNodeDefinition` + keyed renderer |
| Kalıcı session durumu | `SessionEventMap` genişlet |
| Session başlığı | tek `ctx.sessionTitle` provider |
| Aynı-session hedef | `ctx.goals` |
| Canlı session fork | `ctx.sessions.fork(source, boundary?, childSessionId?)` |
| Tek ajana scope | o ajanın `agent.ctx`'i |

---

## 4. ARAÇ KATALOĞU (44 araç — tam envanter)

Katalog `docs/tool-catalog.md` (generated; `pnpm run gen-tool-catalog`) — her araç `name`/`description`/JSON-Schema `parameters` ile listelenir; generator tool plugin'lerini gerçek context'te boot edip `ctx.tools.schemas()` okur.

### 4.1 Dosya sistemi
| Araç | Paket | Parametreler (kritik) |
|---|---|---|
| `read` | dsh-tool-fs | `file_path`, `offset?`(1), `limit?`(2000) |
| `write` | dsh-tool-fs | `file_path`, `content` |
| `edit` | dsh-tool-fs | `file_path`, `old_string`, `new_string`, `replace_all?` |
| `read_image` | dsh-tool-fs | `file_path` (image-capable model + `ctx.attachments` şart) |
| `glob` | dsh-tool-fs-search | `pattern`, `path?` — paketli ripgrep ile |
| `grep` | dsh-tool-fs-search | `pattern`, `path?`, `include?` |
| `str_replace_editor` | dsh-tool-str-replace-editor | `command`(view/create/str_replace/insert), `path`, `old_str?`, `new_str?`, `insert_line?`, `view_range?` |

### 4.2 Kabuk ve terminal
| Araç | Paket | Not |
|---|---|---|
| `bash` | dsh-tool-bash | `command`, `description`, `timeoutMs?`, `workdir?`, `run_in_background?`; her çağrı taze shell |
| `pwsh` | dsh-tool-pwsh | Aynı; Windows'ta `pwsh -Command`, taze süreç |
| `bash` (persistent) | dsh-tool-bash-persistent | State korunur; `command` |
| `terminal_open/send/read/list/close/signal` | dsh-tool-terminal | Owner-izole kalıcı PTY; `signal`: SIGINT/SIGTERM/SIGKILL/SIGTSTP/SIGHUP |

### 4.3 Delegasyon ve orkestrasyon
| Araç | Paket | Not |
|---|---|---|
| `subagent` | dsh-tool-subagent | `description`, `prompt`, `run_in_background?`; continuable, varsayılan arka plan |
| `subagent_fork` | aynı (alias) | Ebeveynin tamamlanmış geçmişinden fork; one-shot, varsayılan foreground |
| `send_message` | dsh-tool-subagent-control | Aynı konuşmaya yeni tur; teslim onayı döner |
| `interrupt_agent` | dsh-tool-subagent-control | Yürüyen turu iptal isteği |
| `list_agents` | dsh-tool-subagent-control | `scope`: children/descendants |
| `report` | dsh-tool-subagent-report | Çocuktan ebeveyne yapılandırılmış rapor |
| `workflow` | dsh-tool-workflow | `script` (plain JS), `meta`{name, description, whenToUse?, phases?}, `args?` |
| `ralph` | dsh-tool-ralph | `objective`, `maxRounds?`; fresh-agent turları |
| `create_goal` / `get_goal` / `update_goal` | dsh-tool-goal | `objective`, `max_goal_rounds?`; update: `goal_id`, `revision`, `action`(edit/pause/resume/complete/blocked) |
| `job_kill` / `job_list` / `job_output` | dsh-tool-jobs | `wait?`, `timeout_ms?` |
| `schedule_create/delete/list` | dsh-schedule | `after_seconds?` / `every_seconds?`(≥300) / `at?`; session-canlanınca devam |
| `todo_write` | dsh-tool-todo | `todos[]` TAM liste; `allowParallelInProgress` zorunlu |
| `exit_plan_mode` | dsh-plan-mode | `plan` (markdown, `#` başlıkla) |
| `ask_user_question` | dsh-tool-ask-user | `questions[]`{id, question, header?, options[], multi_select?} |
| `skill` | dsh-tool-skill | `name` — skill talimatlarını yükler |

### 4.4 Bilgi ve web
| Araç | Paket | Not |
|---|---|---|
| `web_search` | dsh-tool-web | `query`; özet + kaynak URL listesi |
| `web_fetch` | dsh-tool-web | `url`; sınırlar: `fetchTimeoutMs` 30s, `fetchMaxOutputChars` 200000 |
| `session_event_read/search/trace` | dsh-tool-session-query | Log üzerinde event okuma/arama/iz |
| `session_search` / `session_trace` | dsh-tool-session-query | SQLite FTS; lineage izi |
| `lsp` | dsh-tool-lsp | `operation`(goToDefinition/findReferences/goToImplementation/hover), `file_path`, `line`, `character` |

### 4.5 Çalışma zamanı öz-düzenleme (bilinçli opt-in — hiçbir shipped tree'de yok)
| Araç | Ne yapar |
|---|---|
| `cordis_define` / `cordis_undefine` | Immutable Cordis Package tanımlar / kalıcı siler |
| `cordis_run` / `cordis_stop` | Package'ı aktive eder / durdurur (idempotent) |
| `cordis_inspect_list` / `cordis_inspect_query` / `cordis_inspect_self` | Bellekteki Cordis ağacını/servisleri inceler |
| `run_code` | Code Mode: `await tools.<name>(args)` ile TypeScript programı çalıştırır |

---

## 5. CONFIG KATALOĞU (öne çıkanlar)

Tam liste `docs/config-catalog.md` (generated, `pnpm run gen-config-catalog`). Önemli anahtarlar ve varsayılanlar:

| Plugin | Anahtar (varsayılan) | Ne işe yarar |
|---|---|---|
| `dsh-agent-loop` | `agents[]` (id, sessionId?, cwd?, resumeSessionId?); `maxParallelToolCalls?` | Hangi ajanlar hangi modelle koşar |
| `dsh-agent-instructions` | `maxBytes` (zorunlu); `projectRootMarkers?` | Workspace talimatları (AGENTS.md vb.) bağlamı |
| `dsh-sandbox-policy` | `mode` (**read-only**); `workspaceRoot?` | Varsayılan dosya-etki politikası |
| `dsh-permission-presets` | `presets?` (workspace-write + danger-full-access); `defaultPreset?` | Onay/sandbox ön ayarları |
| `dsh-user-approval` | `policy` ('ask'\|'never', default ask) | Onay akışı açık/kapalı |
| `dsh-compaction-basic` | `auto` (true); `thresholdRatio` (0.8); `retainRatio` (0.16); `maxTokens` (8192) | Context basıncında otomatik özetleme |
| `dsh-llm-deepseek` | `apiKeyEnv` (DEEPSEEK_API_KEY); `reasoningEffort` (high); `maxTokens` (256000); `defaultContextWindow` (1000000) | DeepSeek adaptörü |
| `dsh-llm-pi-ai` | `providers?` (route→profil: apiKeyEnv/baseURL/models/modelOverrides/defaultInput/…) | OpenAI uyumlu çok-sağlayıcı adaptör |
| `dsh-session-persistence-jsonl/sqlite` | `root` / `path`; `compression` (zstd); `journalMode` (wal) | Session persistence backend'i |
| `dsh-session-query-sqlite` | `path`; `defaultLimit` (20); `maxLimit` (100) | FTS arama |
| `dsh-storage-domain` | `backend`, `routes?` | Domain-öncelikli KV deposu |
| `dsh-session-telemetry-otel` | `mode` (DISABLED); `exporter.url` | OTLP telemetri (FULL/FEEDBACK_ONLY/DISABLED) |
| `dsh-tool-subagent` | `provider`; `backgroundMode` ('one-shot'/'continuable'); `maxDepth` (3/'provider-managed'); `toolFilter?` | Delegasyon tool'u politikası |
| `dsh-workflow-worker-thread` | `maxConcurrentAgents` (cores-2, 16 cap); `maxTotalAgents` (1000) | Workflow motoru sınırları |
| `dsh-tool-ralph` | `maxRounds` (256); `maxHandoffChars` (16384) | Ralph sınırları |
| `dsh-jobs-local` | `maxConcurrentJobsPerOwner` (10) | Arka plan iş sınırı |
| `dsh-tool-jobs` | `waitTimeoutMs` (30s); `maxWaitTimeoutMs` (10dk); `completionDelivery` (wakeup) | Job bekleme politikası |
| `dsh-tool-todo` | `allowParallelInProgress` (ZORUNLU, varsayılan yok) | Paralel in-progress izni |
| `dsh-tools` | `mode` ('native'/'code'/'both', default native); `maxParallelSubCalls` (10) | Code Mode taşıma |
| `dsh-host-webserver` | `host` (127.0.0.1); `port` (0 = OS atar) | Web sunucusu |
| `dsh-tool-fs-search` | `globMaxResults?`, `grepMaxMatches?` | Keşif araç sınırları |
| `dsh-spill-policy` | `maxInlineBytes?` | Tool sonuç spill politikası |
| `dsh-web-search-deepseek` | `model` (deepseek-v4-flash); `maxUses` (5) | DeepSeek native arama |
| `dsh-mcp-client` | `serverName` (regex [A-Za-z0-9_-]{1,32}); `toolCallTimeoutMs`; stdio/http config | MCP sunucu entegrasyonu |
| `dsh-tool-call-timeout-policy` | per-call deadline'lar | Tool deadline enforcer |
| `dsh-repeat-tool-reminder` | `thresholds` ([3,5,8]) | Tekrar eden çağrı hatırlatması |

Kategoriler: "Loadable plugins with no config" (dsh-agent, dsh-session, dsh-tool-ask-user, dsh-schedule, dsh-goal-round-driver…) · "Seam packages" (abstract, doğrudan yüklenmez: attachment, code-runtime, compaction, credentials, fs, jobs, sandbox, session-persistence, settings, shell, spill, subprocess, workflow…) · "Library packages" (dsh-base, dsh-scope, dsh-sdk-protocol, dsh-typert-*…).

---

## 6. PERSISTENCE (event kataloğu + depolama katmanları)

### 6.1 Kalıcı event envanteri (`docs/persistence-catalog.md`)
Seçmeler: `agent/inbox/*`, `agent-preset/selected`, `approval/asked|decided|policy`, `assistant/chunk`, `assistant/message` (surface), `command/run|done`, `compaction/start|prune|summary|end`, `feedback/record`, `goal/change`, `hook/invoked|result`, `llm/retry*`, `permission/preset`, `plan/mode`, `request/context|header`, `sandbox/mode`, `schedule/change`, `session/end-seed`, `session/title*`, `step/start|end`, `subagent/descriptor`, `todo/write`, `tool/call` (arguments ham JSON string), `tool/result` (surface), `tool/code-dispatch*`, `tool-workflow/*`, `turn/start|end`, `user/message` (surface), `web/deepseek-search-llm-request`.

### 6.2 Depolama katmanları
| Seam | Provider'lar | Not |
|---|---|---|
| `ctx.sessionPersistence` | jsonl (root, zstd, packChunks) / sqlite (path, WAL) | Session event log |
| `ctx.storage` (+ `ctx.storageDomain`) | storage-json / storage-sqlite | Domain-öncelikli KV |
| `ctx.sessionQuery` | session-query-sqlite (FTS) | `SESSION_QUERY_SEARCH_DISABLED` hatası üretebilir |
| `ctx.sessionProjectionCache` | projection cache | turn/end checkpoint'leri |
| `ctx.sessionTelemetry` | session-telemetry-otel (OTLP, DISABLED default) | Gözlemlenebilirlik |
| `ctx.attachments` | attachment-local | Görüntü sınırları (maxImageBytes/Pixels…) |

---

## 7. ALT SİSTEMLER (subsystems — tam envanter)

Her subsystem'ın davranış dokümanı `docs/subsystems/*.md` içindedir (sayfa altlarında üretilmiş `cordis-surface` API bölümü). Gruplu tam envanter:

### 7.1 Session / Persistence
- **session** (`ctx.sessions`) — Append-only `SessionEvent` logu tek doğruluk kaynağı; LLM geçmişi `deriveMessages()` ile türetilir. `seq` bitişik olmalı; `append()` JSON-serializability'yi kaynakta doğrular (BigInt/function/circular/Map/Set/Date reddedilir). Yüzey event'leri (`user/message`, `assistant/message`, `tool/result`) `SurfaceIntent` ile girer; `SurfaceOp: 'append' | {op:'replace', start, end}` (compaction). Boş içerikli `assistant/message` derived history'den düşer ama logda kalır. `TurnEndReasonMap`: completed|aborted|blocked|error|max-tokens|interrupted (bir turn'de herhangi bir max-tokens adım → tüm turn max-tokens; interrupted yalnız crash-recovery sentezi). `fork(source, boundary?, childSessionId?)`: prefix açık turn içinde biterse reddedilir.
- **persistence** (`ctx.sessionPersistence`) — Flush: `session/event` senkron; batch penceresi + `session/flush`. Crash recovery: açık turn truncate EDİLMEZ, sentetik `turn/end {interrupted}` eklenir; yalnız soğuk session'lar onarılır. Backend'ler: JSONL (checksum'lı Zstandard frame, atomik) / SQLite (event başına 1 satır). `SessionHeader` (log dışı): version, id, createdAt, cwd?, parentSession?, seedLength?, origin?:'subagent', delegationDepth?, agentPreset?. Format hataları: `SessionFormatUnsupportedError` vs `SessionPersistenceCorruptionError`; tanınmayan gerekli event (`ignorable:true` yoksa) reddedilir.
- **session-projection** (`ctx.sessionProjections`) — Log-türetimli state'in tam değer sunumu; `init/apply/view` senkron + plain JSON; `apply` değişmeyen event'te AYNI referansı döndürmeli. `checkpoint/restore`; cache `turn/end` + disposal'da.
- **session-query** (`ctx.sessionQuery`) — Canlı-tercihli logical corpus; `searchSessions/searchEvents/readEvent/traceSession/traceEvent/...`; filtreler AND'li (liste içi OR); SQLite FTS + opak cursor. 17 kapalı hata kodu.
- **session-reference** (`ctx.sessionReferenceResolver`) — Çapraz-session referans: `listCandidates` (cwd affinity, self hariç), `prepare` (en fazla 1 aggregate context). Hata: SELF_REFERENCE, TOO_MANY, BUDGET_EXCEEDED…
- **session-telemetry** (`ctx.sessionTelemetry`) — Outbound raporlama (ledger/ops); yalnız ilk `assistant/chunk` gönderilir; best-effort; redaction waterfall fail-closed (canonical log asla değişmez). OTEL provider: FULL/FEEDBACK_ONLY/DISABLED.
- **session-title** (`ctx.sessionTitle`) — Tek provider; `session/title` log-only; `user` kaynağı pin'ler (otomatik üretim durur).
- **feedback** (`ctx.messageFeedback`) — Mesaj-başı rating/not (sidecar domain, session-log değil); optimistic concurrency (`ifVersion`); hedef yalnız append-origin boş olmayan `assistant/message`; `maxNoteBytes` (Web Host 8192).
- **storage** (`ctx.storage` + `ctx.storageDomain`) — Session-event dışı her şey; backend'ler json/sqlite; `Domain.open(spec)` strict sıra; yazma zinciri backend durability → memory → `domain/changed`; `update(key, fn)` atomik RMW.
- **token-meter** (`ctx.tokenMeter`) — Servis-geneli estimator + session başına izole fold; baseline `usage` (kanonik envelope eşleşirse) | `estimated`.

### 7.2 Orkestrasyon
- **core** — Omurga: session, system-prompt, tools, agent, agent-loop, scope. `AgentHandle {agent, dispose}` yalnız oluşturana; `Agent` yüzeyi: `cancel(cause,{keepInbox?})`, `whenIdle()`, `runMaintenance`, `send/followup/steer/inject`; inbox `next-turn|next-step` iki sıralı liste. Interception: `agent/pre-step` (waterfall; reject|enter), `agent/request` (waterfall), `agent/request-error` (waterfall; retry), `agent/turn-stopping` (serial), `agent/session-start` (startup|resume|clear|compact). Tip desenleri: `…Map → derived-union` + branded ID'ler.
- **llm-streaming** (`ctx.llm`) — `ContentBlockMap`: text, reasoning, image, tool-call, tool-result. `StreamChunk` kapalı union: block-start, text-delta, reasoning-delta, tool-call-delta, block-end, usage, finish. Adapter MUST'ları: usage finish'ten önce; tool args uçtan uca raw JSON string; **bir adapter çağrısı = bir provider denemesi**; `streamIdleTimeoutMs` 5dk; context overflow tek kodu `CONTEXT_WINDOW_EXCEEDED`; boş completion `EMPTY_RESPONSE` (retryable); her HTTP isteği `attributionHeaders()`. `TokenUsage` cache alanları ayrık (input + cacheRead + cacheWrite).
- **scope** — Kütüphane primitifi; `ScopeKey` opak; loop canlı `Agent`'ı anahtar yapar; `Scoped<T>` routing-only marka.
- **goal** (`ctx.goals`) — Event-sourced same-session hedef; her mutasyon kalıcı `goal/change`; `GoalPhase`: active|paused|blocked|complete; `GoalBlockReason{code,message}`; devam round'ları yalnız kabul edilen `user/message` ile `roundsStarted` artırır (replay non-positive/gap/stale/stopped/cap-overflow reddeder); `disarm` durable phase'i değiştirmez; aktivasyon process-local.
- **schedule** — Session-local hatırlatıcı; teslim `followup()` ile normal turn (at-least-once); `every_seconds ≥ 300`; `at` offset'li RFC3339 veya `{date,time,time_zone}`; DST boşluğu/offset'siz reddedilir; due iş agent idle olunca claim edilir (asla `steer()` etmez); cold session iş yapmaz.
- **commands** (`ctx.commands`) — İnsan slash-komut registry'si; `command/run|done` log-only (turn sarmaz); syntax/bilinmeyen isim hiç log yazmaz.
- **compaction** (`ctx.compaction`) — Tetikleyiciler: `pressure` (agent/pre-step) ve `context-overflow` (agent/request-error); özet ayrı `user/message` + `surfaceOp:{op:'replace',start,end}`; lock tüm operasyonu çevreler; `compactNow()` turn arası; `ctx.toolResultPruner` model-free pruning (Unicode code-point dilimleme).
- **subagent** (`ctx.subagents`) — İsimli provider registry (birden çok bir arada): spawn, fork, acp, codex, claude-code, dsh-sdk. `SubagentCapabilities {outputSchema, depthLimit, toolFilter, persona}`; eksik yetenek `UNSUPPORTED_CAPABILITY`. Continuable çocuk: durable child Session + en fazla bir process-local Activation (`running|waiting|settled`); `interrupt` = `Agent.cancel(cause,{keepInbox:true})`, fire-and-return; yetki `user`(parentSessionId) veya `ancestor`(canlı Agent); derinlik durable `SessionHeader.delegationDepth`.
- **workflow** (`ctx.workflowEngine`) — Model-yazımlı orkestrasyon script'i; tek engine; `meta`+`args` plain JSON (script eval edilmeden meta validate); `WorkflowRun.result` asla reject etmez; `dispose()` bounded; `WorkflowError.fatal` hook misuse'de script'i öldürür; `parallel()/pipeline()` fatal'i re-throw eder (per-item null yalnız child-run başarısızlığı); event'ler observe-only snapshot.
- **jobs** (`ctx.jobs`) — `JobId = <kind>-N`; `JobStatus`: running|stopping|completed|killed|failed; `done` "kaynak bırakıldı" demektir (iş bitti değil); `maxConcurrentJobsPerOwner` 10; `kill` → 'requested'|'already-finished'; settlement first-wins.
- **plan** (`ctx.planMode`) — Yumuşak rehberlik (enforcement değil); `plan/mode` log-only; aktifken `plan:policy` prompt bölümü order 50; `exit_plan_mode` + `/plan` komutu; çıkış `#` başlıklı markdown + plan-review intent.
- **typert** (`ctx.typert`/`ctx.typertGateway`/`ctx.remote`) — Uzaktan çağrı tipleri; unary yalnız (`POST /api/<namespace>/<method>`); `@Remote`/`@RemoteScope`; 17 kapalı gateway hata kodu; client `$mount/$on/$dispatch`.

### 7.3 Güvenlik / Sandbox
- **sandbox** (`ctx.sandbox`/`ctx.sandboxPolicy`) — `SandboxMode`: read-only | workspace-write | danger-full-access (yalnız dosya etkileri; ağ/süreç görünürlüğü dışında); `danger-full-access` confinement'ı baypas eder. Enforcement full/partial (eski Landlock ABI, Windows ACL = partial). Öncelik: onaylı explicit mode > son `sandbox/mode` event > deployment default; `workspaceRoot` = session'ın immutable cwd'si. `ConfinedArgv {argv, enforcement, denialSignatures[], runnerFailureRules[]}` — denial (confinement çalıştı) ≠ runner failure (komut hiç çalışmadı). Fail-closed: `SANDBOX_UNAVAILABLE`; sessiz unconfined passthrough yasak. Backend'ler: Linux bwrap/Landlock, macOS Seatbelt, Windows ACL restricted-token.
- **approval** (`ctx.approval`) — Fail-closed; tek geçit `allowed-once`; `ApprovalPolicy` 'ask'|'never' (never → deterministik rejected, waterfall'dan önce uygulanır, prepend bile baypas edemez); `approval/asked|decided` log-only çifti; yalnız açık turn içinde istenebilir; per-session override son `approval/policy` event'inden fold.
- **permission-presets** (`ctx.permissionPresets`) — `sandbox/mode` + `approval/policy` iki knob'unu tek seçiciye paketler (enforcement YOK); varsayılanlar: `workspace-write` (workspace-write+ask), `danger-full-access` (danger-full-access+never); `custom` derived-only.
- **credentials** (`ctx.credentials`) — Config yalnız referans taşır; değerler operasyon başına `resolve()` (restart'sız rotasyon); boş değer her yerde yok; process-env kaynağı `writable:false`; local provider katmanları env/file/project-env/user-env.
- **invariants** (`ctx.invariants`) — Paket-sahipli runtime invariant registry; installer child fiber'de; `fail()` → `InvariantError`; allowlist/blocklist regex; her paket `./invariant` companion taşır.

### 7.4 Araçlar / Yetenekler
- **tools** (`ctx.tools`) — `ToolDefinition`: schema + output{schema, render, presentationMeta?} + execute(args, exec) + finalizeContent? + timeoutMs? + presentCall/presentResult. `defineTool` DSL (16 konteyner seviyesi sonrası JsonValue); `ToolArgsError(INVALID_ARGS)`, `ToolOutputError(INVALID_TOOL_OUTPUT)`. `ToolRestriction{allow?,deny?}` global sete scope filtresi (scoped kayıtlar ve run_code muaf; çoklu kısıtlar kesişir). Pipeline: pre-execute → monotonic guard'lar (yalnız deny) → execute → post-execute → finalizeContent → result. `ToolExecutionMode` parallel|exclusive. Argümanlar rewrite EDİLEMEZ (yalnız allow/deny/ask). Presenter'lar saf fonksiyon (replay'de de çağrılır).
- **system-prompt** (`ctx.systemPrompt`) — `section()/context()/tools()/variable()/suppressRuntimeContext()/assemble()`; order kuralı: -100 harness kimliği, 0 persona, 100-199 tool guidance; `complete` bölüm tek prompt olur.
- **filesystem** (`ctx.fs`) — `writeText(target, content, expected?)`: `createIfAbsent` | `replaceIfVersion` | unconditional; `editText` literal (version guard atomik); observation policy: varsayılan read-before-write/edit (`FS_NOT_OBSERVED`/`FS_STALE_VERSION`); 13 `FsErrorCode` (FS_SANDBOX_DENIED ≠ FS_PERMISSION_DENIED); **file IO'da timeout yok**.
- **shell** (`ctx.shell`) — `resolve(request) → ShellExecSpec` (explicit > implicit şablonu); `ShellRunResult {exitCode, signal, timedOut, aborted, timeoutMs, stdout, stderr, sandbox?}` — timedOut/aborted birbirini dışlar; **nonzero çıkış/kill reject değil resolve'dur**; sandbox genişletme: tek geniş retry + gerekçe; `ctx.shellEnv` trusted `DSH_*` registry.
- **subprocess** (`ctx.subprocess`) — `resolveExecutable/spawn/spawnTerminal`; `SubprocessSpawnSpec` hiçbir default uygulamaz; argv asla shell-interpreted; terminate tree-scoped SIGTERM→grace→SIGKILL; ambient `DSH_*` önce atılır sonra explicit env merge.
- **terminal** (`ctx.terminals`) — Owner-scoped kalıcı PTY; yetki tam sahip Agent'a göre; session başına bir aktif send; dayanıklılık tool/call+tool/result üzerinden (ayrı PTY event yok); PTY state process-local.
- **code-runtime** (`ctx.codeRuntime`) — `run(request)`; hata ALAN (`error`), reject yok; `CodeRunFailure.kind`: exception|timeout|abort|worker-exit|invalid-output|output-limit; descriptor language (typescript|python; published backend yalnız TS) + isolation (worker-thread|process|container — tanı, güvenlik iddiası değil).
- **lsp** (`ctx.lsp`) — 4 işlem (goToDefinition|findReferences|goToImplementation|hover); findReferences her zaman declaration'ları içerir; generic JSON-RPC escape-hatch YOK; pozisyonlar zero-based UTF-16 (model aracı 1-based'e çevirir).
- **web** (`ctx.web`) — search + fetch tek servis; `searchMaxResults` default 8; `WebFetchResult {url, statusCode, body, truncated}` — **non-2xx sonuçtur, hata değil**; local fetch yalnız HTTP(S), credential reddeder, redirect/byte/char limitli; private-network engeli YOK (uyarı); hata kodları WEB_*.
- **spill** (`ctx.spillStore`) — `saveText` tek işlem; opak locator (parse edilmez); root 0700, `wx`+0o600 (symlink redirect engeli); spill-policy `maxInlineBytes` üstünü head/tail preview + ref ile değiştirir (best-effort).
- **skills** (`ctx.skills`) — Host + per-scope katmanlı provider registry; keşif rank: project-dsh(100) `.dsh/skills` → project-agents(200) `.agents/skills` → custom(300) → user-dsh(400) `$DSH_HOME/skills` → user-agents(500) `~/.agents/skills` → bundled(600); ad kebab-case; `<name>/SKILL.md` veya `<name>.md`; `SkillInvocationPolicy {modelInvocable, userInvocable}`; katalog açıklama cap'i default 500 karakter.
- **attachment** (`ctx.attachments`) — İçerik adresli görüntü sahipliği log dışında; yalnız referans loga girer (browser URL/base64/host path yok); `persist-before-event`; limitler maxImageBytes/PerMessage/MessageImageBytes/Pixels; batch önce validate sonra save.
- **user-questions** (`ctx.userQuestions`) — UI destekli soru/cevap; **yalnız tam canlı runtime root sorabilir** (owned child `DELEGATED_CALLER` reddeder); hata kodları EMPTY_QUESTIONS/NO_PROVIDER/ASK_ABORTED/CALLER_NOT_LIVE/DELEGATED_CALLER; tek aktif provider.
- **extensions** (`ctx.dynamicCordisRunner`/`ctx.cordisInspect`) — Dinamik Cordis Plugin/Package tanımlama + Host/Client çalıştırma; `define/undefine/run/stop/snapshot/inspect`; client-bearing aktivasyon onay isteyebilir.

### 7.5 UI / Web
- **web-server** (`ctx.webServer`) — Tek node:http taşıyıcı; exact → en uzun prefix → fallback; TLS/auth/origin YOK (0.0.0.0 bind ağı açar); SPA fallback (405/403/index.html 200).
- **client-modules** (`ctx.clientModules`) — Web plugin tablosu; `dsh.client` bildiren paketler; `window.__DSH_BOOT__` graph'ı; incremental tarama; client bundle yeniden derlemesi + mevcut URL refresh'i gerekir (`pnpm run dev:web` watcher'ı).
- **api gateway / host** — Remote BFF: `remotes → gateway → connection → webserver`; trust check connection'da.

### 7.6 Platform
- **settings** (`ctx.settings`) — Tek kullanıcı dokümanı; çözümleme schema default → kompozisyon base → kullanıcı katmanı; `update` (merge) / `replace` (wholesale) / `mutate` (path-op, `expectedRevision` conflict koruması); **`describe({redactSecrets:true})` her wire yüzeyinde zorunlu**; `role('secret')` alanları sıyrılır.
- **workspace** (`ctx.workspaceRegistry`) — Kullanıcının çalıştığı dizinin kalıcı kaydı (modele görünmez); `WorkspaceId` = uuid; üyelik = id + header `cwd` canon eşleşmesi; `delete` yalnız kaydı siler (dizin/session/log asla).

---

## 8. PAKET ENVANTERİ (npm: `@deepseek-ai/dsh-*`, tek sürüm 0.1.0-rc.5)

Grup yapısı: `packages/<grup>/<pkg>/`. Grup README'leri paket→ctx-key eşlemesinin sahibidir. Kurallar: extension plugin'leri Service Definition'a bağlanır, somut provider'a değil; `dsh-agent-loop` değiştirilebilir.

| Grup | Alt paketler (özet) | Rol |
|---|---|---|
| `core` | scope, session, system-prompt, tools, agent, agent-default-model, agent-loop, agent-tool-presentation | Ürün omurgası; SD+Service+Provider+library |
| `api` | api-gateway (`ctx.typertGateway`/`ctx.remote`), api-remotes | Remote BFF |
| `typert` | registry (`ctx.typert`), protocol, loader, generator | Tip grafiği/RPC |
| `llm` | llm (`ctx.llm`), token-meter (`ctx.tokenMeter`), llm-retry, llm-deepseek, llm-pi-ai | LLM seam + adaptörler |
| `e2b` | e2b (`ctx.e2b`), fs-e2b, subprocess-e2b | **POC** — uzak sandbox |
| `subprocess` | subprocess (`ctx.subprocess`), subprocess-local | Process altyapısı |
| `shell` | shell (`ctx.shell`), bash-local/sandbox, pwsh-local/sandbox, shell-env, tool-bash, tool-bash-persistent, tool-pwsh | Bash/PowerShell ailesi |
| `terminal` | terminal (`ctx.terminals`), terminal-bash, tool-terminal | Kalıcı PTY |
| `fs` | fs (`ctx.fs`), fs-local, fs-sandbox, fs-observation-policy, tool-fs, tool-fs-search, tool-str-replace-editor | Dosya sistemi ailesi |
| `lsp` | lsp (`ctx.lsp`), lsp-stdio, tool-lsp | Dil sunucusu |
| `skill` | skill (`ctx.skills`), skill-badge, skill-filesystem, tool-skill | Skill'ler |
| `web` | web (`ctx.web`), web-search-exa/perplexity/deepseek, web-fetch-http, tool-web | Web arama/getirme |
| `compaction` | compaction (`ctx.compaction`), compaction-basic, compaction-tool-result-pruner, command-compact | Context yönetimi |
| `context` | session-reference, time-context, tmux-context, agent-instructions | Modele görünen bağlam |
| `subagent` | subagent (`ctx.subagents`), subagent-in-process-driver, spawn/fork-in-process, subagent-acp/codex/claude-code/dsh-sdk, tool-subagent, tool-subagent-control, tool-subagent-report | Delegasyon |
| `bundle` | dsh-base, dsh-web-app, dsh-headless | Kompozisyon katmanları |
| `workflow` | workflow (`ctx.workflowEngine`), workflow-worker-thread, tool-workflow, tool-ralph | Orkestrasyon |
| `todo` | tool-todo | todo_write |
| `plan` | plan-mode (`ctx.planMode`) | Plan modu |
| `preset` | agent-presets (`ctx.agentPresets`), persona | Ajan preset'leri |
| `guard` | repeat-tool-reminder, tool-call-timeout-policy | Döngü hijyeni |
| `hooks` | hook-protocol, hooks-claude-code, hooks-codex | Harici hook köprüleri |
| `session` | session-persistence, session-checkpoint-policy, persistence-jsonl/sqlite, session-projection, projection-cache, session-stats, session-title, title-llm, title-first/all-prompts-llm, session-telemetry, telemetry-otel | Kalıcı veri düzlemi |
| `identity` | anonymous-user-id | Anonim korelasyon id'si |
| `settings` | settings (`ctx.settings`), settings-file | Kullanıcı ayarları |
| `credentials` | credentials (`ctx.credentials`), credentials-local | Credential referansları |

**Kalan gruplar (Bölüm 2 kazısı):**

| Grup | Alt paketler (özet) | Rol |
|---|---|---|
| `acp` | acp (yalnızca-otomasyon ACP sunucusu; stdio JSON-RPC; `@agentclientprotocol/sdk 0.25.1`) | Programatik istemci sunucusu |
| `interaction` | commands (`ctx.commands`), user-approval (`ctx.approval`), permission-presets (`ctx.permissionPresets`), user-questions (`ctx.userQuestions`), tool-ask-user | İnsan işbirliği düzlemi |
| `boot` | app-boot (`.env`, fail-loud Loader guard'ları, snapshot-aware config, settle-the-tree), cmdline (`ctx.cmdlineArgs`, `ctx.appExit`) | CLI boot yapıştırıcısı |
| `sdk` | protocol (wire), client (TS istemci), server (`dsh-sdk-jsonrpc-server`) | Süreç-dışı runtime sürüşü |
| `examples` | agent-spine-demo, acp-demo, jsonrpc-demo (bundle'lar; `-demo` = non-product) | Demo bundle'ları |
| `util` | brand (nominal branded tipler), home-paths, timeout, output-retention, atomic-write, native-command, launch-environment | Sıfır-bağımlı primitifler |
| `attachment` | attachment (`ctx.attachments`), attachment-local | İçerik adresli ikili depo |
| `client` | 37 paket: web, modules, web-react, connection, runtime, hmr, locale, schema-form + ui-* ailesi (slots, theme, primitives, attachment, layout, sidebar, workspace, conversation, tool, workflow-run, goal, trajectory, commands, input-trigger, skill, subagent, jobs, model-selection, permission-presets, plan, settings*, user-questions, agent-preset) | GUI tarayıcı yarısı |
| `code-runtime` | code-runtime (`ctx.codeRuntime`), code-runtime-worker-thread | Code Mode çalıştırma |
| `extensions` | tool-cordis, cordis-host-runner (`ctx.dynamicCordisRunner`; node:vm sandbox), cordis-client-runner, ui-cordis | Öz-düzenleme |
| `feedback` | command-feedback (`/feedback`, `feedback/record`), message-feedback (sidecar + Remote list/put/delete) | İnsan geri bildirimi |
| `goal` | goal (`ctx.goals`), goal-round-driver, tool-goal, command-goal | Same-session hedef |
| `host` | apiproxy (`ctx.apiProxy`), webserver (`ctx.webServer`), frontend-static, directory-picker/-native/-browse/-auto, plugin-inventory | GUI host yarısı |
| `jobs` | jobs (`ctx.jobs`), jobs-local, tool-jobs | Arka plan iş |
| `mcp` | mcp-client (stdio + streamable-http; dış sunucu araçlarını `ctx.tools`'a kaydeder; `mcp__<server>__<tool>`) | MCP istemcisi |
| `runtime-diagnostics` | invariants (`ctx.invariants`; allowlist/blocklist) | Runtime invariant registry |
| `sandbox` | sandbox (`ctx.sandbox`), sandbox-local, sandbox-policy (`ctx.sandboxPolicy`), sandbox-windows-acl | Süreç hapsi |
| `schedule` | schedule (tek paket; durable state logda; root-Agent timer owner) | Hatırlatıcılar |
| `session-query` | session-query (`ctx.sessionQuery`), session-query-sqlite (FTS), session-log-export (Web /export + ZIP), tool-session-query | Session sorgulama |
| `spill` | spill (`ctx.spillStore`), spill-local, spill-policy | Büyük çıktı kalıcılaştırma |
| `storage` | storage (`ctx.storage`), storage-json, storage-sqlite, storage-domain (`ctx.storageDomain`) | Event dışı kalıcılık |
| `test-support` | acp-snapshot, agent-loop-testkit, client-runtime, llm-mock-server, llm-replay, loader-smoke | Test altyapısı |
| `workspace` | workspace (`ctx.workspaceRegistry`; uuid id, cwd canon eşleşmesi) | Workspace varlığı |

---

## 9. UYGULAMALAR, PYTHON SDK, NATIVE VE ÖRNEKLER

### 9.1 `apps/cli` — `@deepseek-ai/dsh` launcher (bin: `dsh`)
Profillerin ürün başlatıcısı; `src/args.ts` komut gramerinin, `src/bin.ts` seçili runner'ı yükler. Geçersiz komut/opsiyon/boot hatası non-zero çıkar (SIGINT=130, SIGTERM=0). Giriş modları: `dsh --profile <ad>` / `dsh --profile headless "görev"` / `dsh web` / `dsh plugin --profile <ad> <pnpm args>` / `--dump-config|--dump-default-config`. Launcher yalnız kendi flag'lerini ayrıştırır; ilk tanınmayan token app argümanlarını başlatır (`--port`, `--host`, `--trusted-host` web app'e). Katman önceliği: bundle patch'leri → profil patch → `$DSH_HOME/cordis.patch.yml` → `--patch` overlay'leri. Kaynak çalıştırma: build sonrası `pnpm dsh <args>` (tsx ESM hook'u). CLI davranış referansı `apps/cli/reference/README.md`.

### 9.2 `apps/web` — `@deepseek-ai/dsh-web-frontend` (tarayıcı yarısı)
Vite girişi; `@deepseek-ai/dsh-client-web` shell'i üzerine build edilir; `dist/` `dsh web` tarafından servis edilir. **Tek başına uygulama değildir** — bare Vite `window.__DSH_BOOT__` enjekte edemediğinden `rejectStandaloneServe()` ile serve'i reddeder. Varsayılan adres `http://127.0.0.1:3080` (`--port` override; `--host 0.0.0.0` desteklenmez; `--trusted-host` /api güven çitine authority ekler). React 18.2 + Vite 6. Client plugin HMR: `pnpm dsh web` + `pnpm run dev:web` birlikte; client-plugin değişiklikleri ancak bundle rebuild + mevcut URL refresh ile görünür. E2E test kapsamından özellik yüzeyi: chat/scroll sözleşmesi, composer, model seçimi/default, settings (models/plugins/general), onay composer'ı, soru composer'ı, plan-mode review, goal bar, subagent etkinliği + interrupt, workflow-run replay, arka plan job listesi, skill kullanımı/politikası, terminal (pwsh dahil), schedule, feedback, code-mode round, cordis-tool round, agent preset yazarlığı/seçimi, üretilen dosya kartları, arama kartı, markdown/math/görüntü render, PWA manifest, HMR.

### 9.3 `python/sdk` + `python/sdk-runtime` — Python SDK
- **Dağıtım:** `pip install deepseek-harness-sdk` (modül `deepseek_harness`); aynı sürümlü `deepseek-harness-runtime-bin` platform wheel'i otomatik kurar — **sistemde Node.js gerekmez**. `requires-python >= 3.10`; dep: `pydantic>=2.12,<3`. Platform: Linux x64/arm64, macOS 14+ arm64 (`py3-none-manylinux_2_28_*`, `py3-none-macosx_14_0_arm64`).
- **Çalışma modeli:** Harness'ı alt süreç olarak stdio üzerinden newline-delimited JSON-RPC ile sürer; runtime daima explicit config ister (`$DSH_CORDIS_CONFIG` veya argv); istemci bundled launch'ta `runtime/cordis.yml`'i enjekte eder (JSON-RPC server + agent core + DeepSeek adapter + JSONL persistence + checkpoint policy + local bash + FS provider).
- **API:** üst seviye `DeepSeekHarness` (context manager; lazy runtime; `run()`), `DeepSeekHarnessConfig` (provider/model/max_tokens/cwd/session_root/cordis/env/base_url/api_key/…), `Session`, `RunResult` (session_id, final_response, finish_reason, events, notifications); alt seviye `HarnessClient` (senkron JSON-RPC: initialize/session_prompt/request/notify); hatalar `HarnessError` → `TransportClosedError`/`SdkProtocolError`/`JsonRpcError`. Modüller: `__init__`, `api.py`, `client.py`, `errors.py`, `models.py`.
- **Kullanım:**
```python
with DeepSeekHarness(provider="deepseek-official", model="deepseek-v4-flash",
    max_tokens=49_152, cwd=workspace, session_root=sessions, cordis=config) as h:
    result = h.run("Inspect the repository and fix the failing tests.", session_id="example-001")
print(result.final_response)
```
- `minimal` kompozisyonu (examples/jsonrpc-agent): yalnız kalıcı bash + str_replace_editor; compaction kapalı; `danger-full-access` (disposable ortam); POSIX PTY gerektirdiğinden **Windows desteklemez**. Benchmark kullanımı: ayrı workspace + ayrı session id (BENCHMARK.md).

### 9.4 `native/landlock-run` — `@deepseek-ai/node-addon-landlock-run`
Linux'ta alt süreçleri hapsetmek için **Landlock self-restrict-then-exec** başlatıcı (~300 satır C11, raw kernel UAPI, musl'e statik bağlı): kendi üzerine Landlock ruleset kurup komutu `exec` eder; ruleset execve boyunca miras alınır (komut + tüm çocukları hapsolur, çağıran serbest kalır). **Fail-closed:** kernel uygulayamazsa komutu çalıştırmadan çıkar (`LAUNCHER_FAILURE_EXIT` 125). API: `launcherPath()`, `probe()` → 'full'|'partial'|'unusable', `grantArgs({readOnly?, readWrite?})`. Platform paketleri `-linux-x64`/`-linux-arm64`; Landlock 5.13+ çekirdek; diğer platformlarda bilinçli olarak paket yok.

### 9.5 `examples/` — çalıştırılabilir demolar (detay)
| Örnek | Ne gösterir | Nasıl çalışır |
|---|---|---|
| `headless-agent` | Tek görev alan, seçili formatta çıktı basan başsız ajan | `pnpm dsh --profile headless "görev"`; `advanced.cordis.yml` (Code Mode + Cordis tools), `goal.cordis.yml` (goal tool'ları), `e2b.cordis.yml` (E2B POC) |
| `acp-agent` | ACP otomasyon sunucusu (session/izin/iptal destekli) | `pnpm run demo:acp`; `DSH_PERMISSION_MODE` workspace-write/danger-full-access seçer; stdout yalnızca protokol; 20+ overlay (code-mode, fs, image, pty, retry, web, depth-two…) |
| `jsonrpc-agent` | Python SDK + JSON-RPC ile sürülen başsız ajan | `python examples/jsonrpc-agent/minimal.py --workspace … --session-root … --session-id … "görev"`; `minimal.cordis.yml` minimal kompozisyon |
| `mcp-memory` | Memorix/MCP Reference Memory/Engram bellek sunucularını generic MCP client ile bağlama | `dsh web --patch "$PWD/examples/mcp-memory/memorix.cordis.yml"`; araçlar `mcp__<serverName>__<tool>` |
| `web-cordis` | Ajanın kendi in-memory Cordis ağacını inceleyip değiştirmesi (geçici plugin'ler süreç çıkışında kaybolur) | `pnpm run demo:cordis` / `pnpm run demo:cordis acp` |
| `web-schedule` | Session-local kalıcı hatırlatıcılar | `dsh web --patch examples/web-schedule/cordis.yml` |

---

## 10. EKLENTİ GELİŞTİRME (DSH'i genişletmek)

### 10.1 Plugin biçimleri ve config
```ts
// 1) Fonksiyon
export const name = 'hello-plugin'
export function apply(ctx: Context, config: Config) { /* ... */ }

// 2) Servis sınıfı
export class MyService extends Service {
  constructor(ctx: Context) { super(ctx, 'myService') }
}
```

```ts
// Config: TS interface + Schemastery şeması (aynı isim; düz nesne OLMAZ)
export interface Config { greeting: string; maxRetries: number }
export const Config: Schema<Config> = Schema.object({
  greeting: Schema.string().default('Hello'),
  maxRetries: Schema.number().default(3),
})
```

```yaml
# cordis.yml overlay (mutlak yol)
- insert:
    - id: hello
      name: '/abs/path/scratch-plugin/src/my-plugin.ts'
      config:
        greeting: !!js process.env.DEMO_GREETING ?? 'Hello'   # !!js yalnız config + disabled alanında
```
Kurallar: ayarlanabilir değerleri hardcode etme; geçersiz config'de yüksek sesle başarısız ol; HMR config değişimini hot-replace eder.

### 10.2 Araç ekleme (`docs/cookbook/adding-a-tool.md`)
```ts
export const name = 'greet-tool'
export const inject = ['tools']
export function apply(ctx: Context) {
  ctx.tools.register(defineTool({
    name: 'greet',
    description: 'Greet someone by name.',
    parameters: { name: { type: 'string', required: true, description: 'The name to greet' } },
    output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
    async execute(args) { return `Hello, ${args.name}!` },
  }))
}
```
**`execute` sözleşmesi:** args sizin için doğrulanır (DSL dışı kısıtları elle kontrol edin); TEK kanonik JSON değeri döndürün (`output.schema`; content block değil); altyapı hatasında throw (→ `isError`); `exec.signal`'a uyun; async bildirim için `exec.agent.inject(...)`; uzun işler `ctx.jobs.start(...)` + `{ kind: 'background', jobId }` handle'ı; presenter'lar saf fonksiyon (replay'de de çalışır).

### 10.3 LLM adaptörü (`docs/cookbook/adding-an-llm-adapter.md`)
```ts
class MyAdapter extends LlmAdapter {
  async * stream(options: GenerateOptions): AsyncIterable<StreamChunk> { /* ... */ }
}
export const inject = ['llm']
export function apply(ctx: Context, config: Config) {
  ctx.llm.registerAdapter(config.providers, new MyAdapter(config.apiKey))
}
```
**Chunk sırası:** `block-start(index, blockType) → text-delta* / tool-call-delta(argumentsDelta = RAW JSON string)* → block-end → usage → finish`. `usage` finish'ten ÖNCE; finish'ten sonra hiçbir şey. Hatalar: throw `LlmError`+stabil kod (transport) VEYA `finish {kind:'error'|'aborted'}` (provider in-band). Karşılanamayan `GenerateOptions` alanı → `LlmError('UNSUPPORTED')`. Her HTTP çağrısı `attributionHeaders()` + `options.signal` taşır. Referanslar: `dsh-llm-deepseek` (direkt HTTP + SSE), `dsh-llm-pi-ai` (kütüphane sarmalayıcı).

### 10.4 Yayınlama ve kurulum (`docs/user/develop/basic/publish.md`)
```jsonc
// bundle package.json
{ "name": "dsh-hello-plugin", "type": "module",
  "dsh": { "bundle": { "patch": "./cordis.patch.yml" } } }
```
```sh
dsh plugin --profile demo add ./hello-plugin
dsh --profile demo --dump-config
dsh plugin --profile demo remove dsh-hello-plugin
```

### 10.5 Web Chat node'u (`adding-a-conversation-node.md`)
Replay'lenebilir event ailesi (tek business id, `(kind,id)` başına en fazla bir start) → `ConversationNodeDefinition` (`match`/`start`/`update`/`buildViewNode`/`buildLocationData`/`publication`) → replace/prepend/append ingestion → 6 odaklı test.

---

## 11. WEB UI KULLANIMI

- **Başlangıç:** `npx @deepseek-ai/dsh web` → `http://127.0.0.1:3080`. Workspace seçilene kadar session composer kapalı.
- **Model kurulumu (Settings → Models):** DeepSeek kartı (tek API-key alanı; anahtarlar write-only — kaydedince redacted descriptor; sır `$DSH_HOME/.credentials.yaml`, ayarlarda yalnız referans). **Add provider:** Anthropic/OpenAI vb. katalog provider'ları (endpoint/protokol/model listesi kurulu katalogdan, ağsız). Native auth'lılar (Bedrock/Vertex/Azure/Codex) kendi credential'larını ister. **Add a custom provider:** kalıcı küçük-harf Provider ID + base URL + protokol + en az bir model; "Fetch available models" `GET /models` çağırır.
- **Görüntü girişi:** elle girilen model text-only sayılır; vision için `settings.yaml`'da modele `input: [text, image]` veya route'a `defaultInput` (fallback, override değil; katalog modelleri `modelOverrides` ile daraltılır). DeepSeek chat-completions route'u text-only'dur.
- **Model seçimi:** picker; seçim yeni session'ların varsayılanı olur; istek göndermiş session kendi logundaki modeli korur. Silinen provider → "Select model" ile girdi kilitlenir.
- **Hata kodları:** `MISSING_CREDENTIAL`, `UNKNOWN_MODEL`, fetch 401 (endpoint `GET /models` vermiyorsa elle model girin).

---

## 12. REPO MÜHENDİSLİK KÜLTÜRÜ

- **Konvansiyonlar (kök AGENTS.md):** ESM everywhere; `@deepseek-ai/cordis` her paketin peer dependency'si; kayıtlar effect'tir; runtime invariant'lar sahiplik ilişkilerini assert eder; tip güvenli event'ler declaration-merging; waterfall listener'ları `next()` çağırmalı; "model-visible ⟺ logged"; explicit > implicit; misconfig yüksek sesle başarısız olur; cross-boundary id'ler branded (`Branded<B>`); TS'e güven, sınırlarda doğrula (parser/config, queued, model/tool JSON, durable/file, worker, process, wire); source plane vs artifact plane ayrımı.
- **Savunmacı kalıplar (`defensive-patterns.md`):** bağımsız sonuçları ayrı raporla (timeout+exit 0); kamu kontratını iki tarafta onurlandır; async state ≠ sync state; dispose quiescence'a ulaşmalı; callback exception'larını dispatcher'da hapset; güvenilmeyen çıktıya ambient env/predictable path verme; link şekilli path'leri unlink'le.
- **Test katmanları:** unit (vitest) / coverage gate (per-file %100) / real-API e2e (key ile, yoksa skip) / keyless snapshot (ACP/headless replay) / web browser snapshot (Chromium). "Dünyayı doğrula, self-report'u değil."
- **Dokümantasyon kapıları (`docs/AGENTS.md`):** her gerçeğin tek evi; tutorial vs reference; wordcount bütçeleri (root AGENTS ≤1600 kelime…); iki dilli EN/ZH eşleştirme (`foo.md` + `foo.zh.md` + `foo.i18n.yaml` blob-hash kaydı; `verify-translation-pairing`); `ts type-equiv` blokları derlenmeli; slop checklist.
- **Agent Notes (`.agents/notes/`):** implemented/archived/proposed/rejected — non-trivial her değişiklik aynı PR'da Agent Note ister; arşivlenenler donuktur.
- **Skill'ler (`.agents/skills/`):** dsh-pre-push-checks, dsh-code-review, dsh-translate-docs, dsh-prose-standard, dsh-archive-agent-notes, dsh-doc-site-sync, dsh-trim-cot-leakage, dsh-find-simplifications, dsh-merging-stacked-prs, record-browser-gif.
- **Postmortem'ler (`docs/postmortem/`):** gerçek kullanıcıya ulaşan subtle/systemic bug kayıtları (0001: ACP default-export inject düşürdü; 0002: `!!js` nesnesi FS tool'larını devre dışı bıraktı; 0003: Web ajanı yanlış sunucuyu doğruladı; 0004: Landlock partial bildirimi child hatalarını yanlış sınıflandırdı).
- **Script'ler (`scripts/`):** 100+ gate/generator (gen-tool-catalog, gen-config-catalog, gen-persistence-catalog, gen-module-graph, gen-doc-graphs, verify-* ailesi, rescope-vendor, publication-payload, run-gates…).
- **Vendoring:** `vendor/` pinned source kopyaları (cordis, cosmokit, schemastery, loader, include, group, hmr, logger-console, timer); sync prosedürü `vendor/README.md`; pre-commit guard manifesti zorlar.
- **PR/stack kültürü:** `kind/*` + `area/*` etiketleri; stack'ler `--force-with-lease` (asla raw `--force`); FIXME>TODO>XXX; tek trailing newline.

---

## 13. GÜVENLİK MODELİ (özet)

- Sandbox kelimesi **dosya etkileriyle** sınırlıdır (ağ/süreç görünürlüğü dışında); modlar read-only/workspace-write/danger-full-access; enforcement full/partial; fail-closed.
- Onay akışı `tools/pre-execute` (allow/deny/ask) → monotonic guard'lar → `ctx.approval` one-shot (cevaplanamazsa deny).
- Sırlar: `ctx.credentials` referans seam'i; env-over-`.env` provider; UI write-only; env scrub (`*KEY*/*SECRET*/*TOKEN*/*PASSWORD*`); temp 0700.
- `dsh-invariants` runtime invariant registry; `permission-presets` (workspace-write/danger-full-access ön ayarları).
- E2B POC: yalnızca execution world (dosyalar + process) sandbox'a taşınır; harness process/Cordis/session state taşınmaz.

---

## 14. STUHUB DS İÇİN ÇIKARIMLAR

1. **DSH geliştirme katmanıdır, ürün değil:** StuHub DS ürünü FastAPI+React'tir; DSH ajanları onu inşa eder. DSH'e bağımlılık yalnızca geliştirme sürecindedir; ürünün çalışma zamanı DSH içermez.
2. **Orkestrasyon araçları birebir yol haritasıyla eşleşir:** Ana Ajan'ın goal turları (`create_goal`/`update_goal`), paralel delegasyon (subagent/subagent_fork), faz bazlı model override'ı (workflow `provider`/`model`), arka plan indexer (bash+pwsh `run_in_background` + `job_*`), TDD döngüsü (pwsh + testler) DSH'in belgelenmiş yetenekleridir.
3. **Effort kuralı DSH'de nasıl uygulanır:** subagent delegasyonlarında prompt içinde açık seviye talimatı; workflow fazlarında `provider`/`model` override'ı; Ana Ajan sabit V4 Pro.
4. **Sandbox pratiği:** StuHub DS workspace'i `workspace-write` modunda çalışır; workspace dışı yazmalar (ör. DSH checkout'una müdahale) reddedilir — bu beklenen davranıştır. Genişletme yalnızca gerçek bir reddin ardından, tek seferlik ve dar kapsamlı talep edilir.
5. **Kalite kapıları ↔ DSH test felsefesi:** "dünyayı doğrula, self-report'u değil" ilkesi StuHub DS'in Kalite Kontrol Ajanı'na birebir aktarılabilir; keyless snapshot yaklaşımı quiz/not üretiminin deterministik kalite testleri için ilhamdır.
6. **Maliyet gözetimi ↔ DSH pratiği:** DSH'in `generation_logs` benzeri `token-meter` + compaction ayarları (thresholdRatio 0.8, retainRatio 0.16) StuHub DS prompt bütçelemesine model olabilir.
7. **Gizlilik notu:** DSH kendisi (geliştirme ortamı) ayrı bir güven yüzeyidir; ürünün gizlilik sözleşmesi (yol haritası Bölüm 8) ürün verisini kapsar. DSH checkout'u ürün verisi içermez.
8. **Uyumluluk riski:** Developer preview — StuHub DS yol haritası DSH'in iç API'lerine bağımlılık kurmaz; yalnızca model-facing araçlar ve CLI kullanılır (bunlar dokümante yüzeydir).

---

## 15. KAYNAKLAR

**Checkout içi (birincil):**
- `README.md`, `AGENTS.md`, `docs/architecture.md`, `docs/glossary.md`, `docs/agent-lifecycle.md`, `docs/tool-execution-pipeline.md`, `docs/tool-catalog.md`, `docs/config-catalog.md`, `docs/persistence-catalog.md`, `docs/capability-seams.md`, `docs/defensive-patterns.md`, `docs/event-producer-consumer.md`, `docs/api-gateway.md`, `docs/graph-atlas.md`, `docs/module-graph.md`, `docs/development.md`, `docs/testing.md`, `docs/web-styling.md`, `docs/rescope.md`, `docs/cordis-primer.md`, `docs/cordis-tutorial/*`, `docs/cordis-api/*`, `docs/cookbook/*`, `docs/subsystems/*` (50+ dosya), `docs/user/**`, `docs/i18n/*`, `docs/postmortem/*`, `packages/README.md` + tüm paket README/package.json'ları, `apps/cli/README.md`, `apps/web/tests/*`, `examples/*/README.md`, `python/README.md`, `native/README.md`, `BENCHMARK.md`.

**Web (ikincil, güncel durum):**
- [GitHub: deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)
- [DeepSeek Harness 公测 — ithome](https://www.ithome.com/0/989/446.htm)
- [实测 DeepSeek Harness — zhidx](https://www.zhidx.com/p/584897.html)
- [npm: @deepseek-ai/dsh ekosistemi](https://www.npmjs.com/package/@why913/dshx)
- Cordis: [github.com/cordiverse/cordis](https://github.com/cordiverse/cordis) + [_A Programming Paradigm for Spatiotemporal Composability_](https://github.com/cordiverse/paper)
