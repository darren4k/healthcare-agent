"""Intelligent therapist assignment engine."""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database.scheduling_models import (
    Therapist, TherapistSpecialty, Appointment, AppointmentStatus,
    PatientIntake, TimeOffRequest
)

logger = logging.getLogger(__name__)


class TherapistAssignmentEngine:
    """
    Intelligent therapist assignment using multi-factor scoring.

    Considers:
    - Specialty matching
    - Availability at requested time
    - Current caseload
    - Patient preferences
    - Geographic proximity (for mobile therapy)
    - Language requirements
    - Historical performance
    """

    def __init__(self, db: Session):
        self.db = db

    def assign_therapist(
        self,
        patient_intake: PatientIntake,
        appointment_datetime: datetime,
        duration_minutes: int = 45,
        required_specialty: Optional[TherapistSpecialty] = None,
        facility_id: Optional[int] = None
    ) -> Tuple[Optional[Therapist], float, str]:
        """
        Find best therapist match.

        Args:
            patient_intake: Patient intake record
            appointment_datetime: Requested appointment time
            duration_minutes: Session duration
            required_specialty: Required specialty (if any)
            facility_id: Facility ID (if any)

        Returns:
            Tuple of (therapist, confidence_score, reason)
        """
        # Get available therapists
        therapists = self._get_available_therapists(
            required_specialty=required_specialty,
            facility_id=facility_id
        )

        if not therapists:
            logger.warning("No available therapists found")
            return None, 0, "No available therapists"

        # Score each therapist
        scored_therapists = []
        for therapist in therapists:
            score, reasons = self._score_therapist(
                therapist=therapist,
                patient_intake=patient_intake,
                appointment_datetime=appointment_datetime,
                duration_minutes=duration_minutes,
                required_specialty=required_specialty
            )
            scored_therapists.append((therapist, score, reasons))

        # Sort by score (descending)
        scored_therapists.sort(key=lambda x: x[1], reverse=True)

        # Get best match
        best_therapist, best_score, best_reasons = scored_therapists[0]

        reason_text = ", ".join(best_reasons)

        logger.info(
            f"Assigned therapist {best_therapist.id} ({best_therapist.first_name} "
            f"{best_therapist.last_name}) with score {best_score}: {reason_text}"
        )

        return best_therapist, best_score, reason_text

    def _get_available_therapists(
        self,
        required_specialty: Optional[TherapistSpecialty] = None,
        facility_id: Optional[int] = None
    ) -> List[Therapist]:
        """Get list of available therapists based on criteria."""
        query = self.db.query(Therapist).filter(
            Therapist.is_active == True,
            Therapist.is_accepting_patients == True
        )

        if required_specialty:
            query = query.filter(Therapist.specialty == required_specialty)

        if facility_id:
            query = query.filter(Therapist.primary_facility_id == facility_id)

        return query.all()

    def _score_therapist(
        self,
        therapist: Therapist,
        patient_intake: PatientIntake,
        appointment_datetime: datetime,
        duration_minutes: int,
        required_specialty: Optional[TherapistSpecialty] = None
    ) -> Tuple[float, List[str]]:
        """
        Score a therapist for assignment.

        Returns:
            Tuple of (score, list_of_reasons)
        """
        score = 0.0
        reasons = []

        # Factor 1: Patient preference (30 points)
        if patient_intake.preferred_therapist_id == therapist.id:
            score += 30
            reasons.append("Patient preferred therapist")

        # Factor 2: Specialty match (25 points)
        if required_specialty and therapist.specialty == required_specialty:
            score += 25
            reasons.append("Perfect specialty match")
        elif not required_specialty:
            # No specialty required, any therapist is fine
            score += 15
            reasons.append("General therapy")

        # Factor 3: Availability at requested time (25 points)
        is_available, conflict_info = self._check_availability(
            therapist=therapist,
            appointment_datetime=appointment_datetime,
            duration_minutes=duration_minutes
        )

        if is_available:
            score += 25
            reasons.append("Available at requested time")
        else:
            # No points if unavailable
            reasons.append(f"Conflict: {conflict_info}")
            # Return early if not available
            return score, reasons

        # Factor 4: Caseload (15 points)
        caseload_score, caseload_reason = self._score_caseload(therapist)
        score += caseload_score
        reasons.append(caseload_reason)

        # Factor 5: Language match (10 points)
        if patient_intake.language_preference and therapist.languages:
            if patient_intake.language_preference in therapist.languages:
                score += 10
                reasons.append(f"Speaks {patient_intake.language_preference}")

        # Factor 6: Experience (10 points)
        if therapist.years_experience:
            if therapist.years_experience >= 10:
                score += 10
                reasons.append("Highly experienced (10+ years)")
            elif therapist.years_experience >= 5:
                score += 7
                reasons.append("Experienced (5+ years)")
            elif therapist.years_experience >= 2:
                score += 5
                reasons.append("Moderately experienced")

        # Factor 7: Performance rating (10 points)
        if therapist.average_rating:
            rating_score = (therapist.average_rating / 5.0) * 10
            score += rating_score
            reasons.append(f"Rating: {therapist.average_rating:.1f}/5.0")

        # Factor 8: Time of day preference (5 points)
        if patient_intake.preferred_time_of_day:
            hour = appointment_datetime.hour
            if self._matches_time_preference(hour, patient_intake.preferred_time_of_day):
                score += 5
                reasons.append("Matches preferred time of day")

        return score, reasons

    def _check_availability(
        self,
        therapist: Therapist,
        appointment_datetime: datetime,
        duration_minutes: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if therapist is available at requested time.

        Returns:
            Tuple of (is_available, conflict_info)
        """
        scheduled_end = appointment_datetime + timedelta(minutes=duration_minutes)

        # Check for appointment conflicts
        conflicts = self.db.query(Appointment).filter(
            Appointment.therapist_id == therapist.id,
            Appointment.status.in_([
                AppointmentStatus.SCHEDULED,
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.CHECKED_IN,
                AppointmentStatus.IN_PROGRESS
            ]),
            Appointment.scheduled_start < scheduled_end,
            Appointment.scheduled_end > appointment_datetime
        ).first()

        if conflicts:
            return False, f"Existing appointment at {conflicts.scheduled_start.strftime('%I:%M %p')}"

        # Check for time off requests
        time_off = self.db.query(TimeOffRequest).filter(
            TimeOffRequest.therapist_id == therapist.id,
            TimeOffRequest.status == "approved",
            TimeOffRequest.start_date <= appointment_datetime,
            TimeOffRequest.end_date >= appointment_datetime
        ).first()

        if time_off:
            return False, f"On {time_off.reason} leave"

        # Check work schedule (if defined)
        if therapist.work_schedule:
            day_of_week = appointment_datetime.strftime('%A').lower()
            if day_of_week in therapist.work_schedule:
                work_hours = therapist.work_schedule[day_of_week]
                if not self._is_within_work_hours(appointment_datetime, work_hours):
                    return False, "Outside work hours"

        # Check daily patient limit
        day_start = appointment_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        appointments_today = self.db.query(Appointment).filter(
            Appointment.therapist_id == therapist.id,
            Appointment.scheduled_start >= day_start,
            Appointment.scheduled_start < day_end,
            Appointment.status != AppointmentStatus.CANCELLED
        ).count()

        if appointments_today >= therapist.max_patients_per_day:
            return False, "Daily patient limit reached"

        return True, None

    def _score_caseload(self, therapist: Therapist) -> Tuple[float, str]:
        """
        Score therapist based on current caseload.

        Returns:
            Tuple of (score, reason)
        """
        if not therapist.max_patients_per_day or therapist.max_patients_per_day == 0:
            return 10, "Standard caseload"

        caseload_ratio = therapist.current_caseload / therapist.max_patients_per_day

        if caseload_ratio < 0.5:
            return 15, "Low caseload"
        elif caseload_ratio < 0.75:
            return 12, "Moderate caseload"
        elif caseload_ratio < 0.9:
            return 8, "High caseload"
        else:
            return 5, "Very high caseload"

    def _is_within_work_hours(
        self,
        appointment_datetime: datetime,
        work_hours: List[Dict]
    ) -> bool:
        """
        Check if appointment time is within work hours.

        Args:
            appointment_datetime: Appointment datetime
            work_hours: List of work hour dicts with 'start' and 'end' times

        Returns:
            True if within work hours
        """
        appointment_time = appointment_datetime.time()

        for period in work_hours:
            start_str = period.get('start', '00:00')
            end_str = period.get('end', '23:59')

            start_time = datetime.strptime(start_str, '%H:%M').time()
            end_time = datetime.strptime(end_str, '%H:%M').time()

            if start_time <= appointment_time <= end_time:
                return True

        return False

    def _matches_time_preference(self, hour: int, preference: str) -> bool:
        """
        Check if hour matches time preference.

        Args:
            hour: Hour of day (0-23)
            preference: 'morning', 'afternoon', or 'evening'

        Returns:
            True if matches
        """
        if preference == 'morning':
            return 8 <= hour < 12
        elif preference == 'afternoon':
            return 12 <= hour < 17
        elif preference == 'evening':
            return 17 <= hour < 21
        return False

    def get_therapist_availability(
        self,
        therapist_id: int,
        start_date: datetime,
        end_date: datetime,
        duration_minutes: int = 45
    ) -> List[datetime]:
        """
        Get available time slots for a therapist.

        Args:
            therapist_id: Therapist ID
            start_date: Start of date range
            end_date: End of date range
            duration_minutes: Appointment duration

        Returns:
            List of available datetime slots
        """
        therapist = self.db.query(Therapist).filter(Therapist.id == therapist_id).first()

        if not therapist or not therapist.is_active:
            return []

        available_slots = []

        # Iterate through each day
        current_date = start_date
        while current_date <= end_date:
            day_of_week = current_date.strftime('%A').lower()

            # Check if therapist works this day
            if therapist.work_schedule and day_of_week in therapist.work_schedule:
                work_hours = therapist.work_schedule[day_of_week]

                for period in work_hours:
                    start_str = period.get('start', '08:00')
                    end_str = period.get('end', '17:00')

                    # Generate time slots for this work period
                    start_time = datetime.strptime(start_str, '%H:%M').time()
                    end_time = datetime.strptime(end_str, '%H:%M').time()

                    slot_start = datetime.combine(current_date.date(), start_time)
                    period_end = datetime.combine(current_date.date(), end_time)

                    # Generate slots every 15 minutes
                    while slot_start + timedelta(minutes=duration_minutes) <= period_end:
                        # Check if this slot is available
                        is_available, _ = self._check_availability(
                            therapist=therapist,
                            appointment_datetime=slot_start,
                            duration_minutes=duration_minutes
                        )

                        if is_available:
                            available_slots.append(slot_start)

                        # Move to next slot (15-minute increments)
                        slot_start += timedelta(minutes=15)

            current_date += timedelta(days=1)

        return available_slots

    def recommend_alternative_times(
        self,
        therapist: Therapist,
        requested_datetime: datetime,
        duration_minutes: int = 45,
        window_days: int = 7
    ) -> List[datetime]:
        """
        Recommend alternative appointment times near requested time.

        Args:
            therapist: Therapist instance
            requested_datetime: Originally requested time
            duration_minutes: Appointment duration
            window_days: Days before/after to search

        Returns:
            List of alternative datetime slots (up to 10)
        """
        start_date = requested_datetime - timedelta(days=window_days)
        end_date = requested_datetime + timedelta(days=window_days)

        all_slots = self.get_therapist_availability(
            therapist_id=therapist.id,
            start_date=start_date,
            end_date=end_date,
            duration_minutes=duration_minutes
        )

        # Sort by proximity to requested time
        all_slots.sort(key=lambda slot: abs((slot - requested_datetime).total_seconds()))

        # Return top 10
        return all_slots[:10]
