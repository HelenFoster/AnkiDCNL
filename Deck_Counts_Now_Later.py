# -*- coding: utf-8 -*-
# New code copyright Helen Foster
# Original code from Anki, copyright Damien Elmes <anki@ichi2.net>
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""
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

The table does not auto-refresh:
 you can update the times/counts by clicking on "Decks" above the table.
TODO: Trigger a table refresh once per minute?
"""

import time
from aqt.deckbrowser import DeckBrowser
from aqt.qt import *
from aqt.utils import downArrow
from anki.utils import intTime
import aqt

class DeckNode:
    "A node in the new more advanced deck tree."
    def __init__(self, mw, oldNode):
        "Build the new deck tree or subtree (with extra info) by traversing the old one."
        self.mw = mw
        self.name, self.did, self.dueRevCards, self.dueLrnReps, self.newCards, oldChildren = oldNode
        cutoff = intTime() + mw.col.conf['collapseTime']
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
            from cards where did=?""", cutoff, today, self.did)
        self.lrnReps = result[0] or 0
        self.lrnCards = result[1] or 0
        self.dueLrnCards = result[2] or 0
        self.lrnDayCards = result[3] or 0
        self.buriedCards = result[4] or 0
        self.lrnSoonest = result[5] #can be null
        self.children = [DeckNode(mw, oldChild) for oldChild in oldChildren]
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
        def makeCell(contents, colour):
            if contents == 0 or contents == "0":
                colour = "#e0e0e0"
            cell = "<td align=right><font color='%s'>%s</font></td>"
            return cell % (colour, contents)
        due = self.dueRevCards + self.lrnDayCards + self.dueLrnCards
        if due == 0 and self.lrnSoonest is not None:
            wait = (self.lrnSoonest - intTime()) / 60
            due = "[" + str(wait) + "m]"
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
        buf  = makeCell(cap(self.newCards), "#000099")
        buf += makeCell(due, "#007700")
        buf += makeCell(later, "#770000")
        buf += makeCell(cap(self.buriedCards), "#997700")
        return buf

#based on Anki 2.0.36 aqt/deckbrowser.py DeckBrowser._renderDeckTree
def renderDeckTree(self, nodes, depth=0):
    if not nodes:
        return ""
    if depth == 0:
    
        #new headings
        headings = ["New", "Due", "Later", "Buried"]
        buf = "<tr><th colspan=5 align=left>%s</th>" % (_("Deck"),)
        for heading in headings:
            buf += "<th class=count>%s</th>" % (_(heading),)
        buf += "<th class=count></th></tr>"
        
        #convert nodes
        nodes = [DeckNode(self.mw, node) for node in nodes]
    
        buf += self._topLevelDragRow()
    else:
        buf = ""
    for node in nodes:
        buf += self._deckRow(node, depth, len(nodes))
    if depth == 0:
        buf += self._topLevelDragRow()
    return buf

#based on Anki 2.0.36 aqt/deckbrowser.py DeckBrowser._deckRow
def deckRow(self, node, depth, cnt):
    did = node.did
    children = node.children
    deck = self.mw.col.decks.get(did)
    if did == 1 and cnt > 1 and not children:
        # if the default deck is empty, hide it
        if not self.mw.col.db.scalar("select 1 from cards where did = 1"):
            return ""
    # parent toggled for collapsing
    for parent in self.mw.col.decks.parents(did):
        if parent['collapsed']:
            buff = ""
            return buff
    prefix = "-"
    if self.mw.col.decks.get(did)['collapsed']:
        prefix = "+"

    def indent():
        return "&nbsp;"*6*depth
    if did == self.mw.col.conf['curDeck']:
        klass = 'deck current'
    else:
        klass = 'deck'
    buf = "<tr class='%s' id='%d'>" % (klass, did)
    # deck link
    if children:
        collapse = "<a class=collapse href='collapse:%d'>%s</a>" % (did, prefix)
    else:
        collapse = "<span class=collapse></span>"
    if deck['dyn']:
        extraclass = "filtered"
    else:
        extraclass = ""
    buf += """

    <td class=decktd colspan=5>%s%s<a class="deck %s" href='open:%d'>%s</a></td>"""% (
        indent(), collapse, extraclass, did, node.name)

    buf += node.makeRow()
    
    # options
    buf += "<td align=right class=opts>%s</td></tr>" % self.mw.button(
        link="opts:%d"%did, name="<img valign=bottom src='qrc:/icons/gears.png'>"+downArrow())
    # children
    buf += self._renderDeckTree(children, depth+1)
    return buf

DeckBrowser._renderDeckTree = renderDeckTree
DeckBrowser._deckRow = deckRow
