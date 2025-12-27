"use client"

import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import type { VideoThemeSummary } from "@/lib/video-themes"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Palette, AlertCircle } from "lucide-react"

interface ThemeSelectorProps {
  value?: string
  onChange: (themeId: string | undefined) => void
  disabled?: boolean
}

export function ThemeSelector({ value, onChange, disabled }: ThemeSelectorProps) {
  const [themes, setThemes] = useState<VideoThemeSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadThemes() {
      try {
        setLoading(true)
        setError(null)
        const themeList = await api.listThemes()
        setThemes(themeList)

        // If no value is set and there's a default theme, select it
        if (!value && themeList.length > 0) {
          const defaultTheme = themeList.find(t => t.is_default)
          if (defaultTheme) {
            onChange(defaultTheme.id)
          } else {
            onChange(themeList[0].id)
          }
        }
      } catch (err) {
        console.error("Failed to load themes:", err)
        setError("Failed to load themes")
      } finally {
        setLoading(false)
      }
    }

    loadThemes()
  }, []) // Only run once on mount

  const selectedTheme = themes.find(t => t.id === value)

  if (loading) {
    return (
      <div className="space-y-2">
        <Label className="text-slate-200 flex items-center gap-2">
          <Palette className="w-4 h-4" />
          Video Theme
        </Label>
        <Skeleton className="h-10 w-full bg-slate-700" />
      </div>
    )
  }

  if (error || themes.length === 0) {
    return (
      <div className="space-y-2">
        <Label className="text-slate-200 flex items-center gap-2">
          <Palette className="w-4 h-4" />
          Video Theme
        </Label>
        <div className="flex items-center gap-2 text-sm text-amber-400 bg-amber-500/10 rounded p-2">
          <AlertCircle className="w-4 h-4" />
          {error || "No themes available"}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <Label htmlFor="theme-select" className="text-slate-200 flex items-center gap-2">
        <Palette className="w-4 h-4" />
        Video Theme
      </Label>

      <Select
        value={value || ""}
        onValueChange={(val) => onChange(val || undefined)}
        disabled={disabled}
      >
        <SelectTrigger
          id="theme-select"
          className="bg-slate-800 border-slate-700 text-white"
        >
          <SelectValue placeholder="Select a theme..." />
        </SelectTrigger>
        <SelectContent className="bg-slate-800 border-slate-700">
          {themes.map((theme) => (
            <SelectItem
              key={theme.id}
              value={theme.id}
              className="text-white hover:bg-slate-700 focus:bg-slate-700"
            >
              <div className="flex items-center gap-2">
                <span>{theme.name}</span>
                {theme.is_default && (
                  <span className="text-xs text-amber-400">(Default)</span>
                )}
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Theme description and preview */}
      {selectedTheme && (
        <div className="mt-2 space-y-2">
          <p className="text-sm text-slate-400">{selectedTheme.description}</p>

          {selectedTheme.thumbnail_url && (
            <div className="relative w-full aspect-video max-w-xs rounded-lg overflow-hidden border border-slate-700">
              <img
                src={selectedTheme.thumbnail_url}
                alt={`${selectedTheme.name} preview`}
                className="w-full h-full object-cover"
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
