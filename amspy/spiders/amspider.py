import re
import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from amspy.items import AmspyItem, AmspyItemLoader


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
    start_urls = ['http://www.amazon.com/gp/bestsellers/digital-text/6190484011/ref=pd_zg_hrsr_kstore_1_4']

    rules = (
            # paginator links
            Rule(LinkExtractor(
                restrict_xpaths='//div[@id="zg_paginationWrapper"]/'
                'ol[@class="zg_pagination"]',
                allow=r'http://www.amazon.com/Best-Sellers-Kindle-Store')),
            # book links from each paginated page
            Rule(LinkExtractor(
                restrict_xpaths='//div[@id="zg_centerListWrapper"]',
                allow=r'http://www.amazon.com/[^/]+/dp/[0-9A-Z]{10}.*',
                process_value=process_book_links),
                callback='book_parse'), )

    def __init__(self, start=None, *args, **kwargs):
        super(AmazonSpider, self).__init__(*args, **kwargs)
        # self.__class__.start_urls = [start]
        # print self.__class__.start_urls

    def dummy(self, req):
        print req

    def book_parse(self, response):
        #map Product Details tags to item labels:
        prodDetMap = {
                'File Size': 'file_size',
                'Print Length': 'print_length',
                'Publisher': 'publisher',
                'Publication Date': 'pub_date',
                'ASIN': 'asin',
        }
        il = AmspyItemLoader(item=AmspyItem(), response=response)
        il.add_xpath('title', '//span[@id="productTitle"]/text()')
        v = response.xpath( '//span[@id="acrPopover"]/@title').re(
                r'([0-5][^\s]+)\s+out')
        il.add_value('avrg_rating', v)
        v = response.xpath('//span[@id="acrCustomerReviewText"]/text()').re(
                r'([0-9]+)\s+customer')
        il.add_value('num_reviews', v)
        il.add_xpath('blurb', '//div[@id="bookDescription_feature_div"]'
                '/noscript/div/text()')

        # price data:
        priceSel = response.xpath('//div[@id="tmmSwatches"]/ul/li')
        for sel in priceSel:
            fmt = sel.xpath(
                    './/span[@class="a-button-inner"]/a/span')[0].re(
                    r'<span>([^<]*)</span>')[0]
            price = sel.xpath('.//span[@class="a-button-inner"]'
                    '/a/span')[1].xpath('span').re(
                    r'<span[^>]*>[^0-9]*([0-9,\.]*)')[0]
            il.add_value('price', [fmt, price])

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
        #for key in item:
        #    print "%s: %s" % (key, item[key])

        return item


