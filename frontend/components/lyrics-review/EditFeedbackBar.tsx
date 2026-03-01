'use client'

import { useEffect, useRef, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { X } from 'lucide-react'
import type { EditLogEntry, EditFeedbackReason } from '@/lib/lyrics-review/types'

const REASONS_BY_OP: Record<string, { label: string; reason: EditFeedbackReason }[]> = {
  word_change: [
    { label: 'Mis-heard word', reason: 'misheard_word' },
    { label: 'Wrong lyrics', reason: 'wrong_lyrics' },
    { label: 'Spelling/punctuation', reason: 'spelling_punctuation' },
    { label: 'Other', reason: 'other' },
  ],
  word_delete: [
    { label: 'Phantom word', reason: 'phantom_word' },
    { label: 'Duplicate', reason: 'duplicate_word' },
    { label: 'Mis-heard word', reason: 'misheard_word' },
    { label: 'Other', reason: 'other' },
  ],
  word_add: [
    { label: 'Missing word', reason: 'missing_word' },
    { label: 'Split word', reason: 'split_word' },
    { label: 'Other', reason: 'other' },
  ],
}

function getQuestionText(entry: EditLogEntry): string {
  const before = entry.text_before.trim()
  const after = entry.text_after.trim()
  switch (entry.operation) {
    case 'word_change':
      return `Changed "${before}" → "${after}", why?`
    case 'word_delete':
      return `Removed "${before}", why?`
    case 'word_add':
      return `Added "${after}", why?`
    default:
      return `Edit made, why?`
  }
}

interface EditFeedbackBarProps {
  entry: EditLogEntry | null
  visible: boolean
  onFeedback: (entryId: string, reason: EditFeedbackReason) => void
  onDismiss: () => void
}

export default function EditFeedbackBar({
  entry,
  visible,
  onFeedback,
  onDismiss,
}: EditFeedbackBarProps) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const entryIdRef = useRef<string | null>(null)
  const hoveredRef = useRef(false)
  const remainingRef = useRef(10_000)
  const startedAtRef = useRef<number | null>(null)

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const startTimer = useCallback((ms: number) => {
    clearTimer()
    startedAtRef.current = Date.now()
    remainingRef.current = ms
    timerRef.current = setTimeout(() => {
      if (entry) {
        onFeedback(entry.id, 'no_response')
        onDismiss()
      }
    }, ms)
  }, [clearTimer, entry, onFeedback, onDismiss])

  const handleMouseEnter = useCallback(() => {
    hoveredRef.current = true
    if (timerRef.current && startedAtRef.current !== null) {
      const elapsed = Date.now() - startedAtRef.current
      remainingRef.current = Math.max(0, remainingRef.current - elapsed)
      clearTimer()
    }
  }, [clearTimer])

  const handleMouseLeave = useCallback(() => {
    hoveredRef.current = false
    if (visible && entry && remainingRef.current > 0) {
      startTimer(remainingRef.current)
    }
  }, [visible, entry, startTimer])

  useEffect(() => {
    clearTimer()

    if (!visible || !entry) return

    // If this is a new entry, start the auto-dismiss timer
    if (entry.id !== entryIdRef.current) {
      entryIdRef.current = entry.id
      remainingRef.current = 10_000
      if (!hoveredRef.current) {
        startTimer(10_000)
      }
    }

    return clearTimer
  }, [visible, entry, clearTimer, startTimer])

  if (!visible || !entry) return null

  const reasons = REASONS_BY_OP[entry.operation] ?? REASONS_BY_OP.word_change

  return (
    <div
      className="fixed bottom-[52px] left-0 right-0 z-40 flex justify-center animate-in slide-in-from-bottom-2 duration-200"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div className="bg-muted/95 backdrop-blur-sm border-t border-b px-4 py-2 flex items-center gap-3 w-full max-w-4xl">
        <span className="text-sm text-muted-foreground shrink-0 truncate max-w-[280px]">
          {getQuestionText(entry)}
        </span>
        <div className="flex items-center gap-1.5 flex-wrap">
          {reasons.map((r) => (
            <Button
              key={r.reason}
              variant="outline"
              size="sm"
              className="h-7 text-xs px-2.5"
              onClick={() => {
                clearTimer()
                onFeedback(entry.id, r.reason)
                onDismiss()
              }}
            >
              {r.label}
            </Button>
          ))}
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 w-7 p-0 ml-auto shrink-0"
          onClick={() => {
            clearTimer()
            onFeedback(entry.id, 'no_response')
            onDismiss()
          }}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}
