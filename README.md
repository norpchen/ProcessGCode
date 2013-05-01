ProcessGCode
============

G-Code post processor

Uses Python 3.3.1, but should work in 3.2 or later. 

Some of the functionality will work on any g-code, but there's more stuff it can do with KISSlicer's output because of the copious comments (thanks Jonathan!) 

Here's what it is currently capable of:

First, the basics that work with any g-code:

* Offset XY position
* Remove redundant move coordinates (slightly smaller file) 
* Remove XY moves smaller than a given threshold
* Adjust fan speed, bed and extruder temperatures throughout file
* Adjust flow and feed rates throughout the file
* Basic replacement of one command for another (swap G0 for G1, for example)
* Comment out all instances of a specific code

Then the more fun KISSlicer specific stuff:

* Inject commands to display the current layer number on the LCD of your printer (M70 or M117 commands)
* Inject commands to set the RGB mood light LED to match the path type as shown in KISSlicer
* Inject commands to show the path type in the LCD of your printer
* Move the slicing summary from the bottom of the file to the top of the file
* Cool the bed temperature by X degrees at layer Y
* Turn on / off the fan for all 'Support Interface' paths (I find it makes it easier to remove the support cleanly)
* Turn on / off the fan for all 'Stacked Sparse Infill" paths
* Turn on the fan and adjust the extruder temperature to make the raft easier to remove cleanly (only activates if it detects there is a raft)

The layer and path type detection from the comments makes it easy to add additional functionality you may need based on path or layer.

----------
April 30, 2013 -- Version 0.8 Initial Release


