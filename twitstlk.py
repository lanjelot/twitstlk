#!/usr/bin/env python

import logging
from logging.handlers import SysLogHandler
formatter = logging.Formatter('%(name)s[%(process)d]: %(levelname)s - %(message)s')
handler = SysLogHandler(address="/dev/log")
handler.setFormatter(formatter)
logger = logging.getLogger('twitstlk')
logger.setLevel(logging.INFO)
logger.addHandler(handler)

import twitter
import sys
import os
import urllib
import urllib2
import Image
import re
from time import sleep
from htmlentitydefs import codepoint2name
from subprocess import Popen

CONSUMER_KEY = '4ErIfugB5uqzSRUKtFQ3qg'
OAUTH_TOKEN = '20048350-pua2lt9w54fIjKnTySemp9gr8tNYQo2vQjh9D7hwm'

# --- NEED TO BE CHANGED ---
CONSUMER_SECRET = '...'
OAUTH_TOKEN_SECRET = '...'
STORAGE_DIR = '~/.twitstlk'
# -------------------------------------------------------------------

API_PROXIES = {}
for i in ('http', 'https'):
  k = '%s_proxy' % i
  if k in os.environ:
    API_PROXIES[i] = os.environ[k]

OAUTH = dict(consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET,
  access_token_key=OAUTH_TOKEN, access_token_secret=OAUTH_TOKEN_SECRET)

SINCE_ID_FILE = STORAGE_DIR + '/since_id.txt'
LOCK_FILE = STORAGE_DIR + '/running.pid'

def escape(s):
  """Encode every '&' that is not a htmlentity into the HTML entity '&amp;'"""
  return re.sub(r'&(?!%s;)' % '|'.join(codepoint2name.values()), 'amp;', s)

def notify(summary, body, icon='/usr/share/icons/oxygen/32x32/apps/preferences-desktop-notification.png', delay=7):
  cmd = ['/usr/bin/notify-send',
         '-u', 'low',
         '-i', icon,
         '-t', '%d' % (delay*1000,),
         '--',
         summary,
         body.encode('utf-8')]
  Popen(cmd)
  sleep(delay+1)

def auth_api():
  return twitter.Api(timeout=30, proxy=API_PROXIES, **OAUTH)

def friends_timeline():
  api = auth_api()
  if os.path.isfile(since_id_file) and os.path.getsize(since_id_file):
    since_id = open(since_id_file).read()
    friends = api.GetFriendsTimeline(since_id=since_id, retweets=True)
  else:
    friends = api.GetFriendsTimeline(count=10, retweets=True)

  for f in friends[::-1]:
    name = f.user.screen_name
    text = re.sub(r'(https?://\S+)', r'<a href="\1">\1</a>', escape(f.text))
    image = '%s/%s.png' % (storage_dir, f.user.id)
    if not os.path.isfile(image):
      urllib.urlretrieve(f.user.profile_image_url, image)
      Image.open(image).convert('RGBA').save(image)

    notify(name, text, image)

  if friends:
    logger.info('Updating %s' % since_id_file)
    open(since_id_file, 'w').write('%s' % max(f.id for f in friends))

  rate = api.GetRateLimitStatus()
  logger.info('Rate: %s / %s' % (rate['remaining_hits'], rate['hourly_limit']))

if __name__ == '__main__':

  if len(sys.argv) > 1:
    action = sys.argv[1]

    if action == 'trends':
      api = auth_api()
      trends = api.GetTrendsCurrent()
      notify('trends', '\n'.join(t.query for t in trends))

  else:
    storage_dir = os.path.expanduser(STORAGE_DIR)
    lock_file = os.path.expanduser(LOCK_FILE)
    since_id_file = os.path.expanduser(SINCE_ID_FILE)

    if not os.path.isdir(storage_dir):
      os.makedirs(storage_dir)

    if os.path.isfile(lock_file) and os.path.getsize(lock_file):
      running_pid = open(lock_file).read()
      logger.info('Already running instance detected, PID: %s' % running_pid)
      sys.exit(0)

    try:
      open(lock_file, 'w').write('%d' % os.getpid())
      friends_timeline()
    except:
      e_type, e_value, _ = sys.exc_info()
      logger.warn('%s, %s' % (e_type, e_value))
      sys.exit(0)
    finally:
      os.remove(lock_file)

