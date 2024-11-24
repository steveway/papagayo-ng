#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-

import PySide6.QtWidgets as QtWidgets
from PySide6 import QtGui

class SceneWithDrag(QtWidgets.QGraphicsScene):
    def dragEnterEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        # find item at these coordinates
        item = self.itemAt(e.scenePos(), QtGui.QTransform())
        if item:
            if item.setAcceptDrops:
                # pass on event to item at the coordinates
                item.dropEvent(e)
                try:
                    item.dropEvent(e)
                except RuntimeError:
                    pass  # This will suppress a Runtime Error generated when dropping into a widget with no MyProxy

    def dragMoveEvent(self, e):
        e.acceptProposedAction()
