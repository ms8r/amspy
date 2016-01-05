import re
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
    m = re.search(r'http://www.amazon.com/[^/]+/dp/[0-9A-Z]{10}', value)
    if m:
        return m.group()


def read_titles(fo):
    """
    Reads white space separated list of ASIN, path pairs from `fo` (file like)
    and returns a list of Amazon ebook URLs. Ignores blank lines and lines
    starting with '#'.
    """
    out = []
    for r in fo:
        if not r.strip() or r.lstrip().startswith('#'):
            continue
        asin, tstring = r.strip().split()
        url = 'http://www.amazon.com/{title}/dp/{asin}'.format(title=tstring,
                asin=asin)
        out.append(url)

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
        il = BookItemLoader(item=BookItem(), response=response)
        if hasattr(self, 'catid'):
            il.add_value('catid', self.catid)
        if hasattr(self, 'category'):
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

        # also boughts:
        le = LinkExtractor(
                restrict_xpaths='//div[@class="a-carousel-viewport"]/ol/li',
                allow=re.compile(
                    r'http://www.amazon.com/[^/]*/dp/[0-9A-Z]{10}'),
                unique=True,
                process_value=process_book_links)
        ab_url_re = re.compile(
                r'http://www\.amazon\.com/(?P<title>[^/]+)/dp/'
                '(?P<asin>[0-9A-Z]{10})')
        for link in le.extract_links(response):
            rec = {}
            rec['url'] = link.url
            rec['title_str'], rec['asin'] = ab_url_re.match(link.url).groups()
            il.add_value('also_boughts', rec)

        item = il.load_item()

        yield item


class BasicBookSpider(BookParser, Spider):
    """
    Basic book page scraper. Either scrapes a single page for which

    * ASIN and title string (as used in Amazon URL) are specified as `-a`
      command line parameters (`-a asin=... -a title=...`), or
    * a file with white space separated ASIN, title string records is provided
      (via `-a infile=...`)
    """
    name = 'BasicBookSpy'

    def __init__(self, asin='', title='', infile='', *args, **kwargs):
        if asin and title:
            self.__class__.start_urls = [
                    'http://www.amazon.com/{title}/dp/{asin}'.format(
                        title=title, asin=asin)]
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
                allow=r'http://www.amazon.com/[^/]+/dp/[0-9A-Z]{10}.*',
                process_value=process_book_links),
                callback='book_parse'), )

    def __init__(self, catid='', category='', *args, **kwargs):
        """
        `catid` and `category` to be specified when calling spider via -a
        option. `catid` is the 10-digit number in the Amazon URL of a
        category's top 100 listing (used here to construct the URL). `category`
        is a decriptive string used to name output files.
        """
        self.__class__.start_urls = ['http://www.amazon.com/gp/bestsellers/'
                'digital-text/{}'.format(catid)]
        super(Top100Spider, self).__init__(*args, **kwargs)
        self.logger.debug('start_urls: %s', self.__class__.start_urls)
        self.catid = catid
        self.category = category


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


class AlsoBoughtSpider(BookParser, CrawlSpider):
    """
    Will scrape "also bought" titles for each book page in `start_urls`.
    """
    name = 'AlsoSpy'

    rules = (
            # "also bought" links
            Rule(LinkExtractor(
                restrict_xpaths='//div[@class="a-carousel-viewport"]/ol/li',
                allow=re.compile(
                    r'http://www.amazon.com/[^/]*/dp/[0-9A-Z]{10}'),
                unique=True,
                process_value=process_book_links),
                callback='book_parse'),
            )

