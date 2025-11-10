# 🎬 Visibility & Live Monitoring Features

## Overview

Enhanced browser automation visibility features for transparency, demonstration, trust-building, and debugging. This includes real-time WebSocket dashboards, video recording, slow motion mode, and Playwright tracing.

---

## 🚀 Features

### 1. **Real-Time WebSocket Dashboard**

Live monitoring of browser automation tasks with step-by-step progress updates.

**What You Get:**
- ✅ Real-time task progress (Step X of Y)
- ✅ Live progress bars (0-100%)
- ✅ Current action descriptions ("Logging in...", "Filling form...")
- ✅ Screenshot previews (updated as automation runs)
- ✅ Error notifications with error screenshots
- ✅ Task completion notifications
- ✅ Recovery attempt tracking

**WebSocket Endpoints:**
```
ws://localhost:8001/ws/tasks/{task_id}  # Watch specific task
ws://localhost:8001/ws/tasks            # Watch all tasks
```

**Frontend Component:**
- Location: `frontend/src/pages/LiveTasksPage.jsx`
- Features: Active tasks list, completed tasks, live screenshots, event log

---

### 2. **Video Recording**

Record full automation sessions as video files for review, training, and auditing.

**Configuration:**
```bash
# Enable video recording
ENABLE_VIDEO_RECORDING=true
VIDEO_QUALITY=720p
```

**Video Details:**
- Format: WebM
- Resolution: 1280x720 (configurable)
- Location: `data/logs/videos/task_{id}_{timestamp}.webm`
- Automatic naming by task ID
- Download link in dashboard

**Usage:**
```python
from browser_agent.enhanced_runner import EnhancedPlaywrightRunner

runner = EnhancedPlaywrightRunner(
    emr_type="mock_emr",
    headless=True,  # Can still record in headless mode
    record_video=True
)

result = await runner.fill_soap_note(task_id=1)
print(f"Video saved: {result['video_path']}")
```

**Access Videos:**
- Via API: `http://localhost:8001/videos/task_1_20251110_143022.webm`
- Via Dashboard: Download button appears after task completion

---

### 3. **Slow Motion Mode**

Slow down browser actions for live demos, training sessions, and presentations.

**Configuration:**
```bash
# Enable slow motion
ENABLE_SLOW_MO=true
SLOW_MO_MS=500  # 500ms delay between actions
```

**Use Cases:**
- 👥 **Live demos** - Show stakeholders exactly what the agent does
- 📚 **Training** - Help clinicians understand the automation
- 🐛 **Debugging** - See exactly where failures occur
- 🎥 **Recording demos** - Create marketing/training videos

**Timing Examples:**
| Slow Mo | Action Time | Total Time (10 actions) |
|---------|-------------|-------------------------|
| 0ms (normal) | Instant | ~20 seconds |
| 250ms | +0.25s/action | ~22.5 seconds |
| 500ms | +0.5s/action | ~25 seconds |
| 1000ms | +1s/action | ~30 seconds |

**Usage:**
```python
runner = EnhancedPlaywrightRunner(
    emr_type="mock_emr",
    headless=False,  # Must be visible for demos
    slow_mo=500  # Half-second delay per action
)
```

---

### 4. **Playwright Tracing**

Capture complete interaction trace for advanced debugging.

**Configuration:**
```bash
# Enable tracing
ENABLE_PLAYWRIGHT_TRACING=true
```

**What's Captured:**
- 📸 Screenshots at every step
- 🖼️ DOM snapshots
- 📝 Full action log
- ⏱️ Timing information
- 🌐 Network requests
- 📦 Source code

**Trace Files:**
- Location: `data/logs/traces/task_{id}_trace.zip`
- Format: Playwright Trace ZIP
- Viewer: Built-in Playwright trace viewer

**View Traces:**
```bash
# Install Playwright CLI
npm install -g playwright

# View trace file
playwright show-trace data/logs/traces/task_1_trace.zip
```

**Trace Viewer Features:**
- Timeline of all actions
- Screenshot at each step
- DOM snapshots (can inspect HTML)
- Network waterfall
- Console logs
- Source code snippets

---

### 5. **Live Dashboard UI**

React component for real-time monitoring.

**Features:**
- **Active Tasks Panel** - Shows all running tasks
- **Task Details** - Click to see full details
- **Progress Bars** - Visual progress for each task
- **Live Screenshots** - Updates as automation runs
- **Event Log** - Chronological event list
- **Error Display** - Red alerts for failures
- **Recovery Tracking** - Shows retry attempts
- **Video/Trace Downloads** - Direct download links

**Access:**
```
http://localhost:3000/live-tasks
```

**WebSocket Events:**
```javascript
{
  "event": "task_started",
  "task_id": 1,
  "patient_id": "PT-12345",
  "total_steps": 10
}

{
  "event": "step_started",
  "task_id": 1,
  "step_number": 3,
  "action": "fill",
  "description": "Filling SOAP form",
  "progress": 30
}

{
  "event": "step_completed",
  "task_id": 1,
  "step_number": 3,
  "screenshot_url": "/screenshots/task_1_step_3.png",
  "progress": 30
}

{
  "event": "task_completed",
  "task_id": 1,
  "success": true,
  "confidence": 85,
  "emr_url": "https://emr.example.com/notes/123",
  "video_url": "/videos/task_1_video.webm",
  "trace_url": "/traces/task_1_trace.zip"
}
```

---

## 📊 Configuration Matrix

| Feature | Production | Demo | Debug | Training |
|---------|------------|------|-------|----------|
| **Headless** | ✅ True | ❌ False | ❌ False | ❌ False |
| **Video Recording** | ❌ False | ✅ True | ✅ True | ✅ True |
| **Slow Motion** | ❌ 0ms | ✅ 500ms | ✅ 250ms | ✅ 1000ms |
| **Tracing** | ❌ False | ❌ False | ✅ True | ❌ False |
| **Live Dashboard** | ✅ True | ✅ True | ✅ True | ✅ True |

**Production:**
```bash
BROWSER_HEADLESS=true
ENABLE_VIDEO_RECORDING=false
ENABLE_SLOW_MO=false
SLOW_MO_MS=0
ENABLE_PLAYWRIGHT_TRACING=false
ENABLE_LIVE_DASHBOARD=true
```

**Demo/Training:**
```bash
BROWSER_HEADLESS=false  # Show browser
ENABLE_VIDEO_RECORDING=true  # Record for later
ENABLE_SLOW_MO=true
SLOW_MO_MS=500  # Visible actions
ENABLE_PLAYWRIGHT_TRACING=false
ENABLE_LIVE_DASHBOARD=true
```

**Debug:**
```bash
BROWSER_HEADLESS=false
ENABLE_VIDEO_RECORDING=true
ENABLE_SLOW_MO=true
SLOW_MO_MS=250
ENABLE_PLAYWRIGHT_TRACING=true  # Full trace
ENABLE_LIVE_DASHBOARD=true
```

---

## 🎯 Use Cases

### 1. **Stakeholder Demo**
```bash
# Show live in conference room
docker-compose exec -e DISPLAY=:0 worker python demo_visible.py

# Configuration:
BROWSER_HEADLESS=false
ENABLE_SLOW_MO=true
SLOW_MO_MS=750  # Slower for presentation
ENABLE_VIDEO_RECORDING=true  # Record demo
```

### 2. **Clinician Training**
```bash
# Record training video
ENABLE_VIDEO_RECORDING=true
ENABLE_SLOW_MO=true
SLOW_MO_MS=500

# Use video in training materials
ffmpeg -i task_1_video.webm task_1_training.mp4
```

### 3. **Production Monitoring**
```bash
# Fast headless with live dashboard
BROWSER_HEADLESS=true
ENABLE_LIVE_DASHBOARD=true
SCREENSHOT_ON_ERROR=true

# Watch dashboard: http://localhost:3000/live-tasks
```

### 4. **Debugging Failures**
```bash
# Full visibility + tracing
BROWSER_HEADLESS=false
ENABLE_PLAYWRIGHT_TRACING=true
ENABLE_VIDEO_RECORDING=true
ENABLE_SLOW_MO=true
SLOW_MO_MS=250

# After failure, review:
# 1. Watch video
# 2. Open trace in viewer
# 3. Check screenshots
```

---

## 🔧 API Usage

### Python API

```python
from browser_agent.enhanced_runner import EnhancedPlaywrightRunner
import asyncio

async def demo_with_recording():
    """Run automation with video recording."""
    runner = EnhancedPlaywrightRunner(
        emr_type="mock_emr",
        headless=False,  # Visible
        record_video=True,
        slow_mo=500,  # Slow for demo
        enable_tracing=True
    )

    result = await runner.fill_soap_note(task_id=1)

    print(f"Success: {result['success']}")
    print(f"Video: {result['video_path']}")
    print(f"Trace: {result['trace_path']}")

asyncio.run(demo_with_recording())
```

### REST API

**Trigger Automation with Options:**
```bash
# POST /api/intake with visibility options
curl -X POST http://localhost:8001/api/intake \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "PT-12345",
    "raw_input": "Patient walked 100ft...",
    "options": {
      "record_video": true,
      "slow_mo": 500,
      "enable_tracing": false
    }
  }'
```

**Get Task with Video/Trace URLs:**
```bash
# GET /api/tasks/{id}
curl http://localhost:8001/api/tasks/1

# Response:
{
  "task_id": 1,
  "status": "completed",
  "video_url": "http://localhost:8001/videos/task_1_20251110_143022.webm",
  "trace_url": "http://localhost:8001/traces/task_1_trace.zip",
  "screenshots": [
    "http://localhost:8001/screenshots/task_1_login_success.png",
    ...
  ]
}
```

---

## 📹 Video Recording Details

### File Details
- **Codec**: VP8 (WebM)
- **Audio**: None
- **Size**: ~5-10 MB per minute
- **Quality**: 720p (1280x720)

### Storage Estimates
| Duration | Size (approx) |
|----------|---------------|
| 30 seconds | 2-4 MB |
| 1 minute | 5-10 MB |
| 5 minutes | 25-50 MB |

### Cleanup
```bash
# Delete old videos (older than 90 days)
find data/logs/videos -name "*.webm" -mtime +90 -delete

# Automatic cleanup via scheduled task
# Runs weekly via Celery Beat
```

---

## 🐛 Debugging with Trace Viewer

### What You Can Do
1. **Step Through Actions** - See exactly what agent did
2. **Inspect DOM** - View page HTML at each step
3. **Check Network** - See API calls, failed requests
4. **View Console** - JavaScript errors, logs
5. **Source Code** - See which code executed
6. **Timing** - Performance analysis

### Example Workflow
```bash
# 1. Enable tracing
export ENABLE_PLAYWRIGHT_TRACING=true

# 2. Run automation
python demo_visible.py

# 3. Get trace file
ls data/logs/traces/task_1_trace.zip

# 4. Open in viewer
playwright show-trace data/logs/traces/task_1_trace.zip

# 5. In viewer:
#    - Click timeline to jump to specific moment
#    - Inspect DOM snapshots
#    - Check network waterfall
#    - Read console logs
```

---

## 🔐 Security Considerations

### PHI in Videos/Traces
- ⚠️ Videos may contain PHI (patient names, dates)
- ⚠️ Traces contain full page content (including PHI)
- ✅ Store in secure location (`data/logs/` - not public)
- ✅ Automatic cleanup after retention period
- ✅ Access logs for audit trail

### Recommendations
1. **Production**: Disable video recording unless debugging
2. **Demo Environment**: Use fake patient data
3. **Training**: Redact PHI from videos before sharing
4. **Trace Files**: Never share outside organization
5. **Storage**: Encrypt video/trace storage volumes

---

## 📊 Performance Impact

| Feature | CPU Impact | Storage Impact | Time Impact |
|---------|------------|----------------|-------------|
| **Headless=False** | +5-10% | 0 MB | +0-1 sec |
| **Video Recording** | +15-20% | 5-10 MB/min | +1-2 sec |
| **Slow Motion (500ms)** | 0% | 0 MB | +5-10 sec total |
| **Tracing** | +10-15% | 10-20 MB | +2-3 sec |
| **Live Dashboard** | +2-5% | 0 MB | 0 sec |

**Total Overhead (All Enabled):**
- CPU: +30-50%
- Storage: 15-30 MB per task
- Time: +8-16 seconds

---

## 🎬 Quick Start

### 1. Enable Features
```bash
# Copy .env.example to .env
cp .env.example .env

# Enable desired features
ENABLE_VIDEO_RECORDING=true
ENABLE_SLOW_MO=true
SLOW_MO_MS=500
ENABLE_LIVE_DASHBOARD=true
```

### 2. Start Services
```bash
docker-compose up -d
```

### 3. Access Live Dashboard
```
http://localhost:3000/live-tasks
```

### 4. Submit Task
```bash
curl -X POST http://localhost:8001/api/intake \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "PT-12345", "raw_input": "Patient walked 100ft..."}'
```

### 5. Watch in Real-Time
- Open live dashboard
- See task appear in "Active Tasks"
- Watch progress bar move
- See screenshots update
- Get notified on completion
- Download video/trace

---

## 🎓 Training Materials

### For Clinicians
**Show them:**
1. Live dashboard with progress bars
2. Video recording of successful automation
3. Slow motion demo in conference room

**Explain:**
- What agent does at each step
- How to review drafts in EMR
- When to expect notifications
- How to provide feedback

### For Admins
**Show them:**
1. Live monitoring dashboard
2. Error recovery in action
3. Trace viewer for debugging

**Explain:**
- How to monitor production
- How to debug failures
- How to adjust selectors
- Security best practices

---

## 🚨 Troubleshooting

### Video Not Recording
```bash
# Check setting
echo $ENABLE_VIDEO_RECORDING  # Should be "true"

# Check logs
docker-compose logs -f worker | grep video

# Check directory
ls -lh data/logs/videos/

# Manually test
docker-compose exec worker python -c "
from browser_agent.enhanced_runner import EnhancedPlaywrightRunner
import asyncio

async def test():
    runner = EnhancedPlaywrightRunner(record_video=True)
    await runner.start_browser(task_id=999)
    await asyncio.sleep(5)
    artifacts = await runner.close_browser(task_id=999)
    print(f'Video: {artifacts[\"video_path\"]}')

asyncio.run(test())
"
```

### WebSocket Not Connecting
```bash
# Check WebSocket endpoint
curl -i -N -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: SGVsbG8sIHdvcmxkIQ==" \
  http://localhost:8001/ws/tasks

# Should see 101 Switching Protocols

# Check CORS
# Ensure ALLOWED_ORIGINS includes frontend URL

# Check browser console
# Should see WebSocket connection messages
```

### Trace Viewer Not Opening
```bash
# Install Playwright
npm install -g playwright

# Or via pip
pip install playwright
playwright install

# Try opening trace
playwright show-trace data/logs/traces/task_1_trace.zip

# If fails, check trace file exists and is valid ZIP
unzip -t data/logs/traces/task_1_trace.zip
```

---

## 📞 Support

**Common Questions:**

Q: Can I record video in headless mode?
A: Yes! Playwright supports video recording in headless mode.

Q: How much does slow motion slow things down?
A: Each action is delayed by SLOW_MO_MS (e.g., 500ms = 0.5 second per action).

Q: Are videos HIPAA compliant?
A: Videos may contain PHI. Store securely and follow retention policies.

Q: Can multiple users watch the same task?
A: Yes! Multiple WebSocket connections can watch the same task_id.

Q: How do I share a trace with support?
A: Export trace ZIP file, but ensure no PHI is visible in screenshots.

---

**🎉 All visibility features are now production-ready!**

For more information, see:
- [Phase 4 Documentation](PHASE_4_COMPLETE.md)
- [Phase 5 Documentation](PHASE_5_COMPLETE.md)
- [Main README](README.md)
