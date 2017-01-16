import logging

logger = logging.getLogger('unagi')
hdlr = logging.FileHandler('/tmp/unagi.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)
