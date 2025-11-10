# Slack Bot Integration

Slack bot for submitting clinical notes via slash commands and interactive modals.

## 🚀 Quick Setup

### 1. Create Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name: "SOAP Note Bot"
4. Select your workspace

### 2. Configure Bot

**OAuth & Permissions:**
- Add scopes:
  - `commands` - Slash commands
  - `chat:write` - Send messages
  - `users:read` - Read user info
  - `im:write` - Send DMs
- Install app to workspace
- Copy **Bot User OAuth Token**

**Slash Commands:**
Create two commands:
- `/note` - Submit a clinical note
  - Request URL: `https://your-domain.com/slack/commands` (or use ngrok for dev)
  - Description: "Submit a clinical note"
  - Usage hint: "[patient_id] | [note text]"

- `/status` - Check task status
  - Request URL: `https://your-domain.com/slack/commands`
  - Description: "Check SOAP note processing status"
  - Usage hint: "[task_id]"

**Socket Mode** (for local development):
- Enable Socket Mode
- Generate App-Level Token with `connections:write` scope
- Copy **App-Level Token**

**Event Subscriptions** (optional):
- Enable if you want to listen to channel messages

### 3. Environment Variables

Add to `.env`:

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token-here  # For Socket Mode
API_BASE_URL=http://localhost:8001
```

### 4. Install Dependencies

```bash
pip install slack-bolt httpx
```

### 5. Run Bot

```bash
# Start bot
python -m integrations.slack.bot

# Or with uvicorn for production
uvicorn integrations.slack.bot:app --host 0.0.0.0 --port 3000
```

## 📱 Usage

### Submit Note

```
/note
```

This opens a modal with:
- Patient ID field
- Visit type dropdown
- Visit date picker
- Clinical note textarea

After submission:
- Bot sends DM with task ID
- Status updates automatically
- Use `/status [task_id]` to check progress

### Check Status

```
/status 42
```

Returns:
- Current processing status
- SOAP components (if complete)
- Confidence score
- Patient info

## 🔧 Architecture

```
Slack User
    ↓
/note command
    ↓
Modal opens → User fills form
    ↓
Form submitted
    ↓
Bot validates → Calls API (/api/intake)
    ↓
API returns task_id
    ↓
Bot sends confirmation DM
    ↓
User can check status with /status [task_id]
```

## 📦 Files

- `bot.py` - Main bot logic, command handlers
- `formatters.py` - Message formatting utilities
- `README.md` - This file

## 🧪 Testing

### Test Locally with ngrok

```bash
# Start ngrok
ngrok http 3000

# Copy ngrok URL and update Slack app Request URLs
# Example: https://abc123.ngrok.io/slack/events
```

### Test Commands

1. In Slack, type `/note`
2. Fill modal and submit
3. Check your DMs for confirmation
4. Use `/status [task_id]` to see results

## 🔐 Security

- **Signature Verification**: All requests verified with signing secret
- **Token Validation**: Bot token required for API calls
- **User Context**: User info included in audit logs
- **PHI Protection**: No sensitive data in channel messages
- **DM Delivery**: Results sent via direct message only

## 🚀 Production Deployment

### With Socket Mode

```bash
# Simple - no webhooks needed
python -m integrations.slack.bot
```

### With HTTP Mode

```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-m", "integrations.slack.bot"]
```

```bash
docker build -t slack-bot .
docker run -d --env-file .env slack-bot
```

## 📊 Monitoring

**Slack provides:**
- Command usage stats
- Error logs
- Response time metrics

**In your app:**
- Log all commands to audit trail
- Track submission success rate
- Monitor API errors

## 🐛 Troubleshooting

### "dispatch_failed" error

**Cause**: Request URL not reachable or invalid

**Solution**:
1. Use Socket Mode for local dev
2. For HTTP mode, ensure ngrok/public URL is correct
3. Check Slack app settings

### Bot not responding

**Cause**: Token issues or bot not running

**Solution**:
1. Verify `SLACK_BOT_TOKEN` is correct
2. Check bot process is running: `ps aux | grep slack`
3. Review logs for errors

### Modal not opening

**Cause**: Missing `trigger_id` or expired

**Solution**:
1. Must open modal within 3 seconds of command
2. Don't cache trigger_id
3. Check for exceptions in logs

### API connection error

**Cause**: Backend API not reachable

**Solution**:
1. Verify `API_BASE_URL` in .env
2. Check backend is running: `curl http://localhost:8001/health`
3. Check network/firewall rules

## 🎯 Future Enhancements

- [ ] Shortcuts for quick note entry
- [ ] Interactive buttons (Approve/Reject)
- [ ] Scheduled reminders for incomplete notes
- [ ] Team collaboration features
- [ ] Custom commands per discipline
- [ ] Voice note transcription via Slack
- [ ] Rich formatting for SOAP display
- [ ] Multi-workspace support

## 📚 Resources

- [Slack Bolt Python](https://slack.dev/bolt-python/tutorial/getting-started)
- [Slack API Documentation](https://api.slack.com/)
- [Socket Mode Guide](https://api.slack.com/apis/connections/socket)

---

**Questions?** Check Slack app event logs and backend API logs.
