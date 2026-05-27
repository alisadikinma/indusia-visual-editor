import { describe, expect, it } from 'vitest'
import tailwindConfig from '../../../tailwind.config'

const ext = (tailwindConfig.theme?.extend ?? {}) as Record<string, any>

describe('Tailwind tokens — Figma Foundations sync', () => {
  it('keeps Geist as the sans family (plan §guards overrides Figma "Inter" copy)', () => {
    const sans = ext.fontFamily?.sans as string[]
    expect(Array.isArray(sans)).toBe(true)
    expect(sans.some((f) => /Geist/i.test(f))).toBe(true)
    expect(sans.some((f) => /Inter/i.test(f))).toBe(false)
  })

  it('keeps Geist Mono as the mono family', () => {
    const mono = ext.fontFamily?.mono as string[]
    expect(Array.isArray(mono)).toBe(true)
    expect(mono.some((f) => /Geist Mono/i.test(f))).toBe(true)
  })

  it('preserves emerald-500 at #10b981 (primary ramp anchor)', () => {
    expect(ext.colors.primary['500'].toLowerCase()).toBe('#10b981')
  })

  it('exposes Figma semantic surface tokens (canvas/raised/sunken/inverse/overlay)', () => {
    const s = ext.colors.surface
    expect(s).toBeDefined()
    expect(s.canvas).toMatch(/^#|rgb/)
    expect(s.raised).toMatch(/^#|rgb/)
    expect(s.sunken).toMatch(/^#|rgb/)
    expect(s.inverse).toMatch(/^#|rgb/)
    expect(s.overlay).toMatch(/^#|rgb/)
  })

  it('exposes Figma semantic text tokens (primary/secondary/tertiary/inverse/onPrimary)', () => {
    const t = ext.colors.text
    expect(t).toBeDefined()
    expect(t.primary).toBeDefined()
    expect(t.secondary).toBeDefined()
    expect(t.tertiary).toBeDefined()
    expect(t.inverse).toBeDefined()
    expect(t.onPrimary).toBeDefined()
  })

  it('exposes Figma semantic border tokens (subtle/default/strong/focus)', () => {
    const b = ext.colors.border
    expect(b).toBeDefined()
    expect(b.subtle).toBeDefined()
    expect(b.default).toBeDefined()
    expect(b.strong).toBeDefined()
    expect(b.focus).toBeDefined()
  })

  it('extends primary ramp with semantic states (base/hover/pressed/subtle)', () => {
    const p = ext.colors.primary
    expect(p.base.toLowerCase()).toBe('#10b981')
    expect(p.hover.toLowerCase()).toBe('#059669')
    expect(p.pressed.toLowerCase()).toBe('#047857')
    expect(p.subtle.toLowerCase()).toBe('#ecfdf5')
  })

  it('exposes Figma status semantic tokens (success/warning/danger/info/neutral base+subtle)', () => {
    const c = ext.colors as Record<string, any>
    for (const status of ['success', 'warning', 'danger', 'info'] as const) {
      // existing flat tokens kept for back-compat
      expect(c[status]).toBeDefined()
    }
    // new namespaced status object exposes base+subtle per Figma
    expect(c.status).toBeDefined()
    expect(c.status.success.base).toBeDefined()
    expect(c.status.success.subtle).toBeDefined()
    expect(c.status.warning.base).toBeDefined()
    expect(c.status.warning.subtle).toBeDefined()
    expect(c.status.danger.base).toBeDefined()
    expect(c.status.danger.subtle).toBeDefined()
    expect(c.status.info.base).toBeDefined()
    expect(c.status.info.subtle).toBeDefined()
    expect(c.status.neutral.base).toBeDefined()
    expect(c.status.neutral.subtle).toBeDefined()
  })

  it('preserves the existing borderRadius scale (no breaking shift for current rounded-* call sites)', () => {
    const r = ext.borderRadius
    expect(r.sm).toBe('4px')
    expect(r.md).toBe('6px')
    expect(r.lg).toBe('8px')
    expect(r.xl).toBe('12px')
    expect(r['2xl']).toBe('16px')
  })
})
