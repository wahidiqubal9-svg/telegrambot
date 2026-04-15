# Telegram Referral Bot

This is a Telegram bot that helps you increase your public channel and group subscribers by offering access to a private channel as a reward. Users must subscribe to your public channel and group, and invite 10 friends who do the same.

## Features

- Generates unique referral links for users.
- Verifies if users have actually subscribed to your public channel and group.
- Tracks "successful" referrals (only counts if the invited friend also subscribes to the channel and group).
- Automatically generates a secure, single-use invite link to your private channel once a user reaches 10 successful referrals.
- Easy to use inline button menu.
- Uses a simple SQLite database (no extra software needed).

## Step-by-Step Setup Guide

Since you do not have prior coding experience, follow these steps exactly to get your bot running.

### Step 1: Install Python

If you don't already have Python installed on your computer or server:
1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download the latest version for your operating system.
3. **Important for Windows users:** When running the installer, make sure to check the box that says "Add Python to PATH" before clicking Install.

### Step 2: Get Your Bot Token

1. Open Telegram and search for `@BotFather`.
2. Start a chat and send the command `/newbot`.
3. Follow the instructions to give your bot a name and a username.
4. BotFather will give you a **Bot Token** (it looks something like `123456789:ABCdefGHIjklmNOPqrsTUVwxyz`). Save this token.

### Step 3: Add Bot to Channels and Groups

Your bot needs permission to check who is subscribed, and to create invite links.

1. **Public Channel:** Add your newly created bot as an **Administrator** to your Public Channel.
2. **Public Group:** Add your bot as an **Administrator** to your Public Group.
3. **Private Channel:** Add your bot as an **Administrator** to your Private Channel. It *must* have the **"Invite Users via Link"** permission.

### Step 4: Configure the Bot

1. Open the folder where you downloaded these files.
2. Find the file named `.env.example` and rename it to just `.env`
3. Open the `.env` file with any text editor (like Notepad).
4. Fill in the details:
   - `BOT_TOKEN`: Paste the token you got from BotFather.
   - `PUBLIC_CHANNEL_ID`: If your public channel has a link like `t.me/mychannel`, put `@mychannel`. (If it's private and has an ID like `-100123...`, put that).
   - `PUBLIC_GROUP_ID`: Similar to the channel, put the username like `@mygroup` or the ID.
   - `PRIVATE_CHANNEL_ID`: This is usually a number starting with `-100`. To find this ID easily, you can use a bot like `@userinfobot` or forward a message from your private channel to `@RawDataBot`.
   - `REQUIRED_REFERRALS`: Leave this as `10` or change it if you want to require more/fewer referrals.
5. Save the file.

### Step 5: Install Requirements

Open your computer's terminal or command prompt in the folder containing these files, and run this command to install the required libraries:

```bash
pip install -r requirements.txt
```

### Step 6: Run the Bot!

In the same terminal or command prompt, run the bot with this command:

```bash
python bot.py
```

You should see a message saying "Bot is starting...". Your bot is now live! Open Telegram, search for your bot's username, and press Start.
