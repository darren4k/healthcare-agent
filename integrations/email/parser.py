"""Email parser for extracting clinical note data."""
import re
from datetime import datetime
from email.utils import parseaddr
import logging

logger = logging.getLogger(__name__)


class EmailParser:
    """Parse clinical note data from emails."""

    def __init__(self):
        # Regex patterns for extraction
        self.patient_id_pattern = r'\b([A-Z]{2,3}-\d{4,6})\b'  # PT-12345, OT-678910
        self.visit_type_pattern = r'\b(PT|OT|SLP|Nursing|Home Health|SNF)\b'
        self.date_pattern = r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'

    def parse_email(self, email_message):
        """
        Parse email and extract clinical note data.

        Args:
            email_message: email.message.Message object

        Returns:
            dict: Parsed data ready for API submission, or None if parsing fails
        """
        try:
            # Extract sender
            sender_name, sender_email = parseaddr(email_message.get('From', ''))

            # Extract subject
            subject = self._decode_subject(email_message.get('Subject', ''))

            # Extract body
            body = self._extract_body(email_message)

            # Parse patient ID from subject or body
            patient_id = self._extract_patient_id(subject + ' ' + body)

            if not patient_id:
                logger.warning("Could not extract patient ID from email")
                return None

            # Parse visit type
            visit_type = self._extract_visit_type(subject + ' ' + body)

            # Parse visit date
            visit_date = self._extract_visit_date(subject + ' ' + body)

            # Use body as raw clinical note (clean up email artifacts)
            raw_input = self._clean_body(body)

            if len(raw_input) < 20:
                logger.warning("Clinical note too short")
                return None

            # Construct API payload
            return {
                "patient_id": patient_id,
                "raw_input": raw_input,
                "visit_date": visit_date.isoformat(),
                "visit_type": visit_type,
                "submitted_by": sender_name or sender_email,
                "source": "email",
                "patient_first_name": None,  # Could parse from body
                "patient_last_name": None,
            }

        except Exception as e:
            logger.error(f"Error parsing email: {e}")
            return None

    def _decode_subject(self, subject):
        """Decode email subject."""
        try:
            from email.header import decode_header
            decoded = decode_header(subject)
            return ''.join([
                text.decode(encoding or 'utf-8') if isinstance(text, bytes) else text
                for text, encoding in decoded
            ])
        except:
            return subject

    def _extract_body(self, email_message):
        """Extract plain text body from email."""
        body = ""

        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='ignore')
                        break
                    except:
                        continue
        else:
            try:
                payload = email_message.get_payload(decode=True)
                charset = email_message.get_content_charset() or 'utf-8'
                body = payload.decode(charset, errors='ignore')
            except:
                body = email_message.get_payload()

        return body

    def _extract_patient_id(self, text):
        """Extract patient ID from text."""
        match = re.search(self.patient_id_pattern, text)
        return match.group(1) if match else None

    def _extract_visit_type(self, text):
        """Extract visit type from text."""
        match = re.search(self.visit_type_pattern, text)
        return match.group(1) if match else "PT"  # Default to PT

    def _extract_visit_date(self, text):
        """Extract visit date from text."""
        match = re.search(self.date_pattern, text)

        if match:
            date_str = match.group(1)
            try:
                # Try MM/DD/YYYY format
                if date_str.count('/') == 2:
                    return datetime.strptime(date_str, '%m/%d/%Y')
                # Try MM/DD format (assume current year)
                else:
                    date = datetime.strptime(date_str, '%m/%d')
                    return date.replace(year=datetime.now().year)
            except:
                pass

        # Default to today
        return datetime.now()

    def _clean_body(self, body):
        """Clean email body of signatures and formatting."""
        # Remove email signatures
        if '--' in body:
            body = body.split('--')[0]

        # Remove "On ... wrote:" patterns
        body = re.sub(r'On .+? wrote:', '', body)

        # Remove excessive whitespace
        body = re.sub(r'\n{3,}', '\n\n', body)

        return body.strip()
