"""Created on 2026-08-14.

test the i18n resource of the reel site

@author: wf
"""

from basemkit.basetest import Basetest

from rdd.i18n import FLAGS, LANGUAGES, I18n, pick_language, review_texts, texts


class TestI18n(Basetest):
    """Test the i18n texts loaded from the package resource."""

    def testResource(self):
        """Test that the i18n resource carries languages, flags and the two
        text sets."""
        i18n = I18n.get_instance()
        self.assertTrue(I18n.resource_path().is_file())
        self.assertEqual(("en", "de"), LANGUAGES)
        for lang in LANGUAGES:
            self.assertIn(lang, FLAGS)
            self.assertIn(lang, i18n.texts)
            self.assertIn(lang, i18n.review)

    def testKeyParity(self):
        """Test that every language carries every key - a missing
        translation must fail the build, not fall back silently."""
        i18n = I18n.get_instance()
        for name, text_sets in (("texts", i18n.texts), ("review", i18n.review)):
            expected_keys = set(text_sets["en"].keys())
            for lang in LANGUAGES:
                self.assertEqual(
                    expected_keys,
                    set(text_sets[lang].keys()),
                    f"{name}/{lang} keys differ from en",
                )

    def testLookup(self):
        """Test the lookup functions and the language pick."""
        self.assertEqual("start", texts("de")["home"])
        self.assertEqual("home", texts("en")["home"])
        self.assertEqual("Reel-Urteil", review_texts("de")["reel_verdict"])
        self.assertEqual("reel verdict", review_texts("en")["reel_verdict"])
        # unknown language falls back to english
        self.assertEqual("home", texts("fr")["home"])
        self.assertEqual("de", pick_language(accept_language="de-DE,de;q=0.9"))
        self.assertEqual("en", pick_language(query_lang="en", cookie_lang="de"))
