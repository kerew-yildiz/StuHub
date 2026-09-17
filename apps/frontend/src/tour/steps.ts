/**
 * Layer-aware tour step registry (yönerge §18-24).
 *
 * Her step gerçek bir DOM anchor'ına işaret eder (`data-tour-id` attribute'u
 * component'lerde tanımlı). `why` alanı özelliğin NEDEN var olduğunu açıklar —
 * yalnızca adlandırma değil (§97 kalite barı).
 *
 * Step yalnızca anchor'ı bulunuyorsa gösterilir (çakışmayan/eksik adımlar atlanır).
 */

export type TourLayer = 'global' | 'term' | 'course' | 'chapter'

export interface TourStep {
  id: string
  /** data-tour-id değeri — bulunamazsa adım atlanır. */
  anchor?: string
  title: string
  body: string
  /** Yönlendirme yoksa o adımda görünen buton metni. */
  actionLabel: string
  /** Rota adımı: anchor'ı başka bir sayfada olan adım için gidilecek rota.
   * Anchor yoksa adım spotlightsız (ortada popover) gösterilir — anlatı
   * kaybolmaz, kullanıcı rotaya taşınır. */
  route?: string
}

/** Rota → tur katmanı eşlemesi. Katman, adım kayıt defterinin hangi bölümünün
 * oynayacağını belirler; başlangıçta (startHelpTour) ve rota değişiminde
 * aynı fonksiyon kullanılır — iki yerde ayrışamaz. */
export function layerFromPath(pathname: string): TourLayer {
  if (/^\/dersler\/\d+\/defter\/\d+/.test(pathname)) return 'chapter'
  if (/^\/dersler\/\d+/.test(pathname)) return 'course'
  if (/^\/donemler\/\d+/.test(pathname)) return 'term'
  return 'global'
}

export const TOUR_STEP_TITLES: Record<TourLayer, string> = {
  global: 'StuHub Turu — Genel',
  term: 'StuHub Turu — Dönem',
  course: 'StuHub Turu — Ders',
  chapter: 'StuHub Turu — Chapter',
}

export const TOUR_STEPS: Record<TourLayer, TourStep[]> = {
  global: [
    {
      id: 'g-sidebar',
      anchor: 'global-search',
      title: 'Sidebar ve arama',
      body: 'Sidebar StuHub\'ın ana navigasyon yüzeyidir — breadcrumb yok. Üzerine gelince açılır; içinde bulunduğun katmana göre (genel/dönem/ders/chapter) menü içeriği değişir. Sol üstteki arama Ctrl/Cmd+K ile de açılır.',
      actionLabel: 'İleri',
    },
    {
      id: 'g-tour',
      anchor: 'help-button',
      title: 'Yardım ve tur',
      body: 'Bu turu her katmanda tekrar başlatabilirsin. Aranabilir yardım içeriği de buraya komşudur.',
      actionLabel: 'İleri',
    },
    {
      id: 'g-notifications',
      anchor: 'notification-button',
      title: 'Bildirimler',
      body: 'Üretim işleri (not, quiz, kart) bittiğinde veya hata verdiğinde buradan haberdar olursun — sayfada beklemene gerek yok.',
      actionLabel: 'İleri',
    },
    {
      id: 'g-fullscreen',
      anchor: 'browser-fullscreen-button',
      title: 'Tam ekran',
      body: 'Tarayıcının F11 davranışı gibi çalışır: tarayıcı çubuğunu gizler. Not: çalışma alanı (workspace) tam ekranı farklıdır ve özelliğin kendi kontrolünden yönetilir.',
      actionLabel: 'İleri',
    },
    {
      id: 'g-profile',
      anchor: 'profile-trigger',
      title: 'Hesabın',
      body: 'Profil kontrolü header\'da değil, sidebar\'ın altındadır: hesap kartı, ayarlar ve çıkış buradan.',
      actionLabel: 'İleri',
    },
    {
      // Rota adımı: tur burada bitmez, kullanıcıyı gerçek bir sayfaya taşır —
      // "?" turu her katmanda o katmanın adımlarını gösterir (dönem/ders/chapter).
      id: 'g-rotalar',
      route: '/donemler',
      title: 'Sıra dönemlerinde',
      body: 'Tur bitti. Şimdi dönemlerine geç: bir dönemi aç, ders kartına gir ve aynı "?" turunu orada başlat — adımlar bulunduğun katmana göre değişir.',
      actionLabel: 'Turu bitir',
    },
  ],
  term: [
    {
      id: 't-summary',
      anchor: 'term-overview',
      title: 'Dönem Özeti',
      body: 'Dönemin derslerini, yaklaşan sınav ve ödevlerini ve son etkinliklerini tek bakışta görürsün. Dönem bir ilerleme göstergesi taşımaz — dersler ilerlemeyi taşır.',
      actionLabel: 'İleri',
    },
    {
      id: 't-courses',
      anchor: 'term-courses',
      title: 'Dersler',
      body: 'Kart üzerine gelince son aktivite, toplam çalışma ve tamamlanan chapter sayısı sırayla döner — açmadan önce ne üzerinde kaldığını hatırlaman için.',
      actionLabel: 'İleri',
    },
    {
      id: 't-calendar',
      anchor: 'sidebar-calendar',
      title: 'Takvim ve Sınav Planı',
      body: 'Sınav ve ödev tarihleri dönem bağlamında buradan yönetilir; geri sayımlar çalışma planını besler.',
      actionLabel: 'İleri',
    },
  ],
  course: [
    {
      id: 'c-progress',
      anchor: 'course-progress',
      title: 'Ders ilerlemesi',
      body: 'Tamamlanan chapter oranı — öğrenme sinyallerin (doğru quiz cevapları, tutulan kart tekrarları) üzerinden hesaplanır.',
      actionLabel: 'İleri',
    },
    {
      id: 'c-mistakes',
      anchor: 'course-mistakes',
      title: 'Hatalarım',
      body: 'Tüm quiz türlerinde yanlış cevapladığın sorular burada birikir. En yenisi üstte; aynı konuda tekrarlanan hatalar öncelikli çalışma sinyalidir.',
      actionLabel: 'İleri',
    },
    {
      id: 'c-weak',
      anchor: 'course-weak-topics',
      title: 'Zayıf Konular',
      body: 'Hata geçmişin ısı haritasına dönüşür: hangi konuda daha çok zaman ayırman gerektiğini görmek için.',
      actionLabel: 'İleri',
    },
    {
      id: 'c-notes',
      anchor: 'sidebar-course-notes',
      title: 'Notlar',
      body: 'Ders görünümünde notlar chapter\'a göre gruplanır; her chapter\'ın kendi çalışma alanına kısayoldur.',
      actionLabel: 'İleri',
    },
    {
      id: 'c-saved',
      anchor: 'sidebar-course-saved',
      title: 'Kaydedilenler',
      body: 'Kaydırarak Quiz\'de kaydettiğin sorular yalnızca burada toplanır — tekrar gözden geçirmek için.',
      actionLabel: 'İleri',
    },
    {
      id: 'c-swipe',
      anchor: 'sidebar-course-swipe',
      title: 'Kaydırarak Quiz',
      body: 'Ders seviyesinde çalışır: tüm chapter\'lardan karışık sorularla sosyal akış gibi ilerlersin. Kaydetmek istediğin soruyu işaretleyebilirsin.',
      actionLabel: 'İleri',
    },
    {
      id: 'c-flashcards',
      anchor: 'sidebar-course-flashcards',
      title: 'Flashcard Practice',
      body: 'Ders görünümünde chapter\'a göre gruplu kart setleri; chapter görünümünde ise doğrudan o chapter\'ın listesi gelir.',
      actionLabel: 'İleri',
    },
    {
      id: 'c-ask',
      anchor: 'sidebar-course-ask',
      title: 'Materyale Sor',
      body: 'Yüklediğin kitap/sunuma kaynak atıflı soru sorarsın — yanıtın hangi sayfadan geldiği gösterilir.',
      actionLabel: 'İleri',
    },
    {
      id: 'c-assignments',
      anchor: 'sidebar-course-assignments',
      title: 'Ödevler',
      body: 'Ödev Değerlendir bitmiş metni puanlar; Taslak Koçu teslimden ÖNCE yön verir — ikisi farklı amaçlara hizmet eder.',
      actionLabel: 'İleri',
    },
  ],
  chapter: [
    {
      id: 'ch-progress',
      anchor: 'chapter-progress',
      title: 'Chapter ilerlemesi',
      body: 'Tamamlanan konu oranı: doğru quiz cevapları ve tutulan kart tekrarları konu tamamlandığına dair sinyal sayılır.',
      actionLabel: 'İleri',
    },
    {
      id: 'ch-mistakes',
      anchor: 'chapter-mistakes',
      title: 'Hatalarım',
      body: 'Bu chapter\'da yanlış yaptığın sorular — quizden hemen sonra nereye döneceğini bilmen için en üstte.',
      actionLabel: 'İleri',
    },
    {
      id: 'ch-missing',
      anchor: 'chapter-missing-topics',
      title: 'Eksik Konular',
      body: 'Henüz yeterli öğrenme sinyali toplamamış konular. Chapter Content bir konu listesi değil, öğrenme bağlamıdır: bu liste neyi henüz oturtamadığını gösterir.',
      actionLabel: 'İleri',
    },
    {
      id: 'ch-content',
      anchor: 'chapter-content',
      title: 'Chapter Content',
      body: 'Konu navigasyonu değildir — bu chapter\'ın öğrenme bağlamıdır: notu, kartları ve quiz\'i bağlar. Konular yalnızca bağlam içinde anlamlıdır.',
      actionLabel: 'İleri',
    },
    {
      id: 'ch-notes',
      anchor: 'sidebar-chapter-notes',
      title: 'Notlar',
      body: 'Bu chapter\'ın notu — düzenleme ve silme kartın üzerinde, dikey liste en eskiden yeniye.',
      actionLabel: 'İleri',
    },
    {
      id: 'ch-quiz',
      anchor: 'sidebar-chapter-quiz',
      title: 'Quiz',
      body: 'Normal quiz yalnızca chapter seviyesinde vardır: listeye tıklayarak çözersin; listeye "+ Quiz Oluştur" ile yenisi eklenir.',
      actionLabel: 'İleri',
    },
    {
      id: 'ch-flashcards',
      anchor: 'sidebar-chapter-flashcards',
      title: 'Flashcard Practice',
      body: 'Bu chapter\'ın kart setleri — tekrar zamanı gelen kartlar öne alınır.',
      actionLabel: 'İleri',
    },
    {
      id: 'ch-ask',
      anchor: 'sidebar-chapter-ask',
      title: 'Materyale Sor',
      body: 'Sorular bu chapter\'ın bağlamına odaklanır — ders genelinde sormak için ders görünümünü kullan.',
      actionLabel: 'Başla',
    },
  ],
}
