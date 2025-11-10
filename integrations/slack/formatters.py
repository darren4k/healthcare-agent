"""Message formatters for Slack bot responses."""
from datetime import datetime


def format_submission_message(task_data, patient_id):
    """Format a success message for note submission."""
    task_id = task_data.get("task_id")
    status = task_data.get("status", "pending")
    message = task_data.get("message", "Note submitted successfully")

    status_emoji = {
        "pending": "⏳",
        "processing": "🔄",
        "llm_complete": "✅",
        "completed": "✅",
        "failed": "❌"
    }.get(status, "📝")

    return f"""{status_emoji} *Note Submitted Successfully!*

*Task ID:* #{task_id}
*Patient:* {patient_id}
*Status:* {status.replace('_', ' ').title()}

_{message}_

💡 Check status anytime with: `/status {task_id}`
"""


def format_soap_message(task_data):
    """Format a SOAP note message with all components."""
    task_id = task_data.get("task_id")
    patient_id = task_data.get("patient_id")
    soap = task_data.get("soap_components", {})
    confidence = soap.get("confidence_score", 0)

    confidence_emoji = "🟢" if confidence >= 85 else "🟡" if confidence >= 70 else "🔴"

    return f"""📋 *SOAP Note - Task #{task_id}*

*Patient:* {patient_id}
*Confidence:* {confidence_emoji} {confidence}%

*Subjective:*
{soap.get('subjective', 'N/A')}

*Objective:*
{soap.get('objective', 'N/A')}

*Assessment:*
{soap.get('assessment', 'N/A')}

*Plan:*
{soap.get('plan', 'N/A')}

---
✅ Ready for review and EMR entry
"""


def format_error_message(error_text):
    """Format an error message."""
    return f"❌ *Error*\n\n{error_text}\n\nPlease try again or contact support."
