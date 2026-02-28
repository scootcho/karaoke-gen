"use client"

import { useState, useEffect, useMemo } from "react"
import { api } from "@/lib/api"
import {
  ExtendedAudioSearchResult,
  groupResults,
  getDisplayName,
  formatCount,
  formatMetadata,
  formatQuality,
} from "@/lib/audio-search-utils"
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
  const groupedResults = useMemo(() => groupResults(results), [results])

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
                                  <span className="font-mono truncate">&quot;{result.target_file}&quot;</span>
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
