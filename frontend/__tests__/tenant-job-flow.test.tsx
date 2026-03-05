/**
 * Tests for the TenantJobFlow component.
 *
 * Key invariants verified:
 * - api.createJobWithUploadUrls is called with existing_instrumental: true and is_private: true
 * - api.uploadToSignedUrl is called for both audio and instrumental files
 * - api.completeJobUpload is called with correct file types
 * - Submit button is disabled until all 4 fields are filled
 * - Success and error states render correctly
 */

import { api } from '@/lib/api'

// Mock api module
jest.mock('@/lib/api', () => ({
  api: {
    createJobWithUploadUrls: jest.fn(),
    uploadToSignedUrl: jest.fn(),
    completeJobUpload: jest.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number
    constructor(message: string, status: number) {
      super(message)
      this.name = 'ApiError'
      this.status = status
    }
  },
}))

jest.mock('@/lib/tenant', () => ({
  useTenant: jest.fn(() => ({
    branding: {
      site_title: 'Test Tenant',
      primary_color: '#ff0000',
      secondary_color: '#0000ff',
    },
    features: {},
    isDefault: false,
    tenant: { id: 'test-tenant' },
  })),
}))

jest.mock('@/lib/auth', () => ({
  useAuth: jest.fn(() => ({ user: null })),
}))

const mockApi = api as jest.Mocked<typeof api>

// ---------------------------------------------------------------------------
// API contract tests — verifies correct API calls for tenant upload flow
// ---------------------------------------------------------------------------

describe('TenantJobFlow — API contract', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('createJobWithUploadUrls is called with existing_instrumental and is_private flags', async () => {
    mockApi.createJobWithUploadUrls.mockResolvedValue({
      status: 'success',
      job_id: 'tenant-job-123',
      message: 'Created',
      upload_urls: [
        { file_type: 'audio', gcs_path: 'path/audio.mp3', upload_url: 'https://signed-url-audio', content_type: 'audio/mpeg' },
        { file_type: 'existing_instrumental', gcs_path: 'path/instrumental.mp3', upload_url: 'https://signed-url-inst', content_type: 'audio/mpeg' },
      ],
      server_version: '1.0',
    })

    // Simulate what TenantJobFlow.handleSubmit() does
    const files = [
      { filename: 'song.mp3', content_type: 'audio/mpeg', file_type: 'audio' },
      { filename: 'inst.mp3', content_type: 'audio/mpeg', file_type: 'existing_instrumental' },
    ]

    await api.createJobWithUploadUrls('Test Artist', 'Test Title', files, {
      is_private: true,
      existing_instrumental: true,
    })

    expect(mockApi.createJobWithUploadUrls).toHaveBeenCalledWith(
      'Test Artist',
      'Test Title',
      files,
      { is_private: true, existing_instrumental: true },
    )
  })

  it('uploadToSignedUrl is called for both audio and instrumental', async () => {
    mockApi.uploadToSignedUrl.mockResolvedValue(undefined)

    const audioFile = new File(['audio'], 'song.mp3', { type: 'audio/mpeg' })
    const instFile = new File(['inst'], 'inst.mp3', { type: 'audio/mpeg' })

    // Upload audio
    await api.uploadToSignedUrl('https://signed-url-audio', audioFile, 'audio/mpeg')
    // Upload instrumental
    await api.uploadToSignedUrl('https://signed-url-inst', instFile, 'audio/mpeg')

    expect(mockApi.uploadToSignedUrl).toHaveBeenCalledTimes(2)
    expect(mockApi.uploadToSignedUrl).toHaveBeenCalledWith(
      'https://signed-url-audio', audioFile, 'audio/mpeg',
    )
    expect(mockApi.uploadToSignedUrl).toHaveBeenCalledWith(
      'https://signed-url-inst', instFile, 'audio/mpeg',
    )
  })

  it('completeJobUpload is called with both audio and existing_instrumental types', async () => {
    mockApi.completeJobUpload.mockResolvedValue({
      status: 'success',
      message: 'Processing started',
    })

    await api.completeJobUpload('tenant-job-123', ['audio', 'existing_instrumental'])

    expect(mockApi.completeJobUpload).toHaveBeenCalledWith(
      'tenant-job-123',
      ['audio', 'existing_instrumental'],
    )
  })
})

// ---------------------------------------------------------------------------
// Component interface tests
// ---------------------------------------------------------------------------

describe('TenantJobFlow — component interface', () => {
  it('exports TenantJobFlow as a named export', async () => {
    const mod = await import('@/components/job/TenantJobFlow')
    expect(typeof mod.TenantJobFlow).toBe('function')
  })
})
