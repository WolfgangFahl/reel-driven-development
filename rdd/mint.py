"""Created on 2026-08-13.

owner bootstrap and token minting of a reel site

per the Owner bootstrap and minting ADR on
https://media.bitplan.com/index.php/Talk:Rdd.bitplan.com minting is a
CLI matter - the webservice never mints.

@author: wf
"""

import os
import secrets
from typing import List, Optional

from rdd.rdd_site import Person, Persons, RddSiteConfig, Review, Reviews


class Mint:
    """Mint review tokens - the CLI side of access rights.

    A site without reviews.yaml is in installation mode: init_site
    seeds the owner and mints the wildcard owner token. mint_review
    adds a reviewer. Tokens are 128-bit random - possession is the
    right per the Reel Review decision.
    """

    OWNER_LINK_FILE = "owner_link.yaml"

    def __init__(self, config: RddSiteConfig, rdd_path: str = "~/.rdd"):
        """Initialize with the site configuration.

        Args:
            config: the site configuration - names the url the links carry.
            rdd_path: the directory beside the site configuration where
                persons.yaml, reviews.yaml and the owner link live.
        """
        self.config = config
        self.rdd_dir = os.path.expanduser(rdd_path)
        self.reviews_path = os.path.join(self.rdd_dir, "reviews.yaml")
        self.persons_path = os.path.join(self.rdd_dir, "persons.yaml")
        self.owner_link_path = os.path.join(self.rdd_dir, self.OWNER_LINK_FILE)

    @property
    def base_url(self) -> str:
        """The base url of the site - the configured public url, localhost
        where the configuration names none."""
        base_url = self.config.url or f"http://127.0.0.1:{self.config.port}"
        return base_url

    def token(self) -> str:
        """Mint a 128-bit token.

        Returns:
            32 hex characters of cryptographic randomness.
        """
        token = secrets.token_hex(16)
        return token

    def review_url(self, review: Review) -> str:
        """The link of the given review.

        Args:
            review: the review.

        Returns:
            the url whose possession is the right.
        """
        url = f"{self.base_url}{self.config.reels_url_prefix}{review.token}"
        return url

    def init_site(self, username: str, name: str, email: str, url: str) -> str:
        """Initialize the site: seed the owner and mint the owner token.

        Per the Owner bootstrap decision the owner is written into
        persons.yaml, a wildcard Review into reviews.yaml, and the
        owner link into a file of mode 600 beside the site
        configuration - the caller shows it once on the interactive
        terminal and nowhere else.

        Args:
            username: the username of the owner.
            name: the full name of the owner.
            email: the email of the owner.
            url: the url of the owner.

        Returns:
            the owner link.

        Raises:
            ValueError: where reviews.yaml already exists - a site is
                initialized exactly once.
        """
        if os.path.isfile(self.reviews_path):
            raise ValueError(
                f"{self.reviews_path} exists - the site is already initialized"
            )
        os.makedirs(self.rdd_dir, exist_ok=True)
        persons = Persons.of_path(self.persons_path)
        persons.persons.append(
            Person(username=username, name=name, email=email, url=url)
        )
        persons.save_to_yaml_file(self.persons_path)
        review = Review(
            token=self.token(),
            person=username,
            meeting="owner bootstrap",
            reels=[Review.WILDCARD],
        )
        reviews = Reviews(reviews=[review])
        reviews.save_to_yaml_file(self.reviews_path)
        owner_url = self.review_url(review)
        descriptor = os.open(
            self.owner_link_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
        )
        with os.fdopen(descriptor, "w") as owner_link_file:
            owner_link_file.write(
                f"# the owner link of this reel site - possession is the right\n"
                f"url: {owner_url}\n"
            )
        return owner_url

    def mint_review(
        self,
        person: str,
        meeting: str = "",
        reels: Optional[List[str]] = None,
    ) -> str:
        """Mint a review token for the given person.

        Args:
            person: the person the link is for.
            meeting: the meeting the review belongs to.
            reels: the acronyms the review grants.

        Returns:
            the review link.

        Raises:
            ValueError: where the site is not initialized - init_site
                comes first.
        """
        if not os.path.isfile(self.reviews_path):
            raise ValueError(
                f"no {self.reviews_path} - initialize the site with rdd site --init"
            )
        reviews = Reviews.of_path(self.reviews_path)
        review = Review(
            token=self.token(),
            person=person,
            meeting=meeting,
            reels=list(reels or []),
        )
        reviews.reviews.append(review)
        reviews.save_to_yaml_file(self.reviews_path)
        url = self.review_url(review)
        return url
