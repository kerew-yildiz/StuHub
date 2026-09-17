import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { setAccessToken } from './client'
import { downloadAuthed } from './exports'

/** İndirme yolu K5'te 401 dönüyordu: eski hâli `<a href>` gezinmesiyle indiriyordu ve
 * tarayıcı gezinmesi `Authorization: Bearer` başlığını hiç taşımıyordu. Bu test,
 * indirmenin `authFetch` üzerinden (yani başlıkla) gittiğini ve yanıt gövdesinin blob
 * olarak kaydedildiğini ölçer. */

type FetchCall = { url: string; init?: RequestInit }

/** `global.fetch`'i taklit eder; çağrıları kaydeder. */
function stubFetch(status = 200): FetchCall[] {
  const calls: FetchCall[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init })
      return new Response('not-test-md', { status })
    }),
  )
  return calls
}

/** `<a>` tıklamalarını yakalar (indirme linki DOM'a eklenmiyor). */
function stubLinkClicks(): HTMLAnchorElement[] {
  const clicked: HTMLAnchorElement[] = []
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    clicked.push(this)
  })
  return clicked
}

describe('downloadAuthed', () => {
  beforeEach(() => {
    // jsdom `URL.createObjectURL` uygulamıyor.
    URL.createObjectURL = vi.fn(() => 'blob:stuhub-test')
    URL.revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    setAccessToken(null)
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('isteği Authorization başlığıyla yapar ve yanıtı blob olarak indirir', async () => {
    const calls = stubFetch()
    const clicked = stubLinkClicks()
    setAccessToken('test-token')

    const ok = await downloadAuthed('/notes/7/export?format=md', 'stuhub-not-7.md')

    expect(ok).toBe(true)
    expect(calls).toHaveLength(1)
    expect(calls[0].url).toBe('/api/notes/7/export?format=md')
    expect(new Headers(calls[0].init?.headers).get('Authorization')).toBe('Bearer test-token')

    expect(clicked).toHaveLength(1)
    expect(clicked[0].download).toBe('stuhub-not-7.md')
    expect(clicked[0].href).toBe('blob:stuhub-test')
    expect(vi.mocked(URL.revokeObjectURL)).toHaveBeenCalledWith('blob:stuhub-test')
  })

  it('yanıt başarısızsa indirme başlatmaz ve false döner', async () => {
    stubFetch(500)
    const clicked = stubLinkClicks()
    setAccessToken('test-token')

    const ok = await downloadAuthed('/notes/7/export?format=md', 'stuhub-not-7.md')

    expect(ok).toBe(false)
    expect(clicked).toHaveLength(0)
  })
})
