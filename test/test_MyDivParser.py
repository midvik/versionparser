import unittest
from Parser.MyDivParser import MyDivParser
__author__ = 'midvikus'


class TestMyDivParserTestCase(unittest.TestCase):
    def setUp(self):
        self.parser = MyDivParser('http://soft.mydiv.net/win/')

    def test_get_section_list(self):
        self.assertTrue(len(self.parser.GetSectionList()))

    def test_get_section(self):
        self.assertTrue(len(self.parser.GetSection('http://soft.mydiv.net/win/cname7/')))

if __name__ == '__main__':
    unittest.main()
