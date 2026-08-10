"""Created on 2026-08-10.

quick check page of a reel

One page per reel, one row per hop, three answers - ok, weg, ändern -
and a comment where something is to be changed. A single self contained
html file: the reviewer has no account, no login and no server, and a
page that needs one of those is a page that does not get answered.

The answers come back as a file the reviewer downloads and mails back,
so the reading is machine readable and lands in the reel file again.
The state is kept in the browser while it is being filled in, so a
closed tab does not lose an hour of work.

see https://github.com/WolfgangFahl/reel-driven-development/issues/27

@author: wf
"""

import base64
import html
import json
import os
from typing import List, Optional

from rdd.adoc import LABELS, RecordingDoc

# the answers a reviewer can give, in the language of the recording
ANSWERS = {
    "en": {"ok": "ok", "drop": "drop", "change": "change"},
    "de": {"ok": "ok", "drop": "weg", "change": "ändern"},
}

TEXTS = {
    "en": {
        "intro": "Please go through your walk: is every step right as it is?",
        "comment": "what should be changed",
        "done": "download answers",
        "hint": "The file lands in your downloads - please send it back by mail.",
        "answered": "answered",
    },
    "de": {
        "intro": "Bitte geh deinen Walk durch: stimmt jeder Schritt so?",
        "comment": "was geändert werden soll",
        "done": "Antworten herunterladen",
        "hint": "Die Datei landet in deinen Downloads - bitte per Mail zurück.",
        "answered": "beantwortet",
    },
}

PAGE = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 0 auto; max-width: 50rem;
        padding: 1rem; line-height: 1.5; }}
h1 {{ font-size: 1.4rem; }}
.hop {{ border-top: 1px solid #ccc; padding: 1rem 0; }}
.hop img {{ max-width: 100%; height: auto; border: 1px solid #ddd; }}
.time {{ color: #666; font-variant-numeric: tabular-nums; }}
.answers {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: .5rem 0; }}
label.answer {{ cursor: pointer; padding: .2rem .6rem; border: 1px solid #999;
                border-radius: .4rem; }}
label.answer:has(input:checked) {{ background: #333; color: #fff; }}
textarea {{ width: 100%; min-height: 3rem; display: none; }}
.hop.change textarea {{ display: block; }}
#bar {{ position: sticky; bottom: 0; background: #fff; border-top: 1px solid #ccc;
        padding: .8rem 0; display: flex; gap: 1rem; align-items: center; }}
button {{ font-size: 1rem; padding: .5rem 1rem; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p>{intro}</p>
{hops}
<div id="bar">
  <button id="save">{done}</button>
  <span id="count"></span>
</div>
<p><small>{hint}</small></p>
<script>
const KEY = "quickcheck-{acronym}";
const state = JSON.parse(localStorage.getItem(KEY) || "{{}}");

function apply() {{
  document.querySelectorAll(".hop").forEach(hop => {{
    const pos = hop.dataset.pos;
    const answer = state[pos] && state[pos].answer;
    hop.classList.toggle("change", answer === "change");
    if (answer) {{
      const input = hop.querySelector(`input[value="${{answer}}"]`);
      if (input) input.checked = true;
    }}
    const comment = hop.querySelector("textarea");
    if (state[pos] && state[pos].comment) comment.value = state[pos].comment;
  }});
  const answered = Object.values(state).filter(a => a.answer).length;
  document.getElementById("count").textContent =
    answered + " / {hopCount} {answered}";
}}

document.addEventListener("input", event => {{
  const hop = event.target.closest(".hop");
  if (!hop) return;
  const pos = hop.dataset.pos;
  const checked = hop.querySelector("input:checked");
  state[pos] = {{
    answer: checked ? checked.value : null,
    comment: hop.querySelector("textarea").value
  }};
  localStorage.setItem(KEY, JSON.stringify(state));
  apply();
}});

document.getElementById("save").addEventListener("click", () => {{
  const lines = ["# quick check {acronym}", "recording: {acronym}", "hops:"];
  document.querySelectorAll(".hop").forEach(hop => {{
    const pos = hop.dataset.pos;
    const answer = (state[pos] && state[pos].answer) || "";
    const comment = (state[pos] && state[pos].comment) || "";
    lines.push("- pos: " + pos);
    lines.push("  answer: " + answer);
    if (comment) lines.push("  comment: " + JSON.stringify(comment));
  }});
  const blob = new Blob([lines.join("\\n") + "\\n"], {{type: "text/yaml"}});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "quickcheck-{acronym}.yaml";
  link.click();
}});

apply();
</script>
</body>
</html>
"""

HOP_BLOCK = """<div class="hop" data-pos="{pos}">
<h2>{pos}. {node}</h2>
<p class="time">{time}</p>
{image}
<p>{summary}</p>
<div class="answers">
<label class="answer"><input type="radio" name="a{pos}" value="ok"> {ok}</label>
<label class="answer"><input type="radio" name="a{pos}" value="drop"> {drop}</label>
<label class="answer"><input type="radio" name="a{pos}" value="change"> {change}</label>
</div>
<textarea placeholder="{comment}"></textarea>
</div>
"""


class QuickCheck:
    """The single page quick check of one reel."""

    def __init__(self, doc: RecordingDoc):
        """Initialize with the document of a reel.

        Args:
            doc: the document the page shows the same model as.
        """
        self.doc = doc

    @property
    def lang(self) -> str:
        """The language of the page."""
        page_lang = self.doc.lang if self.doc.lang in ANSWERS else "en"
        return page_lang

    def image_tag(self, screenshot: Optional[str], path: Optional[str]) -> str:
        """Get the img tag of an evidence frame.

        The frame is embedded as a data url: the page travels as one
        file, by mail or from a share, and a page whose pictures are
        missing is a page nobody can answer.

        Args:
            screenshot: the frame name.
            path: the path of the frame, None where there is none.

        Returns:
            the img tag, empty where the hop has no frame.
        """
        tag = ""
        if path:
            with open(path, "rb") as frame_file:
                data = base64.b64encode(frame_file.read()).decode("ascii")
            alt = html.escape(screenshot or "")
            tag = f'<img src="data:image/jpeg;base64,{data}" alt="{alt}">'
        return tag

    def hop_blocks(self) -> List[str]:
        """Get the html of every hop."""
        answers = ANSWERS[self.lang]
        texts = TEXTS[self.lang]
        blocks = []
        for hop in self.doc.hop_set.hops:
            frame = self.doc.frame_path(hop)
            scaled = None
            if frame:
                scaled = os.path.join(self.doc.images_dir, hop.screenshot)
                if not os.path.isfile(scaled):
                    scaled = frame
            blocks.append(
                HOP_BLOCK.format(
                    pos=hop.pos,
                    node=html.escape(hop.node or hop.time),
                    time=html.escape(hop.time),
                    image=self.image_tag(hop.screenshot, scaled),
                    summary=html.escape(hop.summary or ""),
                    comment=html.escape(texts["comment"]),
                    **answers,
                )
            )
        return blocks

    def html(self) -> str:
        """Get the whole page.

        Returns:
            the self contained html.
        """
        recording = self.doc.recording
        texts = TEXTS[self.lang]
        title = recording.name or recording.acronym or "reel"
        page = PAGE.format(
            lang=self.lang,
            title=html.escape(title),
            acronym=recording.acronym or "reel",
            hopCount=self.doc.hop_set.hopCount,
            hops="\n".join(self.hop_blocks()),
            intro=html.escape(texts["intro"]),
            done=html.escape(texts["done"]),
            hint=html.escape(texts["hint"]),
            answered=html.escape(texts["answered"]),
        )
        return page

    def save(self, path: str) -> str:
        """Write the page to the given path.

        Args:
            path: the file to write.

        Returns:
            the path written.
        """
        self.doc.scale_frames()
        with open(path, "w", encoding="utf-8") as page_file:
            page_file.write(self.html())
        return path
