import re
try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

import scrapy
from scrapy.http import Request
from scrapy.spiders import Spider, CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from amspy.items import BookItem, BookItemLoader
import amspy.pipelines


def process_book_links(value):
    """
    Filters to book links and strips off anything after asin.
    """
    m = re.search(r'http[s]?://www.amazon.com/[^/]+/dp/[0-9A-Z]{10}', value)
    if m:
        return m.group()


def read_titles(fo):
    """
    Reads list of ASIN from `fo` (file like) and returns a list of Amazon ebook
    URLs. Ignores blank lines and lines starting with '#'.
    """
    out = ['https://www.amazon.com/dp/{}'.format(asin.strip()) for asin in fo
            if asin.strip() and not asin.lstrip().startswith('#')]

    return out


class BookParser(object):
    """
    Mixin class that provides `book_parse` method for parsing an Amazon eBook
    product page.
    """

    def book_parse(self, response):
        """
        Parses individual book pages into BookItem
        """
        #map Product Details tags to item labels:
        prodDetMap = {
                'File Size': 'file_size',
                'Print Length': 'print_length',
                'Publisher': 'publisher',
                'Publication Date': 'pub_date',
                'ASIN': 'asin',
        }
        book_url_re = re.compile(
                r'http[s]?://www\.amazon\.com/(?P<title>[^/]+)/dp/'
                '(?P<asin>[0-9A-Z]{10})')
        il = BookItemLoader(item=BookItem(), response=response)
        if hasattr(self, 'catid'):
            il.add_value('catid', self.catid)
        if hasattr(self, 'category'):
            il.add_value('category', self.category)
        il.add_value('item_type', 'book_page')
        il.add_value('url', response.url)
        il.add_xpath('title', '//span[@id="ebooksProductTitle"]/text()')
        il.add_xpath('authors', '//div[@id="byline"]/span[contains(@class,'
                '"author")]//a/text()')
        v = response.xpath( '//span[@id="acrPopover"]/@title').re(
                r'([0-5][^\s]+)\s+out')
        il.add_value('avrg_rating', v)
        v = response.xpath('//span[@id="acrCustomerReviewText"]/text()').re(
                r'([0-9]+)\s+customer')
        il.add_value('num_reviews', v)
        # il.add_xpath('blurb', '//div[@id="bookDescription_feature_div"]'
        #        '/noscript/div/text()')

        # price data:
        price = response.xpath('//div[@id="tmmSwatches"]').re_first(
                r'\s*(\d+\.\d\d).*to buy')
        il.add_value('price', price)
        # priceSel = response.xpath('//div[@id="tmmSwatches"]/ul/li')
        # for sel in priceSel:
        #    fmt = sel.xpath(
        #            './/span[@class="a-button-inner"]/a/span')[0].re(
        #            r'<span>([^<]*)</span>')[0]
        #    if fmt != u'Kindle':
        #        continue
            # price = sel.xpath('.//span[@class="a-button-inner"]'
            #        '/a/span')[1].xpath('span').re(
            #         r'<span[^>]*>[^0-9]*([0-9,\.]*)')[0]
        #    price = sel.xpath('.//span[@class="a-button-inner"]'
        #            '/a/span')[1].xpath('span/text()').extract()[0]
        #    il.add_value('price', price)
        #    break

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

        # also boughts:
        le = LinkExtractor(
                restrict_xpaths='//div[@class="a-carousel-viewport"]/ol/li',
                allow=re.compile(
                    r'http[s]?://www.amazon.com/[^/]*/dp/[0-9A-Z]{10}'),
                unique=True,
                process_value=process_book_links)
        for link in le.extract_links(response):
            rec = {}
            rec['url'] = link.url
            rec['title_str'], rec['asin'] = book_url_re.match(link.url).groups()
            il.add_value('also_boughts', rec)

        item = il.load_item()

        return item


class BasicBookSpider(BookParser, Spider):
    """
    Basic book page scraper. Either scrapes a single page for which

    * ASIN specified as `-a` command line parameter (`-a asin=... ) or
    * a file with a list of ASINs, provided (via `-a infile=...`)
    """
    name = 'BasicBookSpy'

    def __init__(self, asin='', infile='', *args, **kwargs):
        if asin:
            self.__class__.start_urls = [
                    'https://www.amazon.com/dp/{}'.format(asin)]
        else:
            with open(infile, 'r') as foi:
                self.__class__.start_urls = read_titles(foi)
        super(BasicBookSpider, self).__init__(*args, **kwargs)
        self.logger.debug('start_urls: %s', self.__class__.start_urls)

    # overwrite `make_requests_from_url(url)` to specify `book_parse` as
    # callback:
    def make_requests_from_url(self, url):
        return Request(url, self.book_parse)


class Top100Spider(BookParser, CrawlSpider):
    """
    Crawls top 100 books for a given catergory and retrieves their overall
    ranks. Arguments to be specified via -a command line option:

        catid:      10-digit category identifier

        category:   descriptive text for category (used to name output files)

    """
    name = 'Top100Spy'

    custom_settings = {
            'ITEM_PIPELINES': {'amspy.pipelines.Top100Pipeline': 300}}

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
                allow=r'(http[s]?://www.amazon.com)?/[^/]+/dp/[0-9A-Z]{10}.*',
                process_value=process_book_links),
                callback='book_parse'), )

    def __init__(self, catid='', category='', infile='', *args, **kwargs):
        """
        Either `catid` and `category` or `infile` need to be specified when
        calling spider via -a option. `catid` is the 10-digit number in the
        Amazon URL of a category's top 100 listing (used here to construct the
        URL). `category` is a decriptive string used to name output files.
        `infile` is is a whitespace separated list of category decsriptors and
        catids.
        """
        top100_cat_url = 'https://www.amazon.com/gp/bestsellers/digital-text/{}'

        if catid and category:
            self.__class__.start_urls = [top100_cat_url.format(catid)]
            self.catid = catid
            self.category = category
        else:
            with open(infile, 'r') as foi:
                self.__class__.start_urls = [
                        top100_cat_url.format(rec.split()[1]) for rec in foi]

        super(Top100Spider, self).__init__(*args, **kwargs)
        self.logger.debug('start_urls: %s', self.__class__.start_urls)


    def rank_parse(self, response):
        """
        Parses a "Top 100" overview page and scrapes title segement of the URL,
        ASIN and rank into item
        """
        category = response.xpath(
                '//span[@class="category"]/text()').extract_first()
        url_path = urlparse(response.url).path
        catid = re.search(r'/([0-9]+)(/|\Z)', url_path).group(1)
        top = response.xpath('//div[@id="zg_centerListWrapper"]/'
                             'div[@class="zg_itemImmersion"]')
        for t in top:
            il = BookItemLoader(item=BookItem(), response=response)
            il.add_value('catid', catid)
            il.add_value('category', category)
            il.add_value('item_type', 'top_100')
            # il.add_xpath('top_100_rank',
            #        './/span[@class="zg_rankNumber"]/text()')
            v = t.xpath('.//span[@class="zg_rankNumber"]/text()').extract()
            il.add_value('top_100_rank', v)
            v = t.xpath('.//div[@class="zg_title"]/a/text()').extract()
            il.add_value('title', v)
            v = t.xpath('.//div[@class="zg_title"]/a/@href').re_first(
                    r'\s*http[s]?://www.amazon.com/[^/]*/dp/([A-Z0-9]{10})')
            il.add_value('asin', v)

            item = il.load_item()
            yield item


# class AlsoBoughtSpider(BookParser, CrawlSpider):
class AlsoBoughtSpider(CrawlSpider, BookParser):
    """
    Will scrape "also bought" titles for each book page in `start_urls`.

    `start_urls` are determined from

    * ASIN  specified as `-a` command line parameters (`-a asin=...`), or
    * a file with list of ASINs, provided (via `-a infile=...`)

    Maximum depth to with to follow also-boughts should be defined by
    `-s DEPTH_LIMIT=<number> when calling the spider (otherwise DEPTH_LIMIT value
    in settings.py will be applied).
    """
    name = 'AlsoSpy'

    rules = (
            # "also bought" links
            Rule(LinkExtractor(
                restrict_xpaths='//div[@class="a-carousel-viewport"]/ol/li',
                allow=re.compile(
                   r'http[s]?://www.amazon.com/[^/]*/dp/[0-9A-Z]{10}'),
                unique=True,
                process_value=process_book_links,
                ),
                follow=True,
                callback='book_parse',
                ),
            )

    def __init__(self, asin='', infile='', *args, **kwargs):
        if asin:
            self.__class__.start_urls = [
                    'https://www.amazon.com/dp/{}'.format(asin)]
        else:
            with open(infile, 'r') as foi:
                self.__class__.start_urls = read_titles(foi)
        super(AlsoBoughtSpider, self).__init__(*args, **kwargs)
        self.logger.debug('start_urls: %s', self.__class__.start_urls)

    # overwrite `make_requests_from_url(url)` to specify `book_parse` as
    # callback:
    # def make_requests_from_url(self, url):
    #    return Request(url, self.book_parse)

    # overwrite `parse_start_url`:
    def pasre_start_url(self, repsonse):
       return self.book_parse(self, response)
