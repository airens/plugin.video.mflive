# -*- coding: utf-8 -*-

from resources.lib.mflive import MFLive

plugin = MFLive()


@plugin.action()
def root():
    return plugin.create_listing_()


@plugin.action()
def links(params):
    return plugin.get_links(params)


@plugin.action()
def play(params):
    return plugin.play(params)


@plugin.action()
def reset():
    return plugin.reset()


@plugin.action()
def reset_inter():
    return plugin.create_listing_()


@plugin.action()
def select_matches(params):
    plugin.select_matches(params)


if __name__ == '__main__':
    plugin.run()
