/// <reference types="node" />
// @vitest-environment node

import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { BACKGROUND_VALUES, DEFAULT_BACKGROUND, isBackgroundValue } from './personalization'

/** Katalog elle uc yere yazilir: deger listesi (personalization.ts), katman kurali
 * (styles/personalization.css) ve gorsel dosyasi (public/bg). Ucunden biri eksik kalirsa
 * secim sessizce varsayilan arkaplanda kalir — bu test o kaymayi yakalar. */

const css = readFileSync(fileURLToPath(new URL('../styles/personalization.css', import.meta.url)), 'utf8')

/** `html[data-stuhub-bg='<deger>'] body { ... }` kural govdesi. */
function ruleFor(value: string): string | undefined {
  return css.match(new RegExp(`html\\[data-stuhub-bg='${value}'\\] body \\{[^}]*\\}`))?.[0]
}

/** `html[data-theme='light'][data-stuhub-bg='<deger>'] body { ... }` kural govdesi. */
function lightRuleFor(value: string): string | undefined {
  return css.match(new RegExp(`html\\[data-theme='light'\\]\\[data-stuhub-bg='${value}'\\] body \\{[^}]*\\}`))?.[0]
}

describe('arkaplan katalogu', () => {
  it('varsayilan arkaplan katalogda tanimli', () => {
    expect(BACKGROUND_VALUES).toContain(DEFAULT_BACKGROUND)
    expect(isBackgroundValue(DEFAULT_BACKGROUND)).toBe(true)
  })

  it('bilinmeyen deger reddedilir', () => {
    expect(isBackgroundValue('yok-boyle-arkaplan')).toBe(false)
    expect(isBackgroundValue(undefined)).toBe(false)
  })

  it.each(BACKGROUND_VALUES)('%s: kural + /bg/<deger>.(jpg|png) gorseli tamam', (value) => {
    const rule = ruleFor(value)
    expect(rule).toBeTruthy()
    const asset = rule?.match(/url\("(\/bg\/[^"]+)"\)/)?.[1]
    expect(asset).toMatch(new RegExp(`^/bg/${value}\\.(jpg|png)$`))
    expect(existsSync(fileURLToPath(new URL(`../../public${asset}`, import.meta.url)))).toBe(true)
  })

  it.each(BACKGROUND_VALUES)('%s: acik tema kurali + /bg/<deger>-light.jpg gorseli tamam', (value) => {
    const rule = lightRuleFor(value)
    expect(rule).toBeTruthy()
    const asset = rule?.match(/url\("(\/bg\/[^"]+)"\)/)?.[1]
    expect(asset).toBe(`/bg/${value}-light.jpg`)
    expect(existsSync(fileURLToPath(new URL(`../../public${asset}`, import.meta.url)))).toBe(true)
  })

  it('acik tema zemin+perde tek parlaklik dugmesinden turer (theme.css)', () => {
    const tema = readFileSync(fileURLToPath(new URL('../styles/theme.css', import.meta.url)), 'utf8')
    const acikBlok = tema.match(/:root\[data-theme='light'\] \{[\s\S]*?\n\}/)?.[0] ?? ''

    // Tek dugme: --stuhub-light-ton. Zemin, perde ve vinyet bu tondan uretilir.
    expect(acikBlok).toMatch(/--stuhub-light-ton:\s*\d+ \d+ \d+;/)
    expect(acikBlok).toContain('--stuhub-bg: rgb(var(--stuhub-light-ton));')
    expect(acikBlok).toContain('--bg-curtain: linear-gradient(rgb(var(--stuhub-light-ton) / .78), rgb(var(--stuhub-light-ton) / .78));')
    // Karanlik tema kutuplari dokunulmamis olmali.
    expect(tema).toContain('--bg-curtain: linear-gradient(rgba(0,0,0,.78), rgba(0,0,0,.78));')
    expect(tema).toContain('--bg-image: url("/bg/calisma-masasi-light.jpg");')
  })
})
