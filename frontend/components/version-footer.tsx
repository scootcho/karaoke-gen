"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function VersionFooter() {
  const [backendVersion, setBackendVersion] = useState<string | null>(null);
  // Frontend version is injected at build time from pyproject.toml
  const frontendVersion = process.env.NEXT_PUBLIC_APP_VERSION || "dev";

  useEffect(() => {
    const fetchBackendVersion = async () => {
      try {
        const info = await api.getBackendInfo();
        setBackendVersion(info.version);
      } catch (error) {
        console.error("Failed to fetch backend version:", error);
        setBackendVersion(null);
      }
    };

    fetchBackendVersion();
  }, []);

  return (
    <footer className="border-t mt-12 py-6" style={{ borderColor: 'var(--card-border)' }}>
      <div className="px-4 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
        <p>
          Powered by{" "}
          <a href="https://github.com/nomadkaraoke/karaoke-gen" className="text-amber-500 hover:underline">
            karaoke-gen
          </a>
        </p>
        <p className="mt-1 text-xs opacity-75">
          Frontend: v{frontendVersion}
          {backendVersion && (
            <>
              {" | "}
              Backend: v{backendVersion}
            </>
          )}
        </p>
      </div>
    </footer>
  );
}
