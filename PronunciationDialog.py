# -*- coding: ISO-8859-1 -*-
# generated by wxGlade 0.3.5.1 on Tue Apr 19 20:18:14 2005

# Papagayo-ng, a lip-sync tool for use with several different animation suites
# Original Copyright (C) 2005 Mike Clifton
# Contact information at http://www.lostmarble.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import wx


# begin wxGlade: dependencies
# end wxGlade

class PronunciationDialog(wx.Dialog):
    def __init__(self, parent, phoneme_set):
        # begin wxGlade: PronunciationDialog.__init__
        wx.Dialog.__init__(self, None, -1, "", style=wx.DEFAULT_DIALOG_STYLE)

        self.wordLabel = wx.StaticText(self, -1, "Break down the word:", style=wx.ALIGN_CENTRE)

        phoneme_ids = {}
        self.phoneme_buttons = {}
        for phoneme in phoneme_set:
            if phoneme != 'rest':
                phoneme_ids[phoneme] = wx.NewId()
                self.phoneme_buttons[phoneme] = wx.Button(self, phoneme_ids[phoneme], phoneme)

        self.phonemeCtrl = wx.TextCtrl(self, -1, "")
        self.button_1 = wx.Button(self, wx.ID_OK, "OK")
        self.button_2 = wx.Button(self, wx.ID_CANCEL, "Cancel")

        self.__set_properties()
        self.__do_layout()
        # end wxGlade

        # Connect event handlers
        for phoneme in phoneme_set:
            if phoneme != 'rest':
                wx.EVT_BUTTON(self, phoneme_ids[phoneme], self.OnPhonemeClick)

    def __set_properties(self):
        # begin wxGlade: PronunciationDialog.__set_properties
        self.SetTitle("Unknown Word")
        self.button_1.SetDefault()

    # end wxGlade

    def __do_layout(self):
        # begin wxGlade: PronunciationDialog.__do_layout
        sizer_11 = wx.BoxSizer(wx.VERTICAL)
        sizer_12 = wx.BoxSizer(wx.HORIZONTAL)
        grid_sizer_1 = wx.GridSizer(3, 3, 4, 4)
        sizer_11.Add(self.wordLabel, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_HORIZONTAL, 4)
        for phoneme in self.phoneme_buttons.keys():
            grid_sizer_1.Add(self.phoneme_buttons[phoneme], 0, wx.FIXED_MINSIZE, 0)
        sizer_11.Add(grid_sizer_1, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 4)
        sizer_11.Add(self.phonemeCtrl, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_HORIZONTAL, 4)
        sizer_12.Add(self.button_1, 0, wx.FIXED_MINSIZE, 0)
        sizer_12.Add((20, 20), 0, wx.FIXED_MINSIZE, 0)
        sizer_12.Add(self.button_2, 0, wx.FIXED_MINSIZE, 0)
        sizer_11.Add(sizer_12, 0, wx.ALL | wx.ALIGN_RIGHT, 4)
        self.SetSizer(sizer_11)
        sizer_11.Fit(self)
        self.Layout()
        self.Centre()

    # end wxGlade

    def AddPhoneme(self, phoneme):
        text = "%s %s" % (self.phonemeCtrl.GetValue().strip(), phoneme)
        self.phonemeCtrl.SetValue(text.strip())

    def OnPhonemeClick(self, event):
        phoneme = event.GetEventObject().GetLabel()
        text = "%s %s" % (self.phonemeCtrl.GetValue().strip(), phoneme)
        self.phonemeCtrl.SetValue(text.strip())

# end of class PronunciationDialog
