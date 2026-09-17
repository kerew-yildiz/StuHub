/**
 * Rehberli turun dışa açık API'si.
 *
 * Başka ekiplerin/bileşenlerin kullanacağı yüzey BURASIDIR — turun iç
 * dosyalarına (store/overlay) doğrudan bağlanmak yerine bu modülü import et:
 *
 *   import { startHelpTour } from '../tour'
 *   <button onClick={startHelpTour}>Adım adım turu başlat</button>
 *
 * `startHelpTour()` aktif rotaya göre katmanı kendi seçer; çağıran taraf turun
 * nerede render edildiğini bilmez. Tur kapalıysa `stopHelpTour()` no-op'tur.
 */
export { startHelpTour, stopHelpTour, useHelpTourOpen } from './tourStore'
export { layerFromPath, type TourLayer } from './steps'
