import datetime
import time
import requests
from logger import logger

class Rarbg:
    token = ''
    tokenDate = ''
    lastRequest = 0
    def __init__(self):
        if not Rarbg.token or Rarbg.tokenDate < datetime.datetime.now().timestamp() - (15*60):
            Rarbg.token = self.request('get_token=get_token')['token']
            Rarbg.tokenDate = datetime.datetime.now().timestamp()

    def request(self, query):
        if query != 'get_token=get_token':
            if Rarbg.lastRequest > datetime.datetime.now().timestamp()-2:
                time.sleep(2)
            Rarbg.lastRequest = datetime.datetime.now().timestamp()
        url = 'https://torrentapi.org/pubapi_v2.php?token=%s&%s' % (Rarbg.token, query)
        logger.info("Fetch %s" % url)
        req = requests.get(url)
        return req.json()

