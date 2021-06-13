from flask_sqlalchemy import SQLAlchemy
from typing import Callable


class MYSQLAlchemy(SQLAlchemy):
    Column: Callable
    Integer: Callable
    String: Callable
    Text: Callable
    ForeignKey: Callable
