'use client'

import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { Highlighter, Edit, Trash2 } from 'lucide-react'
import { InteractionMode } from '@/lib/lyrics-review/types'

interface ModeSelectorProps {
  effectiveMode: InteractionMode
  onChange: (mode: InteractionMode) => void
}

export default function ModeSelector({ effectiveMode, onChange }: ModeSelectorProps) {
  return (
    <TooltipProvider>
      <div className="flex items-center gap-2 h-8">
        <span className="text-xs text-muted-foreground">Mode:</span>
        <ToggleGroup
          type="single"
          value={effectiveMode}
          onValueChange={(value) => value === 'edit' && onChange(value as InteractionMode)}
          className="h-8"
        >
          <Tooltip>
            <TooltipTrigger asChild>
              <ToggleGroupItem value="edit" className="h-8 px-2 text-xs">
                <Edit className="h-4 w-4 mr-1" />
                Edit
              </ToggleGroupItem>
            </TooltipTrigger>
            <TooltipContent>
              <p>Default mode; click words to edit that lyrics segment</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <ToggleGroupItem value="highlight" className="h-8 px-2 text-xs" disabled>
                <Highlighter className="h-4 w-4 mr-1" />
                Highlight
              </ToggleGroupItem>
            </TooltipTrigger>
            <TooltipContent>
              <p>Hold SHIFT and click words to highlight the matching anchor sequence</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <ToggleGroupItem value="delete_word" className="h-8 px-2 text-xs" disabled>
                <Trash2 className="h-4 w-4 mr-1" />
                Delete
              </ToggleGroupItem>
            </TooltipTrigger>
            <TooltipContent>
              <p>Hold CTRL and click words to delete them</p>
            </TooltipContent>
          </Tooltip>
        </ToggleGroup>
      </div>
    </TooltipProvider>
  )
}
