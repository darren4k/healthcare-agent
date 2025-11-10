"""Slack bot using Bolt framework for Python."""
import os
import logging
from datetime import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import httpx

from integrations.slack.formatters import format_submission_message, format_soap_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Slack app
app = App(
    token=os.getenv("SLACK_BOT_TOKEN"),
    signing_secret=os.getenv("SLACK_SIGNING_SECRET")
)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")


@app.command("/note")
def handle_note_command(ack, command, client):
    """
    Handle /note slash command.

    Usage: /note PT-12345 | Patient walked 100ft with CGA. Mild pain 3/10. Continue exercises.
    """
    ack()

    user_id = command["user_id"]
    user_name = command["user_name"]
    text = command["text"]

    # Open modal for structured input
    try:
        client.views_open(
            trigger_id=command["trigger_id"],
            view=build_note_modal()
        )
    except Exception as e:
        logger.error(f"Error opening modal: {e}")
        client.chat_postEphemeral(
            channel=command["channel_id"],
            user=user_id,
            text=f"❌ Error: {str(e)}"
        )


@app.view("note_submission")
def handle_note_submission(ack, body, client, view):
    """Handle note submission from modal."""
    ack()

    user = body["user"]
    values = view["state"]["values"]

    try:
        # Extract form data
        patient_id = values["patient_id_block"]["patient_id"]["value"]
        visit_type = values["visit_type_block"]["visit_type"]["selected_option"]["value"]
        raw_input = values["raw_input_block"]["raw_input"]["value"]
        visit_date_str = values["visit_date_block"]["visit_date"]["value"]  # YYYY-MM-DD format

        # Convert visit date to ISO format
        visit_date = datetime.strptime(visit_date_str, "%Y-%m-%d")
        visit_datetime = visit_date.replace(hour=datetime.now().hour, minute=datetime.now().minute)

        # Prepare payload for API
        payload = {
            "patient_id": patient_id,
            "raw_input": raw_input,
            "visit_date": visit_datetime.isoformat(),
            "visit_type": visit_type,
            "submitted_by": f"{user['name']} (via Slack)",
            "source": "slack_bot"
        }

        # Submit to API
        async def submit_note():
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                response = await http_client.post(
                    f"{API_BASE_URL}/api/intake",
                    json=payload
                )
                response.raise_for_status()
                return response.json()

        # Execute async submission
        import asyncio
        result = asyncio.run(submit_note())

        # Send confirmation message
        client.chat_postMessage(
            channel=user["id"],  # Send DM to user
            text=format_submission_message(result, patient_id)
        )

        logger.info(f"Note submitted successfully. Task ID: {result['task_id']}")

    except Exception as e:
        logger.error(f"Error submitting note: {e}")
        client.chat_postMessage(
            channel=user["id"],
            text=f"❌ Failed to submit note: {str(e)}"
        )


@app.command("/status")
def handle_status_command(ack, command, client):
    """
    Handle /status slash command to check task status.

    Usage: /status 42
    """
    ack()

    user_id = command["user_id"]
    task_id = command["text"].strip()

    if not task_id.isdigit():
        client.chat_postEphemeral(
            channel=command["channel_id"],
            user=user_id,
            text="❌ Please provide a valid task ID. Usage: `/status 42`"
        )
        return

    try:
        # Fetch task status from API
        async def get_status():
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                response = await http_client.get(
                    f"{API_BASE_URL}/api/tasks/{task_id}"
                )
                response.raise_for_status()
                return response.json()

        import asyncio
        task = asyncio.run(get_status())

        # Format and send status message
        if task.get("soap_components"):
            message = format_soap_message(task)
        else:
            message = format_submission_message(task, task["patient_id"])

        client.chat_postEphemeral(
            channel=command["channel_id"],
            user=user_id,
            text=message
        )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            client.chat_postEphemeral(
                channel=command["channel_id"],
                user=user_id,
                text=f"❌ Task #{task_id} not found."
            )
        else:
            client.chat_postEphemeral(
                channel=command["channel_id"],
                user=user_id,
                text=f"❌ Error fetching task: {str(e)}"
            )
    except Exception as e:
        logger.error(f"Error fetching status: {e}")
        client.chat_postEphemeral(
            channel=command["channel_id"],
            user=user_id,
            text=f"❌ Error: {str(e)}"
        )


def build_note_modal():
    """Build the modal for note submission."""
    return {
        "type": "modal",
        "callback_id": "note_submission",
        "title": {"type": "plain_text", "text": "Submit Clinical Note"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "patient_id_block",
                "label": {"type": "plain_text", "text": "Patient ID"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "patient_id",
                    "placeholder": {"type": "plain_text", "text": "PT-12345"}
                }
            },
            {
                "type": "input",
                "block_id": "visit_type_block",
                "label": {"type": "plain_text", "text": "Visit Type"},
                "element": {
                    "type": "static_select",
                    "action_id": "visit_type",
                    "options": [
                        {"text": {"type": "plain_text", "text": "Physical Therapy (PT)"}, "value": "PT"},
                        {"text": {"type": "plain_text", "text": "Occupational Therapy (OT)"}, "value": "OT"},
                        {"text": {"type": "plain_text", "text": "Speech-Language Pathology (SLP)"}, "value": "SLP"},
                        {"text": {"type": "plain_text", "text": "Nursing"}, "value": "Nursing"},
                        {"text": {"type": "plain_text", "text": "Home Health"}, "value": "Home Health"},
                    ]
                }
            },
            {
                "type": "input",
                "block_id": "visit_date_block",
                "label": {"type": "plain_text", "text": "Visit Date"},
                "element": {
                    "type": "datepicker",
                    "action_id": "visit_date",
                    "initial_date": datetime.now().strftime("%Y-%m-%d")
                }
            },
            {
                "type": "input",
                "block_id": "raw_input_block",
                "label": {"type": "plain_text", "text": "Clinical Note"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "raw_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Patient walked 100ft with CGA. Reports mild knee pain 3/10. Balance steady. Continue exercises."
                    }
                }
            }
        ]
    }


def start_bot():
    """Start the Slack bot."""
    handler = SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
    logger.info("⚡ Slack bot is running!")
    handler.start()


if __name__ == "__main__":
    start_bot()
