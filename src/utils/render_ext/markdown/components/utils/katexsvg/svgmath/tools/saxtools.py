"""Miscellaneous SAX-related utilities used in SVGMath"""

import io
from xml.sax import handler


def escape(data):
    """Escape &, <, and > in a string of data."""
    data = str(data)  # Ensure string
    return data.replace("&", "&amp;").replace(">", "&gt;").replace("<", "&lt;")


def quoteattr(data):
    """Escape and quote an attribute value."""
    data = escape(data)
    if '"' in data:
        if "'" in data:
            data = '"%s"' % data.replace('"', "&quot;")
        else:
            data = "'%s'" % data
    else:
        data = '"%s"' % data
    return data


class XMLGenerator(handler.ContentHandler):
    """Clone of xml.sax.saxutils.XMLGenerator with fixes for Python 3."""

    def __init__(self, out, encoding="iso-8859-1"):
        handler.ContentHandler.__init__(self)
        self._encoding = encoding

        # Ensure `out` is a binary stream and wrap it correctly
        if isinstance(out, io.TextIOBase):
            self._out = out  # Already a text stream
        else:
            self._out = io.TextIOWrapper(out,
                                         encoding=encoding,
                                         errors="xmlcharrefreplace")

        self._ns_contexts = [{}]
        self._current_context = self._ns_contexts[-1]
        self._undeclared_ns_maps = []
        self._starttag_pending = False

    def _write(self, text):
        self._out.write(str(text))

    def _qname(self, name):
        if name[0]:
            prefix = self._current_context[name[0]]
            if prefix:
                return f"{prefix}:{name[1]}"
        return name[1]

    def _flush_starttag(self):
        if self._starttag_pending:
            self._write(">")
            self._starttag_pending = False

    # ContentHandler methods
    def startDocument(self):
        self._write('<?xml version="1.0" encoding="%s"?>\n' % self._encoding)

    def endDocument(self):
        pass  # `reset()` removed

    def startPrefixMapping(self, prefix, uri):
        self._ns_contexts.append(self._current_context.copy())
        self._current_context[uri] = prefix
        self._undeclared_ns_maps.append((prefix, uri))

    def endPrefixMapping(self, prefix):
        self._current_context = self._ns_contexts[-1]
        del self._ns_contexts[-1]

    def startElement(self, name, attrs):
        self._flush_starttag()
        self._write("<%s" % name)
        for name, value in attrs.items():
            self._write(" %s=%s" % (name, quoteattr(value)))
        self._starttag_pending = True

    def endElement(self, name):
        if self._starttag_pending:
            self._write("/>")
            self._starttag_pending = False
        else:
            self._write("</%s>" % name)

    def startElementNS(self, name, qname, attrs):
        qattrs = {
            self._qname(attname): attvalue
            for attname, attvalue in attrs.items()
        }
        for prefix, uri in self._undeclared_ns_maps:
            qattrs[f"xmlns:{prefix}" if prefix else "xmlns"] = uri
        self._undeclared_ns_maps = []
        self.startElement(self._qname(name), qattrs)

    def endElementNS(self, name, qname):
        self.endElement(self._qname(name))

    def characters(self, content):
        self._flush_starttag()
        self._write(escape(content))

    def ignorableWhitespace(self, content):
        self.characters(content)

    def processingInstruction(self, target, data):
        self._flush_starttag()
        self._write("<?%s %s?>" % (target, data))


class ContentFilter(handler.ContentHandler):
    """Implementation of ContentHandler that filters XML output."""

    def __init__(self, out):
        handler.ContentHandler.__init__(self)
        self.output = out

    # ContentHandler methods
    def startDocument(self):
        self.output.startDocument()

    def endDocument(self):
        self.output.endDocument()

    def startPrefixMapping(self, prefix, uri):
        self.output.startPrefixMapping(prefix, uri)

    def endPrefixMapping(self, prefix):
        self.output.endPrefixMapping(prefix)

    def startElement(self, elementName, attrs):
        self.output.startElement(elementName, attrs)

    def endElement(self, elementName):
        self.output.endElement(elementName)

    def startElementNS(self, elementName, qName, attrs):
        self.output.startElementNS(elementName, qName, attrs)

    def endElementNS(self, elementName, qName):
        self.output.endElementNS(elementName, qName)

    def characters(self, content):
        self.output.characters(content)

    def ignorableWhitespace(self, content):
        self.output.ignorableWhitespace(content)

    def processingInstruction(self, target, data):
        self.output.processingInstruction(target, data)
