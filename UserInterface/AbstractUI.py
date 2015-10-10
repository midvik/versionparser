from abc import ABCMeta, abstractmethod
__author__ = 'midvikus'


class AbstractUI(metaclass=ABCMeta):

    @abstractmethod
    def init(self):
        pass

    @abstractmethod
    def start(self):
        pass
