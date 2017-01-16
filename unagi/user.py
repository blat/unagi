from database import Base, session
from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship
from unagi.subscription import Subscription
from unagi.show import Show
from unagi.episode import Episode
import datetime
from sqlalchemy import or_
from sqlalchemy import case
import hashlib

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    email = Column(String(250))
    password = Column(String(500))
    shows = relationship(
        "Show",
        secondary=Subscription,
        order_by="Show.title",
        backref="users")

    def __repr__(self):
        return "<User(id=%s, email=%s)>" % (self.id, self.email)

    def load(user_id):
        return session.query(User).filter(User.id == user_id).one()

    def auth(email, password):
        password = hashlib.sha1(password.encode('utf-8')).hexdigest()
        user = session.query(User).filter(User.email == email).filter(User.password == password).first()
        return user

    def subscribe(self, show_id):
        show = Show.create(show_id)
        self.shows.append(show)
        #session.merge(self) # save
        session.commit()

    def unsubscribe(self, show_id):
        for show in self.shows:
            if (show.id == show_id):
                self.shows.remove(show)
                if (len(show.users) == 0):
                    show.reset()
        #session.merge(self) # save
        session.commit()

    def is_subscriber(self, show):
        for s in self.shows:
            if (show.id == s.id):
                return True
        return False

    def episodes_ready(self):
        filters = [
            Episode.aired_at < datetime.date.today(), # in the past
            Episode.status != Episode.STATUS_IGNORED, # active
            Episode.torrent_percent == 100, # torrent completed
            Episode.subtitle_percent == 100 # torrent completed
        ]
        order_by = [
            Episode.aired_at.desc(),
            Show.title.desc(),
            Episode.season.desc(),
            Episode.number.desc()
        ]
        return self.episodes(filters, order_by)

    def episodes_processing(self):
        filters = [
            Episode.aired_at < datetime.date.today(), # in the past
            Episode.status != Episode.STATUS_IGNORED, # active
            Episode.torrent != None, # torrent found
            or_(Episode.subtitle_percent < 100, Episode.torrent_percent < 100) # torrent not completed
        ]
        order_by = [
            Episode.aired_at.desc(),
            Show.title.desc(),
            Episode.season.desc(),
            Episode.number.desc()
        ]
        return self.episodes(filters, order_by)

    def episodes_pending(self):
        filters = [
            Episode.aired_at < datetime.date.today(), # in the past
            Episode.status != Episode.STATUS_IGNORED, # active
            Episode.torrent == None # no torrent found
        ]
        order_by = [
            Episode.aired_at.desc(),
            Show.title.desc(),
            Episode.season.desc(),
            Episode.number.desc()
        ]
        return self.episodes(filters, order_by)

    def episodes_waiting(self):
        filters = [
            or_(Episode.aired_at == None, Episode.aired_at >= datetime.date.today()), # in the future
            Episode.status != Episode.STATUS_IGNORED # active
        ]
        order_by = [
            case([(Episode.aired_at == None, 1)], else_=0).asc(),
            Episode.aired_at.asc(),
            Show.title.asc(),
            Episode.season.asc(),
            Episode.number.asc()
        ]
        return self.episodes(filters, order_by)

    def episodes(self, filters, order_by):
        query = session.query(Episode)
        for f in filters:
            query = query.filter(f)
        query = query.\
            join(Episode.show).\
            join(Show.users).filter(User.id == self.id)
        for o in order_by:
            query = query.order_by(o)
        return query.all()

