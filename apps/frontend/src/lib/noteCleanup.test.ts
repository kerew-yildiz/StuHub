import { describe, expect, it } from 'vitest'

import { normalizeNoteMarkdown } from './noteCleanup'

const BROKEN_RAW = `### Çocuk Gelişimine Giriş ve Tanımı

\`\`\`json
{
  "content": "### Çocuk Gelişimine Giriş ve Tanımı\\n\\nÇocuk gelişimi, biyolojik ve sosyal değişimleri inceler [1].\\n\\n**Temel Kavramlar:**\\n* Gelişim çok boyutludur [1]."
}
\`\`\`

### Psikodinamik Kuramın Temelleri

\`\`\`json
{"content": "### Psikodinamik Kuramın Temelleri\\n\\nBilinçdışı süreçler davranışı etkiler [2]."}
\`\`\`

### Freud'un Evreleri

* Erojen bölgeler vardır [3].

\`\`\`json
{
  "topic": "Freud",
  "summary": "Özet metni",
  "stages_count": 5
}
\`\`\``

describe('normalizeNoteMarkdown', () => {
  it('çitli tek JSON nesnesini açar', () => {
    const out = normalizeNoteMarkdown(
      '```json\n{"content": "### Konu A\\n\\nBağlı listeler doğrusaldır [1].\\n"}\n```',
    )
    expect(out).toBe('### Konu A\n\nBağlı listeler doğrusaldır [1].')
  })

  it('art arda gelen üç nesneyi birleştirir', () => {
    const out = normalizeNoteMarkdown(
      '```json\n{"content": "### Konu A\\n\\nBirinci [1]."}\n```\n\n' +
        '{"content": "### Konu B\\n\\nİkinci [2]."}\n\n' +
        '```json\n{"content": "### Konu C\\n\\nÜçüncü [3]."}\n```',
    )
    expect(out.split('\n\n')).toEqual([
      '### Konu A',
      'Birinci [1].',
      '### Konu B',
      'İkinci [2].',
      '### Konu C',
      'Üçüncü [3].',
    ])
  })

  it('çitsiz düz markdown değişmeden geçer', () => {
    const raw = '### Konu A\n\n**Temel Kavramlar:**\n* Düğümler işaretçi taşır [1].\n'
    expect(normalizeNoteMarkdown(raw)).toBe(raw.trim())
  })

  it('kaçışlı satır sonlarını çözer', () => {
    expect(normalizeNoteMarkdown('{"content": "### Konu\\n\\nSatır bir.\\nSatır iki [2]."}')).toBe(
      '### Konu\n\nSatır bir.\nSatır iki [2].',
    )
  })

  it('sitasyonları korur', () => {
    const out = normalizeNoteMarkdown(
      '```json\n{"content": "### Konu A\\n\\nBilgi [3].\\n\\nDış [kaynak](stuhub-citation://3)."}\n```',
    )
    expect(out).toContain('[3]')
    expect(out).toContain('[kaynak](stuhub-citation://3)')
  })

  it('JSON olmayan kod çitini korur', () => {
    const raw = '### Konu A\n\n```python\nprint("merhaba")\n```'
    expect(normalizeNoteMarkdown(raw)).toBe(raw)
  })

  it('içerik anahtarı olmayan şema dökümünü düşürür', () => {
    expect(normalizeNoteMarkdown('{"topic": "Freud", "summary": "Özet"}')).toBe('')
  })

  it('kesik zarfı kurtarır', () => {
    expect(
      normalizeNoteMarkdown('```json\n{"content": "### Konu A\\n\\nToken bütçesi kesildi'),
    ).toBe('### Konu A\n\nToken bütçesi kesildi')
  })

  it('kullanıcının ekranındaki ham içeriği düzgün markdown yapar', () => {
    const out = normalizeNoteMarkdown(BROKEN_RAW)
    expect(out).not.toContain('```')
    expect(out).not.toContain('"content"')
    expect(out).not.toContain('\\n')
    expect(out.startsWith('### Çocuk Gelişimine Giriş ve Tanımı\n\nÇocuk gelişimi,')).toBe(true)
    expect(out).toContain('**Temel Kavramlar:**')
    expect(out).toContain('[1]')
    // Bölüm başlıkları tekilleşir, şema dökümü eklenmez
    expect(out.match(/^### /gm)).toHaveLength(3)
    expect(out).not.toContain('stages_count')
  })

  it('boş girdide çökmez', () => {
    expect(normalizeNoteMarkdown('')).toBe('')
  })

  it('cümleye yapışmış başlığı ayırır', () => {
    const raw = '### Konu A\n\nBir bilgi [2].### Konu B\n\nİkinci bilgi [1].'
    expect(normalizeNoteMarkdown(raw)).toBe(
      '### Konu A\n\nBir bilgi [2].\n\n### Konu B\n\nİkinci bilgi [1].',
    )
  })

  it('metin içi # işaretine dokunmaz', () => {
    const raw = '### Konu A\n\nC# dili ve https://x.dev/a#bolum bağlantısı.'
    expect(normalizeNoteMarkdown(raw)).toBe(raw)
  })
})
