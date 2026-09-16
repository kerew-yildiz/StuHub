import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type * as ApiClient from '../api/client'

import { authFetch } from '../api/client'
import { FilePreviewModal } from './FilePreviewModal'

vi.mock('../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof ApiClient>()),
  authFetch: vi.fn(),
}))

const pdfBlob = new Blob(['%PDF-1.4 önizleme içeriği'], { type: 'application/pdf' })

/** `authFetch` ham `Response` döner; test için yalnızca kullanılan alanlar taklit edilir. */
const okYanit = () => ({ ok: true, status: 200, blob: async () => pdfBlob }) as unknown as Response
const bulunamadiYaniti = () => ({ ok: false, status: 404 }) as unknown as Response

const BLOB_URL = 'blob:http://localhost:5173/test-onizleme'

/** jsdom `URL.createObjectURL` uygulamaz — önizleme nesne URL yaşam döngüsü elle izlenir. */
let olusturulanUrlSayisi = 0
const revokedUrls: string[] = []

beforeEach(() => {
  olusturulanUrlSayisi = 0
  revokedUrls.length = 0
  URL.createObjectURL = () => {
    olusturulanUrlSayisi += 1
    return BLOB_URL
  }
  URL.revokeObjectURL = (url: string) => {
    revokedUrls.push(url)
  }
})

afterEach(() => {
  cleanup()
  vi.mocked(authFetch).mockReset()
})

describe('FilePreviewModal', () => {
  it('404 yanıtında "Dosya sunucuda bulunamadı." mesajını gösterir', async () => {
    vi.mocked(authFetch).mockResolvedValue(bulunamadiYaniti())
    render(<FilePreviewModal path="/materials/39/file" title="stuhub-not-5.pdf" onClose={() => {}} />)

    expect(await screen.findByText('Dosya sunucuda bulunamadı.')).toBeInTheDocument()
    // Hata yolunda içerik indirilmez; boş/ölü iframe yerine yalnızca mesaj kalır.
    expect(screen.queryByTitle('stuhub-not-5.pdf')).not.toBeInTheDocument()
    expect(olusturulanUrlSayisi).toBe(0)
  })

  it('başarılı yanıtta blob URL iframe src olur ve içerik kaldırılmadan revoke edilmez', async () => {
    vi.mocked(authFetch).mockResolvedValue(okYanit())
    const { unmount } = render(
      <FilePreviewModal path="/materials/5/file" title="kitap.pdf" onClose={() => {}} />,
    )

    const cerceve = await screen.findByTitle('kitap.pdf')
    expect(olusturulanUrlSayisi).toBe(1)
    expect(cerceve).toHaveAttribute('src', BLOB_URL)
    // İçerik iframe'de dururken nesne URL'i serbest bırakılırsa tarayıcı yüklemeyi
    // iptal eder (blob: isteği net::ERR_ABORTED) — revoke YALNIZCA kapanışta olmalı.
    expect(revokedUrls).toEqual([])

    unmount()
    expect(revokedUrls).toEqual([BLOB_URL])
  })
})
