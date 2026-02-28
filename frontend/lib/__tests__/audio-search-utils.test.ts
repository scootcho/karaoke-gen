import {
  categorizeResult,
  groupResults,
  getBestResult,
  getDisplayName,
  formatCount,
  formatMetadata,
  formatQuality,
  ExtendedAudioSearchResult,
} from '../audio-search-utils'

// Helper to create a minimal result with overrides
function makeResult(overrides: Partial<ExtendedAudioSearchResult> & { index: number }): ExtendedAudioSearchResult {
  return {
    title: 'Test Song',
    artist: 'Test Artist',
    is_lossless: false,
    provider: 'other',
    ...overrides,
  } as ExtendedAudioSearchResult
}

describe('categorizeResult', () => {
  it('categorizes YouTube provider as YOUTUBE/LOSSY', () => {
    const result = makeResult({ index: 0, provider: 'YouTube', is_lossless: false })
    expect(categorizeResult(result)).toBe('YOUTUBE/LOSSY')
  })

  it('categorizes non-lossless as YOUTUBE/LOSSY', () => {
    const result = makeResult({ index: 0, is_lossless: false })
    expect(categorizeResult(result)).toBe('YOUTUBE/LOSSY')
  })

  it('categorizes lossless with 50+ seeders as BEST CHOICE', () => {
    const result = makeResult({ index: 0, is_lossless: true, seeders: 55 })
    expect(categorizeResult(result)).toBe('BEST CHOICE')
  })

  it('categorizes lossless 24-bit as HI-RES 24-BIT', () => {
    const result = makeResult({ index: 0, is_lossless: true, seeders: 5, quality_data: { bit_depth: 24 } })
    expect(categorizeResult(result)).toBe('HI-RES 24-BIT')
  })

  it('categorizes lossless vinyl media as VINYL RIPS', () => {
    const result = makeResult({ index: 0, is_lossless: true, seeders: 5, quality_data: { media: 'Vinyl' } })
    expect(categorizeResult(result)).toBe('VINYL RIPS')
  })

  it('categorizes vinyl with 50+ seeders as VINYL RIPS (not BEST CHOICE)', () => {
    const result = makeResult({ index: 0, is_lossless: true, seeders: 100, quality_data: { media: 'Vinyl' } })
    expect(categorizeResult(result)).toBe('VINYL RIPS')
  })

  it('categorizes lossless live album as LIVE VERSIONS', () => {
    const result = makeResult({ index: 0, is_lossless: true, seeders: 5, release_type: 'Live Album' })
    expect(categorizeResult(result)).toBe('LIVE VERSIONS')
  })

  it('categorizes lossless compilation as COMPILATIONS', () => {
    const result = makeResult({ index: 0, is_lossless: true, seeders: 5, release_type: 'Compilation' })
    expect(categorizeResult(result)).toBe('COMPILATIONS')
  })

  it('categorizes lossless single as SINGLES', () => {
    const result = makeResult({ index: 0, is_lossless: true, seeders: 5, release_type: 'Single' })
    expect(categorizeResult(result)).toBe('SINGLES')
  })

  it('categorizes lossless album as STUDIO ALBUMS', () => {
    const result = makeResult({ index: 0, is_lossless: true, seeders: 5, release_type: 'Album' })
    expect(categorizeResult(result)).toBe('STUDIO ALBUMS')
  })

  it('categorizes lossless with no release type as STUDIO ALBUMS', () => {
    const result = makeResult({ index: 0, is_lossless: true, seeders: 5 })
    expect(categorizeResult(result)).toBe('STUDIO ALBUMS')
  })

  it('categorizes lossless with unknown release type as OTHER', () => {
    const result = makeResult({ index: 0, is_lossless: true, seeders: 5, release_type: 'Interview' })
    expect(categorizeResult(result)).toBe('OTHER')
  })
})

describe('getBestResult', () => {
  it('returns null for empty array', () => {
    expect(getBestResult([])).toBeNull()
  })

  it('returns the only result when there is one', () => {
    const result = makeResult({ index: 0, is_lossless: false })
    expect(getBestResult([result])).toBe(result)
  })

  it('prefers BEST CHOICE over STUDIO ALBUMS', () => {
    const bestChoice = makeResult({ index: 0, is_lossless: true, seeders: 100, release_type: 'Album' })
    const studioAlbum = makeResult({ index: 1, is_lossless: true, seeders: 10, release_type: 'Album' })
    expect(getBestResult([studioAlbum, bestChoice])).toBe(bestChoice)
  })

  it('prefers STUDIO ALBUMS over YOUTUBE/LOSSY', () => {
    const studio = makeResult({ index: 0, is_lossless: true, seeders: 10, release_type: 'Album' })
    const youtube = makeResult({ index: 1, provider: 'YouTube', is_lossless: false })
    expect(getBestResult([youtube, studio])).toBe(studio)
  })

  it('prefers higher seeders within same category', () => {
    const lowSeeders = makeResult({ index: 0, is_lossless: true, seeders: 5, release_type: 'Album' })
    const highSeeders = makeResult({ index: 1, is_lossless: true, seeders: 30, release_type: 'Album' })
    expect(getBestResult([lowSeeders, highSeeders])).toBe(highSeeders)
  })

  it('skips VINYL RIPS when other options exist', () => {
    // Use low seeders so vinyl is categorized as VINYL RIPS (not BEST CHOICE)
    const vinyl = makeResult({ index: 0, is_lossless: true, seeders: 10, quality_data: { media: 'Vinyl' } })
    const studio = makeResult({ index: 1, is_lossless: true, seeders: 5, release_type: 'Album' })
    expect(getBestResult([vinyl, studio])).toBe(studio)
  })

  it('falls back to first result when all are VINYL RIPS', () => {
    const vinyl1 = makeResult({ index: 0, is_lossless: true, seeders: 10, quality_data: { media: 'Vinyl' } })
    const vinyl2 = makeResult({ index: 1, is_lossless: true, seeders: 20, quality_data: { media: 'Vinyl' } })
    expect(getBestResult([vinyl1, vinyl2])).toBe(vinyl1)
  })

  it('prefers SINGLES over YOUTUBE/LOSSY', () => {
    const single = makeResult({ index: 0, is_lossless: true, seeders: 3, release_type: 'Single' })
    const youtube = makeResult({ index: 1, provider: 'YouTube', is_lossless: false, view_count: 1000000 })
    expect(getBestResult([youtube, single])).toBe(single)
  })

  it('handles mixed results and picks best category', () => {
    const results = [
      makeResult({ index: 0, provider: 'YouTube', is_lossless: false }), // YOUTUBE/LOSSY
      makeResult({ index: 1, is_lossless: true, seeders: 3, release_type: 'Single' }), // SINGLES
      makeResult({ index: 2, is_lossless: true, seeders: 80 }), // BEST CHOICE
      makeResult({ index: 3, is_lossless: true, seeders: 5, quality_data: { media: 'Vinyl' } }), // VINYL (skipped)
    ]
    expect(getBestResult(results)?.index).toBe(2)
  })
})

describe('groupResults', () => {
  it('returns empty array for empty input', () => {
    expect(groupResults([])).toEqual([])
  })

  it('groups results by category', () => {
    const results = [
      makeResult({ index: 0, is_lossless: true, seeders: 100 }), // BEST CHOICE
      makeResult({ index: 1, is_lossless: true, seeders: 10, release_type: 'Album' }), // STUDIO ALBUMS
      makeResult({ index: 2, is_lossless: true, seeders: 60 }), // BEST CHOICE
    ]
    const groups = groupResults(results)
    expect(groups).toHaveLength(2)
    expect(groups[0].category).toBe('BEST CHOICE')
    expect(groups[0].results).toHaveLength(2)
    expect(groups[1].category).toBe('STUDIO ALBUMS')
    expect(groups[1].results).toHaveLength(1)
  })

  it('sorts groups by category order', () => {
    const results = [
      makeResult({ index: 0, provider: 'YouTube', is_lossless: false }), // YOUTUBE/LOSSY (lower priority)
      makeResult({ index: 1, is_lossless: true, seeders: 100 }), // BEST CHOICE (higher priority)
    ]
    const groups = groupResults(results)
    expect(groups[0].category).toBe('BEST CHOICE')
    expect(groups[1].category).toBe('YOUTUBE/LOSSY')
  })

  it('includes config for each group', () => {
    const results = [makeResult({ index: 0, is_lossless: true, seeders: 100 })]
    const groups = groupResults(results)
    expect(groups[0].config).toBeDefined()
    expect(groups[0].config.color).toBeDefined()
    expect(groups[0].config.maxDisplay).toBeGreaterThan(0)
  })
})

describe('getDisplayName', () => {
  it('returns channel for YouTube results', () => {
    const result = makeResult({ index: 0, provider: 'YouTube', channel: 'VEVO' })
    expect(getDisplayName(result)).toBe('VEVO')
  })

  it('returns artist for non-YouTube results', () => {
    const result = makeResult({ index: 0, artist: 'Queen' })
    expect(getDisplayName(result)).toBe('Queen')
  })

  it('returns empty string when no artist', () => {
    const result = makeResult({ index: 0, artist: undefined } as any)
    expect(getDisplayName(result)).toBe('')
  })
})

describe('formatCount', () => {
  it('returns dash for undefined', () => {
    expect(formatCount(undefined)).toBe('-')
  })

  it('formats millions', () => {
    expect(formatCount(1500000)).toBe('1.5M')
  })

  it('formats thousands', () => {
    expect(formatCount(5600)).toBe('5.6K')
  })

  it('returns raw number for small counts', () => {
    expect(formatCount(42)).toBe('42')
  })

  it('returns 0 for zero', () => {
    expect(formatCount(0)).toBe('0')
  })
})

describe('formatMetadata', () => {
  it('returns empty string when no metadata', () => {
    const result = makeResult({ index: 0 })
    expect(formatMetadata(result)).toBe('')
  })

  it('formats release type and year', () => {
    const result = makeResult({ index: 0, release_type: 'Album', year: 1975 } as any)
    expect(formatMetadata(result)).toBe('[Album / 1975]')
  })

  it('includes label and edition info', () => {
    const result = makeResult({ index: 0, release_type: 'Album', label: 'EMI', edition_info: 'Remaster' })
    expect(formatMetadata(result)).toBe('[Album / EMI / Remaster]')
  })
})

describe('formatQuality', () => {
  it('returns quality string when present', () => {
    const result = makeResult({ index: 0, quality: 'FLAC 16bit 44.1kHz' } as any)
    expect(formatQuality(result)).toBe('FLAC 16bit 44.1kHz')
  })

  it('builds quality from quality_data', () => {
    const result = makeResult({ index: 0, quality_data: { format: 'FLAC', bit_depth: 16, bitrate: 1411 } })
    expect(formatQuality(result)).toBe('FLAC 16bit 1411kbps')
  })

  it('returns dash when no quality info', () => {
    const result = makeResult({ index: 0 })
    expect(formatQuality(result)).toBe('-')
  })
})
