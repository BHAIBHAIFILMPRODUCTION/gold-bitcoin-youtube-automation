# Gold & Bitcoin — free YouTube automation starter

This starter creates a simple educational video with slides, synthetic English narration, and a financial disclaimer, then uploads it publicly to YouTube using the official YouTube Data API.

## What is free / what is not guaranteed

- GitHub Actions standard runners are free for public repositories.
- Python, FFmpeg, Pillow, and espeak-ng are free/open-source.
- YouTube Data API has quota and policy limits.
- No paid AI API is used. This means there is no LLM researching fresh news or writing nuanced new scripts. The included topics are evergreen educational scripts and the voice is synthetic/robotic.
- Two daily uploads are attempted, not guaranteed. Workflow failures, OAuth revocation, quotas, upload limits, or YouTube policies can interrupt runs.
- The code intentionally creates basic slide videos; review content quality before relying on public auto-publishing. Add original analysis and meaningful editing rather than mass-producing near-identical videos.

## 1. Create a new public GitHub repository

Create a repository named `gold-bitcoin-youtube-automation`, set it to **Public**, and upload all files from this folder, including `.github/workflows/daily-videos.yml`.

Do not commit `token.json`, `client_secret.json`, access tokens, or API secrets.

## 2. Enable YouTube Data API and create OAuth credentials

1. Open https://console.cloud.google.com/
2. Create a project.
3. Open APIs & Services → Library → enable **YouTube Data API v3**.
4. Configure the OAuth consent screen. Add your own Google account as a test user if required.
5. Create an OAuth Client ID of type **Desktop app** and download its JSON file as `client_secret.json`.
6. Verify your YouTube account if you need to upload videos longer than 15 minutes. This starter normally creates shorter videos.

## 3. Authorize your channel locally

Use a computer with Python installed. Download/clone this repository and put `client_secret.json` in the project folder (do not upload it to GitHub).

Install dependencies:
```bash
pip install -r requirements.txt
```

Create `authorize.py` with:
```python
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
with open("token.json", "w", encoding="utf-8") as f:
    f.write(creds.to_json())
print("Created token.json. Keep it secret.")
```

Run:
```bash
python authorize.py
```
Sign in to the Google account that owns the channel and approve upload access. Keep `token.json` private.

## 4. Add the GitHub Actions secret

Encode `token.json` as one line of Base64.

**Windows PowerShell:**
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("token.json")) | Set-Clipboard
```

**macOS/Linux:**
```bash
base64 -w 0 token.json
```

In your repository go to **Settings → Secrets and variables → Actions → New repository secret**:
- Name: `YOUTUBE_TOKEN_JSON`
- Value: paste the full Base64 output

Never put this value in source code, an issue, or a public message. If exposed, revoke the OAuth access and create a fresh token.

## 5. Run a test first

Open Actions → “Build and upload Gold & Bitcoin video” → Run workflow. The starter uses public upload mode. To test safely, change `privacyStatus` in `main.py` from `public` to `unlisted`, run once, inspect the result, then switch it back to `public` when satisfied.

## 6. Schedule

The workflow is set for 09:00 and 17:00 India Standard Time daily. GitHub scheduled workflows use UTC. GitHub may delay scheduled runs during high load; it is not an exact-time scheduler.

## 7. Customize

Edit `topics.json` with original, fact-checked scripts and add new topic objects. The script currently uses English synthetic narration and evergreen education, not live prices or breaking news. Never describe a generated price as current unless you add a reliable, timestamped data source.

## Troubleshooting

- `Missing YOUTUBE_TOKEN_JSON`: check the repository secret name.
- `invalid_grant`: rerun local authorization and replace the secret with a fresh token. OAuth consent configuration can affect refresh-token lifetime.
- `quotaExceeded`: check Google Cloud Console quota for the YouTube Data API.
- `ffmpeg` or `espeak-ng` failure: inspect the Actions job log.
- Upload succeeds but content quality is weak: improve scripts, visuals, and narration before leaving automatic public uploads enabled.
