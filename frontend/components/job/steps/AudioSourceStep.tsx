"use client"

import { useState, useEffect, useMemo, useCallback, useRef } from "react"
import { api, ApiError } from "@/lib/api"
import {
  ExtendedAudioSearchResult,
  groupResults,
  getBestResult,
  categorizeResult,
  getDisplayName,
  formatCount,
  formatMetadata,
  formatQuality,
} from "@/lib/audio-search-utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Loader2, Music2, ChevronDown, ChevronUp, Upload, Youtube, ArrowLeft, Check, AlertTriangle } from "lucide-react"
import Link from "next/link"

interface AudioSourceStepProps {
  artist: string
  title: string
  displayArtist: string
  displayTitle: string
  isPrivate: boolean
  onJobCreated: (jobId: string, source: "search" | "upload" | "url") => void
  onSearchResultChosen: (resultIndex: number) => void
  onFallbackComplete: () => void
  onBack: (jobIdToCleanup: string | null) => void
  noCredits: boolean
}

export function AudioSourceStep({
  artist,
  title,
  displayArtist,
  displayTitle,
  isPrivate,
  onJobCreated,
  onSearchResultChosen,
  onFallbackComplete,
  onBack,
  noCredits,
}: AudioSourceStepProps) {
  const [results, setResults] = useState<ExtendedAudioSearchResult[]>([])
  const [isSearching, setIsSearching] = useState(true)
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState("")
  const [isCreditError, setIsCreditError] = useState(false)
  const [showOtherOptions, setShowOtherOptions] = useState(false)
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set())
  const searchTriggered = useRef(false)

  // Fallback form state
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [youtubeUrl, setYoutubeUrl] = useState("")
  const [isSubmittingFallback, setIsSubmittingFallback] = useState(false)
  const [fallbackMode, setFallbackMode] = useState<"upload" | "url" | null>(null)

  // Auto-trigger search on mount
  const triggerSearch = useCallback(async () => {
    if (searchTriggered.current) return
    searchTriggered.current = true

    setIsSearching(true)
    setError("")
    setIsCreditError(false)
    try {
      const response = await api.searchAudio(artist, title, false, {
        is_private: isPrivate,
        display_artist: displayArtist.trim() || undefined,
        display_title: displayTitle.trim() || undefined,
      })
      setJobId(response.job_id)
      onJobCreated(response.job_id, "search")

      // Now poll for results
      await pollForResults(response.job_id)
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        setIsCreditError(true)
        setError("You're out of credits. Buy more to continue creating karaoke videos.")
      } else if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError("Failed to search for audio")
      }
      setIsSearching(false)
    }
  }, [artist, title, displayArtist, displayTitle, isPrivate, onJobCreated])

  useEffect(() => {
    triggerSearch()
  }, [triggerSearch])

  async function pollForResults(jid: string) {
    const maxAttempts = 30
    const interval = 2000

    for (let i = 0; i < maxAttempts; i++) {
      try {
        const data = await api.getAudioSearchResults(jid)
        if (data.results && data.results.length > 0) {
          setResults(data.results as ExtendedAudioSearchResult[])
          setIsSearching(false)
          return
        }
        // Check if search is still in progress
        if (data.status === "search_complete" || data.status === "audio_search_complete") {
          // Search finished but no results
          setResults([])
          setIsSearching(false)
          return
        }
      } catch {
        // Ignore errors during polling - keep trying
      }
      await new Promise(resolve => setTimeout(resolve, interval))
    }
    // Timeout
    setError("Search is taking longer than expected. You can try the fallback options below.")
    setIsSearching(false)
  }

  const bestResult = useMemo(() => getBestResult(results), [results])
  const groupedResults = useMemo(() => groupResults(results), [results])
  const otherResultsCount = results.length > 0 && bestResult ? results.length - 1 : 0

  function handleSelect(index: number) {
    // Don't call the API here — defer selectAudioResult to the Customize & Create step
    // so the job stays in awaiting_audio_selection (hidden from Recent Jobs) until confirmed
    onSearchResultChosen(index)
  }

  function handleBack() {
    onBack(jobId)
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

  async function handleUploadSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!uploadFile) return

    setIsSubmittingFallback(true)
    setError("")
    setIsCreditError(false)
    try {
      const response = await api.uploadJob(uploadFile, artist.trim(), title.trim(), {
        is_private: isPrivate,
      })
      onJobCreated(response.job_id, "upload")
      onFallbackComplete()
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        setIsCreditError(true)
        setError("You're out of credits. Buy more to continue creating karaoke videos.")
      } else if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError("Failed to upload file")
      }
    } finally {
      setIsSubmittingFallback(false)
    }
  }

  async function handleUrlSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!youtubeUrl.trim()) return

    setIsSubmittingFallback(true)
    setError("")
    setIsCreditError(false)
    try {
      const response = await api.createJobFromUrl(youtubeUrl.trim(), artist.trim(), title.trim(), {
        is_private: isPrivate,
      })
      onJobCreated(response.job_id, "url")
      onFallbackComplete()
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        setIsCreditError(true)
        setError("You're out of credits. Buy more to continue creating karaoke videos.")
      } else if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError("Failed to create job from URL")
      }
    } finally {
      setIsSubmittingFallback(false)
    }
  }

  const bestResultCategory = bestResult ? categorizeResult(bestResult) : null
  const isLossyBest = bestResultCategory === 'YOUTUBE/LOSSY'

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
            Find the audio
          </h2>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Searching for <span className="font-medium" style={{ color: 'var(--text)' }}>{artist} - {title}</span>
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleBack}
          disabled={isSubmittingFallback}
          style={{ color: 'var(--text-muted)' }}
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back
        </Button>
      </div>

      {/* Error display */}
      {error && (
        <div className="text-sm text-red-400 bg-red-500/10 rounded p-3">
          <p>{error}</p>
          {isCreditError && (
            <Link href="/#pricing" className="inline-block mt-1 font-medium underline" style={{ color: 'var(--brand-pink)' }}>Buy Credits</Link>
          )}
        </div>
      )}

      {/* Loading state */}
      {isSearching && (
        <div className="flex flex-col items-center justify-center py-12 gap-3">
          <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'var(--brand-pink)' }} />
          <div className="text-center">
            <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>Searching for audio sources...</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              This usually takes 15-30 seconds
            </p>
          </div>
        </div>
      )}

      {/* Section A: Our Pick */}
      {!isSearching && bestResult && (
        <div
          className="border rounded-lg overflow-hidden border-amber-500/40 bg-amber-500/5"
        >
          <div className="px-3 py-2 bg-amber-500/10 flex items-center gap-2">
            <span className="text-xs font-semibold text-amber-400">Our Pick</span>
            {bestResult.is_lossless && (
              <span className="text-[8px] px-1 py-0.5 rounded bg-green-600/20 text-green-400 font-medium">
                LOSSLESS
              </span>
            )}
            {bestResult.provider === "YouTube" && (
              <span className="text-[8px] px-1 py-0.5 rounded font-medium bg-red-600/20 text-red-400">
                YouTube
              </span>
            )}
          </div>
          <div className="px-3 py-3 space-y-2">
            <div className="flex items-start gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="font-medium text-sm" style={{ color: 'var(--text)' }}>
                    {getDisplayName(bestResult)} - {bestResult.title}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap mt-1">
                  <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                    {formatQuality(bestResult)}
                  </span>
                  {bestResult.seeders !== undefined && bestResult.seeders !== null && (
                    <span className={`text-[8px] px-1 py-0.5 rounded font-medium ${
                      bestResult.seeders >= 50 ? 'bg-green-600/20 text-green-400' :
                      bestResult.seeders >= 10 ? 'bg-yellow-600/20 text-yellow-400' :
                      'bg-red-600/20 text-red-400'
                    }`}>
                      {bestResult.seeders >= 50 ? 'High' : bestResult.seeders >= 10 ? 'Medium' : 'Low'} avail.
                    </span>
                  )}
                  {bestResult.view_count !== undefined && !bestResult.seeders && (
                    <span className="text-[8px] px-1 py-0.5 rounded font-medium bg-[var(--secondary)]" style={{ color: 'var(--text-muted)' }}>
                      {formatCount(bestResult.view_count)} views
                    </span>
                  )}
                </div>
                {formatMetadata(bestResult) && (
                  <div className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
                    {formatMetadata(bestResult)}
                  </div>
                )}
              </div>
            </div>

            {/* Lossy quality warning */}
            {isLossyBest && (
              <div className="flex items-start gap-2 rounded p-2 text-[10px] bg-yellow-600/10 text-yellow-400">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                <span>This is a YouTube/lossy source. Lossless audio produces better karaoke results when available.</span>
              </div>
            )}

            <Button
              onClick={() => handleSelect(bestResult.index)}
              disabled={noCredits}
              className="w-full bg-amber-600 hover:bg-amber-500 text-white"
            >
              <Check className="w-4 h-4 mr-1.5" />
              Use This Audio
            </Button>
          </div>
        </div>
      )}

      {/* Section B: Other options (collapsed by default) */}
      {!isSearching && otherResultsCount > 0 && (
        <div>
          <button
            onClick={() => setShowOtherOptions(!showOtherOptions)}
            className="flex items-center gap-1.5 text-xs hover:opacity-80 transition-opacity"
            style={{ color: 'var(--text-muted)' }}
          >
            {showOtherOptions ? (
              <><ChevronUp className="w-3.5 h-3.5" /> Hide other options</>
            ) : (
              <><ChevronDown className="w-3.5 h-3.5" /> Show {otherResultsCount} other option{otherResultsCount !== 1 ? 's' : ''}</>
            )}
          </button>

          {showOtherOptions && (
            <div className="mt-2 space-y-2">
              <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                Check the filename matches your song. Higher availability (green) = more reliable. Studio album versions produce the best results.
              </p>
              <div className="space-y-2 max-h-[350px] overflow-y-auto pr-1">
                {groupedResults.map(({ category, results: catResults, config }) => {
                  const isExpanded = expandedCategories.has(category)
                  // Filter out the best result from display in "other options"
                  const filteredResults = bestResult
                    ? catResults.filter(r => r.index !== bestResult.index)
                    : catResults
                  if (filteredResults.length === 0) return null

                  const displayResults = isExpanded
                    ? filteredResults
                    : filteredResults.slice(0, config.maxDisplay)
                  const hiddenCount = filteredResults.length - config.maxDisplay
                  const hasMore = hiddenCount > 0

                  return (
                    <div
                      key={category}
                      className="border rounded-lg overflow-hidden border-[var(--card-border)] bg-[var(--secondary)]/20"
                    >
                      {/* Category Header */}
                      <div className="px-3 py-1.5 flex items-center justify-between bg-[var(--secondary)]">
                        <div className="flex items-center gap-2 text-xs font-semibold">
                          <span className={config.color}>{category}</span>
                          <span style={{ color: 'var(--text-muted)' }} className="font-normal">({filteredResults.length})</span>
                        </div>
                        {hasMore && (
                          <button
                            onClick={() => toggleCategory(category)}
                            className="text-[10px] hover:opacity-80 flex items-center gap-1"
                            style={{ color: 'var(--text-muted)' }}
                          >
                            {isExpanded ? (
                              <>Show less <ChevronUp className="w-3 h-3" /></>
                            ) : (
                              <>+{hiddenCount} more <ChevronDown className="w-3 h-3" /></>
                            )}
                          </button>
                        )}
                      </div>

                      {/* Results */}
                      <div className="divide-y" style={{ borderColor: 'var(--card-border)' }}>
                        {displayResults.map((result) => (
                          <div
                            key={result.index}
                            className="px-3 py-2 flex items-center gap-3 text-xs hover:bg-[var(--secondary)]/50 transition-colors"
                          >
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                {result.is_lossless && (
                                  <span className="text-[8px] px-1 py-0.5 rounded bg-green-600/20 text-green-400 font-medium">
                                    LOSSLESS
                                  </span>
                                )}
                                {result.provider === "YouTube" && (
                                  <span className="text-[8px] px-1 py-0.5 rounded font-medium bg-red-600/20 text-red-400">
                                    YouTube
                                  </span>
                                )}
                                <span className="font-medium" style={{ color: 'var(--text)' }}>
                                  {getDisplayName(result)} - {result.title}
                                </span>
                                <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                                  ({formatQuality(result)})
                                </span>
                                {result.seeders !== undefined && result.seeders !== null && (
                                  <span className={`text-[8px] px-1 py-0.5 rounded font-medium ${
                                    result.seeders >= 50 ? 'bg-green-600/20 text-green-400' :
                                    result.seeders >= 10 ? 'bg-yellow-600/20 text-yellow-400' :
                                    'bg-red-600/20 text-red-400'
                                  }`}>
                                    {result.seeders >= 50 ? 'High' : result.seeders >= 10 ? 'Medium' : 'Low'} avail.
                                  </span>
                                )}
                                {result.view_count !== undefined && !result.seeders && (
                                  <span className="text-[8px] px-1 py-0.5 rounded font-medium bg-[var(--secondary)]" style={{ color: 'var(--text-muted)' }}>
                                    {formatCount(result.view_count)} views
                                  </span>
                                )}
                              </div>
                              {formatMetadata(result) && (
                                <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
                                  {formatMetadata(result)}
                                </div>
                              )}
                            </div>

                            <Button
                              size="sm"
                              onClick={() => handleSelect(result.index)}
                              disabled={noCredits}
                              className="h-7 px-3 text-xs shrink-0 bg-[var(--brand-pink)] hover:bg-[var(--brand-pink-hover)] text-white"
                            >
                              <Check className="w-3 h-3 mr-1" />
                              Select
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
        </div>
      )}

      {/* No results */}
      {!isSearching && results.length === 0 && !error && (
        <div className="flex flex-col items-center justify-center py-8" style={{ color: 'var(--text-muted)' }}>
          <Music2 className="w-8 h-8 mb-2 opacity-50" />
          <p className="text-sm">No audio sources found for this song.</p>
          <p className="text-xs mt-1">Try the options below instead.</p>
        </div>
      )}

      {/* Section C: Alternative audio sources (always visible after search completes) */}
      {!isSearching && (
        <div className="border-t pt-4 space-y-3" style={{ borderColor: 'var(--card-border)' }}>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Not finding what you need? Try simplifying your search, or provide your own audio:
          </p>

          {/* Two equally prominent buttons */}
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => { setFallbackMode(fallbackMode === "url" ? null : "url"); }}
              className={`h-9 text-xs ${fallbackMode === "url" ? 'border-[var(--brand-pink)] bg-[var(--brand-pink)]/10' : ''}`}
              style={{ borderColor: fallbackMode === "url" ? 'var(--brand-pink)' : 'var(--card-border)', color: 'var(--text)' }}
            >
              <Youtube className="w-3.5 h-3.5 mr-1.5" />
              YouTube URL
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => { setFallbackMode(fallbackMode === "upload" ? null : "upload"); }}
              className={`h-9 text-xs ${fallbackMode === "upload" ? 'border-[var(--brand-pink)] bg-[var(--brand-pink)]/10' : ''}`}
              style={{ borderColor: fallbackMode === "upload" ? 'var(--brand-pink)' : 'var(--card-border)', color: 'var(--text)' }}
            >
              <Upload className="w-3.5 h-3.5 mr-1.5" />
              Upload file
            </Button>
          </div>

          {/* YouTube URL form */}
          {fallbackMode === "url" && (
            <form onSubmit={handleUrlSubmit} className="space-y-2 p-3 rounded-lg" style={{ backgroundColor: 'var(--secondary)' }}>
              <div className="relative">
                <Youtube className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                <Input
                  type="url"
                  placeholder="https://youtube.com/watch?v=..."
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  className="pl-10 text-xs"
                  style={{ backgroundColor: 'var(--background)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
                  disabled={isSubmittingFallback}
                  autoFocus
                />
              </div>
              <Button
                type="submit"
                size="sm"
                disabled={!youtubeUrl.trim() || isSubmittingFallback || noCredits}
                className="w-full bg-[var(--brand-pink)] hover:bg-[var(--brand-pink-hover)] text-white"
              >
                {isSubmittingFallback ? (
                  <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Creating...</>
                ) : (
                  "Use This URL"
                )}
              </Button>
            </form>
          )}

          {/* Upload form */}
          {fallbackMode === "upload" && (
            <form onSubmit={handleUploadSubmit} className="space-y-3 p-3 rounded-lg" style={{ backgroundColor: 'var(--secondary)' }}>
              <div
                className="relative border-2 border-dashed rounded-lg p-4 text-center transition-colors cursor-pointer"
                style={{
                  borderColor: uploadFile ? 'rgba(255, 122, 204, 0.5)' : 'var(--card-border)',
                  backgroundColor: uploadFile ? 'rgba(255, 122, 204, 0.05)' : 'transparent',
                }}
              >
                <Input
                  type="file"
                  accept=".mp3,.wav,.flac,.m4a,.ogg,audio/*"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) setUploadFile(file)
                  }}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  disabled={isSubmittingFallback}
                />
                {uploadFile ? (
                  <div>
                    <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>{uploadFile.name}</p>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{(uploadFile.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                ) : (
                  <div>
                    <Upload className="w-6 h-6 mx-auto mb-1" style={{ color: 'var(--text-muted)' }} />
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>MP3, WAV, FLAC, M4A, or OGG</p>
                  </div>
                )}
              </div>
              <Button
                type="submit"
                size="sm"
                disabled={!uploadFile || isSubmittingFallback || noCredits}
                className="w-full bg-[var(--brand-pink)] hover:bg-[var(--brand-pink-hover)] text-white"
              >
                {isSubmittingFallback ? (
                  <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Uploading...</>
                ) : (
                  "Upload & Create"
                )}
              </Button>
            </form>
          )}
        </div>
      )}
    </div>
  )
}
