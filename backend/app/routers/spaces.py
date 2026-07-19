"""Shared spaces: membership, roles, invite links.

Authorization posture: a space you're not a member of answers 404 (its
existence is not disclosed); a space you can see but may not modify
answers 403."""

import secrets
import uuid
from datetime import timedelta

import sqlalchemy as sa
from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy.exc import IntegrityError

from app import models
from app.db import utcnow
from app.deps import CurrentUser, DbSession
from app.schemas import AutomationIn, SpaceIn
from app.services.activity import record

router = APIRouter(prefix="/api", tags=["spaces"])

_MAX_SPACE_NAME = 100
_INVITE_DAYS = 7
_MAX_ACTIVE_INVITES = 10


def parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")


def get_membership(db, space_id, user) -> models.SpaceMember:
    """The caller's membership in the space — 404 when not a member (or the
    space doesn't exist; the two cases are indistinguishable on purpose)."""
    m = db.get(models.SpaceMember, (space_id, user.id))
    if m is None:
        raise HTTPException(status_code=404, detail="Not found")
    return m


def require_owner(membership: models.SpaceMember) -> None:
    if membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only the space owner can do that")


def _validate_space_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Please enter a space name")
    if len(name) > _MAX_SPACE_NAME:
        raise HTTPException(
            status_code=400, detail=f"Space name must be at most {_MAX_SPACE_NAME} characters"
        )
    return name


@router.get("/spaces")
def list_spaces(user: CurrentUser, db: DbSession):
    import sqlalchemy as sa

    rows = (
        db.query(models.Space, models.SpaceMember.role)
        .join(models.SpaceMember, models.SpaceMember.space_id == models.Space.id)
        .filter(models.SpaceMember.user_id == user.id)
        .order_by(models.Space.created_at)
        .all()
    )
    member_counts = dict(
        db.query(models.SpaceMember.space_id, sa.func.count())
        .filter(models.SpaceMember.space_id.in_([s.id for s, _ in rows]))
        .group_by(models.SpaceMember.space_id)
        .all()
    ) if rows else {}
    todo_counts = _open_todo_counts(db, [s.id for s, _ in rows])
    return {
        "items": [
            {
                "id": str(space.id),
                "name": space.name,
                "my_role": role,
                "member_count": member_counts.get(space.id, 1),
                "todo_count": todo_counts.get(space.id, 0),
            }
            for space, role in rows
        ]
    }


def _open_todo_counts(db, space_ids) -> dict:
    if not space_ids:
        return {}
    import sqlalchemy as sa

    return dict(
        db.query(models.Todo.space_id, sa.func.count())
        .filter(models.Todo.space_id.in_(space_ids), models.Todo.completed_at.is_(None))
        .group_by(models.Todo.space_id)
        .all()
    )


@router.get("/space-templates")
def space_templates(user: CurrentUser):
    """Templates for the create-space screen — straight from the automation
    registry, so a new provider module shows up here with no UI change."""
    from app.services.automations import TEMPLATES

    return {"items": TEMPLATES}


@router.post("/spaces", status_code=201)
def create_space(
    body: SpaceIn, user: CurrentUser, db: DbSession, background: BackgroundTasks
):
    name = _validate_space_name(body.name)
    automation_type = None
    automation_config = None
    if body.template:
        # Template = a space born with its automation on; the config is
        # validated (including one real fetch) BEFORE anything is created.
        automation_type, automation_config = _validated_automation(
            body.template, body.config or {}
        )
    space = models.Space(
        name=name,
        created_by=user.id,
        automation_type=automation_type,
        automation_config=automation_config,
    )
    db.add(space)
    db.flush()
    db.add(models.SpaceMember(space_id=space.id, user_id=user.id, role="owner"))
    if automation_type:
        # First run right away (post-commit): the space opens already
        # populated instead of waiting for the scheduler tick.
        background.add_task(_run_automation_now, space.id)
    return {
        "id": str(space.id),
        "name": space.name,
        "my_role": "owner",
        "automation": (
            {"type": automation_type, "config": automation_config}
            if automation_type
            else None
        ),
    }


def _get_space_or_404(db, sid) -> models.Space:
    """The membership row can outlive the space by a beat under concurrent
    delete — never assume the FK guarantees existence across statements."""
    space = db.get(models.Space, sid)
    if space is None:
        raise HTTPException(status_code=404, detail="Not found")
    return space


@router.get("/spaces/{space_id}")
def space_detail(space_id: str, user: CurrentUser, db: DbSession):
    sid = parse_uuid(space_id)
    membership = get_membership(db, sid, user)
    space = _get_space_or_404(db, sid)
    members = (
        db.query(models.SpaceMember, models.User)
        .join(models.User, models.User.id == models.SpaceMember.user_id)
        .filter(models.SpaceMember.space_id == sid)
        .order_by(models.SpaceMember.joined_at)
        .all()
    )
    return {
        "id": str(space.id),
        "name": space.name,
        "my_role": membership.role,
        "created_at": space.created_at.isoformat(),
        "automation": (
            {"type": space.automation_type, "config": space.automation_config or {}}
            if space.automation_type
            else None
        ),
        "members": [
            {
                "id": str(u.id),
                "display_name": u.display_name,
                "role": m.role,
                "joined_at": m.joined_at.isoformat(),
            }
            for m, u in members
        ],
    }


@router.patch("/spaces/{space_id}")
def rename_space(space_id: str, body: SpaceIn, user: CurrentUser, db: DbSession):
    sid = parse_uuid(space_id)
    require_owner(get_membership(db, sid, user))
    space = _get_space_or_404(db, sid)
    space.name = _validate_space_name(body.name)
    record(db, sid, user, "space_renamed", name=space.name)
    return {"id": str(space.id), "name": space.name}


@router.delete("/spaces/{space_id}")
def delete_space(space_id: str, user: CurrentUser, db: DbSession):
    sid = parse_uuid(space_id)
    require_owner(get_membership(db, sid, user))
    db.delete(_get_space_or_404(db, sid))  # FKs cascade members/invites/todos
    return {"ok": True}


def _validated_automation(atype: str, cfg: dict) -> tuple[str, dict]:
    """Normalized (type, config) or a friendly 400 — shared by the space
    template path and the direct PUT. Validation belongs to the provider
    (each module ships validate_config), so a future template isn't forced
    through prayer-specific rules."""
    from app.services.automations import MODULES

    module = MODULES.get(atype)
    if module is None:
        raise HTTPException(
            status_code=400, detail=f"Unknown template: {', '.join(sorted(MODULES))}"
        )
    try:
        return atype, module.validate_config(cfg or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/spaces/{space_id}/automation")
def set_automation(
    space_id: str, body: AutomationIn, user: CurrentUser, db: DbSession,
    background: BackgroundTasks,
):
    sid = parse_uuid(space_id)
    require_owner(get_membership(db, sid, user))
    space = _get_space_or_404(db, sid)
    space.automation_type, space.automation_config = _validated_automation(
        body.type, body.config or {}
    )
    db.flush()
    # First run right away (post-commit) so todos appear without waiting
    # for the next scheduler tick.
    background.add_task(_run_automation_now, sid)
    return {"automation": {"type": space.automation_type, "config": space.automation_config}}


def _run_automation_now(space_id) -> None:
    """One immediate provider run in its own session/transaction (we're
    after the request's commit here). Failures just wait for the tick."""
    import logging

    from sqlalchemy.orm import Session as OrmSession

    from app.db import get_engine, utcnow
    from app.services.automations import PROVIDERS

    try:
        with OrmSession(get_engine()) as db:
            space = db.get(models.Space, space_id)
            if space is None or not space.automation_type:
                return
            provider = PROVIDERS.get(space.automation_type)
            if provider is not None:
                provider(db, space, utcnow())
                db.commit()
    except Exception:
        logging.getLogger(__name__).exception(
            "immediate automation run failed for space %s", space_id
        )


@router.delete("/spaces/{space_id}/automation")
def clear_automation(space_id: str, user: CurrentUser, db: DbSession):
    sid = parse_uuid(space_id)
    require_owner(get_membership(db, sid, user))
    space = _get_space_or_404(db, sid)
    # Existing auto-created todos stay — turning the tap off doesn't drain
    # the sink. The owner can delete them like any other todo.
    space.automation_type = None
    space.automation_config = None
    return {"ok": True}


@router.delete("/spaces/{space_id}/members/{member_id}")
def remove_member(space_id: str, member_id: str, user: CurrentUser, db: DbSession):
    sid = parse_uuid(space_id)
    mid = parse_uuid(member_id)
    my_membership = get_membership(db, sid, user)
    target = db.get(models.SpaceMember, (sid, mid))
    if target is None:
        raise HTTPException(status_code=404, detail="Not found")
    if target.role == "owner":
        # Nobody removes the owner — they delete the space instead.
        raise HTTPException(status_code=400, detail="Owners can delete the space instead")
    if my_membership.role != "owner" and mid != user.id:
        raise HTTPException(status_code=403, detail="You can only remove yourself")
    if mid == user.id:
        record(db, sid, user, "member_left")
    else:
        removed_user = db.get(models.User, mid)
        record(
            db, sid, user, "member_removed",
            removed_name=removed_user.display_name if removed_user else "?",
        )
    # Lock order: space row first (serializes vs the automation provider's
    # membership sync — it takes the same lock before reading members),
    # then the todo rows.
    db.execute(
        sa.select(models.Space.id).where(models.Space.id == sid).with_for_update()
    ).first()
    db.delete(target)
    # Their pending 'each' checks leave with them — otherwise group todos
    # they never checked could never complete. Checked rows stay (history).
    # Roll-up decisions serialize on the parent todo row locks (same rule
    # as complete/reopen), taken in id order so concurrent removals can't
    # deadlock; otherwise this cleanup races a concurrent last-row check
    # and both sides skip the roll-up.
    db.execute(
        sa.select(models.Todo.id)
        .where(
            models.Todo.space_id == sid,
            models.Todo.completion_mode == "each",
            models.Todo.completed_at.is_(None),
        )
        .order_by(models.Todo.id)
        .with_for_update()
    ).all()
    db.query(models.TodoAssignee).filter(
        models.TodoAssignee.user_id == mid,
        models.TodoAssignee.completed_at.is_(None),
        models.TodoAssignee.todo_id.in_(
            sa.select(models.Todo.id).where(models.Todo.space_id == sid)
        ),
    ).delete(synchronize_session=False)
    from app.routers.todos import roll_up_orphaned_each_todos

    roll_up_orphaned_each_todos(db, sid, utcnow())
    if mid != user.id:
        # A kick must stick: outstanding invite links are bearer tokens the
        # removed member very likely holds (they're listed to every member),
        # so revoke them all — remaining members can mint fresh ones. A
        # voluntary leave keeps links alive (the leaver isn't being locked out).
        db.query(models.Invite).filter(
            models.Invite.space_id == sid, models.Invite.revoked_at.is_(None)
        ).update({"revoked_at": utcnow()})
    return {"ok": True}


# ── Invites ───────────────────────────────────────────────────────────────


@router.post("/spaces/{space_id}/invites", status_code=201)
def create_invite(space_id: str, user: CurrentUser, db: DbSession):
    sid = parse_uuid(space_id)
    get_membership(db, sid, user)  # any member may invite
    now = utcnow()
    # Opportunistic cleanup (same pattern as expired sessions on login) so
    # the table can't grow without bound...
    db.query(models.Invite).filter(
        models.Invite.space_id == sid,
        (models.Invite.expires_at <= now) | models.Invite.revoked_at.is_not(None),
    ).delete()
    # ...and a hard cap on active links per space.
    active = (
        db.query(models.Invite)
        .filter(models.Invite.space_id == sid)
        .count()
    )
    if active >= _MAX_ACTIVE_INVITES:
        raise HTTPException(
            status_code=400,
            detail="This space already has too many active invite links — revoke one first",
        )
    invite = models.Invite(
        space_id=sid,
        code=secrets.token_urlsafe(16),
        created_by=user.id,
        expires_at=utcnow() + timedelta(days=_INVITE_DAYS),
    )
    db.add(invite)
    db.flush()
    return {
        "id": str(invite.id),
        "code": invite.code,
        "url": f"/invite/{invite.code}",
        "expires_at": invite.expires_at.isoformat(),
    }


@router.get("/spaces/{space_id}/invites")
def list_invites(space_id: str, user: CurrentUser, db: DbSession):
    sid = parse_uuid(space_id)
    get_membership(db, sid, user)
    now = utcnow()
    invites = (
        db.query(models.Invite)
        .filter(
            models.Invite.space_id == sid,
            models.Invite.revoked_at.is_(None),
            models.Invite.expires_at > now,
        )
        .order_by(models.Invite.created_at)
        .all()
    )
    return {
        "items": [
            {
                "id": str(i.id),
                "code": i.code,
                "url": f"/invite/{i.code}",
                "expires_at": i.expires_at.isoformat(),
            }
            for i in invites
        ]
    }


@router.delete("/invites/{invite_id}")
def revoke_invite(invite_id: str, user: CurrentUser, db: DbSession):
    iid = parse_uuid(invite_id)
    invite = db.get(models.Invite, iid)
    if invite is None:
        raise HTTPException(status_code=404, detail="Not found")
    get_membership(db, invite.space_id, user)  # any member may revoke
    invite.revoked_at = utcnow()
    return {"ok": True}


def _load_invite(db, code: str) -> models.Invite:
    invite = db.query(models.Invite).filter(models.Invite.code == code).one_or_none()
    if invite is None:
        raise HTTPException(status_code=404, detail="Not found")
    return invite


@router.get("/invites/{code}")
def invite_preview(code: str, db: DbSession):
    """Public: what a recipient sees before signing in. A dead link stops
    disclosing the space/inviter — revocation must also cut the metadata."""
    invite = _load_invite(db, code)
    if invite.revoked_at is not None or invite.expires_at <= utcnow():
        return {"valid": False}
    space = db.get(models.Space, invite.space_id)
    inviter = db.get(models.User, invite.created_by)
    if space is None:
        return {"valid": False}
    return {
        "space_name": space.name,
        "inviter_name": inviter.display_name if inviter else "Someone",
        "valid": True,
    }


@router.post("/invites/{code}/accept")
def accept_invite(code: str, user: CurrentUser, db: DbSession, background: BackgroundTasks):
    invite = _load_invite(db, code)
    if invite.revoked_at is not None or invite.expires_at <= utcnow():
        raise HTTPException(status_code=410, detail="This invite link is no longer valid")
    if db.get(models.SpaceMember, (invite.space_id, user.id)) is None:
        existing_members = [
            m.user_id
            for m in db.query(models.SpaceMember)
            .filter(models.SpaceMember.space_id == invite.space_id)
            .all()
        ]
        db.add(models.SpaceMember(space_id=invite.space_id, user_id=user.id, role="member"))
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            # Either we lost a duplicate-accept race (fine — membership
            # exists) or the space was deleted from under the invite.
            if db.get(models.Space, invite.space_id) is None:
                raise HTTPException(
                    status_code=410, detail="This invite link is no longer valid"
                )
        else:
            record(db, invite.space_id, user, "member_joined")
            space = db.get(models.Space, invite.space_id)
            if space is not None:
                from app.services.notify import notify_users, send_pushes

                prepared = notify_users(
                    db,
                    existing_members,
                    type="joined",
                    title=f"{user.display_name} joined {space.name}",
                    space_id=space.id,
                    url=f"/spaces/{space.id}",
                    exclude=user.id,
                )
                background.add_task(send_pushes, prepared)
    return {"space_id": str(invite.space_id)}
