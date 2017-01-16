from database import Base, session
from sqlalchemy import Column, Integer, ForeignKey, Date, String
from sqlalchemy.orm import relationship
from unagi.rarbg import Rarbg
import transmissionrpc
from logger import logger
import os
from unagi.error import UnagiError
import shutil
from addic7ed_cli.episode import search
import re
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class Episode(Base):
    __tablename__ = 'episode'
    id = Column(Integer, primary_key=True)
    season = Column(Integer)
    number = Column(Integer)
    title = Column(String(250))
    summary = Column(String(2500))
    aired_at = Column(Date)
    rating = Column(Integer)
    image = Column(String(1000))
    status = Column(Integer)
    torrent = Column(String(2500))
    torrent_percent = Column(Integer)
    subtitle_percent = Column(Integer)
    filename = Column(String(2500))
    show_id = Column(Integer, ForeignKey('show.id'))
    show = relationship("Show", back_populates="episodes")

    STATUS_IGNORED = 0
    STATUS_ACTIVE = 1

    DATA_DIR = '/path/to/unagi/data'
    FROM = 'noreply@unagi'

    def __repr__(self):
        return "<Episode(id=%s, show=%s, number=S%02dE%02d)>" % (self.id, self.show.title, self.season, self.number)

    def load(episode_id):
        return session.query(Episode).filter(Episode.id == episode_id).one()

    def queue(self):
        if (self.status != Episode.STATUS_ACTIVE or self.torrent != None):
            raise Exception("Wrong status")
        logger.info("Search torrent for %s" % self)
        rarbg = Rarbg()
        query = "mode=search&search_tvdb=%s&format=json_extended&sort=seeders&limit=100&search_string=S%02dE%02d&ranked=0"
        data = rarbg.request(query % (self.show.id, self.season, self.number))
        if 'torrent_results' in data.keys():
            for torrent in data['torrent_results']:
                if '720p' in torrent['title']:
                    result = Episode.transmission().add_torrent(torrent['download'])
                    logger.info("Queue torrent for %s" % self)
                    self.torrent = result.hashString
                    self.torrent_percent = 0
                    self.subtitle_percent = 0
                    #session.merge(self) # save
                    session.commit()
                    return
        #session.merge(self) # save
        logger.info("Cannot found torrent for %s" % self)
        raise UnagiError("Cannot found torrent")

    def sync_torrent(self):
        if (self.status != Episode.STATUS_ACTIVE or self.torrent == None or self.torrent_percent >= 100):
            raise Exception("Wrong status")
        logger.info("Update torrent status for %s" % self)
        try:
            result = Episode.transmission().get_torrent(self.torrent)
        except:
            logger.error("Cannot sync torrent for %s" % self)
            self.torrent = None
            self.torrent_percent = None
            self.subtitle_percent = None
            self.filename = None
        else:
            self.torrent_percent = result.progress
            if result.progress == 100:
                logger.info("Torrent completed for %s" % self)
                for file in result.files().values():
                    filename = file['name']
                    (base, ext) = os.path.splitext(filename.lower())
                    if not 'sample' in base and ext in ['.mkv', '.avi', '.mp4']:
                        self.filename = "%s/%s" % (result.downloadDir, filename) #
                        break
                Episode.transmission().remove_torrent([result.id]) # TODO: delete data
        #session.merge(self) # save
        session.commit()

    def sync_subtitle(self):
        if (self.status != Episode.STATUS_ACTIVE or self.torrent == None or self.subtitle_percent >= 100):
            raise Exception("Wrong status")
        logger.info("Update subtitle status for %s" % self)

        episodes = search("%s - %02dx%02d" % (re.sub(r'\(\d\d\d\d\)', '', self.show.title), self.season, self.number))
        if (len(episodes) == 1):
            episode = episodes[0]
            episode.fetch_versions()
            subtitles = episode.filter_versions(['fre'])

            percent = 0
            for subtitle in subtitles:
                if (subtitle.language == 'French'):
                    if (subtitle.completeness == 'Completed'):
                        logger.info("Subtitle completed for %s" % self)
                        percent = 100
                        self.create_directory()

                        subtitle.download(self.subtitle_path())

                        (base, ext) = os.path.splitext(self.filename.lower())
                        filename = self.filename
                        self.filename = self.filename2(ext)
                        shutil.move(filename, self.video_path())
                        break
                    else:
                        percent = max(float(subtitle.completeness.replace('%', '')), percent)

            self.subtitle_percent = percent
            #session.merge(self) # save
        else:
            logger.error("Cannot found subtitle for %s" % self)
        session.commit()

    def download_video(self):
        if (self.status != Episode.STATUS_ACTIVE or self.torrent == None or self.torrent_percent < 100 or self.filename == None):
            raise Exception("Wrong status")
        mimeTypes = {}
        mimeTypes[".avi"] = "video/avi"
        mimeTypes[".mp4"] = "video/mp4"
        mimeTypes[".mkv"] = "video/x-matroska"
        (base, ext) = os.path.splitext(self.filename)
        headers = {}
        headers["Content-Type"] = mimeTypes[ext]
        headers["Content-Length"] = os.path.getsize(self.video_path())
        headers["X-Accel-Redirect"] = self.video_url()
        headers["Content-Disposition"] = "attachment; filename=\"%s\"" % os.path.basename(self.filename)
        return headers

    def download_subtitle(self):
        if (self.status != Episode.STATUS_ACTIVE or self.torrent == None or self.subtitle_percent < 100):
            raise Exception("Wrong status")
        headers = {}
        headers["Content-Type"] = 'text/plain'
        headers["Content-Length"] = os.path.getsize(self.subtitle_path())
        headers["X-Accel-Redirect"] = self.subtitle_url()
        headers["Content-Disposition"] = "attachment; filename=\"%s\"" % os.path.basename(self.subtitle_path())
        return headers

    def reset(self):
        logger.info("Reset %s" % self)
        self.status = Episode.STATUS_IGNORED
        self.torrent = None
        self.torrent_percent = None
        self.subtitle_percent = None
        self.filename = None
        # TODO: delete files and torrent
        #session.merge(self) # save

    def notify(self):
        to = []
        for user in self.show.users:
            to.append(user.email)
        if to:
            me = 'noreply@unagi'
            msg = MIMEMultipart()
            msg['To'] = ", ".join(to)
            msg['From'] = Episode.FROM
            msg['Subject'] = "[Unagi] %s - S%02dE%02d - %s" % (self.show.title, self.season, self.number, self.title)
            html = "<p>A new episode is available!<p><strong>%s - S%02dE%02d - %s</strong></p><p><img src='%s' /></p><p><em>%s</em></p><p>Download <a href='http://unagi/video/%d'>video</a> and <a href='http://unagi/subtitle/%d'>french subtitles</a>.</p><p>Enjoy :)</p>"  % (self.show.title, self.season, self.number, self.title, self.image, self.summary, self.id, self.id)
            msg.attach(MIMEText(html, 'html'))
            s = smtplib.SMTP('localhost')
            s.sendmail(Episode.FROM, to, msg.as_string())
            s.quit()

    def create_directory(self):
        dirname = Episode.path(self.show.dirname())
        if not os.path.exists(dirname):
            os.mkdir(dirname)

    def filename2(self, ext):
        return '%s/%s.S%02dE%02d%s' % (self.show.dirname(), self.show.title, self.season, self.number, ext)

    def check_video(self):
        if not os.path.exists(self.video_path()):
            logger.info("Video deleted for %s" % self)
            self.reset()
            session.commit()

    def check_subtitle(self):
        if not os.path.exists(self.subtitle_path()):
            logger.info("Subtitle deleted for %s" % self)
            self.subtitle_percent = 0
            session.commit()

    def subtitle_path(self):
        return Episode.path(self.filename2('.srt'))

    def subtitle_url(self):
        return Episode.url(self.filename2('.srt'))

    def video_path(self):
        return Episode.path(self.filename)

    def video_url(self):
        return Episode.url(self.filename)

    def path(filename):
        return "%s/%s" % (Episode.DATA_DIR, filename)

    def url(filename):
        return "/data/%s" % filename

    def transmission():
        return transmissionrpc.Client('localhost', port=9091, user='root', password='')

    def is_past(episode):
        return episode.aired_at != None and episode.aired_at < datetime.date.today()
