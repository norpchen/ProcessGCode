ProcessGCode
============

G-Code post processor

Use command line option -h for help on commands and options.

Uses Python 3.3.1, but should work in 3.2 or later.   

Some of the functionality will work on any g-code, but there's more stuff it can do with Slic3r / KISSlicer's output because of the copious comments (thanks Jonathan!) 

Here's what it is currently capable of:

First, the basics that work with any g-code:

* Offset XY position
* Scale X, Y, Z (or all three) coordinates
* Remove redundant move coordinates (slightly smaller file) 
* Remove XY moves smaller than a given threshold (more efficient when sliced file has more detail than the printer can handle)
* Adjust fan speed, bed and extruder temperatures throughout file
* Adjust flow and feed rates throughout the file
* Basic replacement of one command for another (swap G0 for G1, for example)
* Comment out all instances of a specific code
* Enforce a maximum and minimum extruder temperature
* change bed & extruder temperature commands between wait / no-wait / first 
* Resume from a given line number, layer or z-height.  All movement commands prior will be tracked but not move the head.  XY position will be recovered, but Z height can be optionally set manually. Be careful of resuming after a retraction, as you might get a blob if your filament moves.
* Convert all movement to absolute or relative mode
* Remove or pad all comments.  Padding comments puts a null movement G0 command in front of each comment to prevent the line from being stripped when sent to the printer by the host (useful if you need to track line numbers for a resume).
* Remove any headers
* Add filament retraction to non-extrusion moves
* Create a DESCRIPT.ION file for the output with same basic metrics
* Append basic metrics to the end (or head) of the file (as comments)
* rough time estimates
* convert slicer generated retraction commands to G10 and G11 commands
* convert to and from Ulticode flavor of gcode (volumetric extrusion units, G10/G11 retraction) 

Then the more fun KISSlicer / Slic3r specific stuff:

* Inject commands to display the current layer number or percent progress on the LCD of your printer (M70 or M117 commands)
* Inject commands to set the RGB mood light LED to match the path type (colors as shown in KISSlicer)
* Inject commands to show the path type in the LCD of your printer
* Move the slicing summary from the bottom of the file to the top of the file
* Cool the bed temperature by X degrees at layer Y
* Turn on / off the fan for KISSlicer's 'Support Interface' paths (I find it makes it easier to remove the support cleanly)
* Turn on / off the fan for KISSlicer's 'Stacked Sparse Infill" paths
* Turn on the fan and adjust the extruder temperature to make the raft easier to remove cleanly (only activates if it detects there is a raft)
* Split the file into two based on layer, z height, path type or every X layers 
* Inject a gcode file at a specific layer, z height, path type, or every X layers.  This is useful for adding filament change pause commands, adding a raft, converting a skirt to a wall, etc.
* Merge multiple files, interleaving them based on z-heights.  This is useful for multiple extruders or combining thicker infill with thin loops, etc.  Merging is experimental and likely does not work with slicer generated retraction commands.
* Add a 'Quality' value to move commands based on path.  Allows you to set a desired quality for specific path types. This requires special support in firmware for a Q variable added to G0/G1 commands.  It's up to the printer to determine how to implement 'quality' -- for example, my firmware scales acceleration, speed and xy jerk by this factor.

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

Sept 27, 2013 -- Version 0.9.0
* Added support for resume on layer and ZHeight
* Started support for merging files
* Added ability to overwrite input file and not require an output file

Dec 24, 2013  -- Version 0.9.4
* Added scaling of x,y,z axes

Jan 6, 2014 -- Version 0.9.5
 * Added metrics and descript.ion support
 * Added ability to specify more than one quality setting type / value
 * Added path and layer detection for Slic3r generated gcode
 * Fixed surplus blank lines and line endings
 * Added progress percentage report

 April 3, 2014
 * Added support for Cura slicer comments for layer and path detection
 * Added support for M82 M83 extrusion relative / absolute positioning
 
 May 26, 2014
 * Added split and inject based on line numbers
 
 Aug 26, 2016 v0.9.7
  * added support for ultigcode / volumetric input and output conversion
  * option to set Z on resume
  * option to remove all movement commands (instead of commenting them out) prior to the resume 
  * ultigcode (for ultimaker printers) includes disabling heater commands at start and proper header
  * really crappy time estimates
  * G10/G11 retract / unretract commands for ultigcode
  * G2 and G3 commands (arc movements) support I and J params to properly reassemble in the line movement processor
  * moved metrics report to top of file
 
 Jan 1, 2017 v 0.9.8.1
   Added / changed metrics info for Duet boards to parse
   added space ~ wildcard to --replace option
   added peak bed and extruder temp tracking
   changed Cura info processing for Cura 2.3 
