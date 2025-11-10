"""Initialize Pinecone vector database for case memory."""
import os
import logging
import pinecone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_pinecone():
    """Initialize Pinecone index for healthcare case memory."""
    try:
        # Get credentials from environment
        api_key = os.getenv("PINECONE_API_KEY")
        environment = os.getenv("PINECONE_ENVIRONMENT", "us-west1-gcp")
        index_name = os.getenv("PINECONE_INDEX_NAME", "healthcare-cases")

        if not api_key:
            logger.error("PINECONE_API_KEY not found in environment")
            return False

        logger.info("Initializing Pinecone...")

        # Initialize Pinecone
        pinecone.init(api_key=api_key, environment=environment)

        # Check if index already exists
        existing_indexes = pinecone.list_indexes()
        logger.info(f"Existing indexes: {existing_indexes}")

        if index_name in existing_indexes:
            logger.info(f"✓ Index '{index_name}' already exists")
            # Get index stats
            index = pinecone.Index(index_name)
            stats = index.describe_index_stats()
            logger.info(f"Index stats: {stats}")
            return True

        # Create new index
        logger.info(f"Creating index '{index_name}'...")

        pinecone.create_index(
            name=index_name,
            dimension=1536,  # OpenAI text-embedding-3-small dimension
            metric="cosine",  # Cosine similarity
            pod_type="p1.x1",  # Starter pod type
            pods=1,
            replicas=1,
            metadata_config={
                "indexed": [
                    "diagnosis",
                    "patient_id",
                    "therapist_id",
                    "outcome.improvement_percentage"
                ]
            }
        )

        logger.info("✓ Pinecone index created successfully!")

        # Verify index
        index = pinecone.Index(index_name)
        stats = index.describe_index_stats()
        logger.info(f"New index stats: {stats}")

        return True

    except Exception as e:
        logger.error(f"Error initializing Pinecone: {str(e)}")
        return False


if __name__ == "__main__":
    success = init_pinecone()
    exit(0 if success else 1)
