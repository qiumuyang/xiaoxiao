from .mathhandler import MathNS
from .tools.saxtools import ContentFilter


class MathFilter(ContentFilter):

    def __init__(self, out, mathout):
        ContentFilter.__init__(self, out)
        self.plainOutput = out
        self.mathOutput = mathout
        self.depth = 0

    # ContentHandler methods
    def setDocumentLocator(self, locator):
        self.plainOutput.setDocumentLocator(locator)
        self.mathOutput.setDocumentLocator(locator)

    def startElementNS(self, elementName, qName, attrs):
        if self.depth == 0:
            (namespace, localName) = elementName
            if namespace == MathNS:
                self.output = self.mathOutput
                self.depth = 1
        else:
            self.depth += 1
        ContentFilter.startElementNS(self, elementName, qName, attrs)

    def endElementNS(self, elementName, qName):
        ContentFilter.endElementNS(self, elementName, qName)
        if self.depth > 0:
            self.depth -= 1
            if self.depth == 0:
                self.output = self.plainOutput
