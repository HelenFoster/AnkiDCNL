# -*- coding: utf-8 -*-
# New code copyright Helen Foster
# Original code from Anki, copyright Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""
"Deck Counts Now/Later"
Anki addon to enhance the info displayed in the main deck tree.

Makes the "Due" count show only the number of cards due now.
If no cards are due now, but some are due later today,
 shows the time until the next review becomes due.
(Originally, if cards were due now, Anki showed all reps left on those cards.
 Otherwise it showed 0.)

Adds a "Later" column to show the number of cards and reps due later.
Formatted as "cards (reps)" if the numbers are different
 (for cards in the learning stage with more than one learning step).

Adds a "Buried" column to show the number of buried cards.

Triggers a refresh every 30 seconds. (Originally every 10 minutes.)
"""

import math
import sys
import time
from dataclasses import dataclass
from aqt.deckbrowser import DeckBrowser
from aqt.qt import *
from aqt.utils import downArrow
from anki.utils import intTime
from anki.rsbackend import DeckTreeNode
from aqt import mw

@dataclass
class RenderDeckNodeContext:
    current_deck_id: int

class BetterDeckNode:
    "A node in the new more advanced deck tree."
    def __init__(self, mw, oldNode: DeckTreeNode):
        "Build the new deck tree or subtree (with extra info) by traversing the old one."
        self.mw = mw
        self.name = oldNode.name
        self.deck_id = oldNode.deck_id
        self.collapsed = oldNode.collapsed
        self.level = oldNode.level
        self.filtered = oldNode.filtered
        self.dueRevCards = oldNode.review_count
        self.dueLrnReps = oldNode.learn_count
        self.newCards = oldNode.new_count
        oldChildren = oldNode.children
        self.cutoff = intTime() + mw.col.conf['collapseTime']
        today = mw.col.sched.today
        #dayCutoff = mw.col.sched.dayCutoff
        result = mw.col.db.first("""select
            --lrnReps
            sum(case when queue=1 then left/1000 else 0 end),
            --lrnCards
            sum(case when queue=1 then 1 else 0 end),
            --dueLrnCards
            sum(case when queue=1 and due<=? then 1 else 0 end),
            --lrnDayCards
            sum(case when queue=3 and due<=? then 1 else 0 end),
            --buriedCards
            sum(case when queue=-2 then 1 else 0 end),
            --lrnSoonest
            min(case when queue=1 then due else null end)
            from cards where did=?""", self.cutoff, today, self.deck_id)
        self.lrnReps = result[0] or 0
        self.lrnCards = result[1] or 0
        self.dueLrnCards = result[2] or 0
        self.lrnDayCards = result[3] or 0
        self.buriedCards = result[4] or 0
        self.lrnSoonest = result[5] #can be null
        self.children = [BetterDeckNode(mw, oldChild) for oldChild in oldChildren]
        for child in self.children:
            self.lrnReps += child.lrnReps
            self.lrnCards += child.lrnCards
            self.dueLrnCards += child.dueLrnCards
            self.lrnDayCards += child.lrnDayCards
            self.buriedCards += child.buriedCards
            if self.lrnSoonest is None:
                self.lrnSoonest = child.lrnSoonest
            elif child.lrnSoonest is not None:
                self.lrnSoonest = min(self.lrnSoonest, child.lrnSoonest)
    def makeRow(self):
        "Generate the HTML table cells for this row of the deck tree."
        def cap(n, c=1000):
            if n >= c:
                return str(c) + "+"
            return str(n)
        def makeCell(contents, klass):
            if contents == 0 or contents == "0":
                klass = "zero-count"
            return f'<td align=right><span class="{klass}">{contents}</span></td>'
        due = self.dueRevCards + self.lrnDayCards + self.dueLrnCards
        if due == 0 and self.lrnSoonest is not None:
            waitSecs = self.lrnSoonest - self.cutoff
            waitMins = int(math.ceil(waitSecs / 60.0))
            due = "[" + str(waitMins) + "m]"
        else:
            due = cap(due)
        laterCards = self.lrnCards - self.dueLrnCards
        laterReps = self.lrnReps - self.dueLrnCards
        if laterReps == laterCards:
            later = cap(laterReps)
        elif laterCards == 0:
            later = "(" + cap(laterReps) + ")"
        elif laterReps >= 1000:
            later = cap(laterCards) + " (+)"
        else:
            later = str(laterCards) + " (" + str(laterReps) + ")"
        buf  = makeCell(cap(self.newCards), "new-count")
        buf += makeCell(due, "review-count")
        buf += makeCell(later, "learn-count")
        buf += makeCell(cap(self.buriedCards), "buried-count") #buried-count doesn't exist now
        return buf

#based on Anki 2.1.33 aqt/deckbrowser.py DeckBrowser._renderDeckTree
def renderDeckTree(self, top: DeckTreeNode) -> str:
    #new headings
    headings = ["New", "Due", "Later", "Buried"]
    buf = "<tr><th colspan=5 align=start>%s</th>" % (_("Deck"),)
    for heading in headings:
        buf += "<th class=count>%s</th>" % (_(heading),)
    buf += "<th class=optscol></th></tr>"

    buf += self._topLevelDragRow()

    ctx = RenderDeckNodeContext(current_deck_id=self.mw.col.conf["curDeck"])

    for child in top.children:
        buf += self._render_deck_node(BetterDeckNode(self.mw, child), ctx)

    return buf

#based on Anki 2.1.33 aqt/deckbrowser.py DeckBrowser._render_deck_node
def render_deck_node(self, node: BetterDeckNode, ctx: RenderDeckNodeContext) -> str:
    if node.collapsed:
        prefix = "+"
    else:
        prefix = "-"

    def indent():
        return "&nbsp;" * 6 * (node.level - 1)

    if node.deck_id == ctx.current_deck_id:
        klass = "deck current"
    else:
        klass = "deck"

    buf = "<tr class='%s' id='%d'>" % (klass, node.deck_id)
    # deck link
    if node.children:
        collapse = (
            "<a class=collapse href=# onclick='return pycmd(\"collapse:%d\")'>%s</a>"
            % (node.deck_id, prefix)
        )
    else:
        collapse = "<span class=collapse></span>"
    if node.filtered:
        extraclass = "filtered"
    else:
        extraclass = ""
    buf += """

    <td class=decktd colspan=5>%s%s<a class="deck %s"
    href=# onclick="return pycmd('open:%d')">%s</a></td>""" % (
        indent(),
        collapse,
        extraclass,
        node.deck_id,
        node.name,
    )

    buf += node.makeRow()

    # options
    buf += (
        "<td align=center class=opts><a onclick='return pycmd(\"opts:%d\");'>"
        "<img src='/_anki/imgs/gears.svg' class=gears></a></td></tr>" % node.deck_id
    )
    # children
    if not node.collapsed:
        for child in node.children:
            buf += self._render_deck_node(child, ctx)
    return buf

#based on Anki 2.0.45 aqt/main.py AnkiQt.onRefreshTimer
def onRefreshTimer():
    if mw.state == "deckBrowser":
        mw.deckBrowser.refresh()

#hooks for Addon Reloader
def addon_reloader_before():
    refreshTimer.stop()  #a new one will be created after reloading
def addon_reloader_after():
    onRefreshTimer()  #refresh right away after reloading

#replace rendering functions in DeckBrowser with these new ones
DeckBrowser._renderDeckTree = renderDeckTree
DeckBrowser._render_deck_node = render_deck_node

#refresh every 30 seconds
refreshTimer = mw.progress.timer(30*1000, onRefreshTimer, True)

