# MidiCo Synchronizer Reference

This document provides a detailed reference for replicating the MidiCo Synchronizer user experience in our Nomad Karaoke lyrics review UI. The MidiCo Synchronizer is a native macOS application that provides a polished, intuitive interface for manually syncing lyrics to audio.

## Problem Statement

Sometimes transcribed lyrics are correct and start well-synced, but progressively drift out of sync towards the second half of the song. We need an efficient way to fix timing for multiple segments without having to re-sync everything from scratch.

## Overview of MidiCo Interface

MidiCo consists of two windows:
1. **Main Audio Player Window** - Controls audio playback
2. **Synchronizer Window** - Timeline-based lyrics sync interface

![Empty Timeline Before Sync](midico-sync-screenshots/MidiCo-Synchronizer-2025-12-18-Empty-Timeline-Before-Any-Words-Synced.png)

---

## 1. Audio Player Integration

The main MidiCo window provides an audio player that stays synchronized with the Synchronizer:

- **Play/Pause/Stop buttons** - Standard playback controls
- **Rewind/Fast-forward buttons** - Skip through the track
- **Progress slider** - Shows current position (00:00 format) and remaining time (-03:45 format)
- **Volume slider** - Control audio volume
- **Tempo/Pitch sliders** - Adjust playback speed and pitch (useful for difficult sections)

**Key behavior:** The playhead position is always synced between the audio player and the Synchronizer timeline.

---

## 2. Synchronizer Primary View

The Synchronizer window contains the main timeline interface for syncing lyrics.

### 2.1 Top Control Buttons

Four main control buttons at the top:

| Button | Function |
|--------|----------|
| **Voice no.1** | Select which vocal track to sync (for multi-voice karaoke) |
| **Start Sync** | Begin sync mode - starts audio, shows upcoming words, listens for spacebar |
| **Clear Sync** | Delete all sync data, reset to unsynced state |
| **Edit Lyrics** | Open modal to edit the lyrics text directly |
| **Import Lrc** | Import timing data from an LRC file |

### 2.2 Timeline View

The main rectangular timeline area is the core of the interface.

![During Sync Showing Synced And Upcoming Words](midico-sync-screenshots/MidiCo-Synchronizer-2025-12-18-During-Sync-Showing-Synced-And-Upcoming-Words.png)

#### Time Bar (Top Strip)
- Thin bar at the top showing time in `MM:SS` format
- Small tick marks for decisecond precision
- Clicking anywhere on the time bar sets the playhead position (without changing playback state)

#### Playhead Marker
- Small arrow/triangle indicator in the time bar
- White vertical line spanning the full height of the timeline
- Shows current playback position
- Synced with the audio player position

#### Timeline Background
- Light gray gradient background
- **Clicking on the background does nothing** (prevents accidental deselection)
- **Click-drag creates a selection rectangle** for selecting multiple word blocks

#### Zoom Control
- Horizontal slider below the timeline labeled "Zoom"
- Smooth continuous zoom (approximately 50 notches)
- **Most zoomed in:** ~4.5 seconds visible edge-to-edge
- **Most zoomed out:** ~24 seconds visible edge-to-edge
- Smooth, responsive zooming is critical for fast songs

![Max Zoom Level](midico-sync-screenshots/MidiCo-Synchronizer-2025-12-18-During-Sync-Showing-Max-Zoom-Level.png)

#### Horizontal Scrolling
- Timeline scrolls horizontally to show different parts of the song
- Small horizontal scrollbar at the bottom of the timeline area
- During sync mode, the timeline auto-scrolls to follow the playhead

### 2.3 Word Blocks

Synced words appear as **red rectangular blocks** on the timeline:

- Each block shows the word text above the red bar
- Block width corresponds to the word's duration
- Block horizontal position corresponds to the word's start time

#### Two-Level Word Layout

When words from different segments overlap in time or are close together, they display on two vertical levels to avoid visual overlap:

![Two Level Word Blocks](midico-sync-screenshots/MidiCo-Synchronizer-2025-12-18-During-Sync-Showing-Two-Levels-Word-Blocks.png)

This is particularly useful for:
- Songs with backing vocals
- Fast sections where words are close together
- Overlapping vocal lines

#### Word Block Selection

- **Single click** on a word block: Selects that block (shown with white 1px border)
- **Click-drag on background**: Creates selection rectangle to select multiple blocks

![Click Drag Word Selection](midico-sync-screenshots/MidiCo-Synchronizer-2025-12-18-Click-Drag-Word-Selection.png)

### 2.4 Upcoming Words Display

During sync mode, unsynced words appear in **two locations**:

![Start Sync Showing Upcoming Words](midico-sync-screenshots/MidiCo-Synchronizer-2025-12-18-Start-Sync-Showing-Upcoming-Words.png)

1. **Fixed position above time bar** (left side): Shows upcoming words as red/white blocks in a horizontal row. The next word to sync is highlighted in red, subsequent words in white.

2. **On the timeline, right of playhead**: Same words appear starting from the playhead position and extending to the right, moving along with the playhead during playback.

This dual display makes it easy to:
- See what's coming next (fixed position - easy to read while focused on timing)
- See where words will land on the timeline relative to already-synced words

---

## 3. Action Buttons (Icon Toolbar)

A row of small icon-only buttons appears above the timeline. Key buttons we need:

### Essential Buttons

| Icon | Tooltip | Function |
|------|---------|----------|
| **AI** | Split, spell or edit selected word | Opens popup to edit a single word. Useful for typos. Entering multiple space-separated words splits the selected word while preserving timing. |
| **Clock with X** | Unsynchronize from cursor position | All word blocks **after** the current playhead position are reset to unsynced state. Critical for fixing drift in later parts of a song. |
| **Trash** | Delete selected | Deletes selected word(s) entirely. Useful for removing backing vocals or nonsense words. |

### Typical Workflow for Deleting Unwanted Words

1. Tap spacebar to sync the unwanted words (so they appear on timeline)
2. Stop playback
3. Click-drag to select the unwanted word blocks
4. Click trash icon to delete
5. Click Start Sync to resume syncing from where you left off

---

## 4. Sync Mode Operation

### Starting Sync

1. Click **Start Sync** button
2. Audio begins playing from current playhead position
3. Upcoming unsynced words appear in both display locations
4. System begins listening for spacebar input

### Spacebar Timing

Two input modes:

**Tap (press and release quickly):**
- Sets the **start time** of the next unsynced word to the current playhead position
- The word's **end time** is set when the following word is synced
- If gap between words > 1 second, previous word gets default 1 second duration

**Press-hold:**
- Hold spacebar down when word starts
- Release when word ends
- Sets both start and end times explicitly

### Stopping Sync

- Click the **Stop** button (replaces Play when in sync mode)
- Or click **Start Sync** again to toggle off
- Sync progress is preserved

---

## 5. Edit Lyrics Modal

![Lyrics Editor Modal](midico-sync-screenshots/MidiCo-Synchronizer-2025-12-18-Lyrics-Editor-Modal.png)

Accessed via the **Edit Lyrics** button. Provides:

- **Left panel**: Plain text editor with all lyrics, newlines separate segments
- **Right panel**: Preview of how lyrics will appear (karaoke style rendering)
- **Language selector**: For hyphenation support
- **Hyphenate button**: Auto-hyphenate words for syllable-level sync
- **Reset button**: Revert to original lyrics
- **Cancel/OK buttons**: Discard or apply changes

### Important Behavior

Editing lyrics when there are already synced timestamps **usually messes up the syncs**. Users typically need to Clear Sync and start over after editing lyrics.

---

## 6. Apply Button

The **Apply** button in the bottom-right corner is critical:

- Changes made in the Synchronizer are **not saved** until Apply is clicked
- This allows experimenting without fear of losing work
- If sync goes badly wrong, user can close the Synchronizer without applying changes
- Provides a safe "sandbox" for sync work

---

## 7. Performance Requirements

The entire interface must be:

- **Smooth and responsive** - No lag or stutter during playback
- **Low latency** - Spacebar input must register with sub-100ms precision
- **Efficient** - No unnecessary computation during sync (user is focused on timing)
- **Native-app feel** - As expected from a macOS application

Since we're dealing with sub-second time precision for synced lyrics, performance is critical.

---

## 8. Implementation Notes for Our App

### Entry Point: "Edit All" Button

The current "Edit All" button should show a choice:
1. **Replace all lyrics** - Shows the existing paste box flow (for completely new lyrics)
2. **Re-sync existing lyrics** - Goes directly to the new Synchronizer view with all existing words/segments plotted on the timeline

This preserves existing sync data while allowing re-sync of later portions.

### Key Features to Implement

1. **Timeline with word blocks showing existing sync data**
2. **Playhead synced with audio player**
3. **Zoom slider (4.5s to 24s range)**
4. **Horizontal scrolling**
5. **Two-level word block layout**
6. **Start Sync mode with spacebar capture**
7. **Upcoming words display (fixed + timeline)**
8. **"Unsynchronize from cursor" - critical for fixing drift**
9. **Word selection (single click + drag-select)**
10. **Delete selected words**
11. **Edit single word popup**
12. **Apply/Cancel for safe experimentation**

### Fixing Timing Drift (Primary Use Case)

The main workflow for fixing drift:

1. Open Synchronizer (with existing sync data loaded)
2. Play audio to find where sync starts drifting
3. Position playhead at last correctly-synced word
4. Click "Unsynchronize from cursor position"
5. Click "Start Sync" to resume syncing from that point
6. Tap spacebar to re-sync the remaining words
7. Click "Apply" when done

This workflow allows keeping good sync data while fixing only the problematic portion.

---

## Screenshots Reference

All screenshots are located in: `docs/midico-sync-screenshots/`

| Filename | Description |
|----------|-------------|
| `MidiCo-Synchronizer-2025-12-18-Empty-Timeline-Before-Any-Words-Synced.png` | Initial state with empty timeline |
| `MidiCo-Synchronizer-2025-12-18-Start-Sync-Showing-Upcoming-Words.png` | Sync mode started, showing upcoming words in both locations |
| `MidiCo-Synchronizer-2025-12-18-During-Sync-Showing-Synced-And-Upcoming-Words.png` | Mid-sync showing both synced blocks and upcoming words |
| `MidiCo-Synchronizer-2025-12-18-During-Sync-Showing-Two-Levels-Word-Blocks.png` | Demonstration of two-level word block layout |
| `MidiCo-Synchronizer-2025-12-18-During-Sync-Showing-Max-Zoom-Level.png` | Maximum zoom level (~4.5 seconds visible) |
| `MidiCo-Synchronizer-2025-12-18-Click-Drag-Word-Selection.png` | Selection rectangle for multi-word selection |
| `MidiCo-Synchronizer-2025-12-18-Lyrics-Editor-Modal.png` | Edit Lyrics modal dialog |
