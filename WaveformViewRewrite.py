#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-

from SceneWithDrag import SceneWithDrag
from MovableButton import MovableButton
from WaveformView import WaveformView, normalize, font, default_sample_width, default_samples_per_frame

# This file now serves as a compatibility layer, importing and re-exporting the classes
# that were previously defined here. This maintains backward compatibility while
# allowing for better code organization.

__all__ = ['SceneWithDrag', 'MovableButton', 'WaveformView', 'normalize', 
           'font', 'default_sample_width', 'default_samples_per_frame']