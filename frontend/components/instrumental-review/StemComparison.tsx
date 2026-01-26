"use client"

import { cn } from "@/lib/utils"
import { Loader2 } from "lucide-react"

export type AudioType = "original" | "backing" | "clean" | "with_backing" | "custom" | "uploaded"

interface StemComparisonProps {
  activeAudio: AudioType
  onAudioChange: (type: AudioType) => void
  hasOriginal: boolean
  hasWithBacking: boolean
  hasCustom: boolean
  hasUploaded: boolean
  uploadedFilename?: string
  isLoading?: boolean
}

interface AudioOption {
  type: AudioType
  label: string
  available: boolean
  title?: string
}

export function StemComparison({
  activeAudio,
  onAudioChange,
  hasOriginal,
  hasWithBacking,
  hasCustom,
  hasUploaded,
  uploadedFilename,
  isLoading = false,
}: StemComparisonProps) {
  const options: AudioOption[] = [
    { type: "original", label: "Original", available: hasOriginal },
    { type: "backing", label: "Backing Vocals Only", available: true },
    { type: "clean", label: "Pure Instrumental", available: true },
    { type: "with_backing", label: "Instrumental + Backing", available: hasWithBacking },
    { type: "custom", label: "Custom", available: hasCustom },
    { type: "uploaded", label: "Uploaded", available: hasUploaded, title: uploadedFilename },
  ]

  const availableOptions = options.filter((opt) => opt.available)

  return (
    <div className="flex flex-wrap gap-1 bg-background rounded-md p-0.5">
      {availableOptions.map((option) => {
        const isActive = activeAudio === option.type
        const showSpinner = isActive && isLoading

        return (
          <button
            key={option.type}
            type="button"
            onClick={() => onAudioChange(option.type)}
            disabled={isLoading}
            title={option.title}
            className={cn(
              "px-2.5 py-1.5 rounded text-xs font-medium transition-all flex items-center gap-1.5",
              "text-muted-foreground hover:text-foreground",
              isActive && "bg-primary text-primary-foreground",
              isLoading && !isActive && "opacity-50 cursor-not-allowed"
            )}
          >
            {showSpinner && <Loader2 className="w-3 h-3 animate-spin" />}
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
