#!/usr/bin/env python

import logging
from logging.handlers import SysLogHandler
formatter = logging.Formatter('%(name)s[%(process)d]: %(levelname)s - %(message)s')
handler = SysLogHandler(address="/dev/log")
handler.setFormatter(formatter)
logger = logging.getLogger('twitstlk')
logger.setLevel(logging.INFO)
logger.addHandler(handler)

import sys
import os
import urllib
import Image
import re
from time import sleep, mktime
from htmlentitydefs import codepoint2name
from subprocess import Popen
import pynotify
import twitter
from feedparser import parse

# --- NEED TO BE CHANGED ACCORDINGLY ---
# You have to create a new application (go to https://dev.twitter.com/apps/)
# in order to get valid tokens that will grant twitstlk access to your twitter account.
GREADER_SHARED_ATOM = 'http://www.google.com/reader/public/atom/user/11898197621162994883/label/partage?n=50'
CONSUMER_KEY = ''
OAUTH_TOKEN = ''
CONSUMER_SECRET = ''
OAUTH_TOKEN_SECRET = ''
SCREENLOCKERS = ['kscreenlocker', 'xlock', ]
STORAGE_DIR = '~/.twitstlk'
# -------------------------------------------------------------------

API_PROXIES = {}
for i in ('http', 'https'):
  k = '%s_proxy' % i
  if k in os.environ:
    API_PROXIES[i] = os.environ[k]

OAUTH = dict(consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET,
  access_token_key=OAUTH_TOKEN, access_token_secret=OAUTH_TOKEN_SECRET)


def escape(s):
  """Encode every '&' that is not a htmlentity into the HTML entity '&amp;'"""
  return re.sub(r'&(?!%s;)' % ';|'.join(codepoint2name.values()), '&amp;', s)


def notify(summary, body, icon='/usr/share/icons/oxygen/32x32/apps/preferences-desktop-notification.png', delay=7):
  pynotify.init('twitstlk')
  n = pynotify.Notification(summary, body, icon)
  n.set_urgency(pynotify.URGENCY_LOW)
  n.set_timeout(delay*1000)
  n.show()

  sleep(delay+2)


def twitter_authapi():
  return twitter.Api(timeout=30, proxy=API_PROXIES, **OAUTH)


def twitter_friends_timeline():

  image_dir = os.path.join(os.path.expanduser(STORAGE_DIR), 'images')
  if not os.path.isdir(image_dir):
    os.makedirs(image_dir)

  last_file = os.path.join(os.path.expanduser(STORAGE_DIR), 'twitter_last.txt')

  api = twitter_authapi()
  if os.path.isfile(last_file) and os.path.getsize(last_file):
    since_id = open(last_file).read()
    friends = api.GetFriendsTimeline(since_id=since_id, retweets=True)
  else:
    friends = api.GetFriendsTimeline(count=10, retweets=True)

  for f in friends[::-1]:
    name = f.user.screen_name
    text = re.sub(r'(https?://t.co/[a-zA-Z0-9]+)', r'<a href="\1">\1</a>', escape(f.text))
    image = '%s/%s.png' % (image_dir, f.user.id)
    if not os.path.isfile(image):
      urllib.urlretrieve(f.user.profile_image_url, image)
      Image.open(image).convert('RGBA').save(image)

    notify(name, text, image)

  if friends:
    update_last(last_file, max(f.id for f in friends))

  rate = api.GetRateLimitStatus()
  logger.info('Rate: %s / %s' % (rate['remaining_hits'], rate['hourly_limit']))


def twitter_trends():
  api = twitter_authapi()
  trends = api.GetTrendsCurrent()
  notify('trends', '\n'.join(t.name for t in trends))


def twitter_timeline():
  api = twitter_authapi()
  last_id = '124711885940600832' #None
  nb_tweets = 0

  while True:
    tweets = api.GetFriendsTimeline(retweets=True, count=100, max_id=last_id)
    if not tweets:
      break
    for t in tweets:
      last_id, name, text = t.id, t.user.screen_name, t.text
      print('%-4d %d %s %s' % (nb_tweets, last_id, name, text))
      nb_tweets += 1
  print('Total tweets: %d' % nb_tweets)


def update_last(last_file, last_value):
  if not is_screen_locked():
    logger.info('Updating %s' % last_file)
    open(last_file, 'w').write('%s' % last_value)
  

def greader_shared():

  last_file = os.path.join(os.path.expanduser(STORAGE_DIR), 'greader_last.txt')
  if os.path.isfile(last_file) and os.path.getsize(last_file):
    last_time = float(open(last_file).read())
  else:
    last_time = None

  news = []
  feed = parse(GREADER_SHARED_ATOM)
  for e in reversed(feed.entries):
    e.updated_parsed = mktime(e.updated_parsed) 
    if last_time and e.updated_parsed <= last_time:
      continue

    news.append(e)

  for e in news:
    summary = e.source.title
    authors = ', '.join(v.name for v in e.authors if v.name != '(author unknown)')
    if authors:
      summary += '- %s' % authors
    body = re.sub(r'(https?://\S+)', r'<a href="\1">\1</a>', '%s\n%s' % (e.title, e.link))

    image = os.path.join(os.path.dirname(__file__), 'greader.png')

    summary, body = escape(summary), escape(body)
    notify(summary, body, image)

  if news:
    update_last(last_file, max(e.updated_parsed for e in news))
    

def is_screen_locked():
  for locker in SCREENLOCKERS:
    if [x for x in os.popen('pgrep %s' % locker)]:
      return True
  return False

if __name__ == '__main__':

  if len(sys.argv) > 1:
    action = sys.argv[1]

    if action == 'trends':
      twitter_trends()
    
    elif action == 'timeline':
      twitter_timeline()
    
    else:
      raise NotImplementedError('incorrect given action')

  else:

    if is_screen_locked():
      sys.exit(0)

    lock_file = os.path.join(os.path.expanduser(STORAGE_DIR), 'running.pid')

    if os.path.isfile(lock_file) and os.path.getsize(lock_file):
      running_pid = open(lock_file).read()
      if not os.path.isdir('/proc/%s' % running_pid):
        os.remove(lock_file)
      else:
        logger.info('Already running instance detected, PID: %s' % running_pid)
        sys.exit(0)

    try:
      open(lock_file, 'w').write('%d' % os.getpid())
      twitter_friends_timeline()
      greader_shared()
    except:
      e_type, e_value, _ = sys.exc_info()
      logger.warn('%s, %s' % (e_type, e_value))
    finally:
      os.remove(lock_file)

