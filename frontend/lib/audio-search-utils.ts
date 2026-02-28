import { AudioSearchResult } from "@/lib/api"

// Extended result type to include all backend fields
export interface ExtendedAudioSearchResult extends AudioSearchResult {
  channel?: string
  view_count?: number
  formatted_duration?: string
  formatted_size?: string
  release_type?: string
  label?: string
  edition_info?: string
  target_file?: string
  quality_data?: {
    format?: string
    bit_depth?: number
    sample_rate?: number
    bitrate?: number
    media?: string
  }
}

// Category configuration matching flacfetch
export interface CategoryConfig {
  name: string
  maxDisplay: number
  color: string
  borderColor: string
}

export const CATEGORY_CONFIG: Record<string, CategoryConfig> = {
  'BEST CHOICE': { name: 'BEST CHOICE', maxDisplay: 3, color: 'text-amber-400', borderColor: 'border-amber-500/30' },
  'HI-RES 24-BIT': { name: 'HI-RES 24-BIT', maxDisplay: 3, color: 'text-purple-400', borderColor: 'border-purple-500/30' },
  'STUDIO ALBUMS': { name: 'STUDIO ALBUMS', maxDisplay: 3, color: 'text-blue-400', borderColor: 'border-blue-500/30' },
  'SINGLES': { name: 'SINGLES', maxDisplay: 2, color: 'text-cyan-400', borderColor: 'border-cyan-500/30' },
  'LIVE VERSIONS': { name: 'LIVE VERSIONS', maxDisplay: 2, color: 'text-pink-400', borderColor: 'border-pink-500/30' },
  'COMPILATIONS': { name: 'COMPILATIONS', maxDisplay: 2, color: 'text-teal-400', borderColor: 'border-teal-500/30' },
  'VINYL RIPS': { name: 'VINYL RIPS', maxDisplay: 2, color: 'text-orange-400', borderColor: 'border-orange-500/30' },
  'YOUTUBE/LOSSY': { name: 'YOUTUBE/LOSSY', maxDisplay: 3, color: 'text-red-400', borderColor: 'border-red-500/30' },
  'OTHER': { name: 'OTHER', maxDisplay: 3, color: 'text-muted-foreground', borderColor: 'border-border' },
}

export const CATEGORY_ORDER = [
  'BEST CHOICE',
  'HI-RES 24-BIT',
  'STUDIO ALBUMS',
  'SINGLES',
  'LIVE VERSIONS',
  'COMPILATIONS',
  'VINYL RIPS',
  'YOUTUBE/LOSSY',
  'OTHER'
]

// Categorize a single result based on flacfetch logic
export function categorizeResult(result: ExtendedAudioSearchResult): string {
  const isLossless = result.is_lossless === true
  const is24Bit = result.quality_data?.bit_depth === 24
  const seeders = result.seeders ?? 0
  const provider = result.provider?.toLowerCase() ?? ''
  const releaseType = result.release_type?.toLowerCase() ?? ''
  const media = result.quality_data?.media?.toLowerCase() ?? ''

  // YouTube and lossy sources
  if (provider === 'youtube' || !isLossless) {
    return 'YOUTUBE/LOSSY'
  }

  // Best choice (50+ seeders, lossless)
  if (isLossless && seeders >= 50) {
    return 'BEST CHOICE'
  }

  // Hi-res 24-bit
  if (isLossless && is24Bit) {
    return 'HI-RES 24-BIT'
  }

  // Vinyl rips
  if (isLossless && media === 'vinyl') {
    return 'VINYL RIPS'
  }

  // Live versions
  if (isLossless && (releaseType === 'live album' || releaseType === 'bootleg' || releaseType.includes('live'))) {
    return 'LIVE VERSIONS'
  }

  // Compilations
  if (isLossless && (releaseType === 'compilation' || releaseType === 'soundtrack' || releaseType === 'anthology')) {
    return 'COMPILATIONS'
  }

  // Singles/EPs
  if (isLossless && (releaseType === 'single' || releaseType === 'ep')) {
    return 'SINGLES'
  }

  // Studio albums
  if (isLossless && (releaseType === 'album' || !releaseType)) {
    return 'STUDIO ALBUMS'
  }

  return 'OTHER'
}

export interface GroupedCategory {
  category: string
  results: ExtendedAudioSearchResult[]
  config: CategoryConfig
}

// Group results by category and sort by category order
export function groupResults(results: ExtendedAudioSearchResult[]): GroupedCategory[] {
  const groups: Record<string, ExtendedAudioSearchResult[]> = {}

  for (const result of results) {
    const category = categorizeResult(result)
    if (!groups[category]) {
      groups[category] = []
    }
    groups[category].push(result)
  }

  const sortedGroups: GroupedCategory[] = []
  for (const cat of CATEGORY_ORDER) {
    if (groups[cat] && groups[cat].length > 0) {
      sortedGroups.push({
        category: cat,
        results: groups[cat],
        config: CATEGORY_CONFIG[cat]
      })
    }
  }

  return sortedGroups
}

// Priority order for picking the best result (lower index = higher priority)
const BEST_RESULT_PRIORITY = [
  'BEST CHOICE',
  'STUDIO ALBUMS',
  'HI-RES 24-BIT',
  'SINGLES',
  'COMPILATIONS',
  'YOUTUBE/LOSSY',
  'OTHER',
]

// Returns the single best result from the array
// Priority: BEST CHOICE > STUDIO ALBUMS > HI-RES 24-BIT > SINGLES > COMPILATIONS > YOUTUBE/LOSSY > OTHER
// Skips VINYL RIPS (surface noise issues for karaoke) and LIVE VERSIONS (unless nothing else)
// Within a category, prefers highest seeders
export function getBestResult(results: ExtendedAudioSearchResult[]): ExtendedAudioSearchResult | null {
  if (results.length === 0) return null

  let best: ExtendedAudioSearchResult | null = null
  let bestPriority = Infinity

  for (const result of results) {
    const category = categorizeResult(result)

    // Skip vinyl rips entirely
    if (category === 'VINYL RIPS') continue

    const priority = BEST_RESULT_PRIORITY.indexOf(category)
    const effectivePriority = priority === -1 ? Infinity : priority

    if (effectivePriority < bestPriority) {
      best = result
      bestPriority = effectivePriority
    } else if (effectivePriority === bestPriority && best) {
      // Same category — prefer higher seeders
      const currentSeeders = result.seeders ?? 0
      const bestSeeders = best.seeders ?? 0
      if (currentSeeders > bestSeeders) {
        best = result
      }
    }
  }

  // If nothing found (all vinyl rips), fall back to first result
  return best ?? results[0]
}

// Get display name - use channel for YouTube, artist for others
export function getDisplayName(result: ExtendedAudioSearchResult): string {
  if (result.provider === "YouTube" && result.channel) {
    return result.channel
  }
  return result.artist || ""
}

// Format views/seeders compactly
export function formatCount(count?: number): string {
  if (!count && count !== 0) return "-"
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`
  return count.toString()
}

// Format release metadata line
export function formatMetadata(result: ExtendedAudioSearchResult): string {
  const parts: string[] = []

  if (result.release_type) parts.push(result.release_type)
  if (result.year) parts.push(result.year.toString())
  if (result.label) parts.push(result.label)
  if (result.edition_info) parts.push(result.edition_info)
  if (result.quality_data?.media) parts.push(result.quality_data.media)

  return parts.length > 0 ? `[${parts.join(' / ')}]` : ''
}

// Get quality display string
export function formatQuality(result: ExtendedAudioSearchResult): string {
  if (result.quality) return result.quality

  const qd = result.quality_data
  if (!qd) return '-'

  const parts: string[] = []
  if (qd.format) parts.push(qd.format)
  if (qd.bit_depth) parts.push(`${qd.bit_depth}bit`)
  if (qd.bitrate) parts.push(`${qd.bitrate}kbps`)
  if (qd.media) parts.push(qd.media)

  return parts.join(' ') || '-'
}
