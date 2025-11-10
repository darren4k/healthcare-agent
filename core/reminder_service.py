"""Appointment reminder service."""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import asyncio

from database.scheduling_models import (
    Appointment, AppointmentReminder, PatientIntake, Therapist, Facility
)
from notifications.notifier import NotificationService

logger = logging.getLogger(__name__)


class ReminderService:
    """
    Appointment reminder management.

    Handles:
    - Automatic reminder scheduling (24h, 2h before)
    - SMS/Email/Push notification delivery
    - Reminder confirmation tracking
    - No-show risk escalation
    """

    def __init__(self, db: Session):
        self.db = db
        self.notifier = NotificationService()

    async def schedule_reminders_for_appointment(
        self,
        appointment: Appointment,
        reminder_types: Optional[List[str]] = None
    ) -> List[AppointmentReminder]:
        """
        Schedule reminders for an appointment.

        Default: 24h and 2h before appointment via SMS and Email.

        Args:
            appointment: Appointment instance
            reminder_types: List of reminder types (sms, email, push). If None, uses all available.

        Returns:
            List of created AppointmentReminder instances
        """
        if not reminder_types:
            reminder_types = ['sms', 'email']

        # Default reminder times: 24h and 2h before
        reminder_hours = [24, 2]

        created_reminders = []

        for hours_before in reminder_hours:
            reminder_time = appointment.scheduled_start - timedelta(hours=hours_before)

            # Don't schedule if reminder time is in the past
            if reminder_time < datetime.utcnow():
                logger.warning(
                    f"Skipping {hours_before}h reminder for appointment {appointment.id} "
                    f"(would be in the past)"
                )
                continue

            for reminder_type in reminder_types:
                reminder = AppointmentReminder(
                    appointment_id=appointment.id,
                    reminder_type=reminder_type,
                    reminder_time=reminder_time,
                    hours_before=hours_before,
                    message_template='default_reminder',
                    created_at=datetime.utcnow()
                )

                self.db.add(reminder)
                created_reminders.append(reminder)

        self.db.commit()

        logger.info(
            f"Scheduled {len(created_reminders)} reminders for appointment {appointment.id}"
        )

        return created_reminders

    async def send_pending_reminders(self) -> Dict[str, int]:
        """
        Send all pending reminders that are due.

        Should be called by scheduled task (e.g., every 5 minutes).

        Returns:
            Dict with counts: {sent, failed, skipped}
        """
        now = datetime.utcnow()

        # Get reminders that are due and haven't been sent
        pending_reminders = self.db.query(AppointmentReminder).filter(
            AppointmentReminder.reminder_time <= now,
            AppointmentReminder.sent_at.is_(None)
        ).all()

        stats = {
            'sent': 0,
            'failed': 0,
            'skipped': 0
        }

        for reminder in pending_reminders:
            try:
                success = await self._send_reminder(reminder)

                if success:
                    stats['sent'] += 1
                    reminder.sent_at = datetime.utcnow()
                    reminder.delivery_status = 'sent'
                else:
                    stats['failed'] += 1
                    reminder.delivery_status = 'failed'

            except Exception as e:
                logger.error(f"Error sending reminder {reminder.id}: {str(e)}")
                stats['failed'] += 1
                reminder.delivery_status = 'failed'
                reminder.delivery_error = str(e)

        self.db.commit()

        logger.info(
            f"Reminder batch complete: {stats['sent']} sent, "
            f"{stats['failed']} failed, {stats['skipped']} skipped"
        )

        return stats

    async def _send_reminder(self, reminder: AppointmentReminder) -> bool:
        """
        Send a single reminder.

        Args:
            reminder: AppointmentReminder instance

        Returns:
            True if sent successfully
        """
        # Get appointment details
        appointment = self.db.query(Appointment).filter(
            Appointment.id == reminder.appointment_id
        ).first()

        if not appointment:
            logger.error(f"Appointment {reminder.appointment_id} not found")
            return False

        # Get patient info
        intake = self.db.query(PatientIntake).filter(
            PatientIntake.id == appointment.patient_intake_id
        ).first()

        if not intake:
            logger.error(f"Patient intake {appointment.patient_intake_id} not found")
            return False

        # Get therapist info
        therapist = self.db.query(Therapist).filter(
            Therapist.id == appointment.therapist_id
        ).first()

        # Get facility info (if available)
        facility = None
        if appointment.facility_id:
            facility = self.db.query(Facility).filter(
                Facility.id == appointment.facility_id
            ).first()

        # Build reminder message
        message = self._build_reminder_message(
            appointment=appointment,
            intake=intake,
            therapist=therapist,
            facility=facility,
            hours_before=reminder.hours_before
        )

        # Store the message that was sent
        reminder.message_sent = message

        # Send based on type
        if reminder.reminder_type == 'sms':
            return await self._send_sms_reminder(intake, message)
        elif reminder.reminder_type == 'email':
            return await self._send_email_reminder(intake, message, appointment, therapist, facility)
        elif reminder.reminder_type == 'push':
            return await self._send_push_reminder(intake, message)
        else:
            logger.error(f"Unknown reminder type: {reminder.reminder_type}")
            return False

    def _build_reminder_message(
        self,
        appointment: Appointment,
        intake: PatientIntake,
        therapist: Optional[Therapist] = None,
        facility: Optional[Facility] = None,
        hours_before: int = 24
    ) -> str:
        """
        Build reminder message text.

        Args:
            appointment: Appointment instance
            intake: PatientIntake instance
            therapist: Therapist instance (optional)
            facility: Facility instance (optional)
            hours_before: Hours before appointment

        Returns:
            Formatted reminder message
        """
        # Format date and time
        apt_datetime = appointment.scheduled_start
        date_str = apt_datetime.strftime('%A, %B %d, %Y')
        time_str = apt_datetime.strftime('%I:%M %p')

        # Build therapist info
        therapist_name = "your therapist"
        if therapist:
            therapist_name = f"{therapist.first_name} {therapist.last_name}"

        # Build facility info
        facility_info = ""
        if facility:
            facility_info = f"\n\nLocation: {facility.name}"
            if facility.address_line1:
                facility_info += f"\n{facility.address_line1}"
                if facility.city and facility.state:
                    facility_info += f"\n{facility.city}, {facility.state} {facility.zip_code or ''}"

        # Build message based on timing
        if hours_before == 24:
            message = (
                f"Hi {intake.first_name},\n\n"
                f"This is a reminder that you have a therapy appointment TOMORROW:\n\n"
                f"Date: {date_str}\n"
                f"Time: {time_str}\n"
                f"With: {therapist_name}"
                f"{facility_info}\n\n"
                f"Please reply CONFIRM to confirm your attendance or CANCEL if you need to cancel.\n\n"
                f"If you need to reschedule, please call us at (555) 123-4567."
            )
        else:
            message = (
                f"Hi {intake.first_name},\n\n"
                f"Your therapy appointment is in {hours_before} hours:\n\n"
                f"Time: {time_str}\n"
                f"With: {therapist_name}"
                f"{facility_info}\n\n"
                f"We look forward to seeing you soon!"
            )

        return message

    async def _send_sms_reminder(self, intake: PatientIntake, message: str) -> bool:
        """
        Send SMS reminder.

        Args:
            intake: PatientIntake instance
            message: Message text

        Returns:
            True if sent successfully
        """
        if not intake.phone_number:
            logger.warning(f"No phone number for patient {intake.id}")
            return False

        try:
            # TODO: Integrate with SMS service (Twilio, etc.)
            # For now, just log
            logger.info(f"SMS reminder to {intake.phone_number}: {message[:50]}...")

            # Simulate sending
            await asyncio.sleep(0.1)

            return True

        except Exception as e:
            logger.error(f"Failed to send SMS to {intake.phone_number}: {str(e)}")
            return False

    async def _send_email_reminder(
        self,
        intake: PatientIntake,
        message: str,
        appointment: Appointment,
        therapist: Optional[Therapist],
        facility: Optional[Facility]
    ) -> bool:
        """
        Send email reminder.

        Args:
            intake: PatientIntake instance
            message: Message text
            appointment: Appointment instance
            therapist: Therapist instance
            facility: Facility instance

        Returns:
            True if sent successfully
        """
        if not intake.email:
            logger.warning(f"No email for patient {intake.id}")
            return False

        try:
            # Build HTML email
            html_body = self._build_reminder_email_html(
                intake=intake,
                appointment=appointment,
                therapist=therapist,
                facility=facility,
                message=message
            )

            # Send via notification service
            result = await self.notifier.send_email(
                to_email=intake.email,
                subject=f"Appointment Reminder - {appointment.scheduled_start.strftime('%b %d')}",
                body_html=html_body
            )

            return result

        except Exception as e:
            logger.error(f"Failed to send email to {intake.email}: {str(e)}")
            return False

    def _build_reminder_email_html(
        self,
        intake: PatientIntake,
        appointment: Appointment,
        therapist: Optional[Therapist],
        facility: Optional[Facility],
        message: str
    ) -> str:
        """Build HTML email for appointment reminder."""
        therapist_name = "Your Therapist"
        if therapist:
            therapist_name = f"{therapist.first_name} {therapist.last_name}"

        facility_name = "Our Clinic"
        facility_address = ""
        if facility:
            facility_name = facility.name
            if facility.address_line1:
                facility_address = f"""
                <p style="color: #666; margin: 5px 0;">
                    {facility.address_line1}<br>
                    {facility.city}, {facility.state} {facility.zip_code or ''}
                </p>
                """

        date_str = appointment.scheduled_start.strftime('%A, %B %d, %Y')
        time_str = appointment.scheduled_start.strftime('%I:%M %p')

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">Appointment Reminder</h1>
                </div>

                <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 18px; color: #333;">
                        Hi {intake.first_name},
                    </p>

                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea;">
                        <h2 style="margin-top: 0; color: #667eea;">Upcoming Appointment</h2>
                        <table style="width: 100%;">
                            <tr>
                                <td style="padding: 10px 0; font-weight: bold; color: #666;">Date:</td>
                                <td style="padding: 10px 0;">{date_str}</td>
                            </tr>
                            <tr>
                                <td style="padding: 10px 0; font-weight: bold; color: #666;">Time:</td>
                                <td style="padding: 10px 0;">{time_str}</td>
                            </tr>
                            <tr>
                                <td style="padding: 10px 0; font-weight: bold; color: #666;">Therapist:</td>
                                <td style="padding: 10px 0;">{therapist_name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 10px 0; font-weight: bold; color: #666;">Location:</td>
                                <td style="padding: 10px 0;">
                                    {facility_name}
                                    {facility_address}
                                </td>
                            </tr>
                        </table>
                    </div>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="#" style="background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                            Confirm Appointment
                        </a>
                        <br><br>
                        <a href="#" style="color: #666; text-decoration: none; font-size: 14px;">
                            Need to reschedule?
                        </a>
                    </div>

                    <div style="background: #fff3cd; padding: 15px; border-radius: 5px; border-left: 4px solid #ffc107; margin-top: 20px;">
                        <p style="margin: 0; font-size: 14px; color: #856404;">
                            <strong>Important:</strong> Please arrive 10 minutes early to complete check-in.
                        </p>
                    </div>

                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

                    <p style="font-size: 14px; color: #666; text-align: center;">
                        Questions? Contact us at (555) 123-4567 or reply to this email.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    async def _send_push_reminder(self, intake: PatientIntake, message: str) -> bool:
        """
        Send push notification reminder.

        Args:
            intake: PatientIntake instance
            message: Message text

        Returns:
            True if sent successfully
        """
        # TODO: Integrate with push notification service (Firebase, OneSignal, etc.)
        logger.info(f"Push reminder for patient {intake.id}: {message[:50]}...")

        # Simulate sending
        await asyncio.sleep(0.1)

        return True

    async def process_reminder_responses(self) -> Dict[str, int]:
        """
        Process responses to reminders (confirmations, cancellations).

        Should be called by scheduled task.

        Returns:
            Dict with counts: {confirmations, cancellations, reschedules}
        """
        # TODO: Implement SMS/email response parsing
        # This would integrate with Twilio webhooks, email parsing, etc.

        stats = {
            'confirmations': 0,
            'cancellations': 0,
            'reschedules': 0
        }

        logger.info("Reminder response processing complete")

        return stats

    def get_unconfirmed_appointments(
        self,
        hours_before: int = 2
    ) -> List[Appointment]:
        """
        Get appointments without confirmation close to appointment time.

        Args:
            hours_before: How many hours before appointment to check

        Returns:
            List of unconfirmed appointments
        """
        cutoff_time = datetime.utcnow() + timedelta(hours=hours_before)

        appointments = self.db.query(Appointment).filter(
            Appointment.scheduled_start <= cutoff_time,
            Appointment.scheduled_start > datetime.utcnow(),
            Appointment.confirmation_received == False,
            Appointment.status.in_(['scheduled', 'confirmed'])
        ).all()

        return appointments
