import logging

_level = logging.CRITICAL
# svgmath verbose / debug
# _level = logging.WARNING

logger = logging.getLogger('svgmath')
handler = logging.StreamHandler()
handler.setLevel(_level)
handler.setFormatter(
    logging.Formatter('%(asctime)s [%(levelname)s] [%(module)s] %(message)s'))
logger.addHandler(handler)
