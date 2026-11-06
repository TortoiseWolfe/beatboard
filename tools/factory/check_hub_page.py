#!/usr/bin/env python3
"""Local check, not part of the CI suite: the n11/n12 arrangement tags still match the hub's jingle page.

Why this is a script and not a unit test: the hub page (tf.JINGLE, band-wagon-jingle.md) is private and
sits outside this repo, so CI can never read it. A test that always skips in CI is not a pass, so the
check lives here and is run by hand on a machine that has the hub page:

    cd tools/factory && python3 check_hub_page.py

Exit 0 = every old tag in take_factory.ARRANGEMENT is still in its song's section of the page (or the
page is not on this machine, which it says out loud). Exit 1 = the page drifted; it lists what moved.
"""
import os
import sys

import take_factory as tf

if not os.path.exists(tf.JINGLE):
    print("hub page not on this machine")
    sys.exit(0)

page = open(tf.JINGLE).read()
drift = []
for nid, title in tf.KIT_REDO:
    if nid in tf.ARRANGEMENT:
        part = page.split(f"### {nid}: ")[1].split("\n### ")[0]
        for old, _ in tf.ARRANGEMENT[nid]:
            if old not in part:
                drift.append(f"{nid} {title}: tag not on the hub page: {old}")
if drift:
    print("\n".join(drift))
    sys.exit(1)
print("hub page matches the arrangement tags")
