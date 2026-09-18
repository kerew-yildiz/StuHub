/**
 * Model çıktısı normalizasyonu — JSON zarfı soyma, kaçış/çit temizliği (2026-09-18).
 *
 * Backend eşi: `apps/backend/src/services/note_cleanup.py` — aynı kurallar, aynı test
 * örnekleri. Buradaki kopya SON SAVUNMA HATTI: kayıtlı nota eski/bozuk veri girse bile
 * ekranda ham JSON görünmez (canlı vaka: not 22 `notes.content_md`ye ham zarf olarak
 * yazılmıştı, ```` ```json ```` çiti tüm notu tek kod bloğuna çeviriyordu).
 *
 * Kural özeti:
 * - `{"content": "..."}` / `{"markdown": ...}` / `{"sections": [...]}` zarfı → içindeki markdown
 * - ```` ```json ```` çitli zarf → açılır; etiketsiz/başka dilli kod çitleri KORUNUR
 * - zarf içindeki `\n` kaçışları çözülür; gerçek satır sonu taşıyan metne dokunulmaz
 * - düzgün markdown (zarf yok) hızlı yoldan değişmeden geçer
 */

const ENVELOPE_HINT_RE =
  /["'](?:content|markdown|markdown_content|note|text|body|answer|[iı]çerik)["']\s*:/i
const FENCE_RE = /```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n?([\s\S]*?)```/g
const JSON_FENCE_RE = /```[ \t]*json[ \t]*\n/i

const CONTENT_KEYS = [
  'content',
  'markdown',
  'markdown_content',
  'note',
  'text',
  'body',
  'answer',
  'icerik',
  'içerik',
  'bolum',
  'bölüm',
]
const LIST_KEYS = ['sections', 'topics', 'parts', 'items', 'chunks']
const MAX_DEPTH = 4

const ESCAPE_MAP: Record<string, string> = {
  n: '\n',
  t: '\t',
  r: '\r',
  '"': '"',
  "'": "'",
  '\\': '\\',
  '/': '/',
}

// Cümle sonuna YAPIŞMIŞ başlık: `... [2].### Oral Dönem` (markdown olarak render edilmez).
const GLUED_HEADING_RE = /([.!?:;)\]"'”’])[ \t]*(#{2,4})[ \t]+/g

/** Cümle sonuna yapışmış markdown başlığını ayırır (`.### X` → `.\\n\\n### X`).
 * Backend `_replace_section` regen turlarında bloğu ayırıcı olmadan yerleştiriyordu;
 * yapışan başlık ekranda düz metin olarak görünüyordu (2026-09-18). Metin içi `#`
 * (C#, URL çapası) etkilenmez. */
function splitGluedHeadings(text: string): string {
  return text.replace(GLUED_HEADING_RE, (_match, punct: string, hashes: string) => `${punct}\n\n${hashes} `)
}

/** Model yanıtını temiz markdown'a çevirir (zarf yoksa metin değişmez). */
export function normalizeNoteMarkdown(text: string, depth = 0): string {
  if (!text || !text.trim()) return text ?? ''
  if (depth > MAX_DEPTH) return text.trim()

  const stripped = text.trim()
  if (!looksLikeEnvelope(stripped)) return splitGluedHeadings(decodeEscapedText(stripped))

  const pieces = scan(stripped)
  const joined = pieces.filter((piece) => piece.trim()).join('\n\n')
  return splitGluedHeadings(dedupeHeadings(joined).replace(/\n{3,}/g, '\n\n').trim())
}

function looksLikeEnvelope(text: string): boolean {
  if (ENVELOPE_HINT_RE.test(text)) return true
  if (text.startsWith('```')) return true // JSON olmayan çit `scan` içinde korunur
  if (text[0] === '{' || text[0] === '[') return jsonPrefix(text) !== null
  if (JSON_FENCE_RE.test(text)) return true
  return text.length >= 2 && text.startsWith('"') && text.endsWith('"')
}

/** Metni kod çitlerine göre parçalar; zarf çitlerini markdown'a çevirir. */
function scan(text: string): string[] {
  const pieces: string[] = []
  const regex = new RegExp(FENCE_RE.source, FENCE_RE.flags)
  let position = 0
  let match: RegExpExecArray | null
  while ((match = regex.exec(text)) !== null) {
    pieces.push(...plainPieces(text.slice(position, match.index)))
    const inner = markdownFromJsonText(match[2])
    if (inner === null) {
      pieces.push(match[0]) // JSON değil: gerçek kod bloğu
    } else if (inner.trim()) {
      pieces.push(inner)
    } else if (match[1].trim().toLowerCase() !== 'json') {
      pieces.push(match[0]) // içerik anahtarı yok ama JSON çiti değil
    }
    position = match.index + match[0].length
  }
  pieces.push(...plainPieces(text.slice(position)))
  return pieces
}

/** Çit DIŞINDAKİ parça: başında JSON varsa soyar, kalanı markdown kabul eder. */
function plainPieces(segment: string): string[] {
  let text = segment.trim()
  if (text.startsWith('```')) {
    // Kapanmamış çit (kesik yanıt) — açılış satırını at, gövdeyi normal işle.
    const newline = text.indexOf('\n')
    text = newline === -1 ? '' : text.slice(newline + 1).trim()
  }
  if (!text) return []
  if (text[0] === '{' || text[0] === '[') {
    const decoded = jsonPrefix(text)
    if (decoded) {
      const inner =
        typeof decoded.value === 'string' ? decoded.value : markdownFromJson(decoded.value)
      return [...(inner.trim() ? [inner] : []), ...plainPieces(decoded.rest)]
    }
    const truncated = truncatedEnvelopeMarkdown(text)
    if (truncated !== null) return [truncated]
  }
  return [decodeEscapedText(text)]
}

const TRUNCATED_ENVELOPE_RE = /^\{\s*"([A-Za-z_]+)"\s*:\s*"/

/** Token bütçesi kesilen zarf: `{"content": "### Konu\n...` → `### Konu\n...` */
function truncatedEnvelopeMarkdown(text: string): string | null {
  const match = TRUNCATED_ENVELOPE_RE.exec(text)
  if (!match || !CONTENT_KEYS.includes(match[1].toLowerCase())) return null
  const body = text.slice(match[0].length).replace(/"\s*\}?\s*$/, '')
  return body.replace(/\\(.)/g, (_, char: string) => ESCAPE_MAP[char] ?? char).trim()
}

/** Metnin BAŞINDAKİ JSON değeri ve kalanı (yoksa null) — art arda nesneler için. */
function jsonPrefix(text: string): { value: unknown; rest: string } | null {
  const end = endOfJsonValue(text)
  if (end === -1) return null
  try {
    return { value: JSON.parse(text.slice(0, end)) as unknown, rest: text.slice(end) }
  } catch {
    return null
  }
}

/** İlk JSON değerinin bittiği indeks (dize/kaçış farkındalıklı tarayıcı). */
function endOfJsonValue(text: string): number {
  if (text[0] !== '{' && text[0] !== '[') return -1
  let depth = 0
  let inString = false
  let escaped = false
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i]
    if (inString) {
      if (escaped) escaped = false
      else if (char === '\\') escaped = true
      else if (char === '"') inString = false
      continue
    }
    if (char === '"') inString = true
    else if (char === '{' || char === '[') depth += 1
    else if (char === '}' || char === ']') {
      depth -= 1
      if (depth === 0) return i + 1
    }
  }
  return -1
}

/** Kod çiti gövdesi JSON mu? JSON ise markdown'ı, değilse null döner. */
function markdownFromJsonText(text: string): string | null {
  const body = text.trim()
  if (!body || (body[0] !== '{' && body[0] !== '[' && body[0] !== '"')) return null
  let value: unknown
  try {
    value = JSON.parse(body)
  } catch {
    return null
  }
  if (typeof value === 'string') return decodeEscapedText(value)
  return markdownFromJson(value)
}

/** JSON değerinden markdown çıkarır; içerik anahtarı yoksa boş string. */
function markdownFromJson(value: unknown, depth = 0): string {
  if (depth > MAX_DEPTH) return ''
  if (typeof value === 'string') {
    return looksLikeEnvelope(value.trim()) ? normalizeNoteMarkdown(value, depth + 1) : value
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => markdownFromJson(item, depth + 1))
      .filter((part) => part.trim())
      .join('\n\n')
  }
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>
    for (const key of CONTENT_KEYS) {
      if (key in record) {
        const inner = markdownFromJson(record[key], depth + 1)
        if (inner.trim()) return inner
      }
    }
    for (const key of LIST_KEYS) {
      if (Array.isArray(record[key])) {
        const inner = markdownFromJson(record[key], depth + 1)
        if (inner.trim()) return inner
      }
    }
  }
  return ''
}

/**
 * Kaçışlı metni çözer — ama YALNIZCA metinde gerçek satır sonu yoksa.
 * (json.loads zarf içini zaten çözer; bu, zarf dışı kalan `"### Konu\n..."` içindir.)
 */
function decodeEscapedText(text: string): string {
  const stripped = text.trim()
  if (stripped.length >= 2 && stripped.startsWith('"') && stripped.endsWith('"')) {
    try {
      const value = JSON.parse(stripped) as unknown
      if (typeof value === 'string') return value
    } catch {
      /* kaçışlı düz metin olarak devam */
    }
  }
  if (stripped.includes('\n') || !stripped.includes('\\n')) return stripped
  return stripped
    .replace(/\\u([0-9a-fA-F]{4})/g, (_, hex: string) => String.fromCharCode(parseInt(hex, 16)))
    .replace(/\\(.)/g, (_, char: string) => ESCAPE_MAP[char] ?? char)
}

/** Yinelenen ardışık başlıkları tekleştirir (zarf + başlık ekleme çakışması). */
function dedupeHeadings(text: string): string {
  const lines: string[] = []
  let lastHeading: string | null = null
  for (const line of text.split('\n')) {
    const stripped = line.trim()
    if (stripped && stripped === lastHeading) continue
    if (stripped) lastHeading = stripped.startsWith('#') ? stripped : null
    lines.push(line)
  }
  return lines.join('\n').trim()
}
