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

## hopdetect flags

Every parameter that influences the hop set is a flag, and the effective
parameter set is recorded in `hops.json`, so a run is reproducible from its
own output ([issue #4](https://github.com/WolfgangFahl/reel-driven-development/issues/4)).

| flag | meaning | default | change it when |
| --- | --- | --- | --- |
| `--start` | segment start (seconds or MM:SS) | 0 | processing a part of the reel |
| `--end` | segment end (seconds or MM:SS) | video duration | processing a part of the reel |
| `--target` | transcript-named capture time, repeatable | none | the transcript names a moment that must have an evidence frame or a proven absence |
| `--out` | output directory for frames and JSON | `hops` | keeping several hop sets apart |
| `--threshold` | block-MAE change threshold (gray levels) | 12.0 | small UI changes are missed (lower) or noise is detected (raise); choose together with the grid, never independently |
| `--min-stable` | seconds of stability separating two hops | 1.0 | bursts (scrolling, rendering) split into several hops (raise) or distinct fast hops merge (lower) |
| `--blocks-x` | block grid columns | 16 | the smallest change area that must stay above threshold is smaller than a block; a finer grid raises the score of a small-area change, so re-check `--threshold` |
| `--blocks-y` | block grid rows | 9 | see `--blocks-x` |
| `--granularity` | minimal bisection interval in seconds | one frame | frame-level precision is not needed and sampling cost matters (raise) |
| `--target-window` | seconds sampled around each transcript target | 5.0 | the narrative anchors are less precise than ±5 s (raise) |
| `--compare-width` | width frames are downscaled to before comparison | 640 | fine detail decides hops (raise); a block must stay wide enough to average meaningfully: keep `compare_width / blocks_x` well above ~10 pixels |
| `--prefix` | evidence frame name prefix | `hop` | several walks share one output directory |
| `--region` | region of interest `x,y,width,height` the change metric is restricted to | full frame | the frame contains a permanently changing area that is not part of the walk |

### Region of interest

Block-MAE scores the whole frame by default. A frame area that changes
permanently without being part of the walk - live participant tiles in a
conference share, a playing video, a clock, a scrolling log pane - defeats the
detection: every frame pair "differs", the bisection degenerates into a dense
frame-by-frame scan, all changes merge into a single hop and proven absence
becomes unreachable
([issue #5](https://github.com/WolfgangFahl/reel-driven-development/issues/5)).

Worked example - a conference screen-share with a live participant tile
column on the right 11% of a 1920x1080 frame:

```bash
hopdetect meeting.mp4 --region 0,0,0.89,1.0 --out hops
```

* pixel form `--region 0,0,1708,1080` refers to the native video frame;
  the fractional form is resolution independent
* the region applies to the change metric only - evidence frames stay full
  frames, so the reader always sees the whole picture
* `hops.json` records the effective (fractional) region: a hop set produced
  under a region is only interpretable together with it

### Progress bar

`--progress` shows the state of a running detection
([issue #6](https://github.com/WolfgangFahl/reel-driven-development/issues/6)).
Phase 1 (anchors and target windows) has a known count and is a determinate
bar. Phase 2 (bisection) is adaptive - the total amount of work is not known
when the run starts, so a percentage would be a fabrication: it shows the
quantities that are actually known - frames sampled, change brackets settled,
intervals open and the current position in the reel. A final line reports the
totals, matching `hops.json`. Bars render only on a TTY; redirected output
stays clean.

### Machine-readable progress

`--progress-details PATH` writes one JSON object per line (JSONL) as the run
proceeds, flushed per event; `-` means stderr, so `hops.json` stays separate
([issue #7](https://github.com/WolfgangFahl/reel-driven-development/issues/7)).
An agent driving `hopdetect` can abort a degenerate run early and account for
proven-absence claims at the moment they are made.

Every event carries `event` and `t` (wall seconds since run start), plus
`pos` (position in the reel in seconds) where a position applies. The schema
is an interface: additive changes only.

| event | fields |
| --- | --- |
| `run_start` | `video`, `start`, `end`, `parameters` (the effective parameter set) |
| `phase` | `phase`: `anchors`, `targets`, `bisection`, `grouping`, `emit`; `total` where the phase has a known count |
| `sample` | `pos`, `frames` sampled so far, `open` intervals, `brackets` settled so far; rate bounded by `--progress-every` seconds |
| `bracket` | `pos`, `before`, `after`, `score` |
| `target` | `pos`, `resolution`: `found` with `time`, or `absent` with `window`, `granularity` and `frames_compared` |
| `hop` | `pos`, `hop_pos`, `time`, `screenshot` |
| `run_end` | `frames_sampled`, `brackets`, `groups`, `hops`, `absences`, `status`; `t` is the wall time |

A `target` event with `resolution: absent` is the machine-readable form of a
proven-absence claim - it carries the window searched and the granularity
reached at the moment the claim is made.

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
