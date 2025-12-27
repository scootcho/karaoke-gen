"use client"

import { useState } from "react"
import type { ColorOverrides } from "@/lib/video-themes"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { ChevronDown, ChevronUp, Paintbrush, RotateCcw } from "lucide-react"

interface ColorOverridesProps {
  value: ColorOverrides
  onChange: (overrides: ColorOverrides) => void
  disabled?: boolean
}

interface ColorFieldProps {
  id: string
  label: string
  description: string
  value?: string
  onChange: (value: string | undefined) => void
  disabled?: boolean
}

function ColorField({ id, label, description, value, onChange, disabled }: ColorFieldProps) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <Label htmlFor={id} className="text-sm text-slate-300">
          {label}
        </Label>
        {value && (
          <button
            type="button"
            onClick={() => onChange(undefined)}
            className="text-xs text-slate-500 hover:text-slate-300"
            disabled={disabled}
          >
            Reset
          </button>
        )}
      </div>
      <div className="flex items-center gap-2">
        <div
          className="w-8 h-8 rounded border border-slate-600 flex-shrink-0"
          style={{ backgroundColor: value || "#333333" }}
        />
        <Input
          id={id}
          type="text"
          placeholder="#RRGGBB"
          value={value || ""}
          onChange={(e) => {
            const val = e.target.value.trim()
            if (val === "") {
              onChange(undefined)
            } else if (/^#[0-9A-Fa-f]{0,6}$/.test(val)) {
              onChange(val)
            }
          }}
          disabled={disabled}
          className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-500 font-mono text-sm"
        />
        <Input
          type="color"
          value={value || "#333333"}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className="w-10 h-8 p-0 border-0 bg-transparent cursor-pointer"
        />
      </div>
      <p className="text-xs text-slate-500">{description}</p>
    </div>
  )
}

export function ColorOverridesPanel({ value, onChange, disabled }: ColorOverridesProps) {
  const [isOpen, setIsOpen] = useState(false)

  const hasAnyOverrides = !!(
    value.artist_color ||
    value.title_color ||
    value.sung_lyrics_color ||
    value.unsung_lyrics_color
  )

  function handleResetAll() {
    onChange({})
  }

  function updateField(field: keyof ColorOverrides, newValue: string | undefined) {
    onChange({
      ...value,
      [field]: newValue,
    })
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          type="button"
          className="w-full justify-between px-3 py-2 h-auto text-slate-300 hover:text-white hover:bg-slate-700/50"
        >
          <span className="flex items-center gap-2">
            <Paintbrush className="w-4 h-4" />
            Customize Colors
            {hasAnyOverrides && (
              <span className="text-xs bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded">
                Modified
              </span>
            )}
          </span>
          {isOpen ? (
            <ChevronUp className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
        </Button>
      </CollapsibleTrigger>

      <CollapsibleContent className="mt-2">
        <div className="space-y-4 p-4 rounded-lg border border-slate-700 bg-slate-800/50">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-400">
              Override theme colors (optional)
            </p>
            {hasAnyOverrides && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleResetAll}
                disabled={disabled}
                className="text-slate-400 hover:text-white"
              >
                <RotateCcw className="w-3 h-3 mr-1" />
                Reset All
              </Button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ColorField
              id="artist-color"
              label="Artist Color"
              description="Color for artist name on title/end screens"
              value={value.artist_color}
              onChange={(v) => updateField("artist_color", v)}
              disabled={disabled}
            />

            <ColorField
              id="title-color"
              label="Title Color"
              description="Color for song title on title/end screens"
              value={value.title_color}
              onChange={(v) => updateField("title_color", v)}
              disabled={disabled}
            />

            <ColorField
              id="sung-lyrics-color"
              label="Sung Lyrics Color"
              description="Color for lyrics being sung (highlighted)"
              value={value.sung_lyrics_color}
              onChange={(v) => updateField("sung_lyrics_color", v)}
              disabled={disabled}
            />

            <ColorField
              id="unsung-lyrics-color"
              label="Unsung Lyrics Color"
              description="Color for lyrics not yet sung"
              value={value.unsung_lyrics_color}
              onChange={(v) => updateField("unsung_lyrics_color", v)}
              disabled={disabled}
            />
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
