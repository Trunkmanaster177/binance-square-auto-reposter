# Binance Square Auto Reposter

Automatically monitors a Binance Square creator and reposts new text posts to your own Binance Square account.

## Source

Default source:

TF_bnb

## How it works

Every 5 minutes:

1. Fetch Binance Square latest feed.
2. Find posts from TF_bnb.
3. Compare post IDs against src/state.json.
4. Detect new posts.
5. Publish new text posts using Binance Square OpenAPI.
6. Save processed post IDs.
7. GitHub Actions commits the updated state.

## Setup

### 1. Create a GitHub repository

Create a new repository and upload the project files.

### 2. Create a Binance Square OpenAPI key

Create your Square OpenAPI key from Binance Creator Center.

Do not put the key inside the source code.

### 3. Add GitHub Secret

Go to:

Repository
→ Settings
→ Secrets and variables
→ Actions
→ New repository secret

Name:

BINANCE_SQUARE_OPENAPI_KEY

Value:

Your Binance Square OpenAPI key.

### 4. Enable Actions

Open:

Actions

Then enable workflows if GitHub asks.

### 5. Test manually

Go to:

Actions
→ Binance Square Auto Reposter
→ Run workflow

The first run initializes existing posts.

It does NOT repost old posts.

New posts appearing after initialization will be reposted.

## Changing the source

Change:

SOURCE_AUTHOR

inside:

.github/workflows/square-reposter.yml

Example:

SOURCE_AUTHOR: another_creator

## Important

The monitor uses a Binance Square feed endpoint that is not documented as an official public reading API.

The publishing API requires a Binance Square OpenAPI key.

The monitoring endpoint may change in the future.
