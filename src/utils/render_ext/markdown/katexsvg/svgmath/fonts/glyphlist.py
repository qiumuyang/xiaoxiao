import os


class GlyphList(dict):

    def __init__(self, f):
        dict.__init__(self)
        while True:
            line = f.readline()
            if len(line) == 0: break
            line = line.strip()
            if len(line) == 0 or line.startswith("#"): continue
            pair = line.split(";")
            if len(pair) != 2: continue
            glyph = pair[0].strip()
            codelist = pair[1].split()
            if len(codelist) != 1: continue  # no support for compounds
            codepoint = int(codelist[0], 16)

            if glyph in list(self.keys()):
                self[glyph].append(codepoint)
            else:
                self[glyph] = [codepoint]

    def lookup(self, glyphname):
        if glyphname in list(self.keys()): return self.get(glyphname)
        else: return defaultGlyphList.get(glyphname)


glyphListName = os.path.join(os.path.dirname(__file__), "default.glyphs")
defaultGlyphList = GlyphList(open(glyphListName, "r"))
