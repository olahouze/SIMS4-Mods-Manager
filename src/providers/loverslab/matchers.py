import re


def is_wickedwhims_name(name: str) -> bool:
    """
    Robust matching for WickedWhims under any format/casing/hyphenation/abbreviation/typos:
    WW, ww, WickedWhims, wickedwhims, Wicked-Whims, wicked_whims, Wicked Whims,
    WickedWhile, wicked while, wickedwhiles, sims 4 wickedwhims, etc.
    Matches when the name itself designates WickedWhims.
    """
    if not name:
        return False
    clean_name = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", "", name).strip()
    clean = re.sub(r"[\s\-_.]+", "", clean_name).lower()
    clean = re.sub(r"v?\d+[a-z]?$", "", clean)
    if clean in [
        "ww",
        "wickedwhims",
        "wickedwhim",
        "wickedwhimsmod",
        "modwickedwhims",
        "ts4wickedwhims",
        "wickedwhimsts4",
        "sims4wickedwhims",
        "wickedwhile",
        "wickedwhiles",
        "wickedwhilemod",
    ]:
        return True
    if re.fullmatch(
        r"(?i)\s*(?:\[?\s*ww\s*\]?|\(?\s*ww\s*\)?|(?:the\s*)?(?:sims\s*4\s*)?wicked[\s\-_.]*(?:whims?|whiles?)(?:\s*mod)?)\s*",
        clean_name.strip(),
    ):
        return True
    return False


def is_nisa_name(name: str) -> bool:
    """
    Robust matching for Nisa's Wicked Perversions under any format/casing:
    NWP, nwp, Nisa's Wicked Perversions, Nisas Wicked Perversions, etc.
    Matches when the name itself designates Nisa's Wicked Perversions.
    """
    if not name:
        return False
    clean = re.sub(r"[\s\-_.'\"]+", "", name).lower()
    if clean in [
        "nwp",
        "nisaswickedperversion",
        "nisaswickedperversions",
        "nisawickedperversions",
        "nisawickedperversion",
        "wickedperversions",
        "nisa'swickedperversions",
        "nisa'swickedperversion",
    ]:
        return True
    if re.fullmatch(
        r"(?i)\s*(?:\[?\s*nwp\s*\]?|\(?\s*nwp\s*\)?|nisa['s\s\-_.]*wicked[\s\-_.]*perversions?)\s*",
        name.strip(),
    ):
        return True
    return False
