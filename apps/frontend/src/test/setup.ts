import '@testing-library/jest-dom/vitest'

// jsdom SVG ölçüm API'lerini (getBBox, getComputedTextLength) uygulamıyor —
// Mermaid (kavram haritası render'ı) düzen hesabı için bunlara ihtiyaç duyuyor.
if (typeof SVGElement !== 'undefined') {
  if (!SVGElement.prototype.getBBox) {
    SVGElement.prototype.getBBox = () => ({ x: 0, y: 0, width: 100, height: 20, top: 0, right: 0, bottom: 0, left: 0, toJSON: () => '' })
  }
  if (!SVGElement.prototype.getComputedTextLength) {
    // @ts-expect-error — jsdom eksik SVG API polyfill'i, sadece test ortamı için.
    SVGElement.prototype.getComputedTextLength = () => 60
  }
}
