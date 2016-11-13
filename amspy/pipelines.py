# -*- coding: utf-8 -*-

# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html

import json
import pandas as pd


class Top100Pipeline(object):

    def open_spider(self, spider):
        suffix = spider.category if hasattr(spider, 'category') else 'mcats'
        self.top_100_foo = open('top_100_{}.jl'.format(suffix), 'w')
        self.books_foo = open('books_{}.jl'.format(suffix), 'w')

    def close_spider(self, spider):
        self.top_100_foo.close()
        self.books_foo.close()

        def make_df(fname):
            out = '['
            with open(fname, 'r') as foi:
                out += next(foi).strip()
                for line in foi:
                    out += ', ' + line.strip()
            out += ']'
            out = json.loads(out)
            out = pd.DataFrame(out).set_index('asin')
            return out

        suffix = spider.category if hasattr(spider, 'category') else 'mcats'
        ranks = make_df('top_100_{}.jl'.format(suffix))
        books = make_df('books_{}.jl'.format(suffix))
        books['kindle_rank'] = books['rank'].map(
                lambda k: k['Paid in Kindle Store'])
        rank_comp = ranks[['catid', 'category', 'title',
                'top_100_rank']].join(books['kindle_rank'])
        rank_comp.sort_index(by='top_100_rank', inplace=True)
        rank_comp.reset_index(inplace=True)
        rank_comp.to_csv('rank_comp_{}.tsv'.format(suffix),
                         sep='\t', index=False)

    def process_item(self, item, spider):
        line = json.dumps(dict(item)) + '\n'
        if item['item_type'] == 'top_100':
            self.top_100_foo.write(line)
        elif item['item_type'] == 'book_page':
            self.books_foo.write(line)
        return item
