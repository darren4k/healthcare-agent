"""Validate production configuration and test all integrations."""
import os
import sys
import asyncio
import httpx
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validate all production configurations."""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []

    def validate_required_env(self):
        """Validate required environment variables."""
        logger.info("\n=== Validating Environment Variables ===")

        required = {
            "DB_PASSWORD": "Database password",
            "REDIS_PASSWORD": "Redis password",
            "JWT_SECRET_KEY": "JWT secret key",
            "LLM_API_KEY": "LLM API key",
            "HELLONOTE_USERNAME": "HelloNote username",
            "HELLONOTE_PASSWORD": "HelloNote password",
            "TWILIO_ACCOUNT_SID": "Twilio Account SID",
            "TWILIO_AUTH_TOKEN": "Twilio Auth Token",
            "SENDGRID_API_KEY": "SendGrid API key",
        }

        for var, description in required.items():
            value = os.getenv(var)
            if not value or value.startswith("CHANGE_THIS") or value.startswith("your_"):
                self.errors.append(f"{var} not configured ({description})")
            else:
                self.passed.append(f"{var} configured")

    def validate_optional_env(self):
        """Validate optional but recommended environment variables."""
        logger.info("\n=== Validating Optional Configurations ===")

        optional = {
            "PINECONE_API_KEY": "Pinecone (for vector search)",
            "OPENAI_API_KEY": "OpenAI (for embeddings)",
            "CHANGE_HEALTHCARE_API_KEY": "Change Healthcare (for insurance)",
        }

        for var, description in optional.items():
            value = os.getenv(var)
            if not value or value.startswith("your_"):
                self.warnings.append(f"{var} not configured ({description})")
            else:
                self.passed.append(f"{var} configured")

    async def test_database_connection(self):
        """Test PostgreSQL connection."""
        logger.info("\n=== Testing Database Connection ===")

        try:
            from database.session import SessionLocal
            db = SessionLocal()
            # Try a simple query
            db.execute("SELECT 1")
            db.close()
            self.passed.append("Database connection successful")
        except Exception as e:
            self.errors.append(f"Database connection failed: {str(e)}")

    async def test_redis_connection(self):
        """Test Redis connection."""
        logger.info("\n=== Testing Redis Connection ===")

        try:
            import redis
            r = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
            r.ping()
            self.passed.append("Redis connection successful")
        except Exception as e:
            self.errors.append(f"Redis connection failed: {str(e)}")

    async def test_llm_endpoint(self):
        """Test LLM API endpoint."""
        logger.info("\n=== Testing LLM Endpoint ===")

        endpoint = os.getenv("LLM_ENDPOINT")
        api_key = os.getenv("LLM_API_KEY")

        if not endpoint or not api_key:
            self.warnings.append("LLM endpoint not configured")
            return

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    endpoint,
                    json={
                        "model": os.getenv("LLM_MODEL", "llama-70b-instruct"),
                        "messages": [{"role": "user", "content": "Test"}],
                        "max_tokens": 10
                    },
                    headers={"Authorization": f"Bearer {api_key}"}
                )

                if response.status_code == 200:
                    self.passed.append("LLM endpoint responding")
                else:
                    self.warnings.append(f"LLM endpoint returned {response.status_code}")

        except Exception as e:
            self.warnings.append(f"LLM endpoint test failed: {str(e)}")

    async def test_twilio(self):
        """Test Twilio SMS configuration."""
        logger.info("\n=== Testing Twilio Configuration ===")

        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")

        if not account_sid or not auth_token:
            self.warnings.append("Twilio not configured")
            return

        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            # Just validate credentials by fetching account
            account = client.api.accounts(account_sid).fetch()
            self.passed.append(f"Twilio credentials valid (Account: {account.friendly_name})")
        except Exception as e:
            self.errors.append(f"Twilio validation failed: {str(e)}")

    async def test_sendgrid(self):
        """Test SendGrid email configuration."""
        logger.info("\n=== Testing SendGrid Configuration ===")

        api_key = os.getenv("SENDGRID_API_KEY")

        if not api_key:
            self.warnings.append("SendGrid not configured")
            return

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.sendgrid.com/v3/user/profile",
                    headers={"Authorization": f"Bearer {api_key}"}
                )

                if response.status_code == 200:
                    data = response.json()
                    self.passed.append(f"SendGrid credentials valid (User: {data.get('username')})")
                else:
                    self.errors.append(f"SendGrid validation failed: {response.status_code}")

        except Exception as e:
            self.errors.append(f"SendGrid test failed: {str(e)}")

    async def test_pinecone(self):
        """Test Pinecone vector database."""
        logger.info("\n=== Testing Pinecone Configuration ===")

        api_key = os.getenv("PINECONE_API_KEY")

        if not api_key:
            self.warnings.append("Pinecone not configured (optional)")
            return

        try:
            import pinecone
            pinecone.init(
                api_key=api_key,
                environment=os.getenv("PINECONE_ENVIRONMENT", "us-west1-gcp")
            )
            indexes = pinecone.list_indexes()
            index_name = os.getenv("PINECONE_INDEX_NAME", "healthcare-cases")

            if index_name in indexes:
                self.passed.append(f"Pinecone index '{index_name}' exists")
            else:
                self.warnings.append(f"Pinecone index '{index_name}' not found (run init_pinecone.py)")

        except Exception as e:
            self.warnings.append(f"Pinecone test failed: {str(e)}")

    async def test_insurance_api(self):
        """Test insurance clearinghouse API."""
        logger.info("\n=== Testing Insurance Clearinghouse ===")

        api_key = os.getenv("CHANGE_HEALTHCARE_API_KEY")

        if not api_key:
            self.warnings.append("Insurance API not configured")
            return

        # Just validate that credentials are set
        # Actual API test would require a valid eligibility request
        self.passed.append("Insurance credentials configured (full test requires patient data)")

    def print_report(self):
        """Print validation report."""
        logger.info("\n" + "=" * 60)
        logger.info("CONFIGURATION VALIDATION REPORT")
        logger.info("=" * 60)

        if self.passed:
            logger.info(f"\n✓ PASSED ({len(self.passed)}):")
            for item in self.passed:
                logger.info(f"  ✓ {item}")

        if self.warnings:
            logger.warning(f"\n⚠ WARNINGS ({len(self.warnings)}):")
            for item in self.warnings:
                logger.warning(f"  ⚠ {item}")

        if self.errors:
            logger.error(f"\n✗ ERRORS ({len(self.errors)}):")
            for item in self.errors:
                logger.error(f"  ✗ {item}")

        logger.info("\n" + "=" * 60)

        if self.errors:
            logger.error("\n❌ VALIDATION FAILED - Please fix errors before deploying to production")
            return False
        elif self.warnings:
            logger.warning("\n⚠️  VALIDATION PASSED WITH WARNINGS - Review warnings before production")
            return True
        else:
            logger.info("\n✅ VALIDATION PASSED - Configuration looks good!")
            return True


async def main():
    """Run all validation tests."""
    validator = ConfigValidator()

    # Run all validations
    validator.validate_required_env()
    validator.validate_optional_env()

    await validator.test_database_connection()
    await validator.test_redis_connection()
    await validator.test_llm_endpoint()
    await validator.test_twilio()
    await validator.test_sendgrid()
    await validator.test_pinecone()
    await validator.test_insurance_api()

    # Print report
    success = validator.print_report()

    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nValidation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\nValidation failed with error: {str(e)}")
        sys.exit(1)
