# Gold & Bitcoin — Hindi YouTube Automation

This repository builds an educational Gold & Bitcoin video on GitHub Actions and uploads it through the official YouTube Data API.

## Current behavior

- Scheduled for one run per day at **7:00 PM India Standard Time** (13:30 UTC). GitHub may delay scheduled runs during busy periods.
- Uses five pre-written evergreen topics in Hindi. It cycles through them in order, then repeats after the fifth topic. This is **not yet a live-news or current-price research pipeline**.
- Creates 8 visual scenes with a free synthetic Hindi voice (espeak-ng) and Hindi-capable Noto fonts.
- Attempts to upload a custom 16:9 thumbnail after the video upload. YouTube may reject custom thumbnails if the channel is not eligible or API permissions are unavailable.
- Scheduled uploads use **Public** visibility. The manual workflow defaults to a safe **validate-only** run and does not upload a video.
- No paid AI API is used. Video originality and quality are limited by the supplied topic scripts. Add and fact-check more original scripts before relying on this for a long-running channel.

## 1. GitHub Actions

Open the repository's **Actions** tab and ensure Actions are enabled.

The workflow file is **.github/workflows/daily-videos.yml**; it runs daily at 13:30 UTC (7:00 PM IST). Scheduled runs use GitHub-hosted Linux runners, so your Windows PC does not need to stay on.

### Run a safe validation

1. Open **Actions**.
2. Select **Build and upload Gold & Bitcoin video**.
3. Choose **Run workflow**.
4. Keep the **video_slot** input set to **validate** and start the run.

This mode installs dependencies, compiles main.py, checks the Hindi topic JSON, tests Hindi speech synthesis, and checks whether the OAuth secret is present and structurally contains a refresh token without printing its value. It does **not** call the YouTube upload code. It does not perform a live Google authorization refresh.

Do not change the input to **1** for testing unless you deliberately want to perform a real public upload.

## 2. YouTube API and OAuth setup

The repository connector cannot read repository secret values, so check the secret name in GitHub yourself. The required secret is **YOUTUBE_TOKEN_JSON**.

1. Open https://console.cloud.google.com/ and create/select a Google Cloud project.
2. Enable **YouTube Data API v3**.
3. Configure the OAuth consent screen and authorize the Google account that owns your YouTube channel.
4. Create an OAuth Client ID of type **Desktop app** and download its JSON as **client_secret.json**. Never commit this file.
5. In the project folder, use Python and install requirements with **pip install -r requirements.txt**.
6. Create **authorize.py** containing:

~~~python
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
with open("token.json", "w", encoding="utf-8") as f:
    f.write(creds.to_json())
print("Created token.json. Keep it private.")
~~~

7. Run **python authorize.py**, sign in to the correct Google account, and approve upload permission.
8. In PowerShell, from the folder containing token.json, run:

~~~powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("token.json")) | Set-Clipboard
~~~

9. In GitHub, go to **Settings → Secrets and variables → Actions → New repository secret**. Set the name to **YOUTUBE_TOKEN_JSON** and paste the clipboard value into the secret's value field.

Never paste the token into ChatGPT/Claude, an issue, a commit, or a screenshot. Do not expose the secret value. The code decodes it inside the workflow runner only.

The Python dependency constraint for google-auth is capped below 2.42.0 because the installed google-auth-oauthlib release requires that range.

## 3. Publishing behavior

- Manual run with **video_slot=validate**: safe checks only; no YouTube upload.
- Scheduled run at 7 PM IST: builds the selected Hindi topic and uploads it as **Public**.
- Script topics recur after five days until more original topic scripts are added.
- The code currently does not fetch live Gold/Bitcoin prices or breaking news. Do not label the video as breaking news or state a price as current unless a reliable, timestamped data source is added.
- Uploads may fail because of missing/expired OAuth, YouTube quota, channel eligibility, or YouTube policy restrictions. A schedule alone does not guarantee a successful upload.

## Troubleshooting

- **Missing YOUTUBE_TOKEN_JSON:** add the repository secret with exactly that name.
- **invalid_grant / expired authorization:** repeat the OAuth authorization locally and replace the secret with a fresh token.
- **Dependency resolution error:** use the committed requirements.txt; it caps google-auth below 2.42.0.
- **Hindi speech test fails:** inspect the validate run logs for the espeak-ng Hindi voice command.
- **Thumbnail skipped:** check channel eligibility and YouTube API access; the video upload may still have succeeded.
