# AmSPy &ndash; Crawler and Scraper for Amazon eBook Listings

**AmSPy** is a Python crawler and scraper for Amazon eBook listings. It is built on top of the [Scrapy](https://scrapy.org/) framework and provides three simple spiders:

* **BasicBookSpy**: Basic book page scraper. Either scrapes a single page for which a single ASIN is specified as a command line parameter (`-a asin=...`) or a list of ASINs is provided in a text file (via `-a infile=...`)

* **Top100Spy**: Crawls top 100 books for a given Amazon catergory and retrieves their overall Kindle eBook sales ranks (plus other book data retrieved by `BasicBookSpy`. Either `catid` and `category` or an `infile` need to be specified when calling the spider via `-a` command line option. `catid` is the 9-10 digit number in the Amazon URL of a category's top 100 listing (used here to construct the URL). `category` is a decriptive string used to name output files. To crawl multiple categories a whitespace separated list of category decsriptors and catids can be provided via  `-a infile=...`. Uses a custom pipeline `Top100Pipeline` in `amspy/pipelines.py` to post-process and combine data from Top 100 listing and individual book pages.

* **AlsoSpy**: Will scrape "also bought" titles for each book page in `start_urls`. `start_urls` are determined from either an ASIN  specified as `-a` command line parameters (`-a asin=...`) or from a file with a list of ASINs, provided (via `-a infile=...`). Maximum depth to with to follow also-boughts should be defined by `-s DEPTH_LIMIT=<number>` when calling the spider (otherwise DEPTH_LIMIT value in settings.py will be applied).

The data scraped from each book listing contains the following:

    {'also_boughts': [{'asin': 'B00XEWHNYM',
                       'title_str': 'Sailing-Impunity-Adventure-South-Pacific-ebook',
                       'url': 'https://www.amazon.com/Sailing-Impunity-Adventure-South-Pacific-ebook/dp/B00XEWHNYM'},
                      {'asin': 'B01BHW58LU',
                       'title_str': 'This-hemispheres-people-Jackie-Parry-ebook',
                       'url': 'https://www.amazon.com/This-hemispheres-people-Jackie-Parry-ebook/dp/B01BHW58LU'},
                      {'asin': 'B012BYBDD0',
                       'title_str': 'Get-Real-Gone-Become-Forever-ebook',
                       'url': 'https://www.amazon.com/Get-Real-Gone-Become-Forever-ebook/dp/B012BYBDD0'},
                      {'asin': 'B01G9Y2O2M',
                       'title_str': 'Storm-Proofing-your-Boat-Gear-ebook',
                       'url': 'https://www.amazon.com/Storm-Proofing-your-Boat-Gear-ebook/dp/B01G9Y2O2M'},
                      {'asin': 'B011PPNIRA',
                       'title_str': 'Around-World-Six-Years-circumnavigation-ebook',
                       'url': 'https://www.amazon.com/Around-World-Six-Years-circumnavigation-ebook/dp/B011PPNIRA'},
                      {'asin': 'B00U01QTIQ',
                       'title_str': 'Stress-free-Sailing-Single-Short-handed-Techniques-ebook',
                       'url': 'https://www.amazon.com/Stress-free-Sailing-Single-Short-handed-Techniques-ebook/dp/B00U01QTIQ'}],
     'asin': u'B00RAD0W30',
     'authors': [u'Nadine Slavinski', u'Markus Schweitzer'],
     'avrg_rating': 4.7,
     'file_size': 12719,
     'item_type': 'book_page',
     'num_reviews': 34,
     'price': 6.99,
     'print_length': 389,
     'pub_date': u'February 10, 2015',
     'rank': {u'Books > Travel > Australia & South Pacific > General': 341,
              u'Kindle Store > Kindle eBooks > Nonfiction > Sports > Water Sports > Sailing': 206,
              u'Kindle Store > Kindle eBooks > Nonfiction > Travel > Australia & South Pacific': 144,
              u'Paid in Kindle Store': 416903},
     'url': 'https://www.amazon.com/Pacific-Crossing-Notes-Sailors-Coconut-ebook/dp/B00RAD0W30'}

Currently runs under Python 2.7. Requires [Scrapy](https://scrapy.org/) and [Pandas](http://pandas.pydata.org/). MIT license. Use responsibly &ndash; complying with Amazon's [Conditions of Use](https://www.amazon.com/gp/help/customer/display.html/?nodeId=508088) is your responsibility.
