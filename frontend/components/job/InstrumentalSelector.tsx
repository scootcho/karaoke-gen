"use client"

import { useState, useEffect } from "react"
import { api, InstrumentalOption } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Loader2, Music2, Play, Pause } from "lucide-react"

interface InstrumentalSelectorProps {
  jobId: string
  open: boolean
  onClose: () => void
  onSelect: () => void
}

export function InstrumentalSelector({ jobId, open, onClose, onSelect }: InstrumentalSelectorProps) {
  const [options, setOptions] = useState<InstrumentalOption[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSelecting, setIsSelecting] = useState(false)
  const [error, setError] = useState("")
  const [playingId, setPlayingId] = useState<string | null>(null)
  const [audioElements, setAudioElements] = useState<Map<string, HTMLAudioElement>>(new Map())

  useEffect(() => {
    if (open) {
      loadOptions()
    }
    return () => {
      // Cleanup audio elements
      audioElements.forEach(audio => {
        audio.pause()
        audio.src = ""
      })
    }
  }, [open])

  async function loadOptions() {
    setIsLoading(true)
    setError("")
    try {
      const data = await api.getInstrumentalOptions(jobId)
      setOptions(data.options || [])
    } catch (err: any) {
      console.error("Failed to load instrumental options:", err)
      setError(err.message || "Failed to load options")
    } finally {
      setIsLoading(false)
    }
  }

  async function handleSelect(selection: 'clean' | 'with_backing') {
    setIsSelecting(true)
    try {
      await api.selectInstrumental(jobId, selection)
      onSelect()
      onClose()
    } catch (err: any) {
      console.error("Failed to select instrumental:", err)
      setError(err.message || "Failed to select instrumental")
    } finally {
      setIsSelecting(false)
    }
  }

  function togglePlayback(optionId: string, audioUrl: string) {
    if (playingId === optionId) {
      // Pause current
      const audio = audioElements.get(optionId)
      if (audio) {
        audio.pause()
      }
      setPlayingId(null)
    } else {
      // Stop any currently playing audio
      audioElements.forEach(audio => audio.pause())
      
      // Play new audio
      let audio = audioElements.get(optionId)
      if (!audio) {
        audio = new Audio(audioUrl)
        audio.addEventListener('ended', () => setPlayingId(null))
        audioElements.set(optionId, audio)
        setAudioElements(new Map(audioElements))
      }
      audio.play()
      setPlayingId(optionId)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl bg-slate-900 border-slate-700">
        <DialogHeader>
          <DialogTitle className="text-white">Select Instrumental Version</DialogTitle>
          <DialogDescription className="text-slate-400">
            Choose between a clean instrumental or one with backing vocals
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            <span className="ml-2 text-slate-400">Loading options...</span>
          </div>
        ) : error ? (
          <div className="text-center py-8 text-red-400">{error}</div>
        ) : options.length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            <Music2 className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No instrumental options available</p>
          </div>
        ) : (
          <div className="space-y-3">
            {options.map((option) => (
              <div
                key={option.id}
                className="border border-slate-700 rounded-lg p-4 hover:bg-slate-800/50 transition-colors"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex-1">
                    <p className="font-medium text-white">{option.label}</p>
                    {option.duration_seconds && (
                      <p className="text-xs text-slate-400 mt-1">
                        Duration: {Math.floor(option.duration_seconds / 60)}:
                        {(option.duration_seconds % 60).toString().padStart(2, '0')}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {option.audio_url && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => togglePlayback(option.id, option.audio_url)}
                        className="text-slate-400 hover:text-white"
                      >
                        {playingId === option.id ? (
                          <Pause className="w-4 h-4" />
                        ) : (
                          <Play className="w-4 h-4" />
                        )}
                      </Button>
                    )}
                    <Button
                      size="sm"
                      onClick={() => handleSelect(option.id as 'clean' | 'with_backing')}
                      disabled={isSelecting}
                      className="bg-pink-600 hover:bg-pink-500 text-white"
                    >
                      {isSelecting ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        "Select"
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

