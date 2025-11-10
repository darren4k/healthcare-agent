"""Email monitoring service using IMAP."""
import asyncio
import logging
import email
from email.header import decode_header
from datetime import datetime
import httpx
from aioimaplib import aioimaplib
import os

from integrations.email.parser import EmailParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailMonitor:
    """Monitor email inbox for clinical note submissions."""

    def __init__(
        self,
        imap_server: str,
        email_address: str,
        password: str,
        api_base_url: str,
        poll_interval: int = 120
    ):
        """
        Initialize email monitor.

        Args:
            imap_server: IMAP server address (e.g., imap.gmail.com)
            email_address: Email address to monitor
            password: Email password or app-specific password
            api_base_url: Base URL of intake API
            poll_interval: Polling interval in seconds (default: 120)
        """
        self.imap_server = imap_server
        self.email_address = email_address
        self.password = password
        self.api_base_url = api_base_url
        self.poll_interval = poll_interval
        self.parser = EmailParser()

    async def connect(self):
        """Connect to IMAP server."""
        self.client = aioimaplib.IMAP4_SSL(host=self.imap_server)
        await self.client.wait_hello_from_server()
        await self.client.login(self.email_address, self.password)
        await self.client.select('INBOX')
        logger.info(f"Connected to {self.imap_server} as {self.email_address}")

    async def fetch_unread_emails(self):
        """Fetch unread emails from inbox."""
        try:
            # Search for unread messages
            status, messages = await self.client.search('UNSEEN')

            if status != 'OK' or not messages or messages[0] == b'':
                return []

            email_ids = messages[0].split()
            logger.info(f"Found {len(email_ids)} unread emails")

            emails = []
            for email_id in email_ids:
                try:
                    # Fetch email
                    status, msg_data = await self.client.fetch(email_id, '(RFC822)')

                    if status == 'OK':
                        email_body = msg_data[1]
                        email_message = email.message_from_bytes(email_body)
                        emails.append((email_id, email_message))

                except Exception as e:
                    logger.error(f"Error fetching email {email_id}: {e}")

            return emails

        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return []

    async def process_email(self, email_id, email_message):
        """Process a single email and submit to API."""
        try:
            # Parse email
            parsed_data = self.parser.parse_email(email_message)

            if not parsed_data:
                logger.warning(f"Could not parse email {email_id}")
                return False

            # Submit to API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base_url}/api/intake",
                    json=parsed_data
                )
                response.raise_for_status()
                result = response.json()

            logger.info(f"Email {email_id} submitted successfully. Task ID: {result['task_id']}")

            # Mark email as read
            await self.client.store(email_id, '+FLAGS', '\\Seen')

            # Send confirmation email (optional)
            # await self.send_confirmation(parsed_data['submitted_by'], result['task_id'])

            return True

        except httpx.HTTPError as e:
            logger.error(f"API error processing email {email_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error processing email {email_id}: {e}")
            return False

    async def run(self):
        """Main monitoring loop."""
        await self.connect()

        logger.info(f"Email monitor started. Polling every {self.poll_interval} seconds...")

        while True:
            try:
                # Fetch unread emails
                emails = await self.fetch_unread_emails()

                # Process each email
                for email_id, email_message in emails:
                    await self.process_email(email_id, email_message)

                # Wait before next poll
                await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.poll_interval)

    async def close(self):
        """Close IMAP connection."""
        if hasattr(self, 'client'):
            await self.client.logout()
            logger.info("IMAP connection closed")


async def main():
    """Start email monitoring."""
    # Load configuration from environment
    imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.gmail.com')
    email_address = os.getenv('EMAIL_ADDRESS')
    password = os.getenv('EMAIL_PASSWORD')
    api_base_url = os.getenv('API_BASE_URL', 'http://localhost:8001')
    poll_interval = int(os.getenv('EMAIL_POLL_INTERVAL', '120'))

    if not email_address or not password:
        logger.error("EMAIL_ADDRESS and EMAIL_PASSWORD must be set in environment")
        return

    monitor = EmailMonitor(
        imap_server=imap_server,
        email_address=email_address,
        password=password,
        api_base_url=api_base_url,
        poll_interval=poll_interval
    )

    try:
        await monitor.run()
    except KeyboardInterrupt:
        logger.info("Shutting down email monitor...")
        await monitor.close()


if __name__ == "__main__":
    asyncio.run(main())
