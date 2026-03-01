"use client"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ArrowLeft, Loader2 } from "lucide-react"
import { TitleCardPreview } from "../TitleCardPreview"

interface CustomizeStepProps {
  artist: string
  title: string
  displayArtist: string
  displayTitle: string
  onDisplayArtistChange: (value: string) => void
  onDisplayTitleChange: (value: string) => void
  isPrivate: boolean
  onPrivateChange: (value: boolean) => void
  onConfirm: () => void
  onBack: () => void
  isSubmitting: boolean
  disabled?: boolean
}

export function CustomizeStep({
  artist,
  title,
  displayArtist,
  displayTitle,
  onDisplayArtistChange,
  onDisplayTitleChange,
  isPrivate,
  onPrivateChange,
  onConfirm,
  onBack,
  isSubmitting,
  disabled,
}: CustomizeStepProps) {
  // The displayed artist/title on the title card
  const previewArtist = displayArtist.trim() || artist
  const previewTitle = displayTitle.trim() || title

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
            Customize & Create
          </h2>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Preview your title card and confirm your settings.
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onBack}
          disabled={disabled || isSubmitting}
          style={{ color: 'var(--text-muted)' }}
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back
        </Button>
      </div>

      {/* Title card preview - half width, centered */}
      <div className="space-y-2">
        <Label className="text-xs" style={{ color: 'var(--text-muted)' }}>Title Card Preview</Label>
        <div className="mx-auto w-full sm:w-1/2">
          <TitleCardPreview artist={previewArtist} title={previewTitle} />
        </div>
      </div>

      {/* Display override fields */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="guided-display-artist" className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Title Card Artist
            {!displayArtist.trim() && artist.trim() && (
              <span className="ml-1 opacity-50">(same as above)</span>
            )}
          </Label>
          <Input
            id="guided-display-artist"
            placeholder={artist || "Artist on title card"}
            value={displayArtist}
            onChange={(e) => onDisplayArtistChange(e.target.value)}
            disabled={disabled || isSubmitting}
            style={{ backgroundColor: 'var(--secondary)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="guided-display-title" className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Title Card Title
            {!displayTitle.trim() && title.trim() && (
              <span className="ml-1 opacity-50">(same as above)</span>
            )}
          </Label>
          <Input
            id="guided-display-title"
            placeholder={title || "Title on title card"}
            value={displayTitle}
            onChange={(e) => onDisplayTitleChange(e.target.value)}
            disabled={disabled || isSubmitting}
            style={{ backgroundColor: 'var(--secondary)', borderColor: 'var(--card-border)', color: 'var(--text)' }}
          />
        </div>
      </div>
      <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
        These default to your search values. Override for soundtracks, covers, or alternate formatting.
      </p>

      {/* Privacy toggle */}
      <div className="space-y-2 pt-2 border-t" style={{ borderColor: 'var(--card-border)' }}>
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            id="guided-private"
            checked={isPrivate}
            onChange={(e) => onPrivateChange(e.target.checked)}
            disabled={disabled || isSubmitting}
            className="mt-1 w-4 h-4 rounded border-border bg-secondary accent-[var(--brand-pink)] focus:ring-[var(--brand-pink)] focus:ring-offset-background"
          />
          <div>
            <Label htmlFor="guided-private" className="cursor-pointer" style={{ color: 'var(--text)' }}>
              Private (no YouTube upload)
            </Label>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              Files delivered via Dropbox only. No YouTube or Google Drive upload.
            </p>
          </div>
        </div>
      </div>

      {/* Create button */}
      <Button
        onClick={onConfirm}
        disabled={disabled || isSubmitting}
        className="w-full bg-[var(--brand-pink)] hover:bg-[var(--brand-pink-hover)] text-white shadow-[0_0_15px_rgba(255,122,204,0.3)] hover:shadow-[0_0_20px_rgba(255,122,204,0.5)] h-11 text-base"
      >
        {isSubmitting ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            Creating...
          </>
        ) : (
          "Create Karaoke Video"
        )}
      </Button>
    </div>
  )
}
