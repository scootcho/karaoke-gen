"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { User } from "./types"

interface AuthStore {
  user: User | null
  login: (token: string) => Promise<boolean>
  logout: () => void
  updateCredits: (credits: number) => void
}

export const useAuth = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      login: async (token: string) => {
        // In a real app, validate token with backend
        // For demo, parse token to determine role
        try {
          const isAdmin = token.toLowerCase().includes("admin")
          const user: User = {
            token,
            role: isAdmin ? "admin" : "user",
            credits: isAdmin ? 999 : 3,
          }
          set({ user })
          return true
        } catch {
          return false
        }
      },
      logout: () => set({ user: null }),
      updateCredits: (credits: number) =>
        set((state) => ({
          user: state.user ? { ...state.user, credits } : null,
        })),
    }),
    {
      name: "nomad-karaoke-auth",
    },
  ),
)
