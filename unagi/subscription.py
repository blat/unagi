from database import Base
from sqlalchemy import Table, Column, Integer, ForeignKey

Subscription = Table('subscription', Base.metadata,
    Column('user_id', Integer, ForeignKey('user.id'), primary_key=True),
    Column('show_id', Integer, ForeignKey('show.id'), primary_key=True)
)
