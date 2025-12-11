"use client"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Trash2, VolumeX, Plus } from "lucide-react"

interface MuteRegion {
  start_seconds: number
  end_seconds: number
}

interface AudibleSegment {
  start_seconds: number
  end_seconds: number
  duration_seconds: number
  avg_amplitude_db: number
}

interface RegionSelectorProps {
  muteRegions: MuteRegion[]
  audibleSegments?: AudibleSegment[]
  onAddRegion: (region: MuteRegion) => void
  onRemoveRegion: (index: number) => void
  onClearAll: () => void
  onSeekTo?: (time: number) => void
  isSelectionMode: boolean
  onToggleSelectionMode: () => void
  className?: string
}

export function RegionSelector({
  muteRegions,
  audibleSegments = [],
  onAddRegion,
  onRemoveRegion,
  onClearAll,
  onSeekTo,
  isSelectionMode,
  onToggleSelectionMode,
  className = "",
}: RegionSelectorProps) {
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    const ms = Math.floor((seconds % 1) * 100)
    return `${mins}:${secs.toString().padStart(2, "0")}.${ms.toString().padStart(2, "0")}`
  }

  const formatDuration = (seconds: number) => {
    if (seconds < 1) {
      return `${Math.round(seconds * 1000)}ms`
    }
    return `${seconds.toFixed(1)}s`
  }

  const totalMutedDuration = muteRegions.reduce(
    (sum, r) => sum + (r.end_seconds - r.start_seconds),
    0
  )

  // Quick mute: add mute region for an audible segment
  const handleQuickMute = (segment: AudibleSegment) => {
    onAddRegion({
      start_seconds: segment.start_seconds,
      end_seconds: segment.end_seconds,
    })
  }

  // Check if a segment is already muted
  const isSegmentMuted = (segment: AudibleSegment) => {
    return muteRegions.some(
      (r) =>
        r.start_seconds <= segment.start_seconds &&
        r.end_seconds >= segment.end_seconds
    )
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Selection Mode Toggle */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Mute Regions</CardTitle>
            <Button
              variant={isSelectionMode ? "default" : "outline"}
              size="sm"
              onClick={onToggleSelectionMode}
            >
              <Plus className="h-4 w-4 mr-2" />
              {isSelectionMode ? "Click waveform to select" : "Add Region"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {muteRegions.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No mute regions selected. Click "Add Region" and drag on the waveform to select areas to mute.
            </p>
          ) : (
            <div className="space-y-2">
              {muteRegions.map((region, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-2 bg-muted/50 rounded-lg group"
                >
                  <div className="flex items-center gap-3">
                    <VolumeX className="h-4 w-4 text-destructive" />
                    <button
                      onClick={() => onSeekTo?.(region.start_seconds)}
                      className="text-sm font-mono hover:text-primary transition-colors"
                    >
                      {formatTime(region.start_seconds)}
                    </button>
                    <span className="text-muted-foreground">→</span>
                    <button
                      onClick={() => onSeekTo?.(region.end_seconds)}
                      className="text-sm font-mono hover:text-primary transition-colors"
                    >
                      {formatTime(region.end_seconds)}
                    </button>
                    <Badge variant="secondary" className="ml-2">
                      {formatDuration(region.end_seconds - region.start_seconds)}
                    </Badge>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onRemoveRegion(index)}
                    className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              ))}
              
              <div className="flex items-center justify-between pt-2 border-t mt-3">
                <span className="text-sm text-muted-foreground">
                  Total muted: {formatDuration(totalMutedDuration)}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onClearAll}
                  className="text-destructive hover:text-destructive"
                >
                  Clear All
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detected Audible Segments */}
      {audibleSegments.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Detected Backing Vocals</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              Click a segment to jump to that time, or click the mute button to add it as a mute region.
            </p>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {audibleSegments.map((segment, index) => {
                const isMuted = isSegmentMuted(segment)
                return (
                  <div
                    key={index}
                    className={`flex items-center justify-between p-2 rounded-lg transition-colors ${
                      isMuted ? "bg-destructive/10" : "bg-muted/50 hover:bg-muted"
                    }`}
                  >
                    <button
                      onClick={() => onSeekTo?.(segment.start_seconds)}
                      className="flex items-center gap-3 text-left"
                    >
                      <span className="text-sm font-mono">
                        {formatTime(segment.start_seconds)} - {formatTime(segment.end_seconds)}
                      </span>
                      <Badge variant="outline" className="text-xs">
                        {formatDuration(segment.duration_seconds)}
                      </Badge>
                      <Badge
                        variant="outline"
                        className={`text-xs ${
                          segment.avg_amplitude_db > -20
                            ? "border-yellow-500 text-yellow-500"
                            : "border-muted-foreground"
                        }`}
                      >
                        {segment.avg_amplitude_db.toFixed(1)}dB
                      </Badge>
                    </button>
                    {!isMuted && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleQuickMute(segment)}
                        className="text-xs"
                      >
                        <VolumeX className="h-3 w-3 mr-1" />
                        Mute
                      </Button>
                    )}
                    {isMuted && (
                      <Badge variant="destructive" className="text-xs">
                        Muted
                      </Badge>
                    )}
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
