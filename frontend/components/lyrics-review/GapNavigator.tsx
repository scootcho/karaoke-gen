'use client'

import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface GapNavigatorProps {
  currentGapIndex: number | null
  totalGaps: number
  onPrevGap: () => void
  onNextGap: () => void
}

export default function GapNavigator({
  currentGapIndex,
  totalGaps,
  onPrevGap,
  onNextGap,
}: GapNavigatorProps) {
  if (totalGaps === 0) return null

  const displayIndex = currentGapIndex !== null ? currentGapIndex + 1 : 0

  return (
    <div className="flex items-center gap-1.5">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="outline"
            size="icon"
            className="h-7 w-7"
            onClick={onPrevGap}
            disabled={currentGapIndex === null || currentGapIndex <= 0}
            aria-label="Previous gap"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Previous gap (P)</TooltipContent>
      </Tooltip>
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        Gap {displayIndex} of {totalGaps}
      </span>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="outline"
            size="icon"
            className="h-7 w-7"
            onClick={onNextGap}
            disabled={currentGapIndex !== null && currentGapIndex >= totalGaps - 1}
            aria-label="Next gap"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Next gap (N)</TooltipContent>
      </Tooltip>
    </div>
  )
}
