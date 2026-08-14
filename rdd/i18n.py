"""Created on 2026-08-14.

i18n of the reel site - de and en for a start, the default being the
browser setting and a selector with flag per the i18n issue

@author: wf
"""

from typing import Dict, Optional

LANGUAGES = ("en", "de")

FLAGS = {"en": "\U0001f1ec\U0001f1e7", "de": "\U0001f1e9\U0001f1ea"}

TEXTS: Dict[str, Dict[str, str]] = {
    "en": {
        "home": "home",
        "reels": "reels",
        "github": "github",
        "help": "help",
        "about": "about",
        "intro": (
            "This site keeps the reels of recorded sessions - "
            "a video, the document derived from it and the evidence frames."
        ),
        "reviewing": "Reviewing",
        "reviewing_text": (
            "A review is addressed by its own url. If you were invited to "
            "review, follow the link you received by mail - it opens the "
            "reels of your review. There is no account and no password, and "
            "the link keeps working when reels are added."
        ),
        "browsing": "Browsing",
        "browsing_text": (
            "The reels this site makes public are listed under "
            '<a href="/reels">reels</a>.'
        ),
        "demo": "Demo",
        "demo_text": "See a reel for yourself",
        "demo_hint": (
            "inspect it in true inspection mode; your verdicts stay on " "your device."
        ),
        "rdd_text": "The reels are produced with",
        "rdd_text2": (
            "free software under Apache-2.0, so any organization can run "
            "a site like this one."
        ),
        "review": "review",
        "summary": "summary",
        "file": "file",
        "bytes": "bytes",
        "review_by": "Reels - review by {person}",
        "no_reels": "This site makes no reel public yet.",
        "reel": "reel",
        "title": "title",
        "hops": "hops",
        "status": "status",
        "about_heading": "About",
        "site": "site",
        "software": "software",
        "version": "version",
        "updated": "updated",
        "license": "license",
        "source": "source",
        "documentation": "documentation",
        "not_found": "not found",
        "no_page": "There is no page at",
        "example": "Example of a valid address",
        "reels_listed": (
            'the reels of this site are listed under <a href="/reels">reels</a>.'
        ),
    },
    "de": {
        "home": "start",
        "reels": "reels",
        "github": "github",
        "help": "hilfe",
        "about": "über",
        "intro": (
            "Diese Website bewahrt die Reels aufgezeichneter Sitzungen - "
            "ein Video, das daraus abgeleitete Dokument und die "
            "Beweis-Frames."
        ),
        "reviewing": "Begutachten",
        "reviewing_text": (
            "Eine Begutachtung hat ihre eigene Adresse. Wer zur Begutachtung "
            "eingeladen ist, folgt dem per Mail erhaltenen Link - er öffnet "
            "die Reels der Begutachtung. Es gibt kein Konto und kein "
            "Passwort, und der Link gilt weiter, wenn Reels hinzukommen."
        ),
        "browsing": "Stöbern",
        "browsing_text": (
            "Die öffentlichen Reels dieser Website stehen unter "
            '<a href="/reels">reels</a>.'
        ),
        "demo": "Demo",
        "demo_text": "Ein Reel selbst ansehen",
        "demo_hint": (
            "im echten Inspektionsmodus - die Urteile bleiben auf dem " "eigenen Gerät."
        ),
        "rdd_text": "Die Reels entstehen mit",
        "rdd_text2": (
            "freie Software unter Apache-2.0 - jede Organisation kann eine "
            "solche Website betreiben."
        ),
        "review": "Begutachtung",
        "summary": "Zusammenfassung",
        "file": "Datei",
        "bytes": "Bytes",
        "review_by": "Reels - Begutachtung durch {person}",
        "no_reels": "Diese Website macht noch kein Reel öffentlich.",
        "reel": "Reel",
        "title": "Titel",
        "hops": "Hops",
        "status": "Status",
        "about_heading": "Über",
        "site": "Website",
        "software": "Software",
        "version": "Version",
        "updated": "Stand",
        "license": "Lizenz",
        "source": "Quelle",
        "documentation": "Dokumentation",
        "not_found": "nicht gefunden",
        "no_page": "Es gibt keine Seite unter",
        "example": "Beispiel einer gültigen Adresse",
        "reels_listed": (
            'die Reels dieser Website stehen unter <a href="/reels">reels</a>.'
        ),
    },
}


def texts(lang: str) -> Dict[str, str]:
    """The texts of the given language.

    Args:
        lang: the language code.

    Returns:
        the texts; english where the language is not carried.
    """
    lang_texts = TEXTS.get(lang, TEXTS["en"])
    return lang_texts


def pick_language(
    query_lang: Optional[str] = None,
    cookie_lang: Optional[str] = None,
    accept_language: Optional[str] = None,
) -> str:
    """Pick the language of a request.

    The explicit choice wins, then the remembered one, then the browser
    setting - per the i18n issue the default is the browser setting.

    Args:
        query_lang: the ?lang= parameter, if any.
        cookie_lang: the remembered choice, if any.
        accept_language: the Accept-Language header, if any.

    Returns:
        the language code; en where nothing decides.
    """
    lang = "en"
    if query_lang in LANGUAGES:
        lang = query_lang
    elif cookie_lang in LANGUAGES:
        lang = cookie_lang
    elif accept_language:
        for part in accept_language.split(","):
            code = part.split(";")[0].strip().lower()[:2]
            if code in LANGUAGES:
                lang = code
                break
    return lang
