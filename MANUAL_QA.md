# Manual Quality Assurance (QA) Strategy for Wunschkonzert

Some features in the "Wunschkonzert" application cannot be reliably automated in a headless CI/CD environment due to Digital Rights Management (DRM) restrictions, platform limitations, or the requirement of physical hardware and active paid subscriptions (e.g., Spotify Premium account binding, Spotify Web Playback SDK initialization, Apple Music subscription authentication, MusicKit JS script loading, and physical speaker output).

To ensure a high level of quality, these features must be verified manually on a Staging or local environment before major releases. The 80% automated code coverage threshold applies to the application logic, while this document serves as the guide for the remaining 20% that requires manual interaction.

## Prerequisites

To perform these manual QA tests, you will need:
- A modern desktop web browser with working audio output.
- A valid Spotify Premium account.
- A valid Apple Music subscription.
- Staging environment (or local environment) running with configured:
  - Spotify Client ID and Client Secret.
  - MusicKit Developer Token.
- A track title/artist to search.

---

## Core Manual Test Protocols

### MT-1: Spotify Search and Playback Integration

* **Objective:** Verify that searching for a Spotify track correctly resolves metadata, loads the artwork, adds the track to the queue, and plays back active DRM-protected audio with functioning UI controls.
* **Prerequisites:**
  - 1x Desktop browser with working audio output.
  - 1x Spotify Premium account logged in.
  - Track title/artist to search.
  - Application deployed on the Staging environment.
* **Execution Steps:**
  1. Log in as Host via Spotify OAuth and create a room.
  2. Search for a track by its title/artist in the search input field.
  3. Verify that the search results display the correct title, artist, and cover art.
  4. Add the song to the room queue.
  5. Click the **Play** button in the room control bar.
  6. Verify that real audio is playing from the audio output device.
  7. Click **Pause**, then **Play** again; verify audio responds immediately.
  8. Drag the playback slider (seek) to a different time and verify the track seeks correctly.
* **Expected Results:**
  - **Step 3:** Metadata resolves instantly and search results appear without errors.
  - **Step 6:** Audible sound plays with zero stuttering or DRM decode errors.
  - **Step 7 & 8:** Player state updates seamlessly and controls are fully synchronized.

### MT-2: Apple Music Search and Playback Integration

* **Objective:** Verify Apple Music integration via MusicKit JS, including user authorization, track search resolution, queue addition, and real audio stream playback.
* **Prerequisites:**
  - 1x Desktop browser with working audio output.
  - 1x Valid Apple Music subscription.
  - Track title/artist to search.
  - Staging environment with configured MusicKit Developer Token.
* **Execution Steps:**
  1. Log in as Host and authenticate Apple Music in the app via the MusicKit OAuth popup.
  2. Search for a track by its title/artist in the search input field.
  3. Verify that track details (title, artist, album art) resolve correctly in the search results.
  4. Add the track to the queue.
  5. Play the track from the queue.
  6. Verify audible playback of the stream from the browser.
  7. Test pause, resume, and volume controls, checking for correct UI updates.
* **Expected Results:**
  - **Step 1:** The MusicKit authorization modal completes and registers active login.
  - **Step 3:** The backend/frontend resolves the track details successfully.
  - **Step 6 & 7:** MusicKit streams the DRM-protected track with audible output and responsive control synchronization.

---

## Completed Runs / Sign-off History

Below is the record of completed manual QA runs executed before releases.

| Test ID | Objective | Date | Tester | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **MT-1** | Spotify Playback Integration | 1 June 2026 | Finn Steimle | **Pass** | Metadata resolves instantly, audible sound plays, and controls sync seamlessly. |
| **MT-2** | Apple Music Playback Integration | 1 June 2026 | Finn Steimle | **Pass** | MusicKit authorization is successful and streams DRM-protected tracks properly. |

---

## Coverage Exclusion Policy

Files or functions that strictly interface with third-party player SDKs, such as the Spotify Web Playback SDK (e.g., `frontend/src/lib/spotifySdk.ts`) and Apple Music MusicKit JS (e.g., `frontend/src/lib/providers/appleMusicAuth.ts`), and cannot be mocked effectively without losing their testing value, are excluded from the 80% automated coverage requirement. They must be tested via the manual procedures outlined above.
