import scrapy
from amspy.items import AmspyItem, AmspyItemLoader


class AmazonSpider(scrapy.Spider):
    name = 'amspy'
    allowed_domains = ['amazon.com']
    start_urls = [
            'http://www.amazon.com/gp/product/B015UPORGC',
            # 'http://www.amazon.com/Desert-Hunt-Wolves-Twin-Ranch-ebook/dp/'
            # 'B010W9HEUW',
            'http://www.amazon.com/Pacific-Crossing-Notes-Sailors-Coconut-ebook'
            '/dp/B00RAD0W30']

    def parse(self, response):
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
