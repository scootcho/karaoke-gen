"use client"

import { useState, useEffect, useMemo } from "react"
import { api, AudioSearchResult } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { Loader2, Music2, ChevronDown, ChevronUp } from "lucide-react"

// Version from pyproject.toml (single source of truth)
const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION || "0.0.0"

interface AudioSearchDialogProps {
  jobId: string
  open: boolean
  onClose: () => void
  onSelect: () => void
}

// Extended result type to include all backend fields
interface ExtendedAudioSearchResult extends AudioSearchResult {
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
interface CategoryConfig {
  name: string
  maxDisplay: number
  color: string
  borderColor: string
}

const CATEGORY_CONFIG: Record<string, CategoryConfig> = {
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

const CATEGORY_ORDER = [
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
function categorizeResult(result: ExtendedAudioSearchResult): string {
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

export function AudioSearchDialog({ jobId, open, onClose, onSelect }: AudioSearchDialogProps) {
  const [results, setResults] = useState<ExtendedAudioSearchResult[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSelecting, setIsSelecting] = useState<number | null>(null)
  const [error, setError] = useState("")
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set())

  // Debug: Log component version on mount
  useEffect(() => {
    console.log(`[AudioSearchDialog] App version: ${APP_VERSION}`)
  }, [])

  // Load results when dialog opens
  useEffect(() => {
    if (open) {
      console.log(`[AudioSearchDialog v${APP_VERSION}] Dialog opened for job: ${jobId}`)
      loadResults()
      setExpandedCategories(new Set()) // Reset expanded state
    }
  }, [open, jobId])

  async function loadResults() {
    setIsLoading(true)
    setError("")
    try {
      console.log(`[AudioSearchDialog v${APP_VERSION}] Loading results...`)
      const data = await api.getAudioSearchResults(jobId)
      console.log(`[AudioSearchDialog v${APP_VERSION}] Raw API response:`, data)
      console.log(`[AudioSearchDialog v${APP_VERSION}] Results count: ${data.results?.length || 0}`)
      setResults((data.results || []) as ExtendedAudioSearchResult[])
    } catch (err: any) {
      console.error(`[AudioSearchDialog v${APP_VERSION}] Failed to load search results:`, err)
      setError(err.message || "Failed to load search results")
    } finally {
      setIsLoading(false)
    }
  }

  // Group results by category
  const groupedResults = useMemo(() => {
    const groups: Record<string, ExtendedAudioSearchResult[]> = {}

    for (const result of results) {
      const category = categorizeResult(result)
      if (!groups[category]) {
        groups[category] = []
      }
      groups[category].push(result)
    }

    // Sort by category order
    const sortedGroups: Array<{ category: string; results: ExtendedAudioSearchResult[]; config: CategoryConfig }> = []
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
  }, [results])

  // Count total categories
  const totalCategories = groupedResults.length

  async function handleSelect(index: number) {
    setIsSelecting(index)
    setError("")
    try {
      await api.selectAudioResult(jobId, index)
      onSelect()
      onClose()
    } catch (err: any) {
      console.error("Failed to select audio:", err)
      setError(err.message || "Failed to select audio")
    } finally {
      setIsSelecting(null)
    }
  }

  function toggleCategory(category: string) {
    setExpandedCategories(prev => {
      const next = new Set(prev)
      if (next.has(category)) {
        next.delete(category)
      } else {
        next.add(category)
      }
      return next
    })
  }

  // Get display name - use channel for YouTube, artist for others
  function getDisplayName(result: ExtendedAudioSearchResult): string {
    if (result.provider === "YouTube" && result.channel) {
      return result.channel
    }
    return result.artist || ""
  }

  // Format views/seeders compactly
  function formatCount(count?: number): string {
    if (!count && count !== 0) return "-"
    if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`
    if (count >= 1000) return `${(count / 1000).toFixed(1)}K`
    return count.toString()
  }

  // Format release metadata line
  function formatMetadata(result: ExtendedAudioSearchResult): string {
    const parts: string[] = []

    if (result.release_type) parts.push(result.release_type)
    if (result.year) parts.push(result.year.toString())
    if (result.label) parts.push(result.label)
    if (result.edition_info) parts.push(result.edition_info)
    if (result.quality_data?.media) parts.push(result.quality_data.media)

    return parts.length > 0 ? `[${parts.join(' / ')}]` : ''
  }

  // Get quality display string
  function formatQuality(result: ExtendedAudioSearchResult): string {
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

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-7xl w-[95vw] max-h-[90vh] flex flex-col bg-card border-border !p-0 gap-0 overflow-hidden">
        <div className="px-4 py-2.5 border-b border-border shrink-0 bg-card flex items-center justify-between">
          <DialogTitle className="text-foreground text-sm font-semibold flex items-center gap-2">
            Select Audio Source
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-secondary text-muted-foreground font-mono">v{APP_VERSION}</span>
            <span className="text-muted-foreground font-normal text-xs">
              ({results.length} results across {totalCategories} categories)
            </span>
          </DialogTitle>
        </div>

        {error && (
          <div className="px-4 py-2 text-xs text-red-400 bg-red-500/10 border-b border-border">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="flex-1 flex items-center justify-center py-12">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            <span className="ml-2 text-sm text-muted-foreground">Loading...</span>
          </div>
        ) : results.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center py-12 text-muted-foreground">
            <Music2 className="w-8 h-8 mb-2 opacity-50" />
            <p className="text-sm">No audio sources found</p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto min-h-0 p-4">
            {/* Two-column grid on desktop */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              {groupedResults.map(({ category, results: catResults, config }) => {
                const isExpanded = expandedCategories.has(category)
                const displayResults = isExpanded ? catResults : catResults.slice(0, config.maxDisplay)
                const hiddenCount = catResults.length - config.maxDisplay
                const hasMore = hiddenCount > 0

                return (
                  <div key={category} className="border border-border rounded-lg overflow-hidden bg-secondary/20">
                    {/* Category Header */}
                    <div className={`px-3 py-2 bg-secondary flex items-center justify-between ${config.color}`}>
                      <div className="flex items-center gap-2 text-xs font-semibold">
                        <span>{category}</span>
                        <span className="text-muted-foreground font-normal">({catResults.length})</span>
                      </div>
                      {hasMore && (
                        <button
                          onClick={() => toggleCategory(category)}
                          className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1"
                        >
                          {isExpanded ? (
                            <>Show less <ChevronUp className="w-3 h-3" /></>
                          ) : (
                            <>+{hiddenCount} more <ChevronDown className="w-3 h-3" /></>
                          )}
                        </button>
                      )}
                    </div>

                    {/* Results in category */}
                    <div className="divide-y divide-slate-700/50">
                      {displayResults.map((result) => (
                        <div
                          key={result.index}
                          className="px-3 py-1.5 hover:bg-secondary/50 flex items-center gap-2 text-xs"
                        >
                          {/* Index */}
                          <span className="w-5 text-muted-foreground font-mono shrink-0 text-[10px]">
                            {result.index + 1}.
                          </span>

                          {/* Main content - 2 lines */}
                          <div className="flex-1 min-w-0">
                            {/* Line 1: badges + artist + title + quality + size + availability */}
                            <div className="flex items-center gap-1 flex-wrap">
                              {result.is_lossless && (
                                <span className="text-[8px] px-1 py-0.5 rounded bg-green-600/20 text-green-400 font-medium">
                                  LOSSLESS
                                </span>
                              )}
                              {result.quality_data?.media?.toLowerCase() === 'vinyl' && (
                                <span className="text-[8px] px-1 py-0.5 rounded bg-red-600/20 text-red-400 font-medium">
                                  VINYL
                                </span>
                              )}
                              {result.provider === "YouTube" && (
                                <span className="text-[8px] px-1 py-0.5 rounded font-medium bg-red-600/20 text-red-400">
                                  YouTube
                                </span>
                              )}
                              <span className="text-green-400 font-medium">{getDisplayName(result)}</span>
                              <span className="text-muted-foreground">-</span>
                              <span className="text-foreground">{result.title}</span>
                              <span className={`text-[10px] ${result.is_lossless ? "text-green-400" : "text-muted-foreground"}`}>
                                ({formatQuality(result)})
                              </span>
                              <span className="text-[10px] text-muted-foreground">{result.formatted_size || '-'}</span>
                              {result.seeders !== undefined && result.seeders !== null ? (
                                <span className={`text-[8px] px-1 py-0.5 rounded font-medium ${
                                  result.seeders >= 50 ? 'bg-green-600/20 text-green-400' :
                                  result.seeders >= 10 ? 'bg-yellow-600/20 text-yellow-400' :
                                  'bg-red-600/20 text-red-400'
                                }`}>
                                  {result.seeders >= 50 ? 'High' : result.seeders >= 10 ? 'Medium' : 'Low'} availability
                                </span>
                              ) : result.view_count !== undefined ? (
                                <span className={`text-[8px] px-1 py-0.5 rounded font-medium ${
                                  result.view_count >= 1000000 ? 'bg-green-600/20 text-green-400' :
                                  result.view_count >= 10000 ? 'bg-yellow-600/20 text-yellow-400' :
                                  'bg-muted text-muted-foreground'
                                }`}>
                                  {formatCount(result.view_count)} views
                                </span>
                              ) : null}
                            </div>

                            {/* Line 2: metadata + filename */}
                            {(formatMetadata(result) || result.target_file) && (
                              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                                {formatMetadata(result) && (
                                  <span className="truncate">{formatMetadata(result)}</span>
                                )}
                                {result.target_file && (
                                  <span className="font-mono truncate">"{result.target_file}"</span>
                                )}
                              </div>
                            )}
                          </div>

                          {/* Select button */}
                          <Button
                            size="sm"
                            onClick={() => handleSelect(result.index)}
                            disabled={isSelecting !== null}
                            className="w-14 h-6 text-[9px] bg-amber-600 hover:bg-amber-500 text-foreground px-2 shrink-0"
                          >
                            {isSelecting === result.index ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              "Select"
                            )}
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
