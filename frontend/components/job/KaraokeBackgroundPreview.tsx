"use client"

import { useRef, useEffect, useCallback } from "react"

interface KaraokeBackgroundPreviewProps {
  backgroundUrl?: string  // Object URL from File, or undefined for solid color
  backgroundColor?: string  // Solid color hex (used when no backgroundUrl)
  sungColor?: string  // Highlight color for sung lyrics
  unsungColor?: string  // Color for unsung lyrics
}

const CANVAS_W = 3840
const CANVAS_H = 2160

// 4 sample lines to match real karaoke video rendering
const SAMPLE_LINES = [
  "Don't say that you don't understand",
  "This is California Babylon my man",
  "Don't say that you don't understand",
  "Don't say that you can't comprehend",
]

// Default karaoke colors (matching Nomad theme)
const DEFAULT_SUNG_COLOR = "#7070F7"
const DEFAULT_UNSUNG_COLOR = "#ffffff"

export function KaraokeBackgroundPreview({
  backgroundUrl,
  backgroundColor,
  sungColor,
  unsungColor,
}: KaraokeBackgroundPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const effectiveSungColor = sungColor || DEFAULT_SUNG_COLOR
  const effectiveUnsungColor = unsungColor || DEFAULT_UNSUNG_COLOR

  const draw = useCallback(async () => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    // Draw background: custom image > solid color > default Nomad theme image
    const bgSrc = backgroundUrl || (backgroundColor ? null : "/karaoke-bg.png")
    if (bgSrc) {
      try {
        const img = await new Promise<HTMLImageElement>((resolve, reject) => {
          const el = new Image()
          el.onload = () => resolve(el)
          el.onerror = reject
          el.src = bgSrc
        })
        ctx.drawImage(img, 0, 0, CANVAS_W, CANVAS_H)
      } catch {
        ctx.fillStyle = backgroundColor || "#000000"
        ctx.fillRect(0, 0, CANVAS_W, CANVAS_H)
      }
    } else {
      ctx.fillStyle = backgroundColor || "#000000"
      ctx.fillRect(0, 0, CANVAS_W, CANVAS_H)
    }

    // Draw 4 lines of sample lyrics, vertically centered
    const fontSize = 120
    const fontFamily = "'Arial', 'Helvetica', sans-serif"
    ctx.font = `700 ${fontSize}px ${fontFamily}`
    ctx.textAlign = "center"
    ctx.textBaseline = "middle"

    const centerX = CANVAS_W / 2
    const lineHeight = fontSize * 1.5
    const totalHeight = lineHeight * SAMPLE_LINES.length
    const startY = (CANVAS_H - totalHeight) / 2 + lineHeight / 2

    SAMPLE_LINES.forEach((line, i) => {
      const y = startY + i * lineHeight

      if (i === 1) {
        // Line 2: partially "sung" — highlight first portion
        const words = line.split(" ")
        const midPoint = 3 // "This is Califor" split mid-word effect
        const sungText = words.slice(0, midPoint).join(" ")
        // Simulate mid-word highlight: "Califor" is partially sung
        const sungPart = sungText.slice(0, -2)
        const transitionChar = sungText.slice(-2)
        const unsungPart = words.slice(midPoint).join(" ")

        const fullText = line
        const fullWidth = ctx.measureText(fullText).width
        const lineStartX = centerX - fullWidth / 2

        // Sung portion
        ctx.fillStyle = effectiveSungColor
        ctx.textAlign = "left"
        ctx.fillText(sungPart, lineStartX, y)

        // Transition characters (still sung color)
        const sungPartWidth = ctx.measureText(sungPart).width
        ctx.fillStyle = effectiveSungColor
        ctx.fillText(transitionChar, lineStartX + sungPartWidth, y)

        // Unsung portion
        const transWidth = ctx.measureText(transitionChar).width
        ctx.fillStyle = effectiveUnsungColor
        ctx.fillText(" " + unsungPart, lineStartX + sungPartWidth + transWidth, y)

        ctx.textAlign = "center"
      } else if (i === 0) {
        // Line 1: fully sung (already passed)
        ctx.fillStyle = effectiveSungColor
        ctx.fillText(line, centerX, y)
      } else {
        // Lines 3-4: unsung (upcoming)
        ctx.fillStyle = effectiveUnsungColor
        ctx.fillText(line, centerX, y)
      }
    })
  }, [backgroundUrl, backgroundColor, effectiveSungColor, effectiveUnsungColor])

  useEffect(() => {
    draw()
  }, [draw])

  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_W}
      height={CANVAS_H}
      className="w-full rounded-lg"
      style={{
        aspectRatio: "16/9",
        border: "1px solid var(--card-border)",
      }}
    />
  )
}
