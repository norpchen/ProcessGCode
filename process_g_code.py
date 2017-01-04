# ##################################################################
# This script will tweak and modify the G-Code output
# of a slicer.  While it will work on any G-Code file, 
# it's aimed at KISSlicer output because of the comments
# it adds.

# Written by Lars Norpchen
# http://www.octopusmotor.com
# lars@octopusmotor.com
#
# Creative Commons : Share-Alike Non-Commericial Attribution License

# ##################################################################
# April 30, 2013  (initial release) 
# ##################################################################
# May 3, 2013 -- Version 0.8.2 
# * Added min and max temperatures for extruder to keep adjusted temperatures in valid ranges
# * Changed fan option from 'Stacked Sparse Infill' to 'Sparse Infill'
# * added option to enclose LCD messages in quotes
# * bug fix on raft cooling
# ##################################################################
# May 6, 2013 -- version 0.8.3
# * made stacked infill and support interface cooling start after layer 5
# ##################################################################
# May 9, 2013 -- Version 0.8.5
# * Added support for relative movement
# * Added parsing of G92 and G28 commands
# * Added support for resume (experimental) 
# * Added ability to remove or pad comment lines
# * Changed the way -m works internally
# * Changed command line option --quote-comments to --quote-messages
# ##################################################################
# May 28, 2013 -- version 0.8.6
# * Added support for wait on first / all / none temperature setting commands
# * Added option to report flow (extrusion vs travel)
# ##################################################################
# June 11, 2013 -- version 0.8.8
# * Added support for slicing based on path type, layer, zheight or nth layer
# * Added support for injecting subfiles at path, layer, zheight or nth layer
#   ** Injected files have the z-coordinates stripped out in all move commands
#   ** Filament position, head position, and feed speed are preseved around injected subfile
#   ** Slicing or Injecting do not work well if the slicer does retraction.  Disable retraction in the slicer
#        and use the filament retraction option in this script after slicing / injection operations
# * Addded filament retraction support 
# * Added option to remove header (everything before layer 1 is started) 
# * Added Z-height offset option
# ##################################################################
# Sept 27, 2013
# * Added support for resume on layer and ZHeight
# * Started support for merging files
# * Added ability to overwrite input file and not require an output file
# ##################################################################
# Dec 24, 2013 
# * Added scaling of x,y,z axes
# ##################################################################
#Jan 6, 2014
# * Added metrics and descript.ion support
# * Added ability to specify more than one quality setting type / value
# * Added path and layer detection for Slic3r generated gcode
# * Fixed surplus blank lines and line endings
# * Added progress percentage report
# ##################################################################
# April 3, 2014
# * Added support for Cura slicer comments for layer and path detection
# * Added support for M82 M83 extrusion relative / absolute positioning
# ##################################################################
# May 26, 2014
# * Added split and inject based on line numbers
# TODO:
# support for -X for line number (based off end of file) 
# kickstart fan (enforce minimum speed for period of time when going from 0 -- calculate time based on feedrate and movements) 
# ##################################################################
# Aug 26, 2016 v0.9.7
#  * added support for ultigcode / volumetric input and output conversion
#  * option to set Z on resume
#  * option to remove all movement commands (instead of commenting them out) prior to the resume 
#  * ultigcode (for ultimaker printers) includes disabling heater commands at start and proper header
#  * really crappy time estimates
#  * G10/G11 retract / unretract commands for ultigcode
#  * G2 and G3 commands (arc movements) support I and J params to properly reassemble in the line movement processor
#  * moved metrics report to top of file
# ##################################################################
# Jan 1, 2017 v 0.9.8.1
#   Added / changed metrics info for Duet boards to parse
#   added space ~ wildcard to --replace option
#   added peak bed and extruder temp tracking
#   added 




import string
import re
import sys
import argparse
import math
import os
import time
import ntpath
from colorama import init
from colorama import Fore, Back, Style, Cursor
import colorama

init(autoreset=True)


    

# ##################################################################
#globals
args =0
lcd_comment_string = ""
version_string = "0.9.8.1"

# some state information
has_raft = 0

current_layer = 0
override_fan_on_this_layer = 0
override_fan_off_this_layer = 0
ext_temperature = 0
bed_temperature=0
fan_speed =0 
slic3r = False    
cura = False
craftware = False
retracted = False
# these are used to detect redundant moves
last_x = 0
last_y = 0
last_e = 0
last_f = 0
last_z = 0
peak_x = 0
peak_y = 0
peak_z = 0
min_x  =99999;
min_y = 999999;
#these can be used to determine head speed as well...
delta_x = 0
delta_y = 0
delta_e = 0
delta_f = 0
delta_z = 0
total_e=0

endquote=''
ETA=0
last_path_name = ''
relative_movement = False
relative_extrusion = False
linenumber = 0
output_relative_movement = False
output_relative_extrusion = False
length_to_vol=0;
normalized_volume = 6.379395255  # cubic mm
#unused at the moment...
last_layer = ""
#layer_height=0
fo = None
foo = None
foa = None
current_file=0
materialname=''

total_time =0

peak_ext_temperature=0
peak_bed_temperature=0


lines = []   
linenumbers = []   
layer_heights = []
last_es = []
max_layer_height =0 
current_output_line = 0
        
def clamp(n, minn, maxn):
    return max(min(maxn, n), minn)
    
def remove_non_comment_spaces(line):    
            a = 0 
            line2=''
            while a < len(line):
                if line[a]!=' ': line2=line2+line[a]
                if line[a]==';': 
                    line2 = line2 + line[a:]
                    break
                a += 1
            return line2    

# ##################################################################
# insertline
# writes a line to the output file and echos it to the console
def insertline (line, fo):
    global current_output_line,args    
    if args.no_spaces:
        line = remove_non_comment_spaces(line)
    current_output_line=current_output_line+1
    fo.write (line + "\n") 
    print ('Adding line at ' + str(current_output_line) + ': ' + line)
        
def insertFile (filename):
    global fo
    insertline (conditional_comment('; BEGIN INSERT ' + filename , True),fo)
    fi = open(filename)
    lines2 = fi.readlines()
    for line2 in lines2:
        line2 = re.sub ("\r"," ",line)
        temp = re.search("^(G[01]\s.*)(Z[0-9.\-]+)(.*)", line2)
        if temp:
            line2 = temp.group(1) + temp.group(3)
        insertline (line2,fo)
    insertline ('G92 E'+str(last_e),fo)
    if output_relative_movement:
        insertline ('G1 X'+str(last_x) + " Y"+str(last_y) +' Z'+str(last_z) +' F'+str(last_f),fo)
    else:
        insertline ('G1 F'+str(last_f),fo)
    insertline (conditional_comment('; END INSERT ' + filename ,True),fo)
    
        
def switchOutput (original, cause):
    global foo,foa,fo, last_x,last_y,last_z,last_e,last_f
    if original and fo!=foo: 
        print (Style.BRIGHT +Fore.CYAN + "Switching to original output file " , args.output , " (", cause, ")")
        insertline (conditional_comment('; ------- CUT: ' + cause,True),fo)
        fo = foo
        insertline ('G92 E'+str(last_e),fo)
        if output_relative_movement:
            insertline ('G1 X'+str(last_x) + " Y"+str(last_y) +' Z'+str(last_z) +' F'+str(last_f),fo)
        else:
            insertline ('G1 F'+str(last_f),fo)
        return
    if not original and fo!=foa:
        print (Style.BRIGHT +Fore.BLUE + "Switching to alternate output file " , args.split[0] , " (", cause, ")")
        insertline (conditional_comment('; ------- CUT: ' + cause,True),fo)
        fo = foa
        insertline ('G92 E'+str(last_e),fo)
        if output_relative_movement:
            insertline ('G1 X'+str(last_x) + " Y"+str(last_y) +' Z'+str(last_z) +' F'+str(last_f),fo)
        else:
            insertline ('G1 F'+str(last_f),fo)
    

# ##################################################################
# Process_G1_Movement (string)
# returns the modified string
#
# handle all the move related changes and analysis:
#
# 1. strip out unnecessary coordinates from G1 movement commands 
# (where the XYZE or F) is the same as the previous command
# this saves a little space, but not sure it's worth the risk of causing
# confused G-code results.  SHOULD work...but....
# 2. XY use a threshold, so that micromovements can be stripped out
# or quantized (why would you do that?)
# 3. Add offset to XY movements
# 4. Change flow and feed rates
# 5. convert to and from ultimaker extrusion units (volumetric vs linear)

def process_G1_movement (line, command_override):
    global delta_x, delta_y, delta_e, delta_z, delta_f,peak_x,peak_y,peak_z, min_x, min_y,last_path_name
    global last_x, last_y, last_e, last_z, last_f, total_e, retracted 
    global args ,endquote,relative_movement,output_relative_movement,output_relative_extrusion,relative_extrusion,total_time
    comment_remover = re.search("^(.*);(.*$)",line)
    comment = ""
    if comment_remover:                                     # grab the old comment, if any
        if len (comment_remover.groups()) > 1:
            comment = '; ' + comment_remover.group(2)
        line = comment_remover.group(1)
 #   if comment!= "":
 #       print ("Processing line: " , line, " comment is " + comment)
    use_x = args.strip==False    
    Xcoordindates = re.search("X([\+\-0-9\.]*)",line) 
    if Xcoordindates:
        X = float(Xcoordindates.group(1)) * args.scalex 
        if relative_movement:
            X = last_x + X
        delta_x = X - last_x 
        if abs(delta_x) > args.decimate:
            use_x = 1
            last_x = last_x + delta_x
    else:
       use_x = 0
       delta_x = 0
       if args.explicit:
           use_x = 1
           
    Qfactor  = re.search("Q([\+\-0-9\.]*)",line)         
    Afactor  = re.search("A([\+\-0-9\.]*)",line)         
            
    use_y = args.strip==False 
    Ycoordindates = re.search("Y([\+\-0-9\.]*)",line) ;
    if Ycoordindates:
        Y = float(Ycoordindates.group(1)) * args.scaley 
        if relative_movement:
            Y = last_y + Y
        delta_y = Y - last_y 
        if abs(delta_y) > args.decimate:
            use_y = 1
            last_y = last_y + delta_y
    else:
       use_y = 0
       delta_y = 0 
       if args.explicit:
           use_y = 1

            

    use_e = args.strip==False    
    Ecoordindates = re.search("E([\+\-0-9\.]*)",line) 
    if Ecoordindates:
        E = float(Ecoordindates.group(1))
        if args.ultimaker_in:
            E = E / normalized_volume
        if args.ultimaker_out:
            E = E * length_to_vol
            
        if relative_extrusion:
            E = last_e + E
        
        if E!=last_e:
            use_e = 1
            delta_e = E-last_e
            total_e = total_e + delta_e
            #print ("total=" + str(total_e) + " \tdelta=" + str (delta_e) + " \tlastE=" + str (last_e) + " \tcurrent_E=" + str (E))
            #print ("from " + str (last_e) + " \tto " + str (E) + " \t a difference of " + str (delta_e) + "\t to a total of " + str(total_e))
            last_e = last_e  + delta_e

    
    else:
        delta_e = 0
        use_e = 0
        if args.explicit:
           use_e = 1

        
    use_z = args.strip==False   
    Zcoordindates = re.search("Z([\+\-0-9\.]*)",line)   
    if Zcoordindates:
        Z = float(Zcoordindates.group(1))* args.scalez 
        if relative_movement:
            Z = last_z + Z
        delta_z = Z - last_z
        if Z!=last_z:
            use_z = 1
            delta_z = Z-last_z 
            last_z = last_z + delta_z
            layer_heights[current_file]= Z
            SetNextFile()
    else:
        use_z = 0
        delta_z =0 
        if args.explicit:
           use_z = 1
   

# process feedrate   
    use_f = 0
    if args.explicit:
        use_f = 1
    Feed = re.search("F([\+\-0-9\.]*)",line) 
    if Feed:
    # always use F is given -- need to investigate if it's proper to strip this out!            
        use_f = 1   
        F = float(Feed.group(1))
        if F!=last_f:
#            use_f = 1
            delta_f = last_f - F
            last_f = F
    use_i = 0
    use_j = 0
    
    if command_override=='G2' or command_override=='G3':
            use_i = args.strip==False 
            icoordindates = re.search("I([\+\-0-9\.]*)",line) ;
            if args.explicit:
               use_i = 1
            use_j = args.strip==False 
            jcoordindates = re.search("J([\+\-0-9\.]*)",line) ;
            if args.explicit:
               use_j = 1

# rebuild the G1 command
    if use_x==0 and use_y==0 and use_e==0 and use_z==0 and use_f==0:
        return conditional_comment (comment)
    if command_override: 
        line = command_override
    else:
        line = "G1" 
    if Qfactor: 
        line = line + " Q" + Qfactor.group(1) + " "
    if Afactor: 
        line = line + " Q" + Afactor.group(1) + " "
    if output_relative_movement==False:
        if use_x==1:
            line = line + " X" + "{:g}".format(round((last_x + args.xoffset),args.precision) )
        if use_y==1:
            line = line + " Y" +"{:g}".format(round((last_y + args.yoffset),args.precision)) 
        if use_z==1:
            line = line + " Z" +"{:g}".format(round(last_z+ args.zoffset,args.precision) )
    else:
        if use_x==1:
            line = line + " X" + "{:g}".format(round((delta_x + args.xoffset),args.precision) )
            args.xoffset = 0
        if use_y==1:
            line = line + " Y" +"{:g}".format(round((delta_y + args.yoffset),args.precision)) 
            args.yoffset = 0 
        if use_z==1:
            line = line + " Z" +"{:g}".format(round(delta_z+ args.zoffset,args.precision) )
    if use_i==1:
        line = line + "I" + icoordinate
    if use_j==1:
        line = line + "J" + jcoordinate


# estimate time
    max_dist = max (delta_x, delta_y)
    max_dist = max(max_dist,delta_z)
 #   max_dist = max (max_dist,delta_e)
    if max_dist < 60 and last_f > 1000: 
        max_dist *=1.8;
    else:
        if max_dist < 30:
            max_dist *=4;
    delta_t =  (max_dist / (last_f /60))
    delta_t = (delta_t * 1.2000)         # rough estimate of acceleration delays
    total_time = total_time + delta_t
    if args.report_move_times:
        comment = conditional_comment ('  ; time for move is '+str(int(delta_t*1000))+'ms')
    if args.report_feedrates and use_f:
        comment = conditional_comment ('  ; new feedrate is '+str(int(last_f / 60))+'mm/s')
    
    if use_f==1:    
        line = line + " F" +"{:g}".format(round(last_f * args.feedrate,6)  )
 
    if use_e==1:
          if output_relative_extrusion==False:
                line2 =  " E" +"{:g}".format(round(last_e * args.extrusion_flow,6))
          else:
                line2 =  " E" +"{:g}".format(round(delta_e * args.extrusion_flow,6))
          line = line + line2  
          if args.use_G10_G11 and use_x ==0 and use_y == 0 and use_z == 0:
                if delta_e < 0:
                    if not retracted: 
                        line = "G10\nG92"+line2;
                        retracted = True
                else:     
                    if retracted:
                        line = "G11\nG92"+line2;
                        retracted = False
                return line
    total_distance = math.sqrt (delta_x * delta_x + delta_y * delta_y)
    if total_distance > 0 and args.report_flow: 
        if args.ultimaker-out: 
            line = line + conditional_comment('; extrude microns^2 per mm = ' + str(1000*delta_e / total_distance) + ' over ' + str(total_distance) + 'mm')
        else:   
            line = line + conditional_comment('; extrude microns per mm = ' + str(1000*delta_e / total_distance) + ' over ' + str(total_distance) + 'mm')

#track minima and maxima             
    if last_x > 0: 
        min_x = min (last_x, min_x)
    if last_y > 0: 
        min_y = min (last_y, min_y)
    peak_x = max (last_x, peak_x)
    peak_y = max (last_y, peak_y)
    peak_z = max (last_z, peak_z)
    
#check for a resume state    
    if args.resume and args.resume[1] >0:
        if not args.keep_pre_resume: 
            line = ""
        else:
            line = conditional_comment( "; " + line)
    else:
# add retraction, if requested        
        if args.retract and total_distance > float(args.retract[2]) and delta_e == 0:
            return_pos = last_e
            return_f = last_f
            rp = round(last_e-float(args.retract[0]),6)
            if args.use_G10_G11: 
                retract_line = ('\nG10\n')
                unretract_line = ('\nG11\n') 
            else:
                retract_line = conditional_comment ('; Retract, move distance is ' + "{:g}".format(round(total_distance,2))+"mm",True) + process_G1_movement ('G1 E'+"{:g}".format(rp)+' F'+args.retract[1])
                unretract_line = "\n"+conditional_comment ('; Undo Retract',True) + process_G1_movement('G1 E'+"{:g}".format(return_pos)+' F'+args.retract[1])
            # remove the E coordinate from the non-extruding move
            temp = re.search("^(G[01]\s.*)(E[0-9.\-]+)(.*)", line)
            if temp:
                line = temp.group(1) + temp.group(3)
            line = retract_line +  ('G1  F'+str(return_f)) + line + unretract_line + ('G1  F'+str(return_f))
            total_time = total_time + 0.5      # rough guess on time to retract and prime

    line = line + conditional_comment (comment)
    return line #+ "\n"
    
    
# process the coordinate resetting and homing commands
# as they affect our position tracking
def process_G92_G28_movement (line,isG92):   
    global delta_x, delta_y, delta_e, delta_z, delta_f
    global last_x, last_y, last_e, last_z, last_f
    global args ,endquote,relative_movement
    axis_found = False
    Xcoordindates = re.search("X([\+\-0-9\.]*)",line) 
    if Xcoordindates:
        axis_found = True
        if isG92:
            last_x = float(Xcoordindates.group(1))  * args.scalex
        else:
            last_x = 0
    Ycoordindates = re.search("Y([\+\-0-9\.]*)",line) 
    if Ycoordindates:
        axis_found = True
        if isG92:
            last_y = float(Ycoordindates.group(1)) * args.scaley
        else:
            last_y = 0
            
    Zcoordindates = re.search("Z([\+\-0-9\.]*)",line) 
    if Zcoordindates:
        axis_found = True
        if isG92:
            last_z = float(Zcoordindates.group(1)) * args.scalez
        else:
            last_z = 0
            
    Ecoordindates = re.search("E([\+\-0-9\.]*)",line) 
    if Ecoordindates:
        axis_found = True
        if isG92:
            last_e = float(Ecoordindates.group(1))
        else:
            last_e = 0
        line = line + (conditional_comment ('; E reset to ' +str(last_e) +'   total filament is '+str(total_e)))
    
# a G28 or G92 with no axes will home / reset ALL axes            
    if axis_found==False:
        last_x = last_y= last_e = last_z = 0

        
# adjust a comment based on the comment stripping / padding command    
def conditional_comment (str,start_of_line=False):
    global args    
    if str=="":
        return ""
    if args.comments=='remove':
        return ""
    rv = str
    if args.comments=='pad' and start_of_line:
        rv = "G0 " + str
   # if rv[-1] =='\n':
    return rv
    #return rv + "\n"
    
def get_t_code (t, bed=False):
    global args
    if bed:
        tx = args.wait_bed_temp
    else:
        tx = args.wait_temp
    if tx == "none":
        t = "4"
    if tx == "all":
        t = "9"
    if tx == "first":
        t = "9"
        if bed:
            args.wait_bed_temp = "none"
        else:
            args.wait_temp= "none"
    return t   
    
    
def resume():
    global fo,foa,foo,layer_height,linenumber,last_path_name,endquote,fan_speed,args,bed_temperature,current_layer,override_fan_on_this_layer,override_fan_off_this_layer,has_raft,ext_temperature,lcd_comment_string
    args.resume[0] = ""
    args.resume[1] = -1
    insertline (conditional_comment ("; -------------- reset to resume",True),fo)
    print (Style.BRIGHT +Fore.GREEN+ "Resuming at line ", linenumber)
    if args.print_layer:
       insertline( lcd_comment_string + " Resuming layer " + str(current_layer)+ endquote,fo)

    #resuming print -- set the XY to home, then to the start pos
    insertline ('G28 X0 Y0 '+conditional_comment ('; home x y '),fo)
    insertline ('G1 X'+str(last_x) + " Y"+str(last_y)+conditional_comment (" ; goto last position") ,fo)
    if args.leave_z_on_resume: 
        #  reset the Z and E coordinates to where we left off, without moving them
        insertline ('G92 Z'+str(last_z) + " E"+str(last_e) +conditional_comment (" ; reset Z and E positions"),fo)
    else: 
        insertline ('G1 Z'+str(last_z) + conditional_comment (" ; goto last Z position") ,fo)
        #  reset the E coordinates to where we left off, without moving them
        insertline ('G92 ' + " E"+str(last_e) +conditional_comment (" ; reset E position"),fo)
        
    insertline ('G1 F'+str(last_f) + conditional_comment (" ; set feedrate"),fo)
    if args.use_G10_G11:
        insertline ("G11 ; unretract",fo)
    insertline (conditional_comment ("; ----------------- RESUMING HERE",True),fo)
    
    
# #################################################################
# startlayer (string, outputfile) 
# returns the modified line string
#
# do things that happen only when a certain layer starts
# 
# 1. Print the layer number on the LCD
# 2. Do the magic raft cooling trick
# 3. Cool the bed at a certain layer

def startlayer (line): 
    global max_layer_height,fo,foa,foo,layer_height,linenumber,last_path_name,endquote,fan_speed,args,bed_temperature,current_layer,override_fan_on_this_layer,override_fan_off_this_layer,has_raft,ext_temperature,lcd_comment_string,current_output_line,peak_bed_temperature,peak_ext_temperature
    
    current_layer = current_layer + 1
    print (Style.BRIGHT +Fore.YELLOW + "\n---------------------\nProcessing layer # " + str(current_layer) + " starting on line "  + str(linenumber)  +  " with ZHeight=" + str (layer_height))
    override_fan_on_this_layer = 0
    override_fan_off_this_layer = 0
    args.no_header = False
    if max_layer_height < layer_height: 
        max_layer_height = layer_height
        
    if args.resume and args.resume[0]=="layer" and args.resume[1] >= current_layer:
        resume()
      
    if args.resume and args.resume[0]=="zheight" and layer_height >= args.resume[1]:
        resume()
     
    if args.split:
        if args.split[1]=='layer' :
            if current_layer >= int(args.split[2]):
                switchOutput (False,"Layer >="+ args.split[2])
        elif args.split[1]=='nth' :
            if current_layer > 1 and  (int(current_layer / int(args.split[2]))) % 1 == 0:
                switchOutput (False,"Nth ="+ args.split[2])
            else:
                switchOutput (True,"Nth ="+ args.split[2])
        elif args.split[1]=='zheight' :
            if layer_height >= float(args.split[2]):
                switchOutput (True,"Z height >="+ args.split[2])
        elif args.split[1]=='line':
            if linenumber==args.split[2]:
                switchOutput (False,"Line number is"+ args.split[2])
    
    if args.inject:
        if args.inject[1]=='layer' :
            if current_layer == int(args.inject[2]):
                insertFile (args.inject[0])
        elif args.inject[1]=='nth' :
            if current_layer > 1 and (int(current_layer / int(args.inject[2]))) % 1 == 0:
                insertFile (args.inject[0])
        elif args.inject[1]=='zheight' :
            if layer_height >= float(args.inject[2]):
                insertFile (args.inject[0])
        elif args.split[1]=='line':
            if linenumber==args.split[2]:
                insertFile (args.inject[0])
                 
# add a layer header and LCD message
    if args.print_layer:
        conditional_comment("; --------------------------------------",True);
        current_output_line=current_output_line+1
        fo.write( lcd_comment_string + "Layer=" + str(current_layer)+ endquote+"\n")
        conditional_comment("; --------------------------------------",True);
        
#start of a new layer number:
    if has_raft==1 and args.cool_raft:
        if current_layer==2 or current_layer==3:
            print (Fore.MAGENTA + "Adding commands for easier raft removal")
            fan_speed = args.cool_raft[0]
            insertline("M106 S"+str(args.cool_raft[0])+conditional_comment(" ; fan on for raft layer removal",False),fo)
            override_fan_on_this_layer = 1
            override_fan_off_this_layer = 1
        if current_layer==3:
            droptemp = clamp ((args.temperature*ext_temperature)-args.cool_raft[1] ,  args.minimum_temperature,  args.maximum_temperature)
            insertline("M10"+get_t_code("4")+" S"+str(droptemp)+conditional_comment(" ; lowering temp for first object layer",False),fo)
        if current_layer==4:
            insertline("M10"+get_t_code("4")+ " S"+str(args.temperature*ext_temperature)+conditional_comment(" ; setting temp back to normal",False),fo)
            insertline("M107 "+conditional_comment("; fan off completely for second object layer!",False),fo)
            fan_speed =0
            print (Fore.MAGENTA +"Done processing commands for easier raft removal")
            override_fan_on_this_layer = 1
        
        
    if args.cool_bed and current_layer==args.cool_bed[1]:
        insertline("M1"+get_t_code("4",True)+"0 S"+str(int((args.bed*bed_temperature)-args.cool_bed[0]))+conditional_comment(" ; dropping bed temperature by "+str(args.cool_bed[1]),False),fo)
    return line    

# find which input  file has the lowest height 
def SetNextFile():
    global current_file, lines,fo, last_es,last_e
    if not lines: 
        current_file = -1
        return
    lowestz = 999999
    lowz_index = -1
    for fx in range (0,len(lines)):
        if lowestz > layer_heights[fx]:
            lowestz = layer_heights[fx]
            lowz_index = fx
    if lowz_index!=current_file:
        print (Fore.BLACK+Back.CYAN +"Switching input files")
        insertline (";  --------  Input switch to file " + str(lowz_index),fo) 
        last_es[current_file] = last_e
        last_e = last_es [lowz_index]
        insertline ('G92 E'+str(last_e) +conditional_comment (" ; recover stored e position"),fo)
    current_file = lowz_index
 
# ##################################################################
def QualitySetting(s):
    try:
        sp = s.split(',')
        qual  = sp[0]
        typ  = sp[1]
        val  = sp[2]
        print (Fore.BLACK+Back.WHITE+'Quality setting parsed as ' , qual, ' when ', typ ,' is ' ,val)
        return qual,typ,val
    except:
        raise argparse.ArgumentTypeError("Quality needs set of quality level, trigger type and trigger value (ie: path loop")
        
        
def setRGB_LED_by_path(loline):
    if (re.search("'?skirt'?",loline)):
        insertline ("M420 R220 E255 B64  "+conditional_comment (" ; set LED to Yellow"),fo)
        return
    if (re.search("'?_?wipe'?",loline)):
        insertline ("M420 R255 E128 B0 "+conditional_comment (" ; set LED to Orange"),fo)
        return
    if (re.search("'?crown'?",loline)):
        insertline ("M420 R255 E0 B255  "+conditional_comment (" ; set LED to Pink"),fo)
        return
    if (re.search("'?stacked sparse infill'?",loline)):
        insertline ("M420 R0 E128 B0  "+conditional_comment (" ; set LED to Dk Green"),fo)
        return
    if (re.search("'?sparse infill'?",loline) or re.search("'?infill'?",loline) ):
        insertline ("M420  R0 E255 B0  "+conditional_comment (" ; set LED to Green"),fo)
        return
    if (re.search("'?pillar'?",loline)):
        insertline ("M420 R255 E0 B0 "+conditional_comment (" ; set LED to Red"),fo)
        return
    if (re.search("'?raft'?",loline)):
        insertline ("M420 R255 E0 B0 "+conditional_comment (" ; set LED to Red"),fo)
        return
    if (re.search("'?support interface'?",loline)):
        insertline ("M420 R128 E128 B128 "+conditional_comment (" ; set LED to gray"),fo)
        return
    if (re.search("'?support'?",loline)):
        insertline ("M420 R255 E255 B255 "+conditional_comment (" ; set LED to white"),fo)
        return
    if (re.search("'?prime pillar'?",loline)):
        insertline ("M420 R128 E0 B255"+conditional_comment (" ; set LED to purple"),fo)
        return
    if (re.search("'?perimeter'?",loline) or re.search("wall-inner",loline)):
       insertline ("M420 R0 E255 B255 "+conditional_comment (" ; set LED to cyan"),fo)
       return
    if (re.search("'?solid'?",loline) or re.search("fill",loline)):
        insertline ("M420 R0 E0 B128 "+conditional_comment (" ; set LED to Dark Blue"),fo)
        return
    if (re.search("'?loop'?",loline) or re.search("wall-outer",loline)):
        insertline ("M420 R0 E64 B255  "+conditional_comment (" ; set LED to Lt Blue"),fo)
        return


def processFanAndTemps(line, fan_speed):
            global peak_bed_temperature, peak_ext_temperature
            fan_on = re.search ("^M106\s*S(\d*)",line)
            if fan_on:
                fan_speed = int(fan_on.group(1))
                if args.fan!=1.0:
                    newspeed = int(fan_speed*args.fan)
                    if newspeed > 255: 
                        newspeed = 255
                    if newspeed <0:
                        newspeed =0
                    insertline ("M106 S"+str(newspeed)+" ; existing fan speed " +fan_speed+", adjusted by x"+str(args.fan)+ " to " + newspeed,fo);
                    line = ""
                else:
                    print ("fan speed " + str(fan_speed))
                if override_fan_on_this_layer==1:
                    insertline ("; disabled fan on: " + line ,fo);
                    line = ""
            fan_off = re.search ("^M107.*",line)
            if fan_off:
                fan_speed = 0
                #print ("fan off")
                if override_fan_off_this_layer==1:
                    insertline ("; disabled fan off: " + line ,fo);
                    line=""
                
    #read the extr temperature                
            temp = re.search("^M10([49]) S(\d*)", line)
            if temp:                                            # disable temperature settings at start, the ultimaker job start will handle this.
                if args.ultimaker_out and linenumber < 10: 
                    insertline (conditional_comment ('; Disabled temp command: ' + str(line)),fo)
                    line = ""
                else: 
                    x = int(temp.group(2))
                    if x>0: 
                        ext_temperature = clamp(int(x*args.temperature), args.minimum_temperature, args.maximum_temperature)
                        print (Fore.WHITE+Back.RED + "Extruder temperature command:  " + str(x) + " adjusting to " + str(ext_temperature))
                        insertline ("M10"+get_t_code(temp.group(1))+" S"+str(ext_temperature)+" ; existing extruder temp command adjusted",fo)
                        if ext_temperature > peak_ext_temperature:
                            peak_ext_temperature = ext_temperature
                        line = ""
     #read the bed temperature  -- we'll need that to know what to set it to when we cool it down later in start layers
            temp = re.search("^M1([49])0 S(\d*)", line)
            if temp:
                if args.ultimaker_out and linenumber < 10: 
                    insertline (conditional_comment ('; Disabled bed temp command: ' + str(line)),fo)
                    line = ""
                else: 
                    x = int(temp.group(2))
                    bed_temperature = clamp(int (x * args.bed),0,120 )
                    print (Fore.WHITE+Back.BLUE+ "Bed temperature command:  " + str(x) + " adjusting to " + str(bed_temperature))
                    insertline ("M1"+get_t_code(temp.group(1),True)+"0 S"+str(bed_temperature)+" ; existing bed temp command, adjusted",fo)
                    if bed_temperature > peak_bed_temperature:
                        peak_bed_temperature = bed_temperature
                    line = ""
            return fan_speed, line

def main(argv):
   global layer_height,max_layer_height,linenumbers,current_file,lines,layer_heights,foo,foa,fo,output_relative_movement,relative_movement,linenumber,last_path_name,endquote,version_string,lcd_comment_string,bed_temperature,args,move_threshold,fan_speed,current_layer,override_fan_on_this_layer,override_fan_off_this_layer,has_raft,ext_temperature
   global peak_x, peak_y,peak_z,total_e,min_x,min_y, ETA,materialname,current_output_line,slic3r,cura,craftware, output_relative_extrusion,relative_extrusion,length_to_vol,peak_ext_temperature,peak_bed_temperature
   start_time = time.time()
   print ('\033[2J')
   #deal with the command line: 
   parser = argparse.ArgumentParser(description='Monkey around with GCode (especially from KISSlicer.  Cura, Craftware and Slic3r support not thoroughly tested)\nwritten by Lars Norpchen, http://www.octopusmotor.com')
   group1 = parser.add_argument_group( 'File input and output options')
   group1.add_argument('-i', '--input',required = True, metavar='filename',help='specify the input file to process')
   group1.add_argument('-o', '--output',required = False, metavar='filename',help='specify the output file to generate.  If not specified, output will overwrite the input file when done.')
   group1.add_argument('-umo','--ultimaker-out', action='store_true',help='Output Ultimaker G-Code (extrusion by volume)')
   group1.add_argument('-umi','--ultimaker-in' , action='store_true',help='Input file is Ultimaker G-Code (extrusion by volume)')
   
   group1.add_argument('--split', metavar=('filename', '(line, layer, zheight, nth, or path)','value'),nargs=3,   help='Split the file into a second file based on line number, layer, height or path type.  Nth is every N layers.')
   group1.add_argument('--inject', metavar=('filename', '(line, layer, zheight, nth, or path)','value'),nargs=3,  help='Insert the file snippet based on line number, layer, height or path type.   Nth is every N layers.  MUST use relative E coordindates and disable destringing in slicer')
   group1.add_argument('--merge',  metavar=('filename','additional files'), nargs='+', help='Merge the specified file(s). They will be interleaved by layer, sorted based on Z height.  MUST use relative E coordindates and disable destringing in slicer app \
                                    # (you can add retraction commands using the --retract option)') 
   group1.add_argument('--resume', metavar=('line, layer, or Zheight','value'),nargs=2,help='Resume an interrupted print from a given line, layer or ZHeight.\
                                            X, Y and Z positions will be set for you, \
                                            and you need to manually position the printer\'s Z height before resuming.  Line number is not recommended as it \
                                            is based on the input file, which may change position in the output file based on other post processing commands. ')
 
   group2 = parser.add_argument_group( 'Fan and Temperature control options')
   group2.add_argument('-f', '--fan', metavar='multiplier', type=float, default=1.0, help='Multiply all fan speeds by this.  This only affects fan speeds that were in the original file, not those fan speed commands added by options in this script')
   group2.add_argument('-t', '--temperature', metavar='multiplier', type=float, default=1.0, help='Multiply all extruder temperatures by this. ')
   group2.add_argument('-j', '--minimum-temperature', default = 170, metavar='degrees', type=int,  help='Enforce a minimum temperature for all extruder temperature settings (including raft cooling).  Will not override extruder off (temp=0) commands.')
   group2.add_argument('-n', '--maximum-temperature', default = 250, metavar='degrees', type=int,  help='Enforce a maximum temperature for all extruder temperature settings')
   group2.add_argument('--wait-temp', metavar=('none, first, or all'), choices=('none','all','first'), help='Wait for extruder temperature changes')
   group2.add_argument('--wait-bed-temp', metavar=('none, first, or all'), choices=('none','all','first'), help='Wait for bed temperature changes')
   group2.add_argument('-b', '--bed',  metavar='multiplier',type=float, default=1.0, help='Multiply all bed temps by this')
   group2.add_argument('-k', '--cool-bed',  type=int,nargs=2, metavar=('degrees', 'layer'), help='Slic3r / KISSlicer only. Decrease the bed temperature by DEGREES at specified LAYER')
   group2.add_argument('-q','--cool-support', metavar='fan_speed', type=int, default=0, help='Slic3r / KISSlicer only. Turns the fan on for all "Support Interface" paths. Fan speed is 0 - 255. ')
   group2.add_argument('-g','--cool-sparse-infill', metavar='fan_speed', type=int, default=0, help='Slic3r / KISSlicer only. Turns the fan on for all "Sparse Infill" paths. Fan speed is 0 - 255. ')
   group2.add_argument('-w','--cool-raft',  metavar=('fan_speed', 'temperaturedrop'), nargs=2, type=int, help='Slic3r / KISSlicer only. Adjusts the fan and extrusion temperature to make it easier to remove the raft.  \
                            Set the fan speed (0-255) and temperature reduction (in degrees) for first object layer')
   group2.add_argument('--filament',  metavar='mm',type=float, default=2.85, help='input file\'s assumed filament diameter -- for converting linear to volumetric extrusions')
   
   group3 = parser.add_argument_group( 'Movement control options')
   group3.add_argument('--quality', nargs="+", action='append', metavar=('quality_setting'), help='Adjust the print quality for a given key (path / layer / etc. -- only path type is supported at the moment).\
                          If supported in printer\'s firmware, this scales speed, acceleration and jerk values for each extrusion move  -- for example 1.0 is normal, 2.0 is half speed and 0.5 is double speed.  \
                          Multiple quality options can be set, with each of the three required settings for each option being comma separated (ie: --quality 2,0,path,loop 3.0,path,skirt 0.2,path,perimeter ) . ', dest="quality", type=QualitySetting)
   group3.add_argument('-d', '--decimate',type=float,metavar='mm', default=0, help='Drop XY movements smaller than this.  Useful to get rid of excessive "micromoves" that are below the printer\'s resolution.  Requires "--strip" option enabled to work')
   group3.add_argument('--movement', metavar=('abs or rel') ,choices=('abs','rel'),help='Convert / output all movement to use absolute or relative mode.' )
   group3.add_argument('--extrusion', metavar=('abs or rel') ,choices=('abs','rel'),help='Convert / output all extrusion to use absolute or relative mode.' )
   group3.add_argument('--scalex',  metavar='x',type=float, default=1.0, help='Scale all X movements by this.  Default is 1.0 (unchanged)')
   group3.add_argument('--scaley',  metavar='x',type=float, default=1.0, help='Scale all Y movements by this. Default is 1.0 (unchanged)')
   group3.add_argument('--scalez',  metavar='x',type=float, default=1.0, help='Scale all Z movements by this. Default is 1.0 (unchanged)')
   group3.add_argument('--scaleall',  metavar='x',type=float, default=1.0, help='Scale all X, Y and Z movements by this. Default is 1.0 (unchanged)')
   group3.add_argument('-x', '--xoffset',  metavar='mm',type=float, default=0, help='Offset all X movements by this.  Use only with absolute coordinate mode.')
   group3.add_argument('-y', '--yoffset', metavar='mm', type=float,  default=0,  help='Offset all Y movements by this.  Use only with absolute coordinate mode.')
   group3.add_argument('-z', '--zoffset', metavar='mm', type=float,  default=0,  help='Offset all Z movements by this.  Use only with absolute coordinate mode.')
   group3.add_argument('-r', '--feedrate', metavar='multiplier', type=float, default=1.0, help='Multiply all movement rates by this (X, Y, Z and Extruder)')
   group3.add_argument('-e', '--extrusion-flow' , metavar='multiplier', type=float,  default=1.0,  help='Multiply extrusion amount by this.')
   group3.add_argument('--precision' , metavar='decimal points', type=int,  default=-1,  help='Round XYZ movement to the given number of decimal points.  Extruder position E and arc definitions I / J are not rounded')
   group3.add_argument('--retract', metavar=('distance', 'speed','threshold'),nargs=3, help='Retract the filament a given number of mm for non-extrusion moves greater than the threshold (in mm).   Retraction speed is in F code feedrate (mm/min)')
   group3.add_argument('--report-move-times', action='store_true', help='Output the time in comment are for each move')
   group3.add_argument('--report-feedrates', action='store_true', help='Add comments showing  changes to feedrate in mm/s')
   group3.add_argument('--no-spaces', action='store_true', help='Remove unneed spaces in commands')
   group3.add_argument('--use-G10-G11', action='store_true', help='Replaces retraction and un-retract gcode with G10 / G11 for printer controlled retraction')
   
   
   group4 = parser.add_argument_group( 'Printer user interface options')
   group4.add_argument('-p', '--print-layer', action='store_true', help='Slic3r / KISSlicer only. Print the current layer number on the LCD display')
   group4.add_argument('-v', '--verbose', action='store_true', help='Slic3r / KISSlicer only. Show movement type comments on the LCD display.   This command can be risky on some machines because it adds a \
                                    lot of extra chatter to the user interface and may cause problems during printing.')
   group4.add_argument('-l','--LCD-command', default='M70', help='Set the G-Code M command for showing a message on the device display.  M117 for Marlin, M70 for ReplicatorG (default)')
   group4.add_argument('--progress', metavar =('GCode_header','lines'),nargs=2, help='Output progress percentage (based on input file lines) every N lines with the given GCode prefix / header (ie: M73 Q).  \
                                    Will not give proper values if you merge or insert or split files in the same pass. ')
   group4.add_argument('-c', '--colored-movements', action='store_true', help='Cura / Slic3r / KISSlicer only. Set RGB LED to show the path type using the M420 command (Makerbot).  \
                                                    This command can be risky on some machines because it adds a lot of extra chatter to the user interface and may cause problems during printing.')
   group4.add_argument('--quote-messages', action='store_true', help='LCD display commands will wrap quotes around the message')
   
   group5 = parser.add_argument_group( 'GCode comments options')
   group5.add_argument('--comments', metavar=('pad or remove'), choices=('pad','remove'),  help='Pad or remove comments from gcode file.  Pad adds an empty move command to the start of comment only lines. \
                                         Most hosts will not send comments to printer, however this can cause a line number mismatch between the original file and the printed file (which makes it harder to resume).')
   group5.add_argument('--no-header', action='store_true', help='Remove the header (all commands before the first layer command)')
   group5.add_argument('-m', '--move-header', type=int, default = 0, help='Moves the last X lines (slicing summary) at the end of the file to the head of the file.  KISSlicer uses 30 lines.')
   group5.add_argument('--description', action='store_true', help='Add metrics data to the system DESCRIPT.ION file for the output file')
   group5.add_argument('--metrics', action='store_true', help='Add comments with metrics data to end of the output file')
   group5.add_argument('--report-flow', action='store_true', help='Add comments to movement showing extrusion vs travel rate (micrometers of filament per mm of travel)')
 
   group5.add_argument('--keep_pre_resume', action='store_true', help='Keep movement commands as comments instead of deleting them')
   group5.add_argument('--leave_z_on_resume', action='store_true', help='Leave the Z height when resume (assume head already at proper Z')
 
  # group6 = parser.add_argument_group('group6', 'General options')
   parser.add_argument('-u','--replace', action='append', metavar=('original', 'replacement'), nargs=2, help='Replace a code with another code. Regex coding is supported (^ for beginning of line, etc).  Use ~ for space. \
                                Can be used to comment out codes by adding a ";" to  the code.')
   parser.add_argument('--version', action='version', version=version_string)
 
   group6 = group3.add_mutually_exclusive_group()
   group6.add_argument('--explicit',action='store_true', help='Force all coordinates to be listed in all G0/G1/G2/G3 commands')
   group6.add_argument('-s', '--strip', action='store_true', help='Strip redundant move command parameters. Saves a little space, should not change the result, in theory... use at your own risk!')
   group6.add_argument('--compress', action='store_true', help='Strip redundant move command parameters, remove spaces, turn off comments.  Makes a smaller file, less human readable, but still valid to the printer.')


    #todo:
        # add pause at layer X
        
   try: 
       args = parser.parse_args()
   except:
     #   parser.print_usage()
        exit()
   endquote = ''
   if args.quote_messages:
       endquote = '"'
   replace_existing_file=False
#   args.delete_pre_resume= 1
   
# compress argument sets a collection of settings for smallest output size   
   if args.compress:
        args.strip = True
        args.no_spaces = True
        args.comments = 'remove'
        args.decimate = 0.01
        if args.precision < 0: 
            args.precision=2
   else:
        if args.precision < 0:      # set a default
            args.precision=3
   
   inputfile=str.strip(args.input) #[0] 
   
   #volume to linear conversion -- R^2 * pi * length = mm ^ 3
   length_to_vol = args.filament / 2
   length_to_vol = length_to_vol * length_to_vol
   length_to_vol = length_to_vol * 3.141592
   
   if args.output:
       outputfile=str.strip(args.output) #[0]
   else:
       outputfile=None
   if not outputfile:
        outputfile=inputfile+".tmp"
        replace_existing_file=True
   lcd_comment_string =  args.LCD_command+" "+endquote
   args.cool_support = clamp (args.cool_support,0,255)
   args.cool_sparse_infill = clamp (args.cool_sparse_infill,0,255)
   if args.cool_raft:
        args.cool_raft[0] = clamp (args.cool_raft[0],0,255)
   altoutputfile=None
   foa = None
   if args.split:
       altoutputfile = args.split[0]

   if args.scaleall==None:
        args.scaleall= 1.0
   if args.scalex==None:
        args.scalex= 1.0
   if args.scaley==None:
        args.scaley= 1.0
   if args.scalez==None:
        args.scalez= 1.0
   args.scalex=args.scalex * args.scaleall
   args.scaley=args.scaley * args.scaleall
   args.scalez=args.scalez * args.scaleall
   
   
   print (Style.BRIGHT +  '-' * 80 )
   print ( args.quality)
   
   print (   Fore.BLACK+Back.GREEN + 'Input file is ['+ inputfile+']')
   if not replace_existing_file:
       print (Fore.BLACK+Back.YELLOW +'Output file is ['+outputfile+']')
   else:
       print (Fore.BLACK+Back.YELLOW + 'temp output file is [' +  outputfile +  "] which will replace input file when done.")
   fi = open(inputfile)
   fo = open(outputfile,"w")
   if altoutputfile:
        foa = open(altoutputfile,"w")
   foo= fo    
   lines.append (fi.readlines())
   linenumbers.append (0)
   layer_heights.append (0)
   last_es.append (0)
   print (Style.BRIGHT + 'Read ' +str(len(lines[(len (lines))-1])) + ' lines from ' + inputfile)
   print (Style.BRIGHT + '-' * 80 )
   fanspeedchanged=0
   endline = 1
   
   if args.merge:
        for mf in args.merge:
           # conditional_comment("; Start merging: " + mf,True);
            fm = open(str.strip(mf))
            buf = fm.readlines()
            lines.append (buf)
            linenumbers.append (0)
            layer_heights.append (0)
            last_es.append (0)
           # conditional_comment("; End merging: " + mf + " " + len(buf) +" Lines added" ,True);
            print (Style.BRIGHT + 'Read ' +str(len(lines[(len (lines))-1])) + ' lines from merge file: ' + mf )
            
   #OK, we're done with the parameters, let's do the work!
# start with a little header processing


   baseline_feedrate = args.feedrate  
   baseline_flowrate = args.extrusion_flow 

   if args.resume:
        args.resume[1] = float(args.resume[1])
        print (Style.BRIGHT + Fore.GREEN + "Resume mode: " + args.resume[0] + " at " + str(args.resume[1]))
   if args.move_header and args.move_header > 0:
       lines[0] = lines[0][-(args.move_header):] + lines[0]
       print ("Moving last "+str(args.move_header)+" lines to head of file.")
   blanklines = 0
   if args.ultimaker_out:
       blanklines=5
       #args.use_G10_G11=True
       print ("Converting to volumetric output E based on a filament dia of " + str(args.filament)      )
   if args.metrics:    
       blanklines=blanklines+25
   while blanklines>0:
       insertline (';' + ' ' * 100,fo)
       blanklines=blanklines-1
   if args.ultimaker_in:
       print ("Converting from volumetric input E based on a filament dia of 2.85")

   if args.movement:
       if args.movement=="abs" or args.movement =="absolute":
            insertline (conditional_comment ("; forced movement absolute mode",True),fo)
            insertline ('G90',fo)
            output_relative_movement = False
       if args.movement=="rel" or args.movement =="relative":
            insertline (conditional_comment ("; forced movement relative mode",True),fo)
            insertline ('G91',fo)
            output_relative_movement = True
    
   if args.extrusion:
       if args.extrusion=="abs" or args.extrusion =="absolute":
            insertline (conditional_comment ("; forced extrusion absolute mode",True),fo)
            insertline ('M82',fo)
            output_relative_extrusion = False
       if args.extrusion=="rel" or args.extrusion =="relative":
            insertline (conditional_comment ("; forced extrusion relative mode",True),fo)
            insertline ('M83',fo)
            output_relative_extrusion = True
   
        
    
#process the rest of the file
   current_file =0
   while (True): 
    
        if len(lines[current_file]) <= linenumbers[current_file]:
            del lines[current_file]
            SetNextFile()
            if current_file <0: 
                break

        line = lines[current_file][linenumbers[current_file]]

#   for line in lines[:-endline]:
        linenumbers[current_file] =  linenumbers[current_file]+1
        linenumber= linenumbers[current_file]
        
        if args.resume and args.resume[0]=="line" and args.resume[1] == linenumber:
            resume()
           
        if args.replace:
            for a in args.replace:
                    a[0]=re.sub("~"," ",a[0])
                    a[1]=re.sub("~"," ",a[1])
                    line = re.sub (a[0],a[1]+" ",line)
              #      print ("replacement " + a[0] + " with " + a[1])

#first, replace any * in comments as they get confused with checksums
# when we start echoing comments to the LCD display
        line = re.sub ("\*","-",line)
        line = re.sub ("\r"," ",line)
           
#read the fan speed since we may need to set it back later after messing with it
        fan_speed, line = processFanAndTemps(line,fan_speed)
            
#check if it's a G0 or G1 movement
        temp = re.search("^G[01]\s+", line)
        if temp:
            line = process_G1_movement (line,"G1")

#G2/G3 ARC movement CW, CCW            
        temp = re.search("^G2\s+", line)
        if temp:
             line = process_G1_movement (line,"G2")

        temp = re.search("^G3\s+", line)
        if temp:
            line = process_G1_movement (line,"G3")
            
        temp = re.search("^M82\s+", line)
        if temp:
            relative_extrusion = False
            if args.extrusion:
                line = "; " + line
            else:
                output_relative_extrusion = relative_extrusion
            
        temp = re.search("^M83\s+", line)
        if temp:
            relative_extrusion = True
            if args.extrusion:
                line = "; " + line
            else:
                output_relative_extrusion = relative_extrusion            
            
        temp = re.search("^G90\s+", line)
        if temp:
            relative_movement = False
            relative_extrusion = False
            if args.movement:
                line = "; " + line
            else:
                output_relative_movement = relative_movement
            
        temp = re.search("^G91\s+", line)
        if temp:
            relative_movement = True
            relative_extrusion = True
            if args.movement:
                line = "; " + line
            else:
                output_relative_movement = relative_movement

        temp = re.search("^G92\s", line)
        if temp:
            process_G92_G28_movement(line,True)
            if args.resume and args.resume[1] >0:
                if not args.keep_pre_resume: 
                    line = ""
                else:
                    line = "; " + line

        temp = re.search("^G28\s", line)
        if temp:
            process_G92_G28_movement(line,False)
            if args.resume and args.resume[1] >0:
                if not args.keep_pre_resume: 
                    line = ""
                else:
                    line = "; " + line

        temp = re.search("^G1[01]\s", line)
        if temp:                                                        # strip out the G10 & G11 retract commands if we haven't resumed yet
            if temp=="G10":
                retracted = True;
            if temp=="G11":
                retracted = False;
            
            if args.resume and args.resume[1] >0:
                if not args.keep_pre_resume:
                    line = ""
                else:
                    line = "; " + line

                
  
        # process comment lines:
        #now look for interesting comments, like the path type:        
        comment_tag = re.search(".*;\s+'+(.*)'+(.*)",line)
        if not comment_tag or not comment_tag.group(1):
            # try Slic3r format, which is a comment after every G move
            comment_tag = re.search("G\d\s.*;\s+(.+)",line)
        if not comment_tag or not comment_tag.group(1):
            # try Cura format
            comment_tag = re.search(";TYPE:\s?(.*)",line)
        if not comment_tag or not comment_tag.group(1):
            # try Craftware format
            comment_tag = re.search(";segType:\s?(.*)",line)
          
        if comment_tag and comment_tag.group(1):
            t_last_path_name = str.lower(comment_tag.group(1))
            
            # bypass some Slic3r movement comments that are not path types
            # and do a litle Slic3r->KISSSlicer translation
            if t_last_path_name.startswith("move to "):
                t_last_path_name = 'travel'
            if t_last_path_name.startswith("move inwards before travel"):
                t_last_path_name="wipe"
                
            if last_path_name!=str.lower(comment_tag.group(1)):
                # start a new path
                last_path_name = t_last_path_name
                if args.verbose:
                    insertline ((lcd_comment_string + last_path_name + +endquote),fo)
                
                print (Style.DIM  + 'Path type changed to ' + last_path_name + '          ' + Cursor.UP(1)+Cursor.BACK(40))    
                
                # CRAP.  Destring retraction is breaking isolating paths....
                if args.split and args.split[1]=='path': 
                    if str.lower(args.split[2]) in last_path_name:
                        switchOutput (False,"path is "+ args.split[2])
                    else:
                        switchOutput (True,"path is not "+ args.split[2])
                        
                        
                if args.inject and args.inject[1]=='path' : 
                    if str.lower(args.inject[2]) in last_path_name:
                        insertFile (args.inject[0])
                    
    #handle adding the fan commands to start / stop around specific path types      
                if current_layer > 5 and last_path_name=="support interface" and args.cool_support>0:
                    insertline("M106 S"+str(args.cool_support)+" ; fan on for support interface",fo)
                    args.feedrate = baseline_feedrate * 0.25
                 #   args.extrusion_flow = baseline_flowrate * 2
                 # can't change the flow on the fly without messing up absolute positioning of the E filament!
                 # would work in relative mode tho...
                    fanspeedchanged = 1
                elif current_layer > 5 and last_path_name=="sparse infill" and args.cool_sparse_infill>0:
                    insertline("M106 S"+str(args.cool_sparse_infill)+" ; fan on for sparse infill",fo)
                    args.feedrate = baseline_feedrate * 0.25
                 #   args.extrusion_flow = baseline_flowrate * 2
                    fanspeedchanged = 1
                else:
                    if fanspeedchanged==1:
                        insertline("M106 S"+str(int(fan_speed*args.fan))+" ; set fan speed back to last value",fo)
                        args.feedrate = baseline_feedrate
                        args.extrusion_flow = baseline_flowrate
                        fanspeedchanged=0
                #fo.write (line)
                #continue;
                
        
        # these are color codes for path type, unfortunately settingsetting the I2C BlinkM LED causes 
        # I2C lock ups if done too frequently during an active print job!!
        # however, these commands may work better on another machine that supports like M420 command, 
        # like the makerbot
                if args.colored_movements:
                    setRGB_LED_by_path(last_path_name)
                    
        # process the quality settings -- this is an additional field to the G0/G1 movement commands
        # that tell the printer what level of quality this move should have, based on path type
        if args.quality:
            for q in args.quality:
            #  print ('checking ' , q, ' -> ' ,q[0])
                if q[0][1]=='path':
                    if str.lower(q[0][2]) in last_path_name and delta_e >0:
                #      print ('match path ',last_path_name,' quality set to ',q[0][0])
                        line = re.sub ("G1","G1 Q"+q[0][0]+" ",line)

#check for the raft -- if it does and we have the cool-raft option enabled, we'll deal with it in the start layers function
        if has_raft==0:
            match = re.search("^;\s+'(Raft)|(Pillar)", line)
            #match = re.search(";.*[ _]raft", str.lower(line))      # was catching craftware
            if match: 
                has_raft = 1
                print (Style.BRIGHT + Fore.MAGENTA + "File has raft!")
                #fo.write (line)
                #continue;
            
 #check for the start / end of layer marker, etc,
 
 
        match = re.search(";\s+END_LAYER\S*\sz=([\-0-9.]*)", line)
        if match:
            v = match.group(1)
            layer_heights[current_file] = float(str(v))
            SetNextFile()

        match = re.search(";\s+BEGIN_LAYER\S*\sz=([\-0-9.]*)", line)
        if not match:
            # try to find slic3r's layer comment...
            match = re.search(";\s+move to next layer\S*\s\(([\-0-9.]*)\)", line)
            if match:
                if not slic3r : 
                    print ('This input file appears to come from slic3r')
                slic3r = True
        if not match:
            # try to find Cura's layer comment...
            match = re.search(";LAYER:\s*([\-0-9.]*)", line)
            if match:
                if not cura : 
                    print ('This input file appears to come from cura')
                cura = True
        if not match:
           # try to find Craftware's layer comment...
            match = re.search("; Layer *#([\-0-9.]*)", line)
            if match:
                if not craftware : 
                    print ('This input file appears to come from craftware')
                craftware = True
        if match:
     #       v = match.group(1)
     #       layer_height = float(str(v))
     #       if slic3r or cura:
                layer_height = last_z
                SetNextFile()
                line = startlayer (line)
            
        if args.print_layer:
            match = re.search(";\s+Estimated Build Time:\s*(.*)", line)
            if match:
                insertline(lcd_comment_string+"ETA "+match.group(1)+endquote,fo)
                ETA = match.group(1)
        match = re.search(";\s+material_name =\s*(.*)", line)
        if match:
            materialname = match.group(1)
    
           
        if args.comments=='remove':
            line=re.sub(";.*$","" ,line)
        if args.comments=='pad':
            comment = re.search("^;(.*)",line)
            if comment: 
                line='G0 ;' + comment.group(1) # + "\n"
        if args.progress and current_output_line>0:
            if current_output_line % int(args.progress[1]) == 0:
                percent = 100 * linenumber / len(lines[current_file])
                insertline (args.progress[0] + str(round(percent,2)),fo)
        line = line.rstrip()  
        if args.no_spaces:
            line = remove_non_comment_spaces(line)
        if len(line) > 1 and line!='\n' and line !='\r' and not args.no_header:
            fo.write (line+'\n')
            current_output_line=current_output_line+1

   current_layer = max (current_layer,1)
   net_layer_height = round(peak_z/current_layer,3)            
   print ('-'*20)
               
               
   if args.description:
       dec_file_path  = ntpath.dirname (outputfile)
       if dec_file_path:
           dec_file_path=dec_file_path+'\\'+'descript.ion'            
           dec_file = open (dec_file_path,"a")
           if dec_file: 
               dec_file.write ('"' + ntpath.basename (outputfile) +  '"'+ \
                                            ' Src: <' + ntpath.basename (inputfile) + '>' + \
                                            ' Time=' + str(ETA) +\
                                            ' Needs ' + str(round (total_e/1000,2))+'m of ' + materialname +' filament, '+\
                                            str(current_layer) + ' layers of ' + str(net_layer_height) + 'mm, ' + \
                                            'Size:' + str(round(peak_x-min_x,2)) + 'mm x ' + str(round(peak_y-min_y,2)) + 'mm x ' + str(peak_z) + 'mm high,  ' + \
                                            '\n')
               dec_file.close()
    
   fo.seek (0);
   #if this is UltiGCode output, we need to stick the header back in (now that we know stuff like length and time) 
   # we left a blank spot at the head of the file for this.    
   if args.ultimaker_out:

       insertline (';FLAVOR:UltiGCode',fo)
       insertline (';TIME: '+str(int(total_time)),fo)
       total_e1 = total_e # / length_to_vol;

       insertline (';MATERIAL: '+str(int (total_e1)),fo)
       insertline (';MATERIAL2: 0',fo)      #todo -- dual extrustion estimate
       insertline (';Layer_count: '+ str(current_layer),fo)
       insertline (";Generated with GCodePP "+version_string+" " + time.strftime("%c")+ " temps:" + str(peak_ext_temperature ) +"/" + str(peak_bed_temperature)+ "   ",fo)
       fo.write (';')
   
   if args.metrics:               
       print (Style.BRIGHT + ' done processing, adding metrics data')

       insertline (conditional_comment ("; ---------------------------------",True),fo)
       insertline (conditional_comment ("; Post processing report....",True),fo)
       insertline (conditional_comment ("; raw command line options: " + str(sys.argv),True),fo)
       insertline (conditional_comment ("; parsed command line options: " + str(args),True),fo)
       insertline (conditional_comment ("; original filename = " + inputfile,True),fo)
       insertline (conditional_comment ("; time of processing = " + time.strftime("%c"),True),fo)
       elapsed_time = time.time() - start_time
       insertline (conditional_comment ("; time to process = " + str(round(elapsed_time,2)) + ' seconds',True),fo)
       total_e1 = total_e
       if args.ultimaker_out:
            total_e1 = total_e / length_to_vol

       insertline (conditional_comment ("; filament used: " + str(round (total_e1/1000,3)) + "m  ( " + str(round (3.28084*total_e1/1000,3)) + " feet)",True),fo)
       insertline (conditional_comment ("; size_x : " + format(round(peak_x-min_x,2)) + "mm",True),fo)
       insertline (conditional_comment ("; size_y : " + format(round(peak_y-min_y,2)) + "mm",True),fo)
       insertline (conditional_comment ("; limit_x : " + str (min_x) + ' to ' + str(peak_x) + "mm",True),fo)
       insertline (conditional_comment ("; limit_y : " + str (min_y) + ' to ' + str(peak_y) + "mm",True),fo)
       
       insertline (conditional_comment ("; height : " + str(peak_z) + "mm",True),fo)
       insertline (conditional_comment ("; layer_count  : " + str(current_layer) ,True),fo)
       insertline (conditional_comment ("; layer_height  : " + str(net_layer_height) + "mm",True),fo)
       seconds =str( int (total_time % 60))
       minutes =str( int ((total_time / 60 ) % 60))
       hours  = str( int ( total_time / 3600))
       if (total_time % 60) < 10: 
        seconds = '0' + seconds
       if ((total_time / 60 ) % 60) < 10: 
        minutes = '0' + minutes
                      
       insertline (conditional_comment ("; crap time estimate = " + hours + "h "+ minutes + "m "+ seconds + 's',True),fo)

#       insertline (";Generated with GCodePP "+version_string+" " + time.strftime("%c")+ " temps:" + str(peak_ext_temperature ) +"/" + str(peak_bed_temperature)+ "   ",fo)
       insertline (";Generated by " + time.strftime("%c")+ " tmps:" + str(peak_ext_temperature ) +"/" + str(peak_bed_temperature)+ " time;"+hours + ": "+ minutes + ": "+ seconds,fo)
       insertline (';TIME: '+str(int(total_time)),fo)
       insertline (conditional_comment ("; ---------------------------------",True),fo)
   foo.close()
   if foa:
        foa.close()
   fi.close()
   print (Style.BRIGHT + '------------------------------------')

   if replace_existing_file:
        print (Style.BRIGHT + Fore.CYAN + "Replacing " + inputfile + " with " + outputfile) 
        os.remove (inputfile)
        os.rename (outputfile, inputfile)
    #    os.remove (outputfile)
   print (Style.BRIGHT + "Done. ", linenumber, " lines processed")
   if current_layer == 0: 
       print (Fore.RED + Style.BRIGHT+ "Warning -- No layer markers found!")
   else:
       print (current_layer," layers")
   print (max_layer_height," maximum z height")
   
   if args.resume and args.resume[1] > 0:
       print (Fore.RED + Style.BRIGHT+ "Warning -- resume did not find suitable location to restart...output file has no movement commands!")
       beep()
       
    


if __name__ == "__main__":
   main(sys.argv[1:])    