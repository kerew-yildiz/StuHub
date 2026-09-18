import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { kaydedilmemisGirdiVar } from './pwa-update'

/**
 * pwa-update.ts — kaydedilmemiş girdi tespiti (2 katman).
 *
 * Katman 1: odak-anı referansı (focusin + açılış seed'i). Katman 2: haritada
 * kaydı olmayan DOLU alan da "kaydedilmemiş girdi" sayılır (yanlış-pozitif
 * zararsız — bildirim çıkar; yanlış-negatif sessiz reload = veri kaybı).
 *
 * Regresyon bağlamı (2026-09-18 canlı deney): giriş ekranının ilk odaklanabilir
 * elemanı (e-posta) sayfa yüklenince odaklı; kullanıcı yazarken focusin
 * üretilmez → katman 1 bu alanı hiç göremiyor ve form dolu olduğu halde sayfa
 * sessizce yenileniyordu (veri kaybı). Katman 2 bu kör noktayı kapatır.
 */

function inputYap(deger: string): HTMLInputElement {
  const el = document.createElement('input')
  el.value = deger
  document.body.appendChild(el)
  return el
}

describe('kaydedilmemisGirdiVar — form doluysa sessiz yenileme engellenir', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('boş sayfada false döner (sessiz yenilemeye izin verilir)', () => {
    expect(kaydedilmemisGirdiVar()).toBe(false)
  })

  it('odaklanıp yazılan alan (odak-anı referansı boş) değiştiyse true döner', () => {
    const el = inputYap('')
    // Gerçek kullanıcı akışı: focusin önce gelir (referans = odak anındaki değer),
    // sonra kullanıcı yazar.
    el.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
    el.value = 'yazilan@ornek.dev'
    expect(kaydedilmemisGirdiVar()).toBe(true)
  })

  it('REGRESYON: focusin hiç yakalanmayan (erken-odaklı) DOLU alan true döner', () => {
    // Giriş ekranı senaryosu: alan zaten odaklıydı, focusin üretilemedi, ama
    // kullanıcı yazdı → WeakMap'te kaydı yok, değeri dolu.
    inputYap('yazilan@ornek.dev')
    // focusin dispatch EDİLMEDİ — katman 1 kör, katman 2 konuşmalı.
    expect(kaydedilmemisGirdiVar()).toBe(true)
  })

  it('REGRESYON: focusin yakalanmayan BOŞ alan false döner (gereksiz bildirim yok)', () => {
    inputYap('')
    expect(kaydedilmemisGirdiVar()).toBe(false)
  })

  it('kullanıcı yazdığını silerse (ilk değerine dönerse) false döner', () => {
    const el = inputYap('')
    el.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
    el.value = 'bir seyler'
    expect(kaydedilmemisGirdiVar()).toBe(true)
    el.value = ''
    expect(kaydedilmemisGirdiVar()).toBe(false)
  })

  it('textarea da kapsanır (erken-odaklı dolu textarea true döner)', () => {
    const ta = document.createElement('textarea')
    ta.value = 'uzun not metni'
    document.body.appendChild(ta)
    expect(kaydedilmemisGirdiVar()).toBe(true)
  })

  it('bir alan dolu, diğeri temizse true döner (herhangi biri yeter)', () => {
    inputYap('')
    inputYap('dolu')
    expect(kaydedilmemisGirdiVar()).toBe(true)
  })
})
