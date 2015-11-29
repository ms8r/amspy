# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

import scrapy
from scrapy.loader import ItemLoader
from scrapy.loader.processors import Identity, TakeFirst, Join
from scrapy.loader.processors import Compose, MapCompose


class BookItem(scrapy.Item):

    # use `item_type` to distinguish between individual book pages and top-100
    # listings
    category = scrapy.Field()
    catid = scrapy.Field()
    item_type = scrapy.Field()
    asin = scrapy.Field()
    title = scrapy.Field()
    authors = scrapy.Field()
    price = scrapy.Field()
    num_reviews = scrapy.Field()
    avrg_rating = scrapy.Field()
    blurb = scrapy.Field()
    file_size = scrapy.Field()
    print_length = scrapy.Field()
    publisher = scrapy.Field()
    pub_date = scrapy.Field()
    top_100_rank = scrapy.Field()
    rank = scrapy.Field()


class BookItemLoader(ItemLoader):

    default_output_processor = TakeFirst()

    def price_scrub(price):
        # fmt, price = fmt_price
        return float(price.replace(u'$', u'').replace(u',', u''))

    def rank_scrub(rank_cat):
        rank, cat = rank_cat
        return (cat.strip(), int(rank.replace(u',', u'')))

    def pairs2dict(pairs):
        """
        Turns a list with consequtive key, value entries into a dict.
        """
        return dict(zip(pairs[::2], pairs[1::2]))

    authors_out = Identity()
    price_in = MapCompose(float)
    num_reviews_in = MapCompose(lambda k: k.replace(u',', u''), int)
    avrg_rating_in = MapCompose(float)
    blurb_in = MapCompose(lambda k: k.replace(u'\r', u'\n'))
    blurb_out = Join(separator=u'')
    file_size_in = MapCompose(lambda k: k.replace(u'KB', u'').strip(),
                              lambda k: k.replace(u',', u''),
                              int)
    print_length_in = MapCompose(lambda k: k.replace(u'pages', u'').strip(),
                                 lambda k: k.replace(u',', u''),
                                 int)
    price_in = MapCompose(price_scrub)
    rank_in = Compose(rank_scrub)
    rank_out = Compose(pairs2dict)
    top_100_rank_in = Compose(lambda k: int(k[0].strip('.')))
