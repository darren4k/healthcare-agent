"""Seed initial data for production deployment."""
import asyncio
from sqlalchemy.orm import Session
from database.session import SessionLocal, init_db
from database.engagement_models import (
    ExerciseLibrary, ExerciseDifficulty, OutcomeMeasure
)
from database.revenue_models import BillingCode
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_exercise_library(db: Session):
    """Seed exercise library with common PT exercises."""
    logger.info("Seeding exercise library...")

    exercises = [
        # Shoulder exercises
        {
            "name": "Pendulum Exercise",
            "description": "Gentle shoulder mobility exercise",
            "instructions": "Lean forward, let arm hang, make small circles",
            "category": "flexibility",
            "body_part": "shoulder",
            "difficulty": ExerciseDifficulty.BEGINNER,
            "default_sets": 2,
            "default_reps": 10,
            "video_url": "https://example.com/videos/pendulum.mp4"
        },
        {
            "name": "Shoulder External Rotation",
            "description": "Strengthens rotator cuff",
            "instructions": "With elbow at side, rotate arm outward against resistance",
            "category": "strength",
            "body_part": "shoulder",
            "difficulty": ExerciseDifficulty.INTERMEDIATE,
            "default_sets": 3,
            "default_reps": 12
        },
        # Back exercises
        {
            "name": "Cat-Cow Stretch",
            "description": "Spinal mobility exercise",
            "instructions": "On hands and knees, alternate arching and rounding spine",
            "category": "flexibility",
            "body_part": "back",
            "difficulty": ExerciseDifficulty.BEGINNER,
            "default_sets": 2,
            "default_reps": 10
        },
        {
            "name": "Bird Dog",
            "description": "Core stability exercise",
            "instructions": "On hands and knees, extend opposite arm and leg",
            "category": "stability",
            "body_part": "back",
            "difficulty": ExerciseDifficulty.INTERMEDIATE,
            "default_sets": 3,
            "default_reps": 10
        },
        # Knee exercises
        {
            "name": "Straight Leg Raise",
            "description": "Quadriceps strengthening",
            "instructions": "Lying down, lift straight leg to 45 degrees",
            "category": "strength",
            "body_part": "knee",
            "difficulty": ExerciseDifficulty.BEGINNER,
            "default_sets": 3,
            "default_reps": 15
        },
        {
            "name": "Wall Sits",
            "description": "Quadriceps endurance",
            "instructions": "Slide back down wall to 90-degree knee bend, hold",
            "category": "strength",
            "body_part": "knee",
            "difficulty": ExerciseDifficulty.INTERMEDIATE,
            "default_sets": 3,
            "default_hold_seconds": 30
        },
    ]

    for exercise_data in exercises:
        existing = db.query(ExerciseLibrary).filter(
            ExerciseLibrary.name == exercise_data["name"]
        ).first()

        if not existing:
            exercise = ExerciseLibrary(**exercise_data)
            db.add(exercise)

    db.commit()
    logger.info(f"✓ Seeded {len(exercises)} exercises")


def seed_outcome_measures(db: Session):
    """Seed standardized outcome measures."""
    logger.info("Seeding outcome measures...")

    measures = [
        {
            "measure_name": "Lower Extremity Functional Scale",
            "measure_acronym": "LEFS",
            "description": "Self-report questionnaire for lower extremity function",
            "min_score": 0,
            "max_score": 80,
            "mcid": 9.0,
            "body_regions": ["hip", "knee", "ankle", "foot"],
            "questions": [
                {"id": 1, "text": "Any of your usual work, housework, or school activities", "max_score": 4},
                {"id": 2, "text": "Your usual hobbies, recreational or sporting activities", "max_score": 4},
                # ... 20 total questions
            ]
        },
        {
            "measure_name": "Disabilities of the Arm, Shoulder and Hand",
            "measure_acronym": "DASH",
            "description": "Upper extremity disability/symptom measure",
            "min_score": 0,
            "max_score": 100,
            "mcid": 10.0,
            "body_regions": ["shoulder", "elbow", "wrist", "hand"],
            "questions": [
                {"id": 1, "text": "Open a tight or new jar", "max_score": 5},
                {"id": 2, "text": "Do heavy household chores", "max_score": 5},
                # ... 30 total questions
            ]
        },
        {
            "measure_name": "Oswestry Disability Index",
            "measure_acronym": "ODI",
            "description": "Low back disability questionnaire",
            "min_score": 0,
            "max_score": 50,
            "mcid": 6.0,
            "body_regions": ["back", "spine"],
            "questions": [
                {"id": 1, "text": "Pain Intensity", "max_score": 5},
                {"id": 2, "text": "Personal Care", "max_score": 5},
                # ... 10 total questions
            ]
        }
    ]

    for measure_data in measures:
        existing = db.query(OutcomeMeasure).filter(
            OutcomeMeasure.measure_acronym == measure_data["measure_acronym"]
        ).first()

        if not existing:
            measure = OutcomeMeasure(**measure_data)
            db.add(measure)

    db.commit()
    logger.info(f"✓ Seeded {len(measures)} outcome measures")


def seed_billing_codes(db: Session):
    """Seed common CPT and ICD-10 codes for physical therapy."""
    logger.info("Seeding billing codes...")

    codes = [
        # PT Evaluation codes
        {
            "code_type": "CPT",
            "code": "97161",
            "description": "Physical therapy evaluation - low complexity",
            "specialty": "physical_therapy"
        },
        {
            "code_type": "CPT",
            "code": "97162",
            "description": "Physical therapy evaluation - moderate complexity",
            "specialty": "physical_therapy"
        },
        {
            "code_type": "CPT",
            "code": "97163",
            "description": "Physical therapy evaluation - high complexity",
            "specialty": "physical_therapy"
        },
        {
            "code_type": "CPT",
            "code": "97164",
            "description": "Physical therapy re-evaluation",
            "specialty": "physical_therapy"
        },
        # Treatment codes
        {
            "code_type": "CPT",
            "code": "97110",
            "description": "Therapeutic exercises",
            "specialty": "physical_therapy",
            "commonly_paired_with": ["97140", "97112"]
        },
        {
            "code_type": "CPT",
            "code": "97140",
            "description": "Manual therapy techniques",
            "specialty": "physical_therapy",
            "commonly_paired_with": ["97110"]
        },
        {
            "code_type": "CPT",
            "code": "97112",
            "description": "Neuromuscular reeducation",
            "specialty": "physical_therapy"
        },
        {
            "code_type": "CPT",
            "code": "97530",
            "description": "Therapeutic activities",
            "specialty": "physical_therapy"
        },
        # Common ICD-10 codes
        {
            "code_type": "ICD10",
            "code": "M54.5",
            "description": "Low back pain",
            "specialty": "physical_therapy"
        },
        {
            "code_type": "ICD10",
            "code": "M25.511",
            "description": "Pain in right shoulder",
            "specialty": "physical_therapy"
        },
        {
            "code_type": "ICD10",
            "code": "M25.561",
            "description": "Pain in right knee",
            "specialty": "physical_therapy"
        },
        {
            "code_type": "ICD10",
            "code": "M54.2",
            "description": "Cervicalgia (neck pain)",
            "specialty": "physical_therapy"
        },
    ]

    for code_data in codes:
        existing = db.query(BillingCode).filter(
            BillingCode.code == code_data["code"],
            BillingCode.code_type == code_data["code_type"]
        ).first()

        if not existing:
            code = BillingCode(**code_data)
            db.add(code)

    db.commit()
    logger.info(f"✓ Seeded {len(codes)} billing codes")


def main():
    """Main seeding function."""
    logger.info("Starting data seeding...")

    # Initialize database
    init_db()

    # Get database session
    db = SessionLocal()

    try:
        # Seed all data
        seed_exercise_library(db)
        seed_outcome_measures(db)
        seed_billing_codes(db)

        logger.info("✓ All data seeded successfully!")

    except Exception as e:
        logger.error(f"Error seeding data: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
