"use client"

import { useState } from "react"
import { KeyRound } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { setAccessToken } from "@/lib/api"

interface AuthDialogProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
}

export function AuthDialog({ open, onClose, onSuccess }: AuthDialogProps) {
  const [token, setToken] = useState("")
  const [error, setError] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (token.trim()) {
      setAccessToken(token.trim())
      setError("")
      setToken("")  // Clear token from state for security
      onSuccess()
    } else {
      setError("Please enter a valid token")
    }
  }

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md bg-slate-900 border-slate-700">
        <DialogHeader>
          <DialogTitle className="text-white flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-amber-400" />
            Authentication Required
          </DialogTitle>
          <DialogDescription className="text-slate-400">
            Enter your access token to use the Karaoke Generator
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Input
              type="password"
              placeholder="Enter access token"
              value={token}
              onChange={(e) => {
                setToken(e.target.value)
                setError("")
              }}
              className="bg-slate-800 border-slate-600 text-white"
              autoFocus
            />
            {error && (
              <p className="text-xs text-red-400 mt-1">{error}</p>
            )}
          </div>
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              className="text-slate-400"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!token.trim()}
              className="bg-amber-600 hover:bg-amber-500"
            >
              Authenticate
            </Button>
          </div>
          <p className="text-xs text-slate-500 text-center">
            Contact an admin to get an access token
          </p>
        </form>
      </DialogContent>
    </Dialog>
  )
}
