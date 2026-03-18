from fastapi.testclient import TestClient

from shared.models.location import Location
from shared.models.user import User
from webapp.database import get_db_context, init_db
from webapp.main import app


def test_approved_locations_include_author_rank_fields():
    init_db()
    with get_db_context() as db:
        user = db.get(User, 9001)
        if not user:
            user = User(id=9001, telegram_id=9001, username="rank_user", total_gp=102, points=0)
            db.add(user)
            db.commit()
        loc = Location(
            user_id=9001,
            name="Test place",
            description="Desc",
            latitude=55.75,
            longitude=37.61,
            address="Addr",
            status="approved",
        )
        db.add(loc)
        db.commit()

    client = TestClient(app)
    resp = client.get("/api/map/locations/approved")
    assert resp.status_code == 200
    payload = resp.json()
    found = [x for x in payload["items"] if x["name"] == "Test place"]
    assert found
    author = found[-1]["author"]
    assert set(author.keys()) == {"user_id", "total_gp", "rank_level", "gp_in_rank", "rank_name"}
    assert author["total_gp"] == 102
    assert author["rank_level"] == 2
    assert author["gp_in_rank"] == 2
    assert author["rank_name"] == "🟢 Исследователь 2"
