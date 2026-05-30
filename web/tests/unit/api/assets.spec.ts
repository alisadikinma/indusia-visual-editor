import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { getAssetQc, getRegistrationPreflight } from '@/api/assets'

const env = <T>(data: T) => ({ status: true, message: 'ok', data })

describe('assets api — golden QC (T6)', () => {
  it('getAssetQc returns the parsed QC verdict', async () => {
    server.use(
      http.get('/api/projects/:id/assets/:assetId/qc', () =>
        HttpResponse.json(
          env({
            verdict: 'warn',
            reasons: ['blur_warn'],
            sharpness: 95.2,
            mean_luminance: 140.0,
            clipped_dark: 0.03,
            clipped_bright: 0.04,
          }),
        ),
      ),
    )
    const qc = await getAssetQc('proj-1', 'asset-9')
    expect(qc.verdict).toBe('warn')
    expect(qc.reasons).toContain('blur_warn')
    expect(qc.sharpness).toBeCloseTo(95.2)
  })

  it('getRegistrationPreflight returns the parsed verdict + metrics', async () => {
    server.use(
      http.get('/api/projects/:id/registration-preflight', () =>
        HttpResponse.json(
          env({
            verdict: 'ok',
            reasons: [],
            per_image: [{ keypoints: 412, ok: true }],
            pairwise_residual_px: null,
            sample_count: 1,
          }),
        ),
      ),
    )
    const reg = await getRegistrationPreflight('proj-1', 'top')
    expect(reg.verdict).toBe('ok')
    expect(reg.per_image[0].keypoints).toBe(412)
    expect(reg.sample_count).toBe(1)
  })
})
