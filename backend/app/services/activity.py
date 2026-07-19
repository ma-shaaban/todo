"""One-line activity recording, called from the routers."""

from app import models


def record(db, space_id, actor, type: str, todo=None, **data) -> None:
    db.add(
        models.Activity(
            space_id=space_id,
            actor_id=actor.id if actor else None,
            type=type,
            todo_id=todo.id if todo is not None else None,
            data=data,
        )
    )
