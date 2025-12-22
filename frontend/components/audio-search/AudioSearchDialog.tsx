"use client"

import { useState } from "react"
import { api, AudioSearchResult } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Loader2, Music2, HardDrive, Calendar, Clock } from "lucide-react"

interface AudioSearchDialogProps {
  jobId: string
  open: boolean
  onClose: () => void
  onSelect: () => void
}

export function AudioSearchDialog({ jobId, open, onClose, onSelect }: AudioSearchDialogProps) {
  const [results, setResults] = useState<AudioSearchResult[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSelecting, setIsSelecting] = useState(false)
  const [error, setError] = useState("")

  useState(() => {
    if (open) {
      loadResults()
    }
  })

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

  async function handleSelect(index: number) {
    setIsSelecting(true)
    try {
      await api.selectAudioResult(jobId, index)
      onSelect()
      onClose()
    } catch (err: any) {
      console.error("Failed to select audio:", err)
      setError(err.message || "Failed to select audio")
    } finally {
      setIsSelecting(false)
    }
  }

  function formatDuration(seconds?: number): string {
    if (!seconds) return ""
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto bg-slate-900 border-slate-700">
        <DialogHeader>
          <DialogTitle className="text-white">Select Audio Source</DialogTitle>
          <DialogDescription className="text-slate-400">
            Choose the best quality audio source for your karaoke video
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            <span className="ml-2 text-slate-400">Loading search results...</span>
          </div>
        ) : error ? (
          <div className="text-center py-8 text-red-400">{error}</div>
        ) : results.length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            <Music2 className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No audio sources found</p>
          </div>
        ) : (
          <div className="space-y-2">
            {results.map((result) => (
              <div
                key={result.index}
                className="border border-slate-700 rounded-lg p-3 hover:bg-slate-800/50 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-white truncate">
                      {result.artist} - {result.title}
                    </p>
                    <div className="flex flex-wrap items-center gap-3 mt-1 text-xs text-slate-400">
                      <span className="flex items-center gap-1">
                        <HardDrive className="w-3 h-3" />
                        {result.provider}
                      </span>
                      {result.quality && (
                        <span className={`px-1.5 py-0.5 rounded ${
                          result.is_lossless ? "bg-green-600/20 text-green-400" : "bg-slate-600/20 text-slate-400"
                        }`}>
                          {result.quality}
                        </span>
                      )}
                      {result.duration && (
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatDuration(result.duration)}
                        </span>
                      )}
                      {result.year && (
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {result.year}
                        </span>
                      )}
                      {result.seeders !== undefined && (
                        <span className="text-green-400">
                          {result.seeders} seeders
                        </span>
                      )}
                    </div>
                    {result.album && (
                      <p className="text-xs text-slate-500 mt-1 truncate">
                        Album: {result.album}
                      </p>
                    )}
                  </div>
                  <Button
                    size="sm"
                    onClick={() => handleSelect(result.index)}
                    disabled={isSelecting}
                    className="bg-amber-600 hover:bg-amber-500 text-white shrink-0"
                  >
                    {isSelecting ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      "Select"
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

