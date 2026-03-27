# Manual QA Strategy for Wunschkonzert

Some features in the "Wunschkonzert" application cannot be reliably automated in a headless CI/CD environment due to Digital Rights Management (DRM) restrictions, platform limitations, or the requirement of physical hardware (e.g., Spotify Premium account binding, Web Playback SDK instantiation, physical speaker output).

To ensure a high level of quality, these features must be verified manually before major releases. The 80% automated code coverage threshold applies to the application logic, while this document serves as the guide for the remaining 20% that requires manual interaction.

## Prerequisites
- A valid Spotify Premium account.
- A physical testing device (Laptop, Smartphone) with an active speaker/headphone connection.
- Local development environment running (`docker compose up`).

## Core Manual Test Cases

### 1. Spotify Web Playback SDK Initialization
- **Action:** Open the host view of a room in a modern browser (Chrome, Firefox, Safari).
- **Verification:** Ensure the browser prompts for Spotify authentication if not already authenticated.
- **Verification:** Confirm that the Web Playback SDK successfully initializes and logs "Ready" in the browser console.
- **Verification:** Verify that a new Spotify Connect device named "Wunschkonzert - [Room Name]" appears in the Spotify app or web player.

### 2. DRM-Protected Audio Playback
- **Action:** Add a track to the queue via the guest interface and ensure it is the currently playing track.
- **Action:** Trigger playback via the host interface.
- **Verification:** Confirm that the audio plays correctly through the local speakers.
- **Verification:** Ensure there are no DRM-related errors (e.g., `Failed to initialize media keys`) in the browser console.

### 3. Real-Time Synchronization (Visual & Audio)
- **Action:** Pause playback on the host interface.
- **Verification:** Confirm the audio stops playing.
- **Verification:** Confirm all connected guest clients visually reflect the "Paused" state within 1 second.
- **Action:** Skip to the next track.
- **Verification:** Confirm the new track begins playing and guest interfaces update to show the new current track.

### 4. Hardware & Session Handover
- **Action:** While music is playing on the Wunschkonzert device, open the native Spotify app on a smartphone and select a different playback device (e.g., a smart speaker).
- **Verification:** Confirm that Wunschkonzert detects the device change and pauses or visually indicates that playback has been moved.

## Coverage Exclusion Policy
Files or functions that strictly interface with the Spotify Web Playback SDK (e.g., `frontend/src/lib/spotifySdk.ts`) and cannot be mocked effectively without losing their testing value are excluded from the 80% automated coverage requirement. They must be tested via the procedures outlined above.
