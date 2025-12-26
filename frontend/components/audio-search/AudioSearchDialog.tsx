"use client"

import { useState, useEffect, useMemo } from "react"
import { api, AudioSearchResult } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Loader2, Music2, HardDrive, Calendar, Clock, Users, Eye, FileAudio, Disc3, Building2 } from "lucide-react"

interface AudioSearchDialogProps {
  jobId: string
  open: boolean
  onClose: () => void
  onSelect: () => void
}

// Category display order and labels
const CATEGORY_ORDER = [
  'TOP SEEDED',
  'HI-RES 24-BIT',
  'STUDIO ALBUMS',
  'LIVE VERSIONS',
  'COMPILATIONS',
  'YOUTUBE/LOSSY',
  'OTHER'
]

const CATEGORY_COLORS: Record<string, string> = {
  'TOP SEEDED': 'text-amber-400 border-amber-500/30',
  'HI-RES 24-BIT': 'text-purple-400 border-purple-500/30',
  'STUDIO ALBUMS': 'text-blue-400 border-blue-500/30',
  'LIVE VERSIONS': 'text-pink-400 border-pink-500/30',
  'COMPILATIONS': 'text-cyan-400 border-cyan-500/30',
  'YOUTUBE/LOSSY': 'text-red-400 border-red-500/30',
  'OTHER': 'text-slate-400 border-slate-500/30',
}

export function AudioSearchDialog({ jobId, open, onClose, onSelect }: AudioSearchDialogProps) {
  const [results, setResults] = useState<AudioSearchResult[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSelecting, setIsSelecting] = useState<number | null>(null)
  const [error, setError] = useState("")

  // Load results when dialog opens
  useEffect(() => {
    if (open) {
      loadResults()
    }
  }, [open, jobId])

  async function loadResults() {
    setIsLoading(true)
    setError("")
    try {
      const data = await api.getAudioSearchResults(jobId)
      setResults(data.results || [])
    } catch (err: any) {
      console.error("Failed to load search results:", err)
      setError(err.message || "Failed to load search results")
    } finally {
      setIsLoading(false)
    }
  }

  // Group results by category
  const groupedResults = useMemo(() => {
    const groups: Record<string, AudioSearchResult[]> = {}

    for (const result of results) {
      const category = result.category || 'OTHER'
      if (!groups[category]) {
        groups[category] = []
      }
      groups[category].push(result)
    }

    // Sort categories by predefined order
    const sortedGroups: [string, AudioSearchResult[]][] = []
    for (const cat of CATEGORY_ORDER) {
      if (groups[cat]) {
        sortedGroups.push([cat, groups[cat]])
        delete groups[cat]
      }
    }
    // Add any remaining categories
    for (const [cat, items] of Object.entries(groups)) {
      sortedGroups.push([cat, items])
    }

    return sortedGroups
  }, [results])

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

  function formatDuration(seconds?: number): string {
    if (!seconds) return ""
    const mins = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  function formatViews(views?: number): string {
    if (!views) return ""
    if (views >= 1000000) return `${(views / 1000000).toFixed(1)}M`
    if (views >= 1000) return `${(views / 1000).toFixed(1)}K`
    return views.toString()
  }

  function formatSize(mb?: number): string {
    if (!mb) return ""
    return `${mb.toFixed(1)} MB`
  }

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl h-[85vh] flex flex-col bg-slate-900 border-slate-700 p-0">
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-slate-800">
          <DialogTitle className="text-white text-lg">Select Audio Source</DialogTitle>
          <DialogDescription className="text-slate-400">
            Found {results.length} results across {groupedResults.length} categories
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            <span className="ml-2 text-slate-400">Loading search results...</span>
          </div>
        ) : error && results.length === 0 ? (
          <div className="flex-1 flex items-center justify-center text-red-400">{error}</div>
        ) : results.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
            <Music2 className="w-12 h-12 mb-3 opacity-50" />
            <p>No audio sources found</p>
          </div>
        ) : (
          <ScrollArea className="flex-1 px-6">
            <div className="space-y-6 py-4">
              {error && (
                <div className="text-sm text-red-400 bg-red-500/10 rounded-lg p-3">
                  {error}
                </div>
              )}

              {groupedResults.map(([category, items]) => (
                <div key={category} className="space-y-2">
                  {/* Category Header */}
                  <div className={`flex items-center gap-2 text-sm font-semibold ${CATEGORY_COLORS[category]?.split(' ')[0] || 'text-slate-400'}`}>
                    <span>{category}</span>
                    <span className="text-slate-500 font-normal">({items.length})</span>
                  </div>

                  {/* Results in category */}
                  <div className="space-y-2">
                    {items.map((result) => (
                      <div
                        key={result.index}
                        className={`border rounded-lg p-3 hover:bg-slate-800/50 transition-colors ${
                          CATEGORY_COLORS[category]?.split(' ')[1] || 'border-slate-700'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          {/* Index number */}
                          <div className="text-slate-500 text-sm font-mono w-6 shrink-0 pt-0.5">
                            {result.index + 1}.
                          </div>

                          {/* Content */}
                          <div className="flex-1 min-w-0 space-y-1.5">
                            {/* Title row */}
                            <div className="flex items-start gap-2">
                              {/* Lossless badge */}
                              {result.is_lossless && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-600/20 text-green-400 font-medium shrink-0">
                                  LOSSLESS
                                </span>
                              )}
                              {/* Provider badge */}
                              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0 ${
                                result.provider === 'RED' ? 'bg-red-600/20 text-red-400' :
                                result.provider === 'OPS' ? 'bg-blue-600/20 text-blue-400' :
                                result.provider === 'YouTube' ? 'bg-red-600/20 text-red-400' :
                                'bg-slate-600/20 text-slate-400'
                              }`}>
                                {result.provider}
                              </span>
                              {/* Artist - Title */}
                              <span className="text-white font-medium">
                                {result.artist}
                              </span>
                              <span className="text-slate-400">-</span>
                              <span className="text-white">
                                {result.title}
                              </span>
                            </div>

                            {/* Album/Release info row */}
                            {(result.album || result.release_type) && (
                              <div className="flex items-center gap-1 text-xs">
                                <span className="text-slate-500">[</span>
                                {result.release_type && (
                                  <span className="text-cyan-400">{result.release_type}</span>
                                )}
                                {result.release_type && result.year && (
                                  <span className="text-slate-500">/</span>
                                )}
                                {result.year && (
                                  <span className="text-yellow-400">{result.year}</span>
                                )}
                                {(result.release_type || result.year) && result.label && (
                                  <span className="text-slate-500">/</span>
                                )}
                                {result.label && (
                                  <span className="text-slate-400 truncate max-w-[200px]">{result.label}</span>
                                )}
                                <span className="text-slate-500">]</span>
                                {result.album && (
                                  <>
                                    <span className="text-slate-500 ml-1">-</span>
                                    <span className="text-slate-300 truncate">{result.album}</span>
                                  </>
                                )}
                              </div>
                            )}

                            {/* Technical details row */}
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
                              {/* Quality */}
                              {result.quality && (
                                <span className={`px-1.5 py-0.5 rounded ${
                                  result.is_lossless ? "bg-green-600/20 text-green-400" : "bg-slate-600/30 text-slate-400"
                                }`}>
                                  {result.quality}
                                </span>
                              )}

                              {/* Duration */}
                              {result.duration && (
                                <span className="flex items-center gap-1">
                                  <Clock className="w-3 h-3" />
                                  {formatDuration(result.duration)}
                                </span>
                              )}

                              {/* File size */}
                              {result.size_mb && (
                                <span className="flex items-center gap-1">
                                  <FileAudio className="w-3 h-3" />
                                  {formatSize(result.size_mb)}
                                </span>
                              )}

                              {/* Seeders (for torrents) */}
                              {result.seeders !== undefined && (
                                <span className={`flex items-center gap-1 ${
                                  result.seeders >= 50 ? 'text-green-400' :
                                  result.seeders >= 10 ? 'text-yellow-400' :
                                  'text-red-400'
                                }`}>
                                  <Users className="w-3 h-3" />
                                  {result.seeders} seeders
                                </span>
                              )}

                              {/* Views (for YouTube) */}
                              {result.views && (
                                <span className="flex items-center gap-1 text-slate-400">
                                  <Eye className="w-3 h-3" />
                                  {formatViews(result.views)} views
                                </span>
                              )}
                            </div>

                            {/* Filename row */}
                            {result.filename && (
                              <div className="text-[11px] text-slate-500 font-mono truncate">
                                "{result.filename}"
                              </div>
                            )}
                          </div>

                          {/* Select button */}
                          <Button
                            size="sm"
                            onClick={() => handleSelect(result.index)}
                            disabled={isSelecting !== null}
                            className="bg-amber-600 hover:bg-amber-500 text-white shrink-0"
                          >
                            {isSelecting === result.index ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              "Select"
                            )}
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  )
}
