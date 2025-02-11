"""Configuration for MathML-to-SVG formatter."""

import sys
from xml import sax

from .fonts.afm import AFMMetric
from .fonts.metric import FontFormatError
from .fonts.ttf import TTFMetric
from .logging import logger


class MathConfig(sax.ContentHandler):
    """Configuration for MathML-to-SVG formatter.

    Implements SAX ContentHandler for ease of reading from file."""

    def __init__(self, configfile):
        self.verbose = False
        self.debug = []
        self.currentFamily = None
        self.fonts = {}
        self.variants = {}
        self.defaults = {}
        self.opstyles = {}
        self.fallbackFamilies = []

        # Parse config file
        try:
            parser = sax.make_parser()
            parser.setContentHandler(self)
            parser.setFeature(sax.handler.feature_namespaces, 0)
            parser.parse(configfile)
        except sax.SAXException as xcpt:
            print("Error parsing configuration file ", configfile, ": ",
                  xcpt.getMessage())
            sys.exit(1)

    def startElement(self, name, attributes):
        if name == "config":
            self.verbose = (attributes.get("verbose") == "true")
            self.debug = (attributes.get("debug", "")).replace(",",
                                                               " ").split()

        elif name == "defaults":
            self.defaults.update(attributes)

        elif name == "fallback":
            familyattr = attributes.get("family", "")
            self.fallbackFamilies = [
                " ".join(x.split()) for x in familyattr.split(",")
            ]

        elif name == "family":
            self.currentFamily = attributes.get("name", "")
            self.currentFamily = "".join(self.currentFamily.lower().split())

        elif name == "font":
            weight = attributes.get("weight", "normal")
            style = attributes.get("style", "normal")
            fontfullname = self.currentFamily
            if weight != "normal":
                fontfullname += " " + weight
            if style != "normal":
                fontfullname += " " + style
            fontpath = "<unbound>"
            try:
                if "afm" in list(attributes.keys()):
                    fontpath = attributes.get("afm")
                    metric = AFMMetric(fontpath, attributes.get("glyph-list"),
                                       sys.stderr)
                elif "ttf" in list(attributes.keys()):
                    fontpath = attributes.get("ttf")
                    metric = TTFMetric(fontpath, sys.stderr)
                else:
                    # sys.stderr.write(
                    #     "Bad record in configuration file: font is neither AFM nor TTF\n"
                    # )
                    # sys.stderr.write("Font entry for '%s' ignored\n" %
                    #                  fontfullname)
                    logger.warning(
                        "Bad record in configuration file: font is neither AFM nor TTF"
                    )
                    logger.warning("Font entry for '%s' ignored", fontfullname)
                    return
            except FontFormatError as err:
                # sys.stderr.write(
                #     "Invalid or unsupported file format in '%s': %s\n" %
                #     (fontpath, err.message))
                # sys.stderr.write("Font entry for '%s' ignored\n" %
                #                  fontfullname)
                logger.warning(
                    "Invalid or unsupported file format in '%s': %s", fontpath,
                    err.message)
                logger.warning("Font entry for '%s' ignored", fontfullname)
                return
            except IOError:
                message = sys.exc_info()[1]
                # sys.stderr.write("I/O error reading font file '%s': %s\n" %
                #                  (fontpath, str(message)))
                # sys.stderr.write("Font entry for '%s' ignored\n" %
                #                  fontfullname)
                logger.warning("I/O error reading font file '%s': %s",
                               fontpath, str(message))
                logger.warning("Font entry for '%s' ignored", fontfullname)
                return

            self.fonts[weight + " " + style + " " +
                       self.currentFamily] = metric

        elif name == "mathvariant":
            variantattr = attributes.get("name")
            familyattr = attributes.get("family", "")
            splitFamily = [" ".join(x.split()) for x in familyattr.split(",")]
            weightattr = attributes.get("weight", "normal")
            styleattr = attributes.get("style", "normal")
            self.variants[variantattr] = (weightattr, styleattr, splitFamily)

        elif name == "operator-style":
            opname = attributes.get("operator")
            if opname:
                styling = {}
                styling.update(attributes)
                del styling["operator"]
                self.opstyles[opname] = styling
            else:
                # sys.stderr.write(
                #     "Bad record in configuration file: operator-style with no operator attribute\n"
                # )
                logger.warning(
                    "Bad record in configuration file: operator-style with no operator attribute"
                )

    def endElement(self, name):
        if name == "family":
            self.currentFamily = None

    def findfont(self, weight, style, family):
        """Finds a metric for family+weight+style."""
        weight = (weight or "normal").strip()
        style = (style or "normal").strip()
        family = "".join((family or "").lower().split())

        for w in [weight, "normal"]:
            for s in [style, "normal"]:
                metric = self.fonts.get(w + " " + s + " " + family)
                if metric: return metric
        return None


def main():
    if len(sys.argv) == 1:
        config = MathConfig(None)
    else:
        config = MathConfig(sys.argv[1])

    print("Options:  verbose =", config.verbose, " debug =", config.debug)
    print("Fonts:")
    for (font, metric) in list(config.fonts.items()):
        print("    ", font, "-->", metric.fontname)
    print("Math variants:")
    for (variant, value) in list(config.variants.items()):
        print("    ", variant, "-->", value)
    print("Defaults:")
    for (attr, value) in list(config.defaults.items()):
        print("    ", attr, "=", value)
    print("Operator styling:")
    for (opname, value) in list(config.opstyles.items()):
        print("    ", repr(opname), ":", value)
    print("Fallback font families:", config.fallbackFamilies)


if __name__ == "__main__": main()
