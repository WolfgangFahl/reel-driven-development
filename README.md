# reel-driven-development

Reel Driven Development (RDD) - turn recorded user walks (reels) into domain stories and outcome objects

| | |
| :--- | :--- |
| **PyPi** | [![PyPI Status](https://img.shields.io/pypi/v/reel-driven-development.svg)](https://pypi.python.org/pypi/reel-driven-development/) [![License](https://img.shields.io/github/license/WolfgangFahl/reel-driven-development.svg)](https://www.apache.org/licenses/LICENSE-2.0) [![pypi](https://img.shields.io/pypi/pyversions/reel-driven-development)](https://pypi.org/project/reel-driven-development/) [![format](https://img.shields.io/pypi/format/reel-driven-development)](https://pypi.org/project/reel-driven-development/) [![downloads](https://img.shields.io/pypi/dd/reel-driven-development)](https://pypi.org/project/reel-driven-development/) |
| **GitHub** | [![Github Actions Build](https://github.com/WolfgangFahl/reel-driven-development/actions/workflows/build.yml/badge.svg)](https://github.com/WolfgangFahl/reel-driven-development/actions/workflows/build.yml) [![Release](https://img.shields.io/github/v/release/WolfgangFahl/reel-driven-development)](https://github.com/WolfgangFahl/reel-driven-development/releases) [![Contributors](https://img.shields.io/github/contributors/WolfgangFahl/reel-driven-development)](https://github.com/WolfgangFahl/reel-driven-development/graphs/contributors) [![Last Commit](https://img.shields.io/github/last-commit/WolfgangFahl/reel-driven-development)](https://github.com/WolfgangFahl/reel-driven-development/commits/) [![GitHub issues](https://img.shields.io/github/issues/WolfgangFahl/reel-driven-development.svg)](https://github.com/WolfgangFahl/reel-driven-development/issues) [![GitHub closed issues](https://img.shields.io/github/issues-closed/WolfgangFahl/reel-driven-development.svg)](https://github.com/WolfgangFahl/reel-driven-development/issues/?q=is%3Aissue+is%3Aclosed) |
| **Code** | [![style-black](https://img.shields.io/badge/%20style-black-000000.svg)](https://github.com/psf/black) [![imports-isort](https://img.shields.io/badge/%20imports-isort-%231674b1)](https://pycqa.github.io/isort/) |
| **Docs** | [![API Docs](https://img.shields.io/badge/API-Documentation-blue)](https://WolfgangFahl.github.io/reel-driven-development/) [![formatter-docformatter](https://img.shields.io/badge/%20formatter-docformatter-fedcba.svg)](https://github.com/PyCQA/docformatter) [![style-google](https://img.shields.io/badge/%20style-google-3666d6.svg)](https://google.github.io/styleguide/pyguide.html#s3.8-comments-and-docstrings) |

## Documentation
[Wiki](https://wiki.bitplan.com/index.php/Reel_Driven_Development)

### Authors
* [Wolfgang Fahl](http://www.bitplan.com/Wolfgang_Fahl)

## Reel Driven Development

A reel is a recorded user walk - e.g. a screen-share demo where a domain expert
walks through a system while talking. RDD treats the reel as a graph walk:

* every context switch (page, browser tab, application) and every relevant
  interaction (submenu, filter, zoom, sort) is a hop
* the narrative drives the sampling, never the clock
* every hop gets an evidence frame (screenshot) or a proven-absent note
* findings become outcome objects: a frustration spoken during a walk becomes
  a bug report, which is an acceptance criterion, which is an example

The first tooling milestone is HopDetection - see
[issue #1](https://github.com/WolfgangFahl/reel-driven-development/issues/1).

## Example: GenWiki walk

Acceptance run on the [test video](https://www.youtube.com/watch?v=gVxk-zRb0wQ)
segment 20:00-21:00 - a walk through wiki.genealogy.net category pages:

```bash
hopdetect ~/.rdd/cache/gVxk-zRb0wQ.mp4 --start 20:00 --end 21:00 --out hops
12 hops from 786 sampled frames -> hops/hops.json
```

Raw results in [examples/genwiki-walk](examples/genwiki-walk). Of the 12
detected hops, 9 are distinct content states of the walk (hop numbers kept as
in hops.json):

| hop | time | changes grouped | content | frame |
| --- | --- | --- | --- | --- |
| hop01 | 20:02 | 32 | Kategorie:PDF | <img src="examples/genwiki-walk/hop01.jpg" width="360"> |
| hop02 | 20:06 | 11 | Kategorie:PDF, media section | <img src="examples/genwiki-walk/hop02.jpg" width="360"> |
| hop03 | 20:10 | 24 | file page with PDF viewer (Todfall-Rodel Kloster Salem) | <img src="examples/genwiki-walk/hop03.jpg" width="360"> |
| hop04 | 20:20 | 94 | presentation slide with category links | <img src="examples/genwiki-walk/hop04.jpg" width="360"> |
| hop05 | 20:28 | 57 | Kategorie:Icons, media section | <img src="examples/genwiki-walk/hop05.jpg" width="360"> |
| hop06 | 20:34 | 40 | Kategorie:Icons | <img src="examples/genwiki-walk/hop06.jpg" width="360"> |
| hop07 | 20:37 | 2 | Kategorie:Portal icons | <img src="examples/genwiki-walk/hop07.jpg" width="360"> |
| hop10 | 20:47 | 2 | presentation slide revisited | <img src="examples/genwiki-walk/hop10.jpg" width="360"> |
| hop12 | 20:59 | 73 | Kategorie:SVG, flags gallery | <img src="examples/genwiki-walk/hop12.jpg" width="360"> |

### False positives

Three detections are not content states of the walk - kept in the example as
tool findings:

| hop | time | reason |
| --- | --- | --- |
| hop08 | 20:41 | cursor-motion burst on the unchanged Kategorie:Portal icons page |
| hop09 | 20:45 | transient browser tab-hover preview overlay, page unchanged |
| hop11 | 20:50 | blank frame: Kategorie:SVG captured before rendering; the settled state is hop12 |
