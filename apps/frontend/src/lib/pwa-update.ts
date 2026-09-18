import { toast } from '../stores/toastStore'

/**
 * PWA otomatik güncelleme (2026-09-18).
 *
 * Neden: `registerType: 'autoUpdate'` yalnızca yeni `sw.js`i kaydedip aktive
 * ediyordu; güncelleme denetimi sayfa açılışında bir kez yapılıyordu. Saatlerce
 * açık kalan sekme yeni deploy'u hiç görmüyor, kullanıcı Ctrl+Shift+R'a mahkûm
 * kalıyordu (raporda: prod'da ölçüldü).
 *
 * Davranış:
 *  - 60 sn'de bir + sekme öne geldiğinde (`visibilitychange`) `registration.update()`
 *  - Yeni service worker kontrolü devralınca (`controllerchange`) sayfa BİR KEZ
 *    kendini yeniler; form dolduruluyorsa sessizce yenilenmez — "Yeni sürüm hazır"
 *    bildirimi gösterilir, kararı kullanıcı verir (veri kaybı yok).
 *  - İlk kurulum yenileme sayılmaz (sayfa zaten denetimsizdi).
 */

/** Hangi build çalışıyor — vite.config.ts `define` ile gömülür, konsoldan okunur. */
export const DERLEME_KIMLIGI =
  typeof __STUHUB_BUILD__ === 'string' ? __STUHUB_BUILD__ : 'gelistirme'

if (typeof window !== 'undefined') window.__STUHUB_SURUM__ = DERLEME_KIMLIGI

const DENETIM_ARALIGI_MS = 60_000
/** Aynı oturumda 15 sn içinde ikinci yenileme isteği döngüdür — yok sayılır. */
const YENILEME_ESIGI_MS = 15_000
const YENILEME_ANAHTARI = 'stuhub-pwa-yenilendi'

/**
 * Kullanıcının yazmaya başladığı alanlar → odaklanma ANINDAKİ değer.
 *
 * `value !== defaultValue` işe yaramıyor: React kontrollü input'larda `value`
 * attribute'u güncel değerle senkron tutuluyor (ölçüldü 2026-09-18: yazılan
 * metin attribute'a da yazılıyor, `defaultValue` === `value`). Bu yüzden
 * referans değer odaklanma anında (yazmadan önce) alınır; kullanıcı alanı ilk
 * değerine döndürürse (sildi) karşılaştırma kendiliğinden eşitlenir.
 */
const odakAniDegerler = new WeakMap<Element, string>()

if (typeof document !== 'undefined') {
  document.addEventListener(
    'focusin',
    (olay) => {
      const alan = olay.target as HTMLElement | null
      if (alan && (alan.tagName === 'INPUT' || alan.tagName === 'TEXTAREA')) {
        odakAniDegerler.set(alan, (alan as HTMLInputElement | HTMLTextAreaElement).value)
      }
    },
    true,
  )
}

/**
 * Kullanıcının kaydedilmemiş girdisi var mı? Sessiz yenileme yalnızca bu false
 * iken yapılır; true ise "Yeni sürüm hazır" bildirimi gösterilir (kararı
 * kullanıcı verir — veri kaybı yok). Yanlış-pozitif (gereksiz bildirim)
 * zararsızdır, yanlış-negatif (sessiz reload) veri kaybettirir.
 */
export function kaydedilmemisGirdiVar(): boolean {
  const alanlar = document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>(
    'input, textarea',
  )
  for (const alan of alanlar) {
    const odakAni = odakAniDegerler.get(alan)
    if (odakAni !== undefined && alan.value !== odakAni) return true
  }
  return false
}

export function pwaGuncellemeyiBaslat(): void {
  // Geliştirmede service worker yok (devOptions kapalı) — kayıt denenmez.
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return

  // İlk devralma (denetimsiz → denetimli geçiş) güncelleme DEĞİLDİR: sayfa zaten
  // yeni. Ama bayrağı yine de güncelleriz — sabit kalsaydı, denetimsiz yüklenip
  // sonradan devralınan bir sayfa SONRAKİ hiçbir güncellemeyi görmezdi
  // (2026-09-18 ölçüldü: tam bu durumda 3 controllerchange yok sayıldı).
  let denetimAltinda = navigator.serviceWorker.controller !== null
  let bekleyenGuncelleme = false
  let yenileniyor = false

  const yenile = () => {
    if (yenileniyor) return
    yenileniyor = true
    try {
      sessionStorage.setItem(YENILEME_ANAHTARI, String(Date.now()))
    } catch {
      // Özel mod/engelli depolama: in-memory `yenileniyor` guard'ı yeterli.
    }
    window.location.reload()
  }

  const sonYenilemeZamani = () => {
    try {
      return Number(sessionStorage.getItem(YENILEME_ANAHTARI) ?? 0)
    } catch {
      return 0
    }
  }

  /** Yeni sürüm var: form temizse sessiz yenile, doluysa kullanıcıya sor. */
  const guncellemeUygula = () => {
    if (yenileniyor || bekleyenGuncelleme) return
    if (Date.now() - sonYenilemeZamani() < YENILEME_ESIGI_MS) return
    bekleyenGuncelleme = true
    if (kaydedilmemisGirdiVar()) {
      toast.info('Yeni sürüm hazır.', { label: 'Yenile', onClick: yenile })
      return
    }
    yenile()
  }

  /**
   * Asıl güncelleme sinyali: yayındaki build kimliği (`/version.json`, no-store)
   * bu sayfanın gömülü kimliğinden farklıysa yeni sürüm var demektir. Service
   * worker olaylarına (install/activate/claim) güvenmek yetersiz: 2026-09-18'de
   * ölçüldü — yeni SW aktive olup precache'i tazelediği HALDE sayfaya
   * `controllerchange` ulaşmadı ve sekme saatlerce eski sürümde kaldı. Kimlik
   * karşılaştırması deterministiktir; SW güncellemesi ayrıca tetiklenir ki
   * çevrimdışı kabuk da tazelensin.
   */
  const surumDenetle = async () => {
    try {
      const yanit = await fetch(`/version.json?t=${Date.now()}`, { cache: 'no-store' })
      if (!yanit.ok) return
      const { build } = (await yanit.json()) as { build?: string }
      if (build && build !== DERLEME_KIMLIGI) guncellemeUygula()
    } catch {
      // Ağ yok / bozuk yanıt — sonraki turda yeniden denenir.
    }
  }

  navigator.serviceWorker.addEventListener('controllerchange', () => {
    const kontrolde = navigator.serviceWorker.controller !== null
    if (!denetimAltinda) {
      // İlk devralma: taze sayfayı yenilemeye gerek yok, ama artık denetim altındayız.
      denetimAltinda = kontrolde
      return
    }
    if (!kontrolde) {
      denetimAltinda = false
      return
    }
    guncellemeUygula()
  })

  // Kayıt BİLEREK kendi elimizde: `virtual:pwa-register` (autoUpdate) yeni SW
  // aktive olur olmaz koşulsuz `window.location.reload()` çağırıyor ve buradaki
  // "form doluysa sessizce yenileme" kuralını deliyordu (2026-09-18 ölçüldü:
  // doldurulmuş form varken sayfa sessizce yenilendi, girilen veri gitti). Bu
  // yüzden vite.config.ts'te `injectRegister: null` — kayıt tek yerden, buradan.
  void navigator.serviceWorker
    .register('/sw.js', { scope: '/' })
    .then((kayit) => {
      const denetle = () => {
        if (!navigator.onLine) return
        void kayit.update().catch(() => {})
        void surumDenetle()
      }
      window.setInterval(denetle, DENETIM_ARALIGI_MS)
      void surumDenetle()
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState !== 'visible') return
        denetle()
        // Odak dönüşü = güvenli an: bekleyen güncelleme varsa ve form temizse
        // (kullanıcı sekmeden ayrılırken yazdıklarını bıraktıysa) şimdi uygula.
        if (bekleyenGuncelleme && !yenileniyor && !kaydedilmemisGirdiVar()) yenile()
      })
    })
    .catch(() => {
      // Kayıt başarısızsa uygulama normal çalışır; güncelleme denetimi yapılmaz
      // (F5 yolu zaten no-store başlıklarla taze içerik verir).
    })
}
