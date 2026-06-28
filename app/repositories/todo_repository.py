"""ToDo Repository — Data access for ToDo model."""

from app import db
from app.models.todo import ToDo


def create_todo(**kwargs):
    todo = ToDo(**kwargs)
    db.session.add(todo)
    return todo


def find_todo_by_id(todo_id: str):
    return ToDo.query.filter_by(todo_id=todo_id).first()


def find_todos_by_patient(patient_id: str):
    return (
        ToDo.query
        .filter_by(patient_id=patient_id)
        .order_by(ToDo.created_at.desc())
        .all()
    )


def delete_todo(todo):
    db.session.delete(todo)


def commit():
    db.session.commit()
