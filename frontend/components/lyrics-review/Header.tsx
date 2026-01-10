'use client'

import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Lock,
  Upload,
  Search,
  Edit,
  Undo2,
  Redo2,
  Timer,
  RotateCcw,
  MessageSquare,
  Eye,
  CheckCircle2,
  XCircle,
} from 'lucide-react'
import { CorrectionData, InteractionMode } from '@/lib/lyrics-review/types'
import ModeSelector from './ModeSelector'
import AudioPlayer from './AudioPlayer'
import { findWordById } from '@/lib/lyrics-review/utils/wordUtils'
import { cn } from '@/lib/utils'

interface ApiClient {
  getAudioUrl: (hash: string) => string
}

interface HeaderProps {
  isReadOnly: boolean
  onFileLoad: () => void
  data: CorrectionData
  onMetricClick: {
    anchor: () => void
    corrected: () => void
    uncorrected: () => void
  }
  effectiveMode: InteractionMode
  onModeChange: (mode: InteractionMode) => void
  apiClient: ApiClient | null
  audioHash: string
  onTimeUpdate: (time: number) => void
  onHandlerToggle: (handler: string, enabled: boolean) => void
  isUpdatingHandlers: boolean
  onHandlerClick?: (handler: string) => void
  onFindReplace?: () => void
  onEditAll?: () => void
  onUnCorrectAll?: () => void
  onResetCorrections?: () => void
  onTimingOffset?: () => void
  timingOffsetMs?: number
  onUndo: () => void
  onRedo: () => void
  canUndo: boolean
  canRedo: boolean
  annotationsEnabled?: boolean
  onAnnotationsToggle?: (enabled: boolean) => void
  reviewMode?: boolean
  onReviewModeToggle?: (enabled: boolean) => void
  onAcceptAllCorrections?: () => void
  onAcceptHighConfidenceCorrections?: () => void
  onRevertAllCorrections?: () => void
}

export default function Header({
  isReadOnly,
  onFileLoad,
  data,
  onMetricClick,
  effectiveMode,
  onModeChange,
  apiClient,
  audioHash,
  onTimeUpdate,
  onHandlerToggle,
  isUpdatingHandlers,
  onHandlerClick,
  onFindReplace,
  onEditAll,
  onUnCorrectAll,
  onResetCorrections,
  onTimingOffset,
  timingOffsetMs = 0,
  onUndo,
  onRedo,
  canUndo,
  canRedo,
  annotationsEnabled = true,
  onAnnotationsToggle,
  reviewMode = false,
  onReviewModeToggle,
  onAcceptAllCorrections,
  onAcceptHighConfidenceCorrections,
  onRevertAllCorrections,
}: HeaderProps) {
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768

  // Get handlers with their correction counts
  const handlerCounts =
    data.corrections?.reduce(
      (counts: Record<string, number>, correction) => {
        counts[correction.handler] = (counts[correction.handler] || 0) + 1
        return counts
      },
      {} as Record<string, number>
    ) || {}

  // Get available handlers from metadata
  const availableHandlers = data.metadata.available_handlers || []
  const enabledHandlers = new Set(data.metadata.enabled_handlers || [])

  // Check if agentic mode is active
  const isAgenticMode = availableHandlers.some(
    (h: { id: string }) => h.id === 'AgenticCorrector'
  )

  // Create a map of gap IDs to their corrections
  const gapCorrections = data.corrections.reduce(
    (map: Record<string, number>, correction) => {
      const gap = data.gap_sequences.find((g) =>
        g.transcribed_word_ids.includes(correction.word_id)
      )
      if (gap) {
        map[gap.id] = (map[gap.id] || 0) + 1
      }
      return map
    },
    {} as Record<string, number>
  )

  // Calculate metrics
  const correctedGapCount = Object.keys(gapCorrections).length
  const uncorrectedGapCount = data.gap_sequences.length - correctedGapCount

  // Calculate correction type counts
  const replacedCount = data.corrections.filter(
    (c) => !c.is_deletion && !c.split_total
  ).length
  const addedCount = data.corrections.filter((c) => c.split_total).length
  const deletedCount = data.corrections.filter((c) => c.is_deletion).length

  return (
    <TooltipProvider>
      <div className="space-y-2">
        {/* Read-only indicator */}
        {isReadOnly && (
          <div className="flex items-center gap-1 text-muted-foreground text-sm mb-2">
            <Lock className="h-4 w-4" />
            <span>View Only Mode</span>
          </div>
        )}

        {/* Review Mode toggle and Load File button */}
        <div className="flex gap-2 justify-end items-center mb-2">
          {!isReadOnly && isAgenticMode && onReviewModeToggle && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge
                  variant={reviewMode ? 'default' : 'outline'}
                  className="cursor-pointer"
                  onClick={() => onReviewModeToggle(!reviewMode)}
                >
                  <Eye className="h-3 w-3 mr-1" />
                  {reviewMode ? 'Review Mode' : 'Review Off'}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                {reviewMode
                  ? 'Hide inline correction actions'
                  : 'Show inline actions on all corrections for quick review'}
              </TooltipContent>
            </Tooltip>
          )}
          {isReadOnly && (
            <Button variant="outline" size="sm" onClick={onFileLoad} className={cn(isMobile && 'w-full')}>
              <Upload className="h-4 w-4 mr-1" />
              Load File
            </Button>
          )}
        </div>

        {/* Handler panel and metrics */}
        <div className={cn('flex gap-2 mb-2', isMobile ? 'flex-col' : 'flex-row', isMobile ? 'h-auto' : 'h-[140px]')}>
          {/* Handler panel */}
          <Card className={cn('p-2', isMobile ? 'w-full' : 'w-[280px] min-w-[280px]')}>
            <h4 className="text-xs text-muted-foreground mb-1">Correction Handlers</h4>
            <div className="flex-1 overflow-auto flex flex-col">
              {availableHandlers.map((handler: { id: string; name: string; description: string }) => (
                <div key={handler.id} className="mb-1">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={enabledHandlers.has(handler.id)}
                          onCheckedChange={(checked) => onHandlerToggle(handler.id, checked)}
                          disabled={isUpdatingHandlers}
                          className="scale-75"
                        />
                        <Label
                          className="text-xs cursor-pointer"
                          onClick={() => onHandlerClick?.(handler.id)}
                        >
                          {handler.name} ({handlerCounts[handler.id] || 0})
                        </Label>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>{handler.description}</p>
                    </TooltipContent>
                  </Tooltip>
                </div>
              ))}
            </div>
          </Card>

          {/* Metrics panel */}
          <Card className="flex-1 p-2">
            <div className="grid grid-cols-3 gap-2 h-full">
              <button
                onClick={onMetricClick.anchor}
                className="flex flex-col items-center justify-center p-2 rounded hover:bg-accent transition-colors"
              >
                <span className="text-2xl font-bold">{data.metadata.anchor_sequences_count}</span>
                <span className="text-xs text-muted-foreground">Anchors</span>
              </button>
              <button
                onClick={onMetricClick.corrected}
                className="flex flex-col items-center justify-center p-2 rounded hover:bg-accent transition-colors"
              >
                <span className="text-2xl font-bold text-green-600">{correctedGapCount}</span>
                <span className="text-xs text-muted-foreground">Corrected</span>
              </button>
              <button
                onClick={onMetricClick.uncorrected}
                className="flex flex-col items-center justify-center p-2 rounded hover:bg-accent transition-colors"
              >
                <span className="text-2xl font-bold text-yellow-600">{uncorrectedGapCount}</span>
                <span className="text-xs text-muted-foreground">Uncorrected</span>
              </button>
            </div>
            <div className="flex gap-2 mt-2 justify-center text-xs">
              <Badge variant="secondary">+{replacedCount} replaced</Badge>
              <Badge variant="secondary">+{addedCount} added</Badge>
              <Badge variant="secondary">-{deletedCount} deleted</Badge>
            </div>
          </Card>
        </div>

        {/* Batch Actions Panel */}
        {!isReadOnly && reviewMode && isAgenticMode && data.corrections?.length > 0 && (
          <Card className="p-2 mb-2 bg-accent/50">
            <div className={cn('flex gap-2', isMobile ? 'flex-col' : 'flex-row items-center justify-between')}>
              <span className="text-xs text-muted-foreground">
                Batch Actions ({data.corrections.length} corrections)
              </span>
              <div className="flex gap-2 flex-wrap">
                {onAcceptHighConfidenceCorrections && (
                  <Button
                    size="sm"
                    onClick={onAcceptHighConfidenceCorrections}
                    className="bg-green-600 hover:bg-green-700 text-xs h-7"
                  >
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    Accept High Confidence ({data.corrections.filter((c) => c.confidence >= 0.8).length})
                  </Button>
                )}
                {onAcceptAllCorrections && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onAcceptAllCorrections}
                    className="text-xs h-7"
                  >
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    Accept All
                  </Button>
                )}
                {onRevertAllCorrections && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onRevertAllCorrections}
                    className="text-destructive text-xs h-7"
                  >
                    <XCircle className="h-3 w-3 mr-1" />
                    Revert All
                  </Button>
                )}
              </div>
            </div>
          </Card>
        )}

        {/* Control bar */}
        <Card className="p-2 mb-2">
          <div
            className={cn(
              'flex gap-2 items-center',
              isMobile ? 'flex-col items-start' : 'flex-row justify-between'
            )}
          >
            <div className="flex gap-1 flex-wrap items-center h-8">
              <ModeSelector effectiveMode={effectiveMode} onChange={onModeChange} />

              {!isReadOnly && onResetCorrections && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="outline" size="sm" onClick={onResetCorrections} className="h-8">
                      <Undo2 className="h-4 w-4 mr-1" />
                      Undo All
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Undo all your changes</TooltipContent>
                </Tooltip>
              )}

              {!isReadOnly && (
                <div className="flex h-8">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={onUndo}
                        disabled={!canUndo}
                        className="h-8 w-8"
                      >
                        <Undo2 className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Undo</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={onRedo}
                        disabled={!canRedo}
                        className="h-8 w-8"
                      >
                        <Redo2 className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Redo</TooltipContent>
                  </Tooltip>
                </div>
              )}

              {!isReadOnly && (
                <Button variant="outline" size="sm" onClick={onFindReplace} className="h-8">
                  <Search className="h-4 w-4 mr-1" />
                  Find/Replace
                </Button>
              )}

              {!isReadOnly && onEditAll && (
                <Button variant="outline" size="sm" onClick={onEditAll} className="h-8">
                  <Edit className="h-4 w-4 mr-1" />
                  Edit All
                </Button>
              )}

              {!isReadOnly && onUnCorrectAll && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="outline" size="sm" onClick={onUnCorrectAll} className="h-8">
                      <RotateCcw className="h-4 w-4 mr-1" />
                      Undo Auto Corrections
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Revert only automatic AI corrections (keeps your manual edits)</TooltipContent>
                </Tooltip>
              )}

              {!isReadOnly && onTimingOffset && (
                <div className="flex items-center">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onTimingOffset}
                    className={cn('h-8', timingOffsetMs !== 0 && 'border-purple-500')}
                  >
                    <Timer className="h-4 w-4 mr-1" />
                    Timing Offset
                  </Button>
                  {timingOffsetMs !== 0 && (
                    <span className="ml-1 text-sm font-bold text-purple-500">
                      {timingOffsetMs > 0 ? '+' : ''}
                      {timingOffsetMs}ms
                    </span>
                  )}
                </div>
              )}

              {!isReadOnly && onAnnotationsToggle && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onAnnotationsToggle(!annotationsEnabled)}
                      className={cn('h-8', annotationsEnabled && 'border-primary')}
                    >
                      <MessageSquare className="h-4 w-4 mr-1" />
                      {annotationsEnabled ? 'Feedback On' : 'Feedback Off'}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {annotationsEnabled
                      ? 'Click to disable annotation prompts when editing'
                      : 'Click to enable annotation prompts when editing'}
                  </TooltipContent>
                </Tooltip>
              )}

              <AudioPlayer
                audioUrl={apiClient ? apiClient.getAudioUrl(audioHash) : null}
                onTimeUpdate={onTimeUpdate}
              />
            </div>
          </div>
        </Card>
      </div>
    </TooltipProvider>
  )
}
