import re
import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from amspy.items import BookItem, BookItemLoader


def process_book_links(value):
    """
    Processes the individual book links extracted from a top 100 category
    page.
    """
    m = re.search(r'http://www.amazon.com/[^/]+/dp/[0-9A-Z]{10}', value)
    if m:
        return m.group()


class AmazonSpider(CrawlSpider):
    name = 'amspy'
    allowed_domains = ['amazon.com']
    # start_urls = ['http://www.amazon.com/gp/bestsellers/digital-text/6190484011/ref=pd_zg_hrsr_kstore_1_4']

    rules = (
            # paginator links
            Rule(LinkExtractor(
                restrict_xpaths='//div[@id="zg_paginationWrapper"]/'
                'ol[@class="zg_pagination"]',
                # allow=r'http://www.amazon.com/Best-Sellers-Kindle-Store'
                ),
                follow=True,
                callback='rank_parse'
                ),
            # book links from each paginated page
            Rule(LinkExtractor(
                restrict_xpaths='//div[@id="zg_centerListWrapper"]',
                allow=r'http://www.amazon.com/[^/]+/dp/[0-9A-Z]{10}.*',
                process_value=process_book_links),
                callback='book_parse'), )

    def __init__(self, catid='', category='', *args, **kwargs):
        self.__class__.start_urls = ['http://www.amazon.com/gp/bestsellers/'
                'digital-text/{}'.format(catid)]
        super(AmazonSpider, self).__init__(*args, **kwargs)
        self.logger.debug('start_urls: %s', self.__class__.start_urls)
        self.catid = catid
        self.category=category

    def rank_parse(self, response):
        """
        Parses a "Top 100" overview page and scrapes title segement of the URL,
        ASIN and rank into item
        """
        top = response.xpath('//div[@id="zg_centerListWrapper"]/'
                             'div[@class="zg_itemImmersion"]')
        for t in top:
            il = BookItemLoader(item=BookItem(), response=response)
            il.add_value('catid', self.catid)
            il.add_value('category', self.category)
            il.add_value('item_type', 'top_100')
            # il.add_xpath('top_100_rank',
            #        './/span[@class="zg_rankNumber"]/text()')
            v = t.xpath('.//span[@class="zg_rankNumber"]/text()').extract()
            il.add_value('top_100_rank', v)
            v = t.xpath('.//div[@class="zg_title"]/a/text()').extract()
            il.add_value('title', v)
            v = t.xpath('.//div[@class="zg_title"]/a/@href').re_first(
                    r'\s*http://www.amazon.com/[^/]*/dp/([A-Z0-9]{10})')
            il.add_value('asin', v)

            item = il.load_item()
            yield item

    def book_parse(self, response):
        """
        Parses individual book pages into AmspyItem
        """
        #map Product Details tags to item labels:
        prodDetMap = {
                'File Size': 'file_size',
                'Print Length': 'print_length',
                'Publisher': 'publisher',
                'Publication Date': 'pub_date',
                'ASIN': 'asin',
        }
        il = BookItemLoader(item=BookItem(), response=response)
        il.add_value('catid', self.catid)
        il.add_value('category', self.category)
        il.add_value('item_type', 'book_page')
        il.add_xpath('title', '//span[@id="productTitle"]/text()')
        v = response.xpath( '//span[@id="acrPopover"]/@title').re(
                r'([0-5][^\s]+)\s+out')
        il.add_value('avrg_rating', v)
        v = response.xpath('//span[@id="acrCustomerReviewText"]/text()').re(
                r'([0-9]+)\s+customer')
        il.add_value('num_reviews', v)
        # il.add_xpath('blurb', '//div[@id="bookDescription_feature_div"]'
        #        '/noscript/div/text()')

        # price data:
        priceSel = response.xpath('//div[@id="tmmSwatches"]/ul/li')
        for sel in priceSel:
            fmt = sel.xpath(
                    './/span[@class="a-button-inner"]/a/span')[0].re(
                    r'<span>([^<]*)</span>')[0]
            if fmt != u'Kindle':
                continue
            # price = sel.xpath('.//span[@class="a-button-inner"]'
            #        '/a/span')[1].xpath('span').re(
            #         r'<span[^>]*>[^0-9]*([0-9,\.]*)')[0]
            price = sel.xpath('.//span[@class="a-button-inner"]'
                    '/a/span')[1].xpath('span/text()').extract()[0]
            il.add_value('price', price)
            break


        # Product Details
        prodDetSel = response.xpath(
                '//table[@id="productDetailsTable"]'
                '//div[@class="content"]/ul')
        for sel in prodDetSel.xpath('li'):
            if sel.xpath('@id').extract() == 'SalesRank':
                continue
            s = sel.re(r'\s*<li><b>\s*([^:]+):\s*</b>\s*([^<]*)<')
            if s:
                k, v = s
            else:
                continue
            if k in prodDetMap:
                il.add_value(prodDetMap[k], v)
        # now Sales Rank (rc -> (rank, category):
        rc = prodDetSel.xpath('li[@id="SalesRank"]').re(
                r'<b>Amazon Best Sellers Rank:</b>\s*#([^\s]*)\s+([^(\Z]*)')
        il.add_value('rank', rc)
        # category ranks:
        for sel in prodDetSel.xpath('li[@id="SalesRank"]/ul/li'):
            r = sel.xpath('span[@class="zg_hrsr_rank"]/text()').re_first(
                    r'\s*#?([0-9]+)')
            category = sel.xpath(
                    'span[@class="zg_hrsr_ladder"]/a/text()').extract()
            category += sel.xpath(
                    'span[@class="zg_hrsr_ladder"]/b/a/text()').extract()
            il.add_value('rank', (r, ' > '.join(category)))

        item = il.load_item()

        return item


