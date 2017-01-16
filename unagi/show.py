from pytvdbapi import api
from database import Base, session
from logger import logger
from sqlalchemy import Column, String, Date, Integer, func
from sqlalchemy.orm import relationship
from unagi.subscription import Subscription
from unagi.episode import Episode
import datetime
from sqlalchemy import case

class Show(Base):
    __tablename__ = 'show'
    id = Column(String(50), primary_key=True)
    title = Column(String(250))
    summary = Column(String(2500))
    status = Column(String(250))
    first_aired_at = Column(Date)
    air_time = Column(String(250))
    air_day = Column(String(250))
    network = Column(String(250))
    rating = Column(Integer)
    duration = Column(Integer)
    genre = Column(String(1000))
    poster = Column(String(1000))
    banner = Column(String(1000))
    episodes = relationship("Episode", back_populates="show")

    def __repr__(self):
        return "<Show(id=%s, title=%s)>" % (self.id, self.title)

    def load(show_id):
        return session.query(Show).filter(Show.id == show_id).one()

    def popular(user):
        shows = session.query(Show).join(Subscription).group_by(Show).order_by(func.count('Subscription.user_id').desc(),case([(Show.rating, Show.rating)], else_=0).desc()).all()
        results = []
        for show in shows:
            if not user.is_subscriber(show):
                results.append(show)
        return results

    def search(query):
        logger.info("Search shows for query: %s" % query)
        shows = {}
        tvdbShows = Show.tvdb().search(query, 'fr')
        for tvdbShow in tvdbShows:
            show = Show(id=tvdbShow.id)
            logger.info("Found %s" % show)
            show.sync_metadata()
            shows[tvdbShow.id] = show
            # no save!
        return shows.values()

    def create(show_id):
        try:
            show = session.query(Show).filter(Show.id == show_id).one()
            logger.info("Update %s" % show)
        except:
            show = Show(id=show_id)
            logger.info("Import %s" % show)
        show.sync_metadata()
        #session.merge(show) # save
        show.sync_episodes(Episode.STATUS_IGNORED)
        return show

    def sync_metadata(self):
        logger.info("Fetch metadata for %s" % self)
        tvdbShow = Show.tvdb().get_series(self.id, 'en')

        self.title = tvdbShow.SeriesName

        tvdbShow.load_banners()
        posters = [b for b in tvdbShow.banner_objects if b.BannerType == "poster" and b.Language == 'en' and b.banner_url]
        if len(posters) > 0:
            self.poster = posters[0].banner_url
        else:
            self.poster = None
        banners = [b for b in tvdbShow.banner_objects if b.BannerType == "series" and b.Language == 'en' and b.banner_url]
        if len(banners) > 0:
            self.banner = banners[0].banner_url
        else:
            self.banner = None

        if hasattr(tvdbShow, 'Overview'):
            self.summary = tvdbShow.Overview
        if hasattr(tvdbShow, 'Status'):
            self.status = tvdbShow.Status
        if hasattr(tvdbShow, 'FirstAired') and tvdbShow.FirstAired:
            self.first_aired_at = tvdbShow.FirstAired
        if hasattr(tvdbShow, 'Airs_DayOfWeek'):
            self.air_day = tvdbShow.Airs_DayOfWeek
        if hasattr(tvdbShow, 'Airs_Time'):
            self.air_time = tvdbShow.Airs_Time
        if hasattr(tvdbShow, 'Runtime'):
            self.duration = tvdbShow.Runtime
        if hasattr(tvdbShow, 'Network'):
            self.network = tvdbShow.Network
        if hasattr(tvdbShow, 'Rating'):
            self.rating = tvdbShow.Rating
        if hasattr(tvdbShow, 'Genre'):
            self.genre = ', '.join(tvdbShow.Genre)
        return self

    def sync_episodes(self, default_status):
        logger.info("Fetch episodes for %s" % self)
        tvdbShow = Show.tvdb().get_series(self.id, 'en')
        for tvdbSeason in tvdbShow:
            if tvdbSeason.season_number:
                for tvdbEpisode in tvdbSeason:
                    if tvdbEpisode.EpisodeNumber:
                        try:
                            episode = session.query(Episode).filter(Episode.id == tvdbEpisode.id).one()
                            logger.info("Update %s" % episode)
                        except:
                            episode = Episode()
                            episode.id = tvdbEpisode.id
                            episode.season = tvdbSeason.season_number
                            episode.number = tvdbEpisode.EpisodeNumber
                            episode.show = self
                            logger.info("Import %s" % episode)
                            if tvdbEpisode.FirstAired and tvdbEpisode.FirstAired < datetime.date.today():
                                episode.status = default_status

                        if not tvdbEpisode.FirstAired or tvdbEpisode.FirstAired >= datetime.date.today():
                            episode.status = Episode.STATUS_ACTIVE # always set future episodes as active

                        logger.info("Fetch metadata for %s" % episode)
                        episode.title = tvdbEpisode.EpisodeName
                        episode.summary = tvdbEpisode.Overview
                        episode.rating = tvdbEpisode.Rating
                        episode.season = tvdbSeason.season_number
                        episode.number = tvdbEpisode.EpisodeNumber
                        if not tvdbEpisode.FirstAired:
                            episode.aired_at = None
                        else:
                            episode.aired_at = tvdbEpisode.FirstAired

                        if hasattr(tvdbEpisode, 'filename') and tvdbEpisode.filename:
                            episode.image = 'http://thetvdb.com/banners/%s' % tvdbEpisode.filename

                        #session.merge(episode) # save

    def reset(self):
        logger.info("Reset %s" % self)
        for episode in self.episodes:
            episode.reset()

    def tvdb():
        return api.TVDB('##APIKEY##', banners=True)

    def dirname(self):
        return self.title

