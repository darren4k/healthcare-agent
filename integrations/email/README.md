# Email Intake Pipeline

Monitor a dedicated email inbox and automatically submit clinical notes to the API.

## 🚀 Quick Setup

### 1. Create Dedicated Email

Create a dedicated email address for note submissions:
- `notes@youragency.com`
- Or use Gmail/Outlook with app-specific password

### 2. Enable IMAP

**Gmail:**
1. Settings → Forwarding and POP/IMAP
2. Enable IMAP
3. Create App-Specific Password:
   - Google Account → Security → 2-Step Verification → App passwords
   - Generate password for "Mail"

**Outlook:**
- IMAP is enabled by default
- Use: `outlook.office365.com`

### 3. Environment Variables

Add to `.env`:

```bash
# Email Configuration
EMAIL_IMAP_SERVER=imap.gmail.com  # or imap.outlook.com
EMAIL_ADDRESS=notes@youragency.com
EMAIL_PASSWORD=your-app-specific-password
EMAIL_POLL_INTERVAL=120  # seconds
API_BASE_URL=http://localhost:8001
```

### 4. Install Dependencies

```bash
pip install aioimaplib aiosmtplib
```

### 5. Run Monitor

```bash
# Start email monitor
python -m integrations.email.monitor
```

## 📧 Email Format

### Subject Line

```
PT-12345 | 11/10 Visit
```

Or include visit type:
```
OT | PT-67890 | Morning Session
```

### Email Body

```
Patient ambulated 150 feet with rolling walker.
Reports decreased pain in right hip, now 2/10.
Balance has improved significantly.
Plan to transition to cane next week.
```

### Complete Example

```
From: therapist@agency.com
To: notes@youragency.com
Subject: PT-12345 | 11/10/2025

Patient walked 100 feet with contact guard assist.
Reports mild knee pain rated 3/10.
Gait steady with good balance.
Continue strengthening exercises.
Progress to supervision level next visit.
```

## 🤖 Parsing Logic

The parser extracts:

1. **Patient ID**: Looks for pattern like `PT-12345`, `OT-678910`
2. **Visit Type**: Finds `PT`, `OT`, `SLP`, `Nursing`, etc.
3. **Visit Date**: Parses dates in format `11/10` or `11/10/2025`
4. **Raw Note**: Uses email body as clinical note
5. **Submitter**: Uses sender's name/email

**Defaults:**
- Visit Type: `PT` (if not found)
- Visit Date: Today (if not found)
- Visit Time: Current time

## 🔄 Processing Flow

```
Email arrives
    ↓
Monitor detects (every 2 min)
    ↓
Parser extracts data
    ↓
Validates (patient ID required, note min 20 chars)
    ↓
Submits to API (/api/intake)
    ↓
Marks email as read
    ↓
(Optional) Sends confirmation email
```

## 📊 Monitoring

**Logs show:**
- Number of unread emails found
- Parsing success/failure
- API submission results
- Task IDs created

**Example Output:**
```
INFO: Connected to imap.gmail.com as notes@agency.com
INFO: Email monitor started. Polling every 120 seconds...
INFO: Found 2 unread emails
INFO: Email 1 submitted successfully. Task ID: 42
INFO: Email 2 submitted successfully. Task ID: 43
```

## 🔐 Security

- **App-Specific Passwords**: Never use main email password
- **Dedicated Inbox**: Separate from personal email
- **Auto-Delete**: Emails can be deleted after processing
- **Encryption**: Use TLS/SSL for IMAP connection
- **Audit Trail**: All submissions logged

## 🧪 Testing

### Send Test Email

```bash
# Using mail command (Linux/Mac)
echo "Patient walked 100ft with CGA. Mild pain 3/10." | \
  mail -s "PT-12345 | 11/10 Visit" notes@youragency.com

# Or use your email client
```

### Check Logs

```bash
# Watch logs in real-time
python -m integrations.email.monitor

# Should see:
# INFO: Found 1 unread emails
# INFO: Email 1 submitted successfully. Task ID: 45
```

## 🐛 Troubleshooting

### "Authentication failed"

**Cause**: Wrong password or app-specific password not enabled

**Solution**:
1. For Gmail: Create app-specific password
2. Verify EMAIL_ADDRESS and EMAIL_PASSWORD
3. Check 2FA settings

### "Connection timeout"

**Cause**: IMAP server unreachable or firewall

**Solution**:
1. Verify EMAIL_IMAP_SERVER (imap.gmail.com, imap.outlook.com)
2. Check firewall rules (port 993 for IMAPS)
3. Try different network

### "Could not extract patient ID"

**Cause**: Email format doesn't match parsing pattern

**Solution**:
1. Include patient ID in subject: `PT-12345`
2. Or in first line of body
3. Use format: `[A-Z]{2,3}-[0-9]{4,6}`

### "Clinical note too short"

**Cause**: Email body < 20 characters

**Solution**:
1. Include more detailed clinical information
2. Check parser isn't cutting off body text
3. Review `_clean_body()` logic

## 📈 Future Enhancements

- [ ] Audio attachment transcription (Whisper API)
- [ ] PDF attachment parsing
- [ ] Confirmation email replies
- [ ] Multiple inbox support
- [ ] Rich HTML email parsing
- [ ] Attachment storage (images, documents)
- [ ] Auto-categorization by sender
- [ ] Retry failed submissions
- [ ] Email templates for staff
- [ ] Integration with Outlook/Gmail APIs

## 🚀 Production Deployment

### Systemd Service (Linux)

```ini
# /etc/systemd/system/email-monitor.service
[Unit]
Description=SOAP Note Email Monitor
After=network.target

[Service]
Type=simple
User=soapnote
WorkingDirectory=/opt/healthcare-agent
ExecStart=/usr/bin/python3 -m integrations.email.monitor
Restart=always
RestartSec=10
EnvironmentFile=/opt/healthcare-agent/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable email-monitor
sudo systemctl start email-monitor
sudo systemctl status email-monitor
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-m", "integrations.email.monitor"]
```

```bash
docker build -t email-monitor .
docker run -d --env-file .env --name email-monitor email-monitor
```

## 📚 Resources

- [aioimaplib Documentation](https://github.com/bamthomas/aioimaplib)
- [Gmail IMAP Settings](https://support.google.com/mail/answer/7126229)
- [Outlook IMAP Settings](https://support.microsoft.com/en-us/office/pop-imap-and-smtp-settings-8361e398-8af4-4e97-b147-6c6c4ac95353)

---

**Questions?** Check monitor logs and verify email format.
