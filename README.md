# reel-driven-development

Reel Driven Development (RDD) - turn recorded user walks (reels) into domain stories and outcome objects

| | |
| :--- | :--- |
| **PyPi** | [![PyPI Status](https://img.shields.io/pypi/v/reel-driven-development.svg)](https://pypi.python.org/pypi/reel-driven-development/) [![License](https://img.shields.io/github/license/WolfgangFahl/reel-driven-development.svg)](https://www.apache.org/licenses/LICENSE-2.0) [![pypi](https://img.shields.io/pypi/pyversions/reel-driven-development)](https://pypi.org/project/reel-driven-development/) [![format](https://img.shields.io/pypi/format/reel-driven-development)](https://pypi.org/project/reel-driven-development/) [![downloads](https://img.shields.io/pypi/dd/reel-driven-development)](https://pypi.org/project/reel-driven-development/) |
| **GitHub** | [![Github Actions Build](https://github.com/WolfgangFahl/reel-driven-development/actions/workflows/build.yml/badge.svg)](https://github.com/WolfgangFahl/reel-driven-development/actions/workflows/build.yml) [![Release](https://img.shields.io/github/v/release/WolfgangFahl/reel-driven-development)](https://github.com/WolfgangFahl/reel-driven-development/releases) [![Contributors](https://img.shields.io/github/contributors/WolfgangFahl/reel-driven-development)](https://github.com/WolfgangFahl/reel-driven-development/graphs/contributors) [![Last Commit](https://img.shields.io/github/last-commit/WolfgangFahl/reel-driven-development)](https://github.com/WolfgangFahl/reel-driven-development/commits/) [![GitHub issues](https://img.shields.io/github/issues/WolfgangFahl/reel-driven-development.svg)](https://github.com/WolfgangFahl/reel-driven-development/issues) [![GitHub closed issues](https://img.shields.io/github/issues-closed/WolfgangFahl/reel-driven-development.svg)](https://github.com/WolfgangFahl/reel-driven-development/issues/?q=is%3Aissue+is%3Aclosed) |
| **Code** | [![style-black](https://img.shields.io/badge/%20style-black-000000.svg)](https://github.com/psf/black) [![imports-isort](https://img.shields.io/badge/%20imports-isort-%231674b1)](https://pycqa.github.io/isort/) |
| **Docs** | [![API Docs](https://img.shields.io/badge/API-Documentation-blue)](https://WolfgangFahl.github.io/reel-driven-development/) [![formatter-docformatter](https://img.shields.io/badge/%20formatter-docformatter-fedcba.svg)](https://github.com/PyCQA/docformatter) [![style-google](https://img.shields.io/badge/%20style-google-3666d6.svg)](https://google.github.io/styleguide/pyguide.html#s3.8-comments-and-docstrings) |

## Demo

See a reel for yourself: the [GenWiki demo reel](https://rdd.bitplan.com/reels/RDD-GenWiki-Example/)
(7 hops) on [rdd.bitplan.com](https://rdd.bitplan.com) - true inspection mode,
your verdicts stay on your device. Reviewers get a link by mail - no account,
no password.

## Installation

```bash
pip install reel-driven-development
```

or isolated with [pipx](https://pipx.pypa.io/):

```bash
pipx install reel-driven-development
```

Both put the `rdd` command and the tool entry points on the PATH.

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

HopDetection was the first step -
[issue #1](https://github.com/WolfgangFahl/reel-driven-development/issues/1);
the requirements epic is
[issue #7](https://github.com/WolfgangFahl/reel-driven-development/issues/7).

## rdd - the one command name

`rdd` dispatches to the tools of the pipeline, so a user has to know
one name - the name of what we do:

| subcommand | tool | purpose |
| --- | --- | --- |
| `rdd detect` | `hopdetect` | find the hops of a reel and capture the evidence frames |
| `rdd doc` | `reeldoc` | generate the reel document from a Recording |
| `rdd review` | `reelreview` | serve one reel folder for review |
| `rdd site` | `reelsite` | serve the reel site; `--init` initializes it, `--mint` mints a review token |

`rdd` without a subcommand lists them; the tool names stay available as
entry points of their own.

## rdd detect flags

| flag | meaning | default | change it when |
| --- | --- | --- | --- |
| `--detector` | the detector to find the hops with, by name | `Content` | comparing detectors, or one detector misses hops on this material |
| `--start` | segment start (seconds or MM:SS) | 0 | processing a part of the reel |
| `--end` | segment end (seconds or MM:SS) | video duration | processing a part of the reel |
| `--out` | output directory for the evidence frames, `hops.yaml` and `config.yaml` | `hops` | keeping several hop sets apart |
| `--progress` | show the progress bar of the running detection | off | a run over a long reel must not be silent ([issue #6](https://github.com/WolfgangFahl/reel-driven-development/issues/6)) |

`rdd detect --help` lists these together with the standard options of
[pybasemkit](https://github.com/WolfgangFahl/pybasemkit#cli-tooling).

## Detectors

Hop candidates come from the detectors of
[PySceneDetect](https://www.scenedetect.com), which
[benchmarks them](https://www.scenedetect.com/benchmarks/).

Each detector is on offer at its library default and at half and double its
threshold. `ThresholdDetector` is not on offer: it detects fades to a
near-black level.

Cuts found on [examples/recordings/genwiki-walk](examples/recordings/genwiki-walk) - 1501 frames,
60 s, about 1.4 s per run:

| detector | half | default | double |
| --- | --- | --- | --- |
| Adaptive | 32 | 15 | 11 |
| Content | 17 | 9 | 0 |
| Hash | 32 | 12 | 0 |
| Histogram | 13 | 10 | 7 |

## Output

A run writes to `--out`:

* `hop-<hh>h<mm>m<ss>s[<ms>ms].jpg` - the evidence frame of each hop, the
  full frame as recorded, named by its time offset so curation never
  renames a surviving frame
  ([issue #21](https://github.com/WolfgangFahl/reel-driven-development/issues/21))
* `hops.yaml` - the hop records, whose field names are the property names of
  [Concept:HopContent](https://contexts.bitplan.com/index.php/Concept:HopContent);
  `node`, `url` and `summary` stay empty because they come from the transcript
  and are never guessed from the picture
* `config.yaml` - the values that decided this hop set, so a run can be
  repeated from its own output
  ([issue #4](https://github.com/WolfgangFahl/reel-driven-development/issues/4))

## Example: GenWiki walk

```bash
rdd detect examples/recordings/genwiki-walk/genwiki-walk.mp4 --detector Content --out hops
genwiki-walk.mp4: 9 hops from Content over 1501 frames -> hops
```

Raw results of an earlier run in
[examples/recordings/genwiki-walk](examples/recordings/genwiki-walk).

## Known gaps

* content outside the walk - participant tiles, a clock, a playing video -
  can still decide hop boundaries
  ([issue #5](https://github.com/WolfgangFahl/reel-driven-development/issues/5))
* there is no machine-readable progress stream for an agent driving a run
  ([issue #36](https://github.com/WolfgangFahl/reel-driven-development/issues/36))
* transcript-anchored capture of a named moment is not implemented
