import '@testing-library/jest-dom/vitest'

// jsdom SVG ölçüm API'lerini (getBBox, getComputedTextLength) uygulamıyor —
// Mermaid (kavram haritası render'ı) düzen hesabı için bunlara ihtiyaç duyuyor.
// `getBBox` gerçekte SVGGraphicsElement'te, `getComputedTextLength` SVGTextContentElement'te
// tanımlı (ikisi de SVGElement'in kendisinde değil) — TS bu yüzden okuma/yazmanın HER
// ikisinde de hata verir; satır bazlı `@ts-expect-error` okuma tarafını kaçırıyordu
// (CI'da yakalandı, yerel `npm test` tsc çalıştırmadığı için görünmüyordu). Tek bir
// `any` cast'i ile prototip'i bir kez gevşetmek, her erişimi ayrı ayrı susturmaktan
// daha güvenilir.
if (typeof SVGElement !== 'undefined') {
  const proto = SVGElement.prototype as unknown as {
    getBBox?: () => DOMRect
    getComputedTextLength?: () => number
  }
  if (!proto.getBBox) {
    proto.getBBox = () =>
      ({ x: 0, y: 0, width: 100, height: 20, top: 0, right: 0, bottom: 0, left: 0, toJSON: () => '' }) as DOMRect
  }
  if (!proto.getComputedTextLength) {
    proto.getComputedTextLength = () => 60
  }
}
