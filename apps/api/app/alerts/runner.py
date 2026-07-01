from app.alerts.service import SavedSearchService
from app.database import SessionLocal


def run_due_alerts() -> list:
    with SessionLocal() as db:
        return SavedSearchService(db).run_due_alerts()


def main() -> None:
    results = run_due_alerts()
    print(f"Ran {len(results)} due alert(s).")
    for result in results:
        print(
            f"{result.savedSearchId}: {result.status}, "
            f"results={result.resultCount}, notified={result.notificationSent}"
        )


if __name__ == "__main__":
    main()
