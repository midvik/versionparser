from abc import ABCMeta, abstractmethod
__author__ = 'midvikus'


class AbstractParser(metaclass=ABCMeta):

    @abstractmethod
    def GetSectionList(self):
        pass

    @abstractmethod
    def GetSection(self, section_url):
        pass

    @abstractmethod
    def GetProgram(self):
        pass