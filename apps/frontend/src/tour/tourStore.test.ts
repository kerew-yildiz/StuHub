import { afterEach, describe, expect, it } from 'vitest'

import { layerFromPath } from './steps'
import { startHelpTour, stopHelpTour, useTourStore } from './tourStore'

/**
 * Dışa açık tur API'si (startHelpTour) sözleşmesi: başka ekiplerin butonu bu
 * fonksiyona bağlanır. İki garanti: (a) rota → katman eşlemesi, (b) API
 * çağrısı turu açar/kapatır ve katmanı çağıranın bilmesine gerek kalmaz.
 */
describe('startHelpTour', () => {
  afterEach(() => stopHelpTour())

  it('katmanı aktif rotadan türetir', () => {
    expect(layerFromPath('/')).toBe('global')
    expect(layerFromPath('/takvim')).toBe('global')
    expect(layerFromPath('/donemler/12')).toBe('term')
    expect(layerFromPath('/dersler/7')).toBe('course')
    expect(layerFromPath('/dersler/7/defter/3')).toBe('chapter')
  })

  it('turu açar ve kapatır (kapatma hedef rota işaretini de temizler)', () => {
    startHelpTour()
    expect(useTourStore.getState().open).toBe(true)
    expect(useTourStore.getState().layer).toBe('global')

    useTourStore.getState().hedefRotaAyarla('/donemler')
    stopHelpTour()

    expect(useTourStore.getState().open).toBe(false)
    expect(useTourStore.getState().hedefRota).toBeNull()
  })
})
