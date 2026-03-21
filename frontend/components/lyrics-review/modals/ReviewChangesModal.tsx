'use client'

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { CorrectionData } from '@/lib/lyrics-review/types'
import { AlertTriangle, ArrowLeft, ArrowRight, Loader2 } from 'lucide-react'
import PreviewVideoSection from '../PreviewVideoSection'

interface ApiClient {
  generatePreviewVideo: (data: CorrectionData) => Promise<{
    status: string
    message?: string
    preview_hash?: string
  }>
  getPreviewVideoUrl: (hash: string) => string
}

interface ReviewChangesModalProps {
  open: boolean
  onClose: () => void
  data: CorrectionData
  onSubmit: () => void
  isSubmitting?: boolean
  apiClient?: ApiClient | null
  timingOffsetMs?: number
}

export default function ReviewChangesModal({
  open,
  onClose,
  data,
  onSubmit,
  isSubmitting = false,
  apiClient = null,
  timingOffsetMs = 0,
}: ReviewChangesModalProps) {
  const corrections = data.corrections || []
  const totalSegments = data.corrected_segments?.length || 0
  const hasNoLyrics = totalSegments === 0

  // Check if there are manual corrections (user-made changes)
  const hasManualCorrections = corrections.some(c => c.handler === 'ManualCorrector' || c.handler === 'UserEdit')

  const handleSubmit = () => {
    if (isSubmitting) return
    onSubmit()
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Preview Video (With Vocals)</DialogTitle>
        </DialogHeader>

        {/* Video Preview Section */}
        <PreviewVideoSection
          apiClient={apiClient}
          isModalOpen={open}
          updatedData={data}
          timingOffsetMs={timingOffsetMs}
        />

        {/* No lyrics warning */}
        {hasNoLyrics && (
          <div className="flex items-start gap-3 rounded-lg border border-yellow-500/50 bg-yellow-500/10 p-4">
            <AlertTriangle className="h-5 w-5 text-yellow-500 mt-0.5 shrink-0" />
            <div className="text-sm space-y-2">
              <p className="font-medium text-yellow-500">No lyrics detected</p>
              <p className="text-muted-foreground">
                No lyrics were found in the audio. This usually happens when the input audio has no vocals
                (e.g. a karaoke track or instrumental).
              </p>
              <p className="text-muted-foreground">
                You can go back and paste lyrics manually using <strong>Replace All</strong>,
                or cancel this job and try again with an audio file that contains vocals.
              </p>
            </div>
          </div>
        )}

        {/* Info text */}
        {!hasNoLyrics && (
          <div className="text-sm text-muted-foreground space-y-1">
            {hasManualCorrections ? (
              <p>Manual corrections detected. Review the preview to ensure the lyrics are synchronized correctly.</p>
            ) : (
              <p>No manual corrections detected. If everything looks good in the preview, proceed to select your instrumental.</p>
            )}
            <p>Total segments: {totalSegments}</p>
          </div>
        )}

        <DialogFooter className="border-t pt-4">
          <Button variant="ghost" onClick={onClose} disabled={isSubmitting} className="text-primary">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting || hasNoLyrics}
            className="bg-green-600 hover:bg-green-700"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                Proceed to Instrumental Review
                <ArrowRight className="h-4 w-4 ml-2" />
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
