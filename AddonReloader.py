# -*- coding: utf-8 -*-
# Copyright (C) 2017  Helen Foster
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""
Anki addon to reload other single-file addons (under certain conditions).

It can help speed up addon development, but should be used with caution,
 as unexpected results can occur.

To qualify, the target addon must contain the function
 addon_reloader_before() - this is allowed to do nothing.
(addon_reloader_teardown() still works but "before" is preferred.)
The function addon_reloader_after() is optional.

Selecting "Reload addon..." from the "Tools" menu offers a choice of eligible
 addons. After reloading an addon from this menu, a new option appears:
 "Reload ADDON_NAME" (with Ctrl+R shortcut) which reloads the same one again.

When an addon is reloaded, any items which Anki holds references to will
 still exist from the previous version. Top-level code is executed again.
AddonReloader calls addon_reloader_before() before reloading the target - 
 design it to undo anything necessary, considering these two points.
For example, if you simply declared a new function and replaced one of Anki's
 functions with it, this does not need undoing, as it will be replaced with
 the new version after the addon is reloaded. However, if you used "wrap" or
 similar, this needs undoing, as it should not be done twice.

If present, AddonReloader calls addon_reloader_after() after reloading - 
 place anything here which should be executed only after reloading,
 and not when Anki starts. (Most addons won't need anything here.)

Some addons are unsuitable for reloading. Suitable addons may also break
 after certain changes - restart Anki if this happens.

Multi-file addons should instead implement their own reloading, with a minimal
 amount of code in the primary file (so it won't need modifying often).
See my KanjiVocab addon for an example.
"""

from aqt import mw
from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.QtGui import *

class AddonChooser(QDialog):
    def __init__(self, mw, modules):
        QDialog.__init__(self, mw, Qt.Window)
        self.setWindowTitle("Reload addon")
        
        self.layout = QVBoxLayout(self)
        self.choice = QComboBox()
        self.choice.addItems(modules.keys())
        self.layout.addWidget(self.choice)
        
        buttons = QDialogButtonBox()
        buttons.addButton(QDialogButtonBox.Ok)
        buttons.addButton(QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.layout.addWidget(buttons)

def chooseAddon():
    global actionRepeat
    modules = {}
    filenames = mw.addonManager.files()
    for filename in filenames:
        modname = filename.replace(".py", "")
        try:
            module = __import__(modname)
        except:
            continue  #skip broken modules
        try:
            tmp = module.addon_reloader_before
        except:
            try:
                tmp = module.addon_reloader_teardown
            except:
                continue  #skip modules that don't have either function
        modules[modname] = module

    chooser = AddonChooser(mw, modules)
    response = chooser.exec_()
    choice = chooser.choice.currentText()
    if response == QDialog.Rejected:
        return
    if actionRepeat is not None:
        mw.form.menuTools.removeAction(actionRepeat)
        actionRepeat = None
    if choice != "":
        newAction = QAction("Reload " + choice, mw)
        newAction.setShortcut(_("Ctrl+R"))
        def reloadTheAddon():
            #take "before" in preference to "teardown", but must have one
            try:
                before = modules[choice].addon_reloader_before
            except:
                before = modules[choice].addon_reloader_teardown
            #take "after" if present, otherwise make it do nothing
            try:
                after = modules[choice].addon_reloader_after
            except:
                after = lambda: None
            #execute the reloading
            before()
            reload(modules[choice])
            after()
        mw.connect(newAction, SIGNAL("triggered()"), reloadTheAddon)
        mw.form.menuTools.addAction(newAction)
        actionRepeat = newAction
        reloadTheAddon()

actionRepeat = None
actionChoose = QAction("Reload addon...", mw)
mw.connect(actionChoose, SIGNAL("triggered()"), chooseAddon)
mw.form.menuTools.addAction(actionChoose)
