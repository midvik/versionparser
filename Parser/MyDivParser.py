from Parser import AbstractParser
from pyquery import PyQuery
__author__ = 'midvikus'

MYDIV_URL = 'http://soft.mydiv.net'


class MyDivParser(object):

    def __init__(self, main_section):
        self.main_section = main_section

    def GetSectionList(self):
        pq = PyQuery(url=self.main_section)
        return [(i.text(), MYDIV_URL + i.attr('href')) for i in pq('.list.t5').items('a')]

    def GetSection(self, section_url):
        result = []
        result += self.__parse_page(section_url)

        next_pages = self.__get_next_pages(section_url)
        while next_pages:
            next_page = next_pages[0]
            next_page_url = MYDIV_URL + next_page.attr('href')
            result += self.__parse_page(next_page_url)
            next_pages = self.__get_next_pages(next_page_url)
        return result

    @staticmethod
    def __get_next_pages(page_url):
        page_query = PyQuery(url=page_url)
        return [page for page in page_query('.apage').nextAll().items('a')]

    @staticmethod
    def __parse_page(page_url):
        pq = PyQuery(url=page_url)
        return [(prog.text(), MYDIV_URL + prog.attr('href'), prog.children('.version').text()) for prog in pq('.itemname').items()]

    def GetProgram(self):
        pass