'''
nrkb_fctrl.py

peter hung | phung@post.harvard.edu
2013-3-23 | 3-23

implements a very simple crawler that grabs boards from puzzle-nurikabe.com and saves
them using the file control system
'''


from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request
from nrkb.items import NrkbItem
from math import sqrt
import string
import nrkb_fctrl

class NrkbSpider(BaseSpider):
  name = "nrkb"
  allowed_domains = ["puzzle-nurikabe.com"]
  start_urls = [
       "http://www.puzzle-nurikabe.com/?size=1"
  ]

  def parse(self, response):
    hxs = HtmlXPathSelector(response)

    # grab the table, turn it into ascii
    extracted = hxs.select('//table[@id="NurikabeTable"]').extract()
    text = extracted[0].encode('ascii', 'ignore')

    # split by td, then drop the first one, which was the header of the table itself
    separated = text.split('<td>')
    separated.pop(0)

    # takes a string, chops of everything after <, and attempts to convert it to an int
    def convert(elt):
      stop = elt.find('<')
      chopped = elt[:stop]
      if len(chopped):
        try: 
          return int(chopped)
        except:
          return 0
      else:
        return 0
    def chunks(lst, n):
      chunks = []
      for i in range(0, len(lst), n):
        chunks.append(lst[i:i+n])
      return chunks

    converted = map(convert, separated)

    size = int(sqrt(len(converted)))
    if size ** 2 != len(converted):
      return None

    board = chunks(converted, size)
    item = NrkbItem()    
    item['board'] = board
    nrkb_fctrl.save_board(board)
    return item

  '''
  def parse(self, response):
    hxs = HtmlXPathSelector(response)
    sites = hxs.select('//ul/li')
    items = []
    for site in sites:
      item = NrkbItem()
      item['title'] = site.select('a/text()').extract()
      item['link'] = site.select('a/@href').extract()
      item['desc'] = site.select('text()').extract()
      items.append(item)
  '''