import re

INJ = re.compile(r"(ignore|disregard|forget|override|bypass)[^.]*?(budget|requirement|instruction|rule|constraint)s?[^.]*\.?", re.I)

def sanitize(q):
    hits = [m.group(0) for m in INJ.finditer(q)]
    return INJ.sub("", q).strip(), hits