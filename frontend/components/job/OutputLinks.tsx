"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Download, Loader2, ExternalLink, FolderOpen } from "lucide-react"

interface OutputLinksProps {
  jobId: string
}

export function OutputLinks({ jobId }: OutputLinksProps) {
  const [downloadUrls, setDownloadUrls] = useState<Record<string, any> | null>(null)
  const [youtubeUrl, setYoutubeUrl] = useState<string | null>(null)
  const [dropboxUrl, setDropboxUrl] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    loadOutputLinks()
  }, [jobId])

  async function loadOutputLinks() {
    setIsLoading(true)
    try {
      const result = await api.getDownloadUrls(jobId)
      setDownloadUrls(result.download_urls)
      
      // Extract YouTube and Dropbox URLs from state_data if available
      const job = await api.getJob(jobId)
      if (job.state_data?.youtube_url) {
        setYoutubeUrl(job.state_data.youtube_url)
      }
      if (job.state_data?.dropbox_folder_url) {
        setDropboxUrl(job.state_data.dropbox_folder_url)
      }
    } catch (err) {
      console.error("Failed to load output links:", err)
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <Loader2 className="w-3 h-3 animate-spin" />
        Loading downloads...
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {/* Distribution Links */}
      {(youtubeUrl || dropboxUrl) && (
        <div className="space-y-2">
          <p className="text-xs text-slate-400 font-medium">Distribution:</p>
          <div className="flex flex-wrap gap-2">
            {youtubeUrl && (
              <a
                href={youtubeUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded bg-red-600 hover:bg-red-500 text-white"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink className="w-3 h-3" />
                View on YouTube
              </a>
            )}
            {dropboxUrl && (
              <a
                href={dropboxUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white"
                onClick={(e) => e.stopPropagation()}
              >
                <FolderOpen className="w-3 h-3" />
                Open Dropbox Folder
              </a>
            )}
          </div>
        </div>
      )}

      {/* Download Links */}
      {downloadUrls && Object.keys(downloadUrls).length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-slate-400 font-medium">Downloads:</p>
          <div className="flex flex-wrap gap-2">
            {downloadUrls.finals?.lossy_720p && (
              <a
                href={api.getDownloadUrl(jobId, "finals", "lossy_720p")}
                className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded bg-green-600 hover:bg-green-500 text-white"
                onClick={(e) => e.stopPropagation()}
              >
                <Download className="w-3 h-3" />
                720p Video
              </a>
            )}
            {downloadUrls.finals?.lossy_4k_mp4 && (
              <a
                href={api.getDownloadUrl(jobId, "finals", "lossy_4k_mp4")}
                className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded bg-green-600 hover:bg-green-500 text-white"
                onClick={(e) => e.stopPropagation()}
              >
                <Download className="w-3 h-3" />
                4K Video
              </a>
            )}
            {downloadUrls.packages?.cdg_zip && (
              <a
                href={api.getDownloadUrl(jobId, "packages", "cdg_zip")}
                className="inline-flex items-center gap-1 text-xs px-2 py-1.5 rounded bg-slate-600 hover:bg-slate-500 text-white"
                onClick={(e) => e.stopPropagation()}
              >
                <Download className="w-3 h-3" />
                CDG+MP3
              </a>
            )}
            {downloadUrls.packages?.txt_zip && (
              <a
                href={api.getDownloadUrl(jobId, "packages", "txt_zip")}
                className="inline-flex items-center gap-1 text-xs px-2 py-1.5 rounded bg-slate-600 hover:bg-slate-500 text-white"
                onClick={(e) => e.stopPropagation()}
              >
                <Download className="w-3 h-3" />
                TXT+MP3
              </a>
            )}
          </div>
        </div>
      )}

      {!downloadUrls && !youtubeUrl && !dropboxUrl && (
        <p className="text-xs text-slate-500">No outputs available yet</p>
      )}
    </div>
  )
}

