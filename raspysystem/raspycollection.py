# -*- coding: utf-8 -*-

class RasPyCollection(object):
    def __init__(self, collection):
        self._items = list(collection)

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __getitem__(self, key):
        return self._items[key]

    def __contains__(self, item):
        return item in self._items

    def get_items(self):
        return self._items
