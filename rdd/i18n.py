"""Created on 2026-08-14.

i18n of the reel site - de and en for a start, the default being the
browser setting and a selector with flag per the i18n issue. The texts
are a resource of the package: rdd/resources/i18n.yaml.

@author: wf
"""

from dataclasses import field
from pathlib import Path
from typing import ClassVar, Dict, List, Optional

from basemkit.yamlable import lod_storable


@lod_storable
class I18n:
    """The i18n texts of a reel site.

    Loaded from the i18n.yaml resource the package ships - the texts
    of the site pages and of the packaged review page, the languages
    and their flags.
    """

    languages: List[str] = field(default_factory=list)
    flags: Dict[str, str] = field(default_factory=dict)
    texts: Dict[str, Dict[str, str]] = field(default_factory=dict)
    review: Dict[str, Dict[str, str]] = field(default_factory=dict)

    _instance: ClassVar[Optional["I18n"]] = None

    @classmethod
    def resource_path(cls) -> Path:
        """Path of the i18n texts shipped with the package."""
        path = Path(__file__).parent / "resources" / "i18n.yaml"
        return path

    @classmethod
    def of_resource(cls) -> "I18n":
        """Load the i18n texts shipped with the package."""
        i18n = cls.load_from_yaml_file(str(cls.resource_path()))
        return i18n

    @classmethod
    def get_instance(cls) -> "I18n":
        """Get the shared instance, loaded once from the resource."""
        if cls._instance is None:
            cls._instance = cls.of_resource()
        return cls._instance


_I18N = I18n.get_instance()

LANGUAGES = tuple(_I18N.languages)

FLAGS = _I18N.flags


def texts(lang: str) -> Dict[str, str]:
    """The site page texts of the given language.

    Args:
        lang: the language code.

    Returns:
        the texts; english where the language is not carried.
    """
    i18n = I18n.get_instance()
    lang_texts = i18n.texts.get(lang, i18n.texts["en"])
    return lang_texts


def review_texts(lang: str) -> Dict[str, str]:
    """The review page texts of the given language.

    Args:
        lang: the language code.

    Returns:
        the texts; english where the language is not carried.
    """
    i18n = I18n.get_instance()
    lang_texts = i18n.review.get(lang, i18n.review["en"])
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
