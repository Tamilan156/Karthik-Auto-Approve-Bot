# Karthik-Auto-Approve-Bot

Advanced Telegram Auto Approve Bot built with Python.

## Features
- Automatically approves Telegram join requests.
- Sends a welcome message to approved members.
- Admin-only ban and unban commands.
- Optional spam auto-ban feature.

## Requirements
- Python 3.10 or newer
- Telegram Bot Token
- Telegram Admin User ID

## Configuration
Set these environment variables in your hosting service:

- BOT_TOKEN
- ADMIN_IDS
- WELCOME_MESSAGE
- SPAM_BAN_ENABLED
- SPAM_THRESHOLD
- SPAM_WINDOW_SECONDS

## Deploy
This project is configured to run as a worker using the Procfile.

Never share your bot token publicly.