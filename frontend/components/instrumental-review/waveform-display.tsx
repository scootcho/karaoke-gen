"use client"

import { useRef, useEffect, useState, useCallback } from "react"

interface AudibleSegment {
  start_seconds: number
  end_seconds: number
  duration_seconds: number
  avg_amplitude_db: number
}

interface MuteRegion {
  start_seconds: number
  end_seconds: number
}

interface WaveformDisplayProps {
  amplitudes: number[]
  duration: number
  currentTime?: number
  segments?: AudibleSegment[]
  muteRegions?: MuteRegion[]
  onSeek?: (time: number) => void
  onRegionSelect?: (region: MuteRegion) => void
  isSelecting?: boolean
  width?: number
  height?: number
  className?: string
}

export function WaveformDisplay({
  amplitudes,
  duration,
  currentTime = 0,
  segments = [],
  muteRegions = [],
  onSeek,
  onRegionSelect,
  isSelecting = false,
  width = 800,
  height = 150,
  className = "",
}: WaveformDisplayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState<number | null>(null)
  const [dragEnd, setDragEnd] = useState<number | null>(null)
  const [hoveredTime, setHoveredTime] = useState<number | null>(null)

  // Convert time to x position
  const timeToX = useCallback((time: number) => {
    return (time / duration) * width
  }, [duration, width])

  // Convert x position to time
  const xToTime = useCallback((x: number) => {
    return (x / width) * duration
  }, [duration, width])

  // Draw the waveform
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    // Clear canvas
    ctx.fillStyle = "#1a1a2e"
    ctx.fillRect(0, 0, width, height)

    const barWidth = width / amplitudes.length
    const centerY = height / 2

    // Draw mute regions background
    ctx.fillStyle = "rgba(255, 107, 107, 0.2)"
    for (const region of muteRegions) {
      const startX = timeToX(region.start_seconds)
      const endX = timeToX(region.end_seconds)
      ctx.fillRect(startX, 0, endX - startX, height)
    }

    // Draw current drag selection
    if (isDragging && dragStart !== null && dragEnd !== null) {
      const startX = Math.min(timeToX(dragStart), timeToX(dragEnd))
      const endX = Math.max(timeToX(dragStart), timeToX(dragEnd))
      ctx.fillStyle = "rgba(255, 107, 107, 0.3)"
      ctx.fillRect(startX, 0, endX - startX, height)
    }

    // Draw segment highlights
    for (const segment of segments) {
      const startX = timeToX(segment.start_seconds)
      const endX = timeToX(segment.end_seconds)
      const startIdx = Math.floor((segment.start_seconds / duration) * amplitudes.length)
      const endIdx = Math.ceil((segment.end_seconds / duration) * amplitudes.length)
      
      ctx.fillStyle = "rgba(233, 69, 96, 0.4)"
      for (let i = startIdx; i < endIdx && i < amplitudes.length; i++) {
        const amplitude = amplitudes[i]
        const barHeight = amplitude * height * 0.8
        const x = i * barWidth
        ctx.fillRect(x, centerY - barHeight / 2, barWidth - 1, barHeight)
      }
    }

    // Draw main waveform
    ctx.fillStyle = "#4a90d9"
    for (let i = 0; i < amplitudes.length; i++) {
      const amplitude = amplitudes[i]
      const barHeight = amplitude * height * 0.8
      const x = i * barWidth
      ctx.fillRect(x, centerY - barHeight / 2, barWidth - 1, barHeight)
    }

    // Draw silence threshold line
    ctx.strokeStyle = "rgba(255, 255, 255, 0.2)"
    ctx.setLineDash([5, 5])
    ctx.beginPath()
    const thresholdY = height * 0.5  // Visual representation
    ctx.moveTo(0, thresholdY)
    ctx.lineTo(width, thresholdY)
    ctx.stroke()
    ctx.setLineDash([])

    // Draw playhead
    if (currentTime > 0) {
      const playheadX = timeToX(currentTime)
      ctx.strokeStyle = "#ffffff"
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(playheadX, 0)
      ctx.lineTo(playheadX, height)
      ctx.stroke()
    }

    // Draw hover position
    if (hoveredTime !== null && !isDragging) {
      const hoverX = timeToX(hoveredTime)
      ctx.strokeStyle = "rgba(255, 255, 255, 0.5)"
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(hoverX, 0)
      ctx.lineTo(hoverX, height)
      ctx.stroke()
    }

    // Draw time axis
    ctx.fillStyle = "#ffffff"
    ctx.font = "10px sans-serif"
    ctx.textAlign = "center"
    
    const tickInterval = duration > 300 ? 60 : duration > 60 ? 30 : 10
    for (let t = 0; t <= duration; t += tickInterval) {
      const x = timeToX(t)
      const minutes = Math.floor(t / 60)
      const seconds = Math.floor(t % 60)
      const label = `${minutes}:${seconds.toString().padStart(2, "0")}`
      ctx.fillText(label, x, height - 5)
      
      // Tick mark
      ctx.strokeStyle = "rgba(255, 255, 255, 0.3)"
      ctx.beginPath()
      ctx.moveTo(x, height - 20)
      ctx.lineTo(x, height - 15)
      ctx.stroke()
    }

  }, [amplitudes, duration, currentTime, segments, muteRegions, width, height, isDragging, dragStart, dragEnd, hoveredTime, timeToX])

  // Handle mouse events for seeking and region selection
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const time = xToTime(x)

    if (isSelecting) {
      setIsDragging(true)
      setDragStart(time)
      setDragEnd(time)
    } else if (onSeek) {
      onSeek(time)
    }
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const time = xToTime(x)

    setHoveredTime(time)

    if (isDragging && isSelecting) {
      setDragEnd(time)
    }
  }

  const handleMouseUp = () => {
    if (isDragging && dragStart !== null && dragEnd !== null && onRegionSelect) {
      const start = Math.min(dragStart, dragEnd)
      const end = Math.max(dragStart, dragEnd)
      
      // Only create region if it's at least 0.1 seconds
      if (end - start >= 0.1) {
        onRegionSelect({ start_seconds: start, end_seconds: end })
      }
    }

    setIsDragging(false)
    setDragStart(null)
    setDragEnd(null)
  }

  const handleMouseLeave = () => {
    setHoveredTime(null)
    if (isDragging) {
      handleMouseUp()
    }
  }

  // Format time for tooltip
  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60)
    const seconds = Math.floor(time % 60)
    const ms = Math.floor((time % 1) * 100)
    return `${minutes}:${seconds.toString().padStart(2, "0")}.${ms.toString().padStart(2, "0")}`
  }

  return (
    <div className={`relative ${className}`}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className={`rounded-lg ${isSelecting ? "cursor-crosshair" : "cursor-pointer"}`}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
      />
      
      {/* Time tooltip */}
      {hoveredTime !== null && (
        <div
          className="absolute top-0 transform -translate-x-1/2 bg-black/80 text-white text-xs px-2 py-1 rounded pointer-events-none"
          style={{ left: timeToX(hoveredTime) }}
        >
          {formatTime(hoveredTime)}
        </div>
      )}
    </div>
  )
}
