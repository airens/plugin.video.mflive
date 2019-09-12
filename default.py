#!/usr/bin/python
# -*- coding: utf-8 -*-

from simpleplugin import Plugin
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmc
import BeautifulSoup
from dateutil.tz import tzlocal, tzoffset
import dateutil.parser
import urllib2
from urlparse import urlparse
from datetime import datetime
import pickle
import os
import datetime

import locale
locale.setlocale(locale.LC_ALL, '')


ID_PLUGIN = 'plugin.video.mflive'

__addon__ = xbmcaddon.Addon(id=ID_PLUGIN)
__path__ = __addon__.getAddonInfo('path')
__version__ = __addon__.getAddonInfo('version')
__media__ = os.path.join(__path__, 'resources', 'media')


SITE = __addon__.getSetting('url_site')


def dbg_log(line):
    if __addon__.getSetting('is_debug') == 'true':
        xbmc.log('%s [v.%s]: %s' % (ID_PLUGIN, __version__, line))


def _http_get(url):
    try:
        req = urllib2.Request(url=url)
        req.add_header('User-Agent',
                       'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; Mozilla/4.0'
                       ' (compatible; MSIE 6.0; Windows NT 5.1; SV1) ; .NET CLR 1.1.4322; .NET CLR 2.0.50727; '
                       '.NET CLR 3.0.4506.2152; .NET CLR 3.5.30729; .NET4.0C)')
        resp = urllib2.urlopen(req)
        http = resp.read()
        resp.close()
        return http
    except Exception, e:
        print('[%s]: GET EXCEPT [%s]' % (ID_PLUGIN, e), 4)
        print url


def _load_leagues():
    file_pickle = os.path.join(__path__, 'leagues.pickle')
    if os.path.exists(file_pickle):
        with open(file_pickle, 'r') as f:
            return pickle.load(f)
    else:
        data = ['Все', ]
        with open(file_pickle, 'wt') as f:
            f.write(pickle.dumps(data, 0))
        with open(file_pickle, 'r') as f:
            return pickle.load(f)


def _load_leagues_image():

    html = _http_get(SITE + '/index/0-2')

    soup = BeautifulSoup.BeautifulSoup(html)

    league_pictures = []

    matches_records_page = soup.find(
        'table', {'class': 'matches-records-page'})

    if matches_records_page:
        tags_a = matches_records_page.findAll('a')
        for a in tags_a:
            src = SITE + dict(a.contents[0].attrs)['src'].encode('utf-8')
            # dbg_log(src)
            # dbg_log(type(src))
            # dbg_log(repr(src))
            league_pictures.append(dict(league=a.parent.contents[2].text.encode('utf8'),
                                        src=src))

    return league_pictures


plugin = Plugin()


def _get_selected_leagues():
    sl = __addon__.getSetting('selected_leagues')
    if not sl:
        sl = '0'
    return map(lambda x: int(x), sl.split(','))


@plugin.action()
def root():
    matches = get_matches()
    select_item = [{'label': '[COLOR FF0084FF][B]ВЫБРАТЬ ТУРНИРЫ[/B][/COLOR]',
                    'url': plugin.get_url(action='select_matches')}, ]
    # return plugin.create_listing(select_item + matches, content='tvseries',
    #                              view_mode=55, sort_methods={'sortMethod': xbmcplugin.SORT_METHOD_NONE, 'label2Mask': '% J'})
    return select_item + matches


@plugin.action()
def select_matches(params):

    selected_leagues = _get_selected_leagues()

    result = xbmcgui.Dialog().multiselect(
        'Выбор турнира', _load_leagues(), preselect=selected_leagues)

    if not result is None:
        if not len(result):
            result.append(0)
        __addon__.setSetting('selected_leagues', ','.join(str(x)
                                                          for x in result))
        cache_file = os.path.join(xbmc.translatePath(
            __addon__.getAddonInfo('profile')), '__cache__.pcl')
        if os.path.exists(cache_file):
            os.remove(cache_file)
        root()


@plugin.cached(5)
def get_matches():
    leagues = _load_leagues()
    LEAGUES_IMAGE = _load_leagues_image()
    selected_leagues = _get_selected_leagues()
    html = _http_get(SITE)
    matches = []
    urls = set()
    tzs = int(__addon__.getSetting('time_zone_site'))
#    tzl = 2

    now_date = datetime.datetime.now().replace(tzinfo=tzlocal())
    soup = BeautifulSoup.BeautifulSoup(html)
    days = soup.findAll('div', {'class': 'rewievs_tab1'})

    for match_html in days:

        url = match_html.contents[1]['href']

        if url in urls:
            continue
        dbg_log(url)
        urls.add(url)

        tbody = match_html.findAll('tbody')[1]
        #image = tbody.contents[1].contents[1].contents[1]['src'].encode('utf-8')
        #icon = SITE + image
        game = tbody.contents[1].contents[3].text.encode('utf-8')
        league = tbody.contents[1].contents[1].contents[1]['title'].encode(
            'utf-8')
        dbg_log(game)
        dbg_log(league)
        if league not in leagues:
            dbg_log('*** Добавим - %s - в список' % league)
            leagues.append(league)
            index = leagues.index(league)
            with open(os.path.join(__path__, 'leagues.pickle'), 'wt') as f:
                f.write(pickle.dumps(leagues, 0))
            sl = _get_selected_leagues()
            sl.append(index)
            __addon__.setSetting('selected_leagues',
                                 ','.join(str(x) for x in sl))
        if not selected_leagues or not selected_leagues[0]:
            dbg_log('Фильтра нет')
        else:
            if not leagues.index(league) in selected_leagues:
                continue

        dts = tbody.contents[3].contents[1].contents[0].contents[1]['data-time']
        dt = dateutil.parser.parse(dts)
        tz = tzoffset(None, tzs * 3600)
        dt = dt.replace(tzinfo=tz)
        date_time = dt.astimezone(tzlocal())
        dbg_log(date_time)

        before_time = int((date_time - now_date).total_seconds()/60)

        if before_time < -110:
            status = 'FF999999'
        elif before_time > 0:
            status = 'FFFFFFFF'
        else:
            status = 'FFFF0000'

        label = '[COLOR %s]%s[/COLOR] - [B]%s[/B]  (%s)' % (
            status, date_time.strftime('%H:%M'), game, league)
        plot = '[B][UPPERCASE]%s[/B][/UPPERCASE]\n%s\n%s' % (
            date_time.strftime('%H:%M - %d.%m.%Y'), league, game)

        icon = os.path.join(__path__, 'icon.png')

        for league_pictures in LEAGUES_IMAGE:
            if league_pictures['league'].strip() == league.decode('utf-8').upper().encode('utf-8'):
                icon = league_pictures['src']

        matches.append({'label': label,
                        # 'thumb': icon,
                        # 'fanart': icon,
                        'info': {'video': {'title': plot, 'plot': plot}},
                        'icon': icon,
                        'url': plugin.get_url(action='get_links', url=url, image=icon)})
        dbg_log(matches[-1])

    return matches


@plugin.cached(10)
@plugin.action()
def get_links(params):

    dbg_log(params['url'])

    html = _http_get(params['url'])
    matches = []
    icon1 = ''
    command1 = ''
    icon2 = ''
    command2 = ''

    soup = BeautifulSoup.BeautifulSoup(html)

    stream_full_table_soup = soup.find(
        'table', {'class': 'stream-full-table stream-full-table1'})

    span_soup = stream_full_table_soup.findAll('span')

    #title = stream_full_table_soup.find('td', {'class': 'stream-full5'}).contents[1].text
    # dbg_log(title.encode('utf8'))

    stream_full_soup = stream_full_table_soup.find(
        'td', {'class': 'stream-full'})
    if stream_full_soup:
        icon1 = stream_full_soup.contents[0]['src'].encode('utf-8')
        command1 = stream_full_soup.contents[0]['title'].encode('utf-8')

    stream_full2_soup = stream_full_table_soup.find(
        'td', {'class': 'stream-full2'})
    if stream_full2_soup:
        icon2 = stream_full2_soup.contents[0]['src'].encode('utf-8')
        command2 = stream_full2_soup.contents[0]['title'].encode('utf-8')

    dbg_log(icon1)
    dbg_log(command1)
    dbg_log(type(icon2))
    dbg_log(type(command2))

    plot = '%s\n%s\n%s - %s' % (span_soup[0].text.encode('utf-8'),
                                span_soup[1].text.encode('utf-8'), command1, command2)

    list_link_stream_soup = soup.findAll(
        'table', {'class': 'list-link-stream'})

    #xbmcgui.Dialog().notification('Проверка ссылок:', command1 + ' - ' + command2, xbmcgui.NOTIFICATION_INFO, 5000)

    if list_link_stream_soup:

        links_font_soup = list_link_stream_soup[0].findAll(
            'span', {'class': 'links-font'})

        for link_soup in links_font_soup:
            bit_rate = link_soup.text.split('-')[1].strip().encode('utf-8')
            href = link_soup.contents[0]['href'].encode('utf-8')

            urlprs = urlparse(href)

            if urlprs.scheme == 'acestream':
                icon = os.path.join(__media__, 'ace.png')
            elif urlprs.scheme == 'sop':
                icon = os.path.join(__media__, 'sop.png')
            else:
                icon = os.path.join(__media__, 'http.png')

            matches.append({'label': '%s - %s' % (urlprs.scheme, bit_rate),
                            'info': {'video': {'title': command1 + ' - ' + command2, 'plot': plot}},
                            'thumb': icon,
                            'icon': icon,
                            'fanart': params['image'],
                            'art': {'clearart': params['image']},
                            'url': plugin.get_url(action='play', url=href),
                            'is_playable': True})
            dbg_log(matches[-1])

    iframe_soup = soup.findAll('iframe', {'rel': "nofollow"})
    for s in iframe_soup:
        html_frame = _http_get(s['src'])
        if html_frame:
            ilink = html_frame.find('var videoLink')
            if ilink != -1:
                i1 = html_frame.find('\'', ilink)
                i2 = html_frame.find('\'', i1 + 1)
                href = html_frame[i1+1:i2]
                urlprs = urlparse(href)
                matches.append({'label': '%s - прямая ссылка на видео...' % urlprs.scheme,
                                'info': {'video': {'title': command1 + ' - ' + command2, 'plot': plot}},
                                'thumb': os.path.join(__media__, 'http.png'),
                                'icon': os.path.join(__media__, 'http.png'),
                                'fanart': params['image'],
                                'art': {'clearart': params['image']},
                                'url': plugin.get_url(action='play', url=href),
                                'is_playable': True})
                dbg_log(matches[-1])

    if not matches:
        matches.append({'label': 'Ссылок на трансляции нет, возможно появятся позже!',
                        'info': {'video': {'title': '', 'plot': ''}},
                        # 'thumb': icon2,
                        # 'icon': params['image'],
                        'art': {'clearart': ''},
                        'url': plugin.get_url(action='play', url='https://www.ixbt.com/multimedia/video-methodology/camcorders-and-others/htc-one-x-avc-baseline@l3.2-1280x720-variable-fps-aac-2ch.mp4'),
                        'is_playable': True})
    return matches


@plugin.action()
def play(params):
    path = ''
    item = 0
    url = urlparse(params['url'])
    if url.scheme == 'acestream':
        if __addon__.getSetting('is_default_play') == 'true':
            item = int(__addon__.getSetting('default_ace'))
        else:
            dialog = xbmcgui.Dialog()
            item = dialog.contextmenu(
                ['ACESTREAM %s [%s]' % ('hls' if __addon__.getSetting(
                    'is_hls1') == 'true' else '', __addon__.getSetting('ipace1')),
                 'ACESTREAM %s [%s]' % ('hls' if __addon__.getSetting(
                     'is_hls2') == 'true' else '', __addon__.getSetting('ipace2')),
                 'HTTPAceProxy [%s]' % __addon__.getSetting('ipproxy'), 'Add-on TAM [127.0.0.1]'])
            if item == -1:
                return

        cid = url.netloc

        if item == 0:
            path = 'http://%s:6878/ace/%s?id=%s' % (
                __addon__.getSetting('ipace1'), 'manifest.m3u8' if __addon__.getSetting(
                    'is_hls1') == 'true' else 'getstream', cid)
        elif item == 1:
            path = 'http://%s:6878/ace/%s?id=%s' % (
                __addon__.getSetting('ipace2'), 'manifest.m3u8' if __addon__.getSetting(
                    'is_hls2') == 'true' else 'getstream', cid)
        elif item == 2:
            path = "http://%s:8000/pid/%s/stream.mp4" % (
                __addon__.getSetting('ipproxy'), cid)
        elif item == 3:
            path = "plugin://plugin.video.tam/?mode=play&url=%s&engine=ace_proxy" % params['url']
    elif url.scheme == 'sop':
        path = "plugin://program.plexus/?mode=2&url=" + \
            url.geturl() + "&name=Sopcast"
    else:
        path = url.geturl()

    dbg_log(path)

    return Plugin.resolve_url(path, succeeded=True)


if __name__ == '__main__':
    plugin.run()
