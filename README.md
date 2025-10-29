## RandomCoffee

A friendly Slack bot that automatically pairs team members for casual coffee chats every Tuesday. Perfect for building team connections and fostering a collaborative culture! ☕

### Features

- 🤖 **Auto-Filtering**: Ignores bots and admin users
- 💬 **Friendly Messages**: Sends warm, pressure-free notifications about pairings
- ⏰ **Scheduled**: Runs every Tuesday at a configurable time (default: 09:00 UTC)
- 📅 **Wednesday Suggestion**: Encourages meetups the day after pairing
- 🚨 **Error Notifications**: Automatically notifies admin of any issues via Slack DM
- 📝 **Logging**: Comprehensive logging to both file and console

### Installation

#### Using Docker (Recommended)

```bash
docker compose up -d --remove-orphans --force-recreate --build
```

#### Manual Installation

```bash
# Install dependencies
pip install slack-sdk schedule

# Run the bot
python src/gpusentry/main.py --token "xoxb-your-token" --channel "#random-coffee"
```

### Configuration

#### Option 1: Configuration File

Create a JSON configuration file (default: `/etc/random_coffee/config.json`):

```json
{
  "slack_token": "xoxb-your-slack-token"
}
```

Then run:
```bash
python main.py --config /etc/random_coffee/config.json
```

#### Option 2: Environment Variable

```bash
export SLACK_BOT_TOKEN="xoxb-your-token-here"
python main.py --channel "#random-coffee"
```

#### Option 3: Command Line Arguments

```bash
python main.py --token "xoxb-your-token" --channel "#random-coffee" --time "09:00"
```

### Command Line Options

```
--token, -t       Slack Bot OAuth Token (starts with xoxb-)
--channel, -c     Slack channel for pairings (default: #random-coffee)
--time            Daily pairing time in HH:MM format, 24-hour UTC (default: 09:00)
--config          Path to JSON configuration file (default: /etc/random_coffee/config.json)
```

### Setting Up the Slack Bot

1. **Create a Slack App**
   - Go to https://api.slack.com/apps
   - Click "Create New App" → "From scratch"
   - Name it "Random Coffee Bot" and select your workspace

2. **Add Bot Scopes**
   - Go to "OAuth & Permissions"
   - Add these scopes under "Bot Token Scopes":
     - `channels:read` - View basic channel info
     - `chat:write` - Send messages
     - `users:read` - View workspace members
     - `groups:read` - Access private channels (optional)

3. **Install to Workspace**
   - Click "Install to Workspace"
   - Authorize the app
   - Copy the "Bot User OAuth Token" (starts with `xoxb-`)

4. **Invite Bot to Channel**
   - In Slack, go to your channel (e.g., #random-coffee)
   - Type: `/invite @Random Coffee Bot`

5. **Configure Error Notifications**
   - Update `DEFAULT_ERROR_RECIPIENT` in the code to your Slack username (default: @dchebakov)

### Usage

Once running, the bot will:
1. Automatically run every Tuesday at the configured time (UTC)
2. Fetch all human members from the specified channel (excluding bots and admin)
3. Randomly shuffle and pair members
4. Send a friendly announcement message with the pairings
5. Suggest Wednesday as an optional day for coffee chats

### Example Output

```
☕ Happy Tuesday, Coffee Lovers! ☕
It's time for our weekly Random Coffee pairings! 🎉

Here are this week's wonderful pairings:

1. @Alice & @Bob ☕
2. @Charlie & @Diana ☕
3. @Eve, @Frank & @Grace ☕ (trio!)

✨ Here's the idea: ✨
Tomorrow (Wednesday) would be a lovely day for a coffee chat!
It's totally optional and there's no pressure at all. 💛

📅 Feel free to schedule a quick 15-30 minute call whenever works best for both of you.
💬 Chat about anything - hobbies, weekend plans, fun projects, or just say hi!
🤝 If this week doesn't work out, no worries! There's always next Tuesday.

Have a wonderful week, everyone! 🌟
```

### Logs

Logs are written to:
- **File**: `random_coffee.log` in the working directory
- **Console**: Standard output with timestamps

### Troubleshooting

**Bot not sending messages**
- Ensure the bot has `chat:write` permission
- Verify the bot is invited to the channel: `/invite @BotName`

**"not_in_channel" error**
- Invite the bot to your channel using `/invite @YourBotName`

**Authentication failed**
- Check your token starts with `xoxb-`
- Regenerate token if needed in Slack App settings

**No members found**
- Verify the channel name is correct (with or without #)
- Ensure bot has `channels:read` and `users:read` permissions

**Error notifications not working**
- Update `DEFAULT_ERROR_RECIPIENT` to a valid Slack username
- Ensure the user exists in your workspace

### License

MIT License
