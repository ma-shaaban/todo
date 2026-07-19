import sqlalchemy as sa

from tests.conftest import test_engine


def make_user(c, email, name=None):
    r = c.post(
        "/api/auth/signup",
        json={"email": email, "password": "sup3rsecret", "display_name": name or email.split("@")[0]},
    )
    assert r.status_code == 201
    return r.json()


def create_space(c, name="Family"):
    r = c.post("/api/spaces", json={"name": name})
    assert r.status_code == 201
    return r.json()


def invite_code(c, space_id):
    r = c.post(f"/api/spaces/{space_id}/invites")
    assert r.status_code == 201
    return r.json()["code"]


def test_create_and_list_spaces(client):
    make_user(client, "ana@example.com")
    create_space(client, "Family")
    create_space(client, "Work")
    r = client.get("/api/spaces")
    assert r.status_code == 200
    items = r.json()["items"]
    assert [s["name"] for s in items] == ["Family", "Work"]
    assert all(s["my_role"] == "owner" for s in items)
    assert all(s["todo_count"] == 0 for s in items)


def test_spaces_require_auth(client):
    assert client.get("/api/spaces").status_code == 401
    assert client.post("/api/spaces", json={"name": "X"}).status_code == 401


def test_space_name_validation(client):
    make_user(client, "ana@example.com")
    assert client.post("/api/spaces", json={"name": "   "}).status_code == 400
    assert client.post("/api/spaces", json={"name": "x" * 200}).status_code == 400


def test_non_member_sees_404(client, make_client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    other = make_client()
    make_user(other, "bob@example.com")
    assert other.get(f"/api/spaces/{space['id']}").status_code == 404
    assert other.patch(f"/api/spaces/{space['id']}", json={"name": "Hi"}).status_code == 404
    assert other.delete(f"/api/spaces/{space['id']}").status_code == 404
    assert other.post(f"/api/spaces/{space['id']}/invites").status_code == 404


def test_member_cannot_rename_or_delete_but_owner_can(client, make_client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    code = invite_code(client, space["id"])
    bob = make_client()
    make_user(bob, "bob@example.com")
    assert bob.post(f"/api/invites/{code}/accept").status_code == 200
    # Member sees the space but may not rename or delete it.
    assert bob.get(f"/api/spaces/{space['id']}").status_code == 200
    assert bob.patch(f"/api/spaces/{space['id']}", json={"name": "Bob's"}).status_code == 403
    assert bob.delete(f"/api/spaces/{space['id']}").status_code == 403
    r = client.patch(f"/api/spaces/{space['id']}", json={"name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"


def test_invite_preview_and_accept_flow(client, make_client):
    make_user(client, "ana@example.com", name="Ana")
    space = create_space(client, "Family")
    code = invite_code(client, space["id"])

    bob = make_client()
    # Preview works without auth.
    r = bob.get(f"/api/invites/{code}")
    assert r.status_code == 200
    assert r.json() == {"space_name": "Family", "inviter_name": "Ana", "valid": True}
    # Accept requires auth.
    assert bob.post(f"/api/invites/{code}/accept").status_code == 401
    make_user(bob, "bob@example.com", name="Bob")
    r = bob.post(f"/api/invites/{code}/accept")
    assert r.status_code == 200
    assert r.json()["space_id"] == space["id"]
    # Idempotent.
    assert bob.post(f"/api/invites/{code}/accept").status_code == 200
    # Bob now sees the space; members listed for both.
    detail = bob.get(f"/api/spaces/{space['id']}").json()
    names = sorted(m["display_name"] for m in detail["members"])
    assert names == ["Ana", "Bob"]
    assert detail["my_role"] == "member"


def test_unknown_invite_is_404(client):
    assert client.get("/api/invites/nope-nope").status_code == 404


def test_revoked_invite(client, make_client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    r = client.post(f"/api/spaces/{space['id']}/invites")
    inv = r.json()
    assert client.delete(f"/api/invites/{inv['id']}").status_code == 200
    bob = make_client()
    make_user(bob, "bob@example.com")
    assert bob.get(f"/api/invites/{inv['code']}").json()["valid"] is False
    assert bob.post(f"/api/invites/{inv['code']}/accept").status_code == 410


def test_expired_invite(client, make_client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    code = invite_code(client, space["id"])
    with test_engine().begin() as conn:
        conn.execute(sa.text("UPDATE invites SET expires_at = now() - interval '1 hour'"))
    bob = make_client()
    make_user(bob, "bob@example.com")
    assert bob.get(f"/api/invites/{code}").json()["valid"] is False
    assert bob.post(f"/api/invites/{code}/accept").status_code == 410


def test_active_invites_listing(client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    client.post(f"/api/spaces/{space['id']}/invites")
    r2 = client.post(f"/api/spaces/{space['id']}/invites")
    client.delete(f"/api/invites/{r2.json()['id']}")
    items = client.get(f"/api/spaces/{space['id']}/invites").json()["items"]
    assert len(items) == 1


def test_membership_removal_rules(client, make_client):
    ana = make_user(client, "ana@example.com")
    space = create_space(client)
    code = invite_code(client, space["id"])
    bob_c = make_client()
    bob = make_user(bob_c, "bob@example.com")
    bob_c.post(f"/api/invites/{code}/accept")
    carol_c = make_client()
    carol = make_user(carol_c, "carol@example.com")
    carol_c.post(f"/api/invites/{code}/accept")

    # A member cannot remove another member.
    assert bob_c.delete(f"/api/spaces/{space['id']}/members/{carol['id']}").status_code == 403
    # The owner cannot leave their own space.
    assert client.delete(f"/api/spaces/{space['id']}/members/{ana['id']}").status_code == 400
    # A member can leave.
    assert carol_c.delete(f"/api/spaces/{space['id']}/members/{carol['id']}").status_code == 200
    assert carol_c.get(f"/api/spaces/{space['id']}").status_code == 404
    # The owner can remove a member.
    assert client.delete(f"/api/spaces/{space['id']}/members/{bob['id']}").status_code == 200
    assert bob_c.get(f"/api/spaces/{space['id']}").status_code == 404


def test_owner_delete_cascades(client, make_client):
    make_user(client, "ana@example.com")
    space = create_space(client)
    code = invite_code(client, space["id"])
    bob_c = make_client()
    make_user(bob_c, "bob@example.com")
    bob_c.post(f"/api/invites/{code}/accept")

    assert client.delete(f"/api/spaces/{space['id']}").status_code == 200
    assert bob_c.get("/api/spaces").json()["items"] == []
    with test_engine().begin() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM space_members")).scalar() == 0
        assert conn.execute(sa.text("SELECT count(*) FROM invites")).scalar() == 0
