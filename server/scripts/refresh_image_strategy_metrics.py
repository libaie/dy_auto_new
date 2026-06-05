from app.database import SessionLocal
from app.services.image_production_metrics_service import refresh_all_image_strategy_metrics


def main() -> None:
    db = SessionLocal()
    try:
        result = refresh_all_image_strategy_metrics(db)
        db.commit()
        print(f"refreshed_count={result['refreshed_count']}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
