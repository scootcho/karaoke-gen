'use client'

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { CorrectionData, WordCorrection } from '@/lib/lyrics-review/types'

interface ReviewChangesModalProps {
  open: boolean
  onClose: () => void
  data: CorrectionData
  onSubmit: () => void
  isSubmitting?: boolean
}

export default function ReviewChangesModal({
  open,
  onClose,
  data,
  onSubmit,
  isSubmitting = false,
}: ReviewChangesModalProps) {
  const corrections = data.corrections || []
  const correctionsByHandler = corrections.reduce(
    (acc, correction) => {
      const handler = correction.handler || 'Unknown'
      if (!acc[handler]) acc[handler] = []
      acc[handler].push(correction)
      return acc
    },
    {} as Record<string, WordCorrection[]>
  )

  const totalWords = data.corrected_segments.reduce((sum, seg) => sum + seg.words.length, 0)

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-2xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle>Review Changes</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="bg-muted p-3 rounded">
              <p className="text-muted-foreground">Total Words</p>
              <p className="text-2xl font-bold">{totalWords}</p>
            </div>
            <div className="bg-muted p-3 rounded">
              <p className="text-muted-foreground">Corrections Made</p>
              <p className="text-2xl font-bold">{corrections.length}</p>
            </div>
          </div>

          <div>
            <h4 className="font-medium mb-2">Corrections by Handler</h4>
            <div className="flex flex-wrap gap-2">
              {Object.entries(correctionsByHandler).map(([handler, handlerCorrections]) => (
                <Badge key={handler} variant="secondary">
                  {handler}: {handlerCorrections.length}
                </Badge>
              ))}
            </div>
          </div>

          <div>
            <h4 className="font-medium mb-2">Recent Corrections</h4>
            <ScrollArea className="h-48 border rounded-md p-2">
              <div className="space-y-2">
                {corrections.slice(0, 30).map((correction, index) => (
                  <div key={index} className="text-sm p-2 bg-muted rounded flex justify-between">
                    <div>
                      <span className="text-destructive line-through">{correction.original_word}</span>
                      <span className="mx-2">→</span>
                      <span className="text-primary font-medium">{correction.corrected_word}</span>
                    </div>
                    <Badge variant="outline" className="text-xs">
                      {correction.handler}
                    </Badge>
                  </div>
                ))}
                {corrections.length > 30 && (
                  <p className="text-sm text-muted-foreground text-center">
                    + {corrections.length - 30} more corrections
                  </p>
                )}
              </div>
            </ScrollArea>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={onSubmit} disabled={isSubmitting}>
            {isSubmitting ? 'Submitting...' : 'Submit Changes'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
