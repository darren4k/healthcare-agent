"""Notification service for email and Slack alerts."""
import logging
import os
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from database.models import NoteDraft, TaskStatus

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of notifications."""
    SUCCESS = "success"
    FAILURE = "failure"
    REVIEW_NEEDED = "review_needed"
    LOW_CONFIDENCE = "low_confidence"


class NotificationService:
    """Unified notification service for email and Slack."""

    def __init__(self):
        """Initialize notification service."""
        # Email config
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_user)

        # Slack config
        self.slack_token = os.getenv("SLACK_BOT_TOKEN", "")
        self.slack_client = AsyncWebClient(token=self.slack_token) if self.slack_token else None

        # Notification settings
        self.enable_email = os.getenv("ENABLE_EMAIL_NOTIFICATIONS", "false").lower() == "true"
        self.enable_slack = os.getenv("ENABLE_SLACK_NOTIFICATIONS", "false").lower() == "true"
        self.confidence_threshold = int(os.getenv("LOW_CONFIDENCE_THRESHOLD", "70"))

    async def notify_note_completed(
        self,
        note_draft: NoteDraft,
        recipient_email: Optional[str] = None,
        slack_user_id: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Notify that a SOAP note has been completed and submitted to EMR.

        Args:
            note_draft: The completed note draft
            recipient_email: Email address to notify
            slack_user_id: Slack user ID to DM

        Returns:
            Dict with success status for each channel
        """
        results = {"email": False, "slack": False}

        # Determine notification type
        notification_type = NotificationType.SUCCESS
        if note_draft.status == TaskStatus.FAILED:
            notification_type = NotificationType.FAILURE
        elif note_draft.confidence_score and note_draft.confidence_score < self.confidence_threshold:
            notification_type = NotificationType.LOW_CONFIDENCE

        # Send email
        if self.enable_email and recipient_email:
            try:
                results["email"] = await self._send_email(
                    recipient_email,
                    note_draft,
                    notification_type
                )
            except Exception as e:
                logger.error(f"Failed to send email notification: {e}")

        # Send Slack message
        if self.enable_slack and slack_user_id and self.slack_client:
            try:
                results["slack"] = await self._send_slack_dm(
                    slack_user_id,
                    note_draft,
                    notification_type
                )
            except Exception as e:
                logger.error(f"Failed to send Slack notification: {e}")

        return results

    async def _send_email(
        self,
        recipient: str,
        note_draft: NoteDraft,
        notification_type: NotificationType
    ) -> bool:
        """Send email notification."""
        try:
            # Build email content
            subject, body = self._build_email_content(note_draft, notification_type)

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = recipient

            # Add HTML body
            html_part = MIMEText(body, "html")
            msg.attach(html_part)

            # Send email
            async with aiosmtplib.SMTP(hostname=self.smtp_host, port=self.smtp_port) as smtp:
                await smtp.starttls()
                if self.smtp_user and self.smtp_password:
                    await smtp.login(self.smtp_user, self.smtp_password)
                await smtp.send_message(msg)

            logger.info(f"Email notification sent to {recipient} for task {note_draft.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            return False

    async def _send_slack_dm(
        self,
        user_id: str,
        note_draft: NoteDraft,
        notification_type: NotificationType
    ) -> bool:
        """Send Slack DM notification."""
        try:
            blocks = self._build_slack_blocks(note_draft, notification_type)

            # Send DM
            response = await self.slack_client.chat_postMessage(
                channel=user_id,
                text=f"SOAP Note Update: Task #{note_draft.id}",
                blocks=blocks
            )

            logger.info(f"Slack notification sent to {user_id} for task {note_draft.id}")
            return response["ok"]

        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Failed to send Slack DM: {e}", exc_info=True)
            return False

    def _build_email_content(
        self,
        note_draft: NoteDraft,
        notification_type: NotificationType
    ) -> tuple[str, str]:
        """Build email subject and HTML body."""
        patient_name = f"{note_draft.patient.first_name} {note_draft.patient.last_name}"
        task_id = note_draft.id

        if notification_type == NotificationType.SUCCESS:
            subject = f"✅ SOAP Note Ready for Review - {patient_name}"
            status_color = "#10b981"  # green
            status_text = "Draft Successfully Created"
            message = f"Your SOAP note for {patient_name} has been structured and submitted to the EMR as a draft."
        elif notification_type == NotificationType.LOW_CONFIDENCE:
            subject = f"⚠️ SOAP Note Needs Review - {patient_name}"
            status_color = "#f59e0b"  # orange
            status_text = "Low Confidence - Review Needed"
            message = f"The AI confidence score is {note_draft.confidence_score}%. Please review carefully."
        else:  # FAILURE
            subject = f"❌ SOAP Note Failed - {patient_name}"
            status_color = "#ef4444"  # red
            status_text = "Automation Failed"
            message = f"Failed to process SOAP note. Error: {note_draft.error_message or 'Unknown error'}"

        emr_link = ""
        if note_draft.emr_draft_url:
            emr_link = f'<p><a href="{note_draft.emr_draft_url}" style="display: inline-block; padding: 10px 20px; background-color: #3b82f6; color: white; text-decoration: none; border-radius: 5px; margin: 10px 0;">View in EMR</a></p>'

        body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {status_color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background-color: #f9fafb; padding: 20px; border-radius: 0 0 8px 8px; }}
                .section {{ background-color: white; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid {status_color}; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 style="margin: 0;">{status_text}</h2>
                    <p style="margin: 5px 0 0 0;">Task #{task_id} • {patient_name}</p>
                </div>
                <div class="content">
                    <p>{message}</p>

                    {emr_link}

                    <div class="section">
                        <h3 style="margin-top: 0; color: {status_color};">Subjective</h3>
                        <p>{note_draft.subjective or 'N/A'}</p>
                    </div>

                    <div class="section">
                        <h3 style="margin-top: 0; color: {status_color};">Objective</h3>
                        <p>{note_draft.objective or 'N/A'}</p>
                    </div>

                    <div class="section">
                        <h3 style="margin-top: 0; color: {status_color};">Assessment</h3>
                        <p>{note_draft.assessment or 'N/A'}</p>
                    </div>

                    <div class="section">
                        <h3 style="margin-top: 0; color: {status_color};">Plan</h3>
                        <p>{note_draft.plan or 'N/A'}</p>
                    </div>

                    <div style="margin-top: 20px;">
                        <p><strong>Confidence Score:</strong> {note_draft.confidence_score or 'N/A'}%</p>
                        <p><strong>Visit Date:</strong> {note_draft.visit_date}</p>
                        <p><strong>Submitted By:</strong> {note_draft.submitted_by}</p>
                    </div>
                </div>
                <div class="footer">
                    <p>This is an automated notification from the Healthcare Agent system.</p>
                    <p>Processed at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
                </div>
            </div>
        </body>
        </html>
        """

        return subject, body

    def _build_slack_blocks(
        self,
        note_draft: NoteDraft,
        notification_type: NotificationType
    ) -> List[Dict]:
        """Build Slack message blocks."""
        patient_name = f"{note_draft.patient.first_name} {note_draft.patient.last_name}"

        if notification_type == NotificationType.SUCCESS:
            emoji = "✅"
            status_text = "*Draft Successfully Created*"
            color = "good"
        elif notification_type == NotificationType.LOW_CONFIDENCE:
            emoji = "⚠️"
            status_text = "*Low Confidence - Review Needed*"
            color = "warning"
        else:
            emoji = "❌"
            status_text = "*Automation Failed*"
            color = "danger"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} SOAP Note Update - Task #{note_draft.id}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{status_text}\n*Patient:* {patient_name}\n*Visit Date:* {note_draft.visit_date}"
                }
            },
            {"type": "divider"}
        ]

        # Add SOAP sections
        if note_draft.subjective:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Subjective:*\n{note_draft.subjective[:500]}..."
                }
            })

        if note_draft.objective:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Objective:*\n{note_draft.objective[:500]}..."
                }
            })

        if note_draft.assessment:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Assessment:*\n{note_draft.assessment[:500]}..."
                }
            })

        if note_draft.plan:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Plan:*\n{note_draft.plan[:500]}..."
                }
            })

        # Add metadata
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Confidence:*\n{note_draft.confidence_score or 'N/A'}%"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Submitted By:*\n{note_draft.submitted_by}"
                }
            ]
        })

        # Add EMR link button
        if note_draft.emr_draft_url:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View in EMR"
                        },
                        "url": note_draft.emr_draft_url,
                        "style": "primary"
                    }
                ]
            })

        return blocks

    async def notify_batch_summary(
        self,
        total_processed: int,
        successful: int,
        failed: int,
        recipient_email: Optional[str] = None,
        slack_channel: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Send batch processing summary notification.

        Args:
            total_processed: Total notes processed
            successful: Number of successful submissions
            failed: Number of failed submissions
            recipient_email: Email to notify
            slack_channel: Slack channel to post to

        Returns:
            Dict with success status for each channel
        """
        results = {"email": False, "slack": False}

        success_rate = (successful / total_processed * 100) if total_processed > 0 else 0

        # Email summary
        if self.enable_email and recipient_email:
            subject = f"📊 Daily SOAP Note Summary - {datetime.now().strftime('%Y-%m-%d')}"
            body = f"""
            <html>
            <body style="font-family: sans-serif;">
                <h2>Daily SOAP Note Processing Summary</h2>
                <p><strong>Total Processed:</strong> {total_processed}</p>
                <p style="color: green;"><strong>Successful:</strong> {successful}</p>
                <p style="color: red;"><strong>Failed:</strong> {failed}</p>
                <p><strong>Success Rate:</strong> {success_rate:.1f}%</p>
                <p style="margin-top: 20px; color: #666; font-size: 12px;">
                    Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
                </p>
            </body>
            </html>
            """

            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = self.from_email
                msg["To"] = recipient_email
                msg.attach(MIMEText(body, "html"))

                async with aiosmtplib.SMTP(hostname=self.smtp_host, port=self.smtp_port) as smtp:
                    await smtp.starttls()
                    if self.smtp_user and self.smtp_password:
                        await smtp.login(self.smtp_user, self.smtp_password)
                    await smtp.send_message(msg)

                results["email"] = True
            except Exception as e:
                logger.error(f"Failed to send batch summary email: {e}")

        # Slack summary
        if self.enable_slack and slack_channel and self.slack_client:
            try:
                await self.slack_client.chat_postMessage(
                    channel=slack_channel,
                    text=f"📊 Daily Summary: {successful}/{total_processed} notes processed successfully ({success_rate:.1f}%)",
                    blocks=[
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": "📊 Daily SOAP Note Summary"
                            }
                        },
                        {
                            "type": "section",
                            "fields": [
                                {"type": "mrkdwn", "text": f"*Total:*\n{total_processed}"},
                                {"type": "mrkdwn", "text": f"*Success Rate:*\n{success_rate:.1f}%"},
                                {"type": "mrkdwn", "text": f"*Successful:*\n✅ {successful}"},
                                {"type": "mrkdwn", "text": f"*Failed:*\n❌ {failed}"}
                            ]
                        }
                    ]
                )
                results["slack"] = True
            except Exception as e:
                logger.error(f"Failed to send batch summary to Slack: {e}")

        return results


# Global instance
notification_service = NotificationService()
