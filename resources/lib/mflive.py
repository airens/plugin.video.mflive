# -*- coding: utf-8 -*-

import datetime
import os
# from collections import OrderedDict
from urlparse import urlparse
import pickle

import xbmcgui

import bs4
import dateutil
from dateutil.parser import *
from dateutil.tz import tzlocal, tzoffset

from .plugin import Plugin


def _upper(t):
    RUS = {u"А": u"а", u"Б": u"б", u"В": u"в", u"Г": u"г", u"Д": u"д", u"Е": u"е", u"Ё": u"ё",
           u"Ж": u"ж", u"З": u"з", u"И": u"и", u"Й": u"й", u"К": u"к", u"Л": u"л", u"М": u"м",
           u"Н": u"н", u"О": u"о", u"П": u"п", u"Р": u"р", u"С": u"с", u"Т": u"т", u"У": u"у",
           u"Ф": u"ф", u"Х": u"х", u"Ц": u"ц", u"Ч": u"ч", u"Ш": u"ш", u"Щ": u"щ", u"Ъ": u"ъ",
           u"Ы": u"ы", u"Ь": u"ь", u"Э": u"э", u"Ю": u"ю", u"Я": u"я"}

    for i in RUS.keys():
        t = t.replace(RUS[i], i)
    for i in range(65, 90):
        t = t.replace(chr(i+32), chr(i))
    return t


class MFLive(Plugin):

    def __init__(self):
        super(MFLive, self).__init__()
        self._league_image = []

    def create_listing_(self):
        select_item = [{'label': '[COLOR FF0084FF][B]ВЫБРАТЬ ТУРНИРЫ[/B][/COLOR]',
                        'url': self.get_url(action='select_matches')},
                       {'label': '[COLOR FF0084FF][B]ОБНОВИТЬ[/B][/COLOR]',
                        'url': self.get_url(action='reset_inter')},
                       ]
        # return plugin.create_listing(select_item + matches, content='tvseries',
        #                              view_mode=55, sort_methods={'sortMethod': xbmcplugin.SORT_METHOD_NONE, 'label2Mask': '% J'})
        return select_item + self.get_listing()
        # return self.get_listing()

    def _load_leagues(self):
        file_pickle = os.path.join(self.config_dir, 'leagues.pickle')
        if os.path.exists(file_pickle):
            with open(file_pickle, 'r') as f:
                return pickle.load(f)
        else:
            data = [u'ВСЕ', ]
            with open(file_pickle, 'wt') as f:
                f.write(pickle.dumps(data, 0))
            with open(file_pickle, 'r') as f:
                return pickle.load(f)

    @property
    def league_image(self):

        file = os.path.join(self.config_dir, 'leagues_image.pickle')

        if os.path.exists(file):
            with open(file, 'rb') as f:
                self._league_image = pickle.load(f)
        else:

            html = self.http_get(self._site + '/index/0-2')

            if not html:
                self.logd('_load_league_image', 'not html')
                return self._league_image

            soup = bs4.BeautifulSoup(html, 'html.parser')

            matches_records_page = soup.find(
                'table', {'class': 'matches-records-page'})

            if matches_records_page:
                tags_a = matches_records_page.findAll('a')
                for a in tags_a:
                    src = self._site + a.find('img')['src'].encode('utf-8')
                    league = a.parent.find('p').text  # .encode('utf8')
                    self.log('%s - %s' % (league, src))
                    self._league_image.append(dict(league=league, src=src))

            with open(file, 'wb') as f:
                pickle.dump(self._league_image, f)

        return self._league_image

    def _get_selected_leagues(self):
        sl = str(self.get_setting('selected_leagues'))
        if not sl:
            sl = '0'
        return map(lambda x: int(x), sl.split(','))

    def select_matches(self, params):

        selected_leagues = self._get_selected_leagues()

        result = xbmcgui.Dialog().multiselect(
            'Выбор турнира', self._load_leagues(), preselect=selected_leagues)

        if result is not None:
            if not len(result):
                result.append(0)
            self.set_setting('selected_leagues', ','.join(str(x)
                                                          for x in result))
            self.on_settings_changed()

    def _parse_listing(self, html, progress=None):
        """
        Парсим страницу для основного списка
        :param html:
        :return: listing = {
                        id : {
                            id: int,
                            label: '',
                            league: '',
                            date: datetime,     должно быть осведомленное время в UTC
                            thumb: '',
                            icon: '',
                            poster: '',
                            fanart: '',
                            url_links: '',
                            href: [
                                    {
                                    'id': int,
                                    'title': '',
                                    'kbps': '',
                                    'resol': '',
                                    'href': '',
                                }
                            ]
                        }
                    }
        """
        i = 1
        leagues = self._load_leagues()
        selected_leagues = self._get_selected_leagues()
        urls = set()

        listing = {}

        soup = bs4.BeautifulSoup(html, 'html.parser')

        days = soup.findAll('div', {'class': 'rewievs_tab1'})

        for match_html in days:

            a = match_html.find('a')
            url = a['href']  # .encode('utf-8')
            title = a['title']  # .encode('utf-8')

            if url in urls:
                continue

            urls.add(url)

            td = a.findAll('td')
            game = td[-2].text
            league = _upper(a.find('img')['title'])

            if league not in leagues:
                leagues.append(league)
                index = leagues.index(league)
                with open(os.path.join(self.config_dir, 'leagues.pickle'), 'wt') as f:
                    f.write(pickle.dumps(leagues, 0))
                sl = self._get_selected_leagues()
                sl.append(index)
                self.set_setting('selected_leagues',
                                 ','.join(str(x) for x in sl))
            else:
                if not selected_leagues or not selected_leagues[0]:
                    self.log('Фильтра нет')
                else:
                    if not leagues.index(league) in selected_leagues:
                        continue

            dts = td[-1].find('span',
                              {'class': 'time-for-replace'})['data-time']
            try:
                dt = dateutil.parser.parse(dts)
            except ValueError as e:
                if e.message == 'hour must be in 0..23':
                    dt = dateutil.parser.parse(dts.split()[0])

            date_utc = self._time_naive_site_to_utc_aware(dt)

            id = self.create_id(str(date_utc) + game)

            icon = self.icon

            for league_pictures in self.league_image:
                if league_pictures['league'] == league:
                    icon = league_pictures['src'].encode('utf-8')

            listing[id] = {}
            item = listing[id]
            item['id'] = id
            item['label'] = game
            item['league'] = league
            item['date'] = date_utc
            item['thumb'] = ''
            item['icon'] = icon
            item['poster'] = ''
            item['fanart'] = self.fanart
            item['url_links'] = url
            if 'href' is not item:
                item['href'] = []

            i += 2
            if progress:
                progress.update(i, message=game)

        return listing

    def _parse_links(self, html):
        """
        Парсим страницу для списка ссылок
        :param html:
        :return:
        """

        links = []

        matches = []
        icon1 = ''
        command1 = ''
        icon2 = ''
        command2 = ''

        soup = bs4.BeautifulSoup(html, 'html.parser')
        #dbg_log('bs4.BeautifulSoup get_links(params) - %s' % soup)
        stream_full_table_soup = soup.find(
            'table', {'class': 'stream-full-table stream-full-table1'})

        span_soup = stream_full_table_soup.findAll('span')
        stream_full_soup = stream_full_table_soup.find(
            'td', {'class': 'stream-full'})
        if stream_full_soup:
            icon1 = stream_full_soup.find('img')['src'].encode('utf-8')
            command1 = stream_full_soup.find('img')['title'].encode('utf-8')

        stream_full2_soup = stream_full_table_soup.find(
            'td', {'class': 'stream-full2'})
        if stream_full2_soup:
            icon2 = stream_full2_soup.find('img')['src'].encode('utf-8')
            command2 = stream_full2_soup.find('img')['title'].encode('utf-8')

        plot_base = '%s\n%s\n%s - %s' % (span_soup[0].text.encode('utf-8'),
                                         span_soup[1].text.encode('utf-8'), command1, command2)

        if self.get_setting('is_http_acesop'):
            links_font_soup = soup.findAll('span', {'class': 'links-font'})

            for link_soup in links_font_soup:
                bit_rate = link_soup.text.split('-')[1].strip().encode('utf-8')
                href = link_soup.find('a').attrs['href'].encode('utf-8')

                urlprs = urlparse(href)

                links.append({
                    'icon1': icon1,
                    'command1': command1,
                    'icon2': icon2,
                    'command2': command2,
                    'label': '%s - %s' % (urlprs.scheme, bit_rate),
                    'bit_rate': bit_rate,
                    'href': href,
                })

        if self.get_setting('is_http_link'):
            iframe_soup = soup.findAll('iframe', {'rel': "nofollow"})
            for s in iframe_soup:
                html_frame = self.http_get(s['src'])
                if html_frame:
                    ilink = html_frame.find('var videoLink')
                    if ilink != -1:
                        i1 = html_frame.find('\'', ilink)
                        i2 = html_frame.find('\'', i1 + 1)
                        href = html_frame[i1+1:i2]
                        urlprs = urlparse(href)
                        links.append({
                            'icon1': icon1,
                            'command1': command1,
                            'icon2': icon2,
                            'command2': command2,
                            'label': '%s - прямая ссылка на видео...' % urlprs.scheme,
                            'bit_rate': '',
                            'href': href,
                        })

        return links

    def _get_links(self, id, links):
        """
        Возвращаем список ссылок для папки конкретного элемента
        :param id:
        :return:
        """
        l = []

        for link in links:

            urlprs = urlparse(link['href'])

            plot = ''

            if urlprs.scheme == 'acestream':
                icon = os.path.join(self.dir('media'), 'ace.png')
            elif urlprs.scheme == 'sop':
                icon = os.path.join(self.dir('media'), 'sop.png')
                plot = '\n\n\nДля просмотра SopCast необходим плагин Plexus'
            else:
                icon = os.path.join(self.dir('media'), 'http.png')

            l.append({'label': link['label'],
                      'info': {'video': {'title': self.get(id, 'label'), 'plot': plot}},
                      'thumb': icon,
                      'icon': icon,
                      'fanart': '',
                      'art': {'icon': icon, 'thumb': icon, },
                      'url': self.get_url(action='play', href=link['href'], id=id),
                      'is_playable': True})

        return l

    def _get_listing(self):
        """
        Возвращаем список для корневой виртуальной папки
        :return:
        """

        listing = []

        now_utc = self.time_now_utc()

        self.logd('pimpletv._get_listing()', '%s' %
                  self.time_to_local(now_utc))

        try:
            for item in self._listing.values():
                date_ = item['date']
                if date_ > now_utc:
                    dt = date_ - now_utc
                    plot = self.format_timedelta(dt, u'Через')
                    status = 'FFFFFFFF'
                else:
                    dt = now_utc - date_
                    if int(dt.total_seconds() / 60) < 110:
                        plot = u'Прямой эфир %s мин.' % int(
                            dt.total_seconds() / 60)
                        status = 'FFFF0000'
                    else:
                        plot = self.format_timedelta(dt, u'Закончен')
                        status = 'FF999999'

                title = u'[COLOR %s]%s[/COLOR]\n[B]%s[/B]\n[UPPERCASE]%s[/UPPERCASE]' % (
                    status, self.time_to_local(date_).strftime('%d.%m %H:%M'), item['label'], item['league'])

                label = u'[COLOR %s]%s[/COLOR] - [B]%s[/B]' % (
                    status, self.time_to_local(date_).strftime('%H:%M'), item['label'])

                plot = title + '\n' + plot + '\n\n' + self._site

                href = ''

                if self.get_setting('is_play'):
                    for h in item['href']:
                        if h['title'] == self.get_setting('play_engine').decode('utf-8'):
                            href = h['href']
                            break

                is_folder, is_playable, get_url = self.geturl_isfolder_isplay(
                    item['id'], href)

                icon = self.icon

                for league_pictures in self.league_image:
                    if league_pictures['league'] == item['league']:
                        icon = league_pictures['src']

                listing.append({
                    'label': label,
                    'art': {
                        'thumb': icon,
                        'poster': '',
                        'fanart': self.fanart,
                        'icon': icon,
                    },
                    'info': {
                        'video': {
                            # 'year': '',
                            'plot': plot,
                            'title': label,
                        }
                    },
                    'is_folder': is_folder,
                    'is_playable': is_playable,
                    'url': get_url,
                })

        except Exception as e:
            self.logd('._get_listing() ERROR', str(e))

        return listing
