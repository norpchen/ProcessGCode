ProcessGCode
============

G-Code post processor

Use command line option -h for help on commands and options.

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
* Enforce a maximum and minimum extruder temperature
* Resume from a given line number (experimental).  All movement commands prior to line number will be tracked but not move the head.  XY position will be recovered, but Z height must be set manually. Be careful of resuming after a retraction, as you might get a blob if your filament moves.
* Convert all movement to absolute or relative mode
* Remove or pad all comments.  Padding comments puts a null movement G0 command in front of each comment to prevent the line from being stripped when sent to the printer by the host (useful if you need to track line numbers for a resume).
* Remove any headers
* Add filament retraction to non-extrusion moves

Then the more fun KISSlicer specific stuff:

* Inject commands to display the current layer number on the LCD of your printer (M70 or M117 commands)
* Inject commands to set the RGB mood light LED to match the path type as shown in KISSlicer
* Inject commands to show the path type in the LCD of your printer
* Move the slicing summary from the bottom of the file to the top of the file
* Cool the bed temperature by X degrees at layer Y
* Turn on / off the fan for all 'Support Interface' paths (I find it makes it easier to remove the support cleanly)
* Turn on / off the fan for all 'Stacked Sparse Infill" paths
* Turn on the fan and adjust the extruder temperature to make the raft easier to remove cleanly (only activates if it detects there is a raft)
* Split the file into two based on layer, z height, path type or every X layers 
* Inject a gcode file at a specific layer, z height, path type, or every X layers.  This is useful for adding filament change pause commands, adding a raft, converting a skirt to a wall, etc.

The layer and path type detection from the comments makes it easy to add additional functionality you may need based on path or layer.

----------
April 30, 2013 -- Version 0.8 Initial Release
May 1, 2013 -- Version 0.8.1 
* Fixed bug in replacement
May 3, 2013 -- Version 0.8.2 
* Added min and max temperatures for extruder to keep adjusted temperatures in valid ranges
* Changed fan option from 'Stacked Sparse Infill' to 'Sparse Infill'
* added option to enclose LCD messages in quotes
* bug fix on raft cooling
May 9, 2013 -- Version 0.8.5
* Added support for relative movement
* Added parsing of G92 and G28 commands
* Added support for resume (experimental) 
* Added ability to remove or pad comment lines
* Changed the way -m works internally
* Changed command line option --quote-comments to --quote-messages
May 28, 2013 -- version 0.8.6
* Added support for wait on first / all / none temperature setting commands
* Added option to report flow (extrusion vs travel)
June 11, 2013 -- version 0.8.8
* Added support for slicing based on path type, layer, zheight or nth layer
* Added support for injecting subfiles at path, layer, zheight or nth layer
  ** Injected files have the z-coordinates stripped out in all move commands
  ** Filament position, head position, and feed speed are preseved around injected subfile
  ** Slicing or Injecting do not work well if the slicer does retraction.  Disable retraction in the slicer
	   and use the filament retraction option in this script after slicing / injection operations
* Addded filament retraction support 
* Added option to remove header (everything before layer 1 is started) 
* Added Z-height offset option