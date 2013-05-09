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
#
#
# April 30, 2013  (initial release) 
# May 3, 2013 -- Version 0.8.2 
# * Added min and max temperatures for extruder to keep adjusted temperatures in valid ranges
# * Changed fan option from 'Stacked Sparse Infill' to 'Sparse Infill'
# * added option to enclose LCD messages in quotes
# * bug fix on raft cooling
# May 6, 2013 -- version 0.8.3
# * made stacked infill and support interface cooling start after layer 5
# May 9, 2013 -- Version 0.8.5
# * Added support for relative movement
# * Added parsing of G92 and G28 commands
# * Added support for resume (experimental) 
# * Added ability to remove or pad comment lines
# * Changed the way -m works internally
# * Changed command line option --quote-comments to --quote-messages

# ##################################################################




import string
import re
import sys
import argparse

# ##################################################################
#globals
args =0
lcd_comment_string = ""
version_string = "%(prog)s 0.8.5"

# some state information
has_raft = 0

current_layer = 0
override_fan_on_this_layer = 0
override_fan_off_this_layer = 0
ext_temperature = 0
bed_temperature=0
fan_speed =0 

# these are used to detect redundant moves
last_x = -1
last_y = -1
last_e = -1
last_f = -1
last_z = -1
#these can be used to determine head speed as well...
delta_x = 0
delta_y = 0
delta_e = 0
delta_f = 0
delta_z = 0
endquote=''
last_path_name = ''
relative_movement = False
linenumber = 0
output_relative_movement = False
#unused at the moment...
last_layer = ""

def clamp(n, minn, maxn):
    return max(min(maxn, n), minn)
    
# ##################################################################
# insertline
# writes a line to the output file and echos it to the console
def insertline (line, fo):
    fo.write (line + "\n") 
    print (line)
        

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

def process_G1_movement (line):
    global delta_x, delta_y, delta_e, delta_z, delta_f
    global last_x, last_y, last_e, last_z, last_f
    global args ,endquote,relative_movement,output_relative_movement
    use_x = args.strip==False    
    Xcoordindates = re.search("X([\+\-0-9\.]*)",line) 
    if Xcoordindates:
        X = float(Xcoordindates.group(1))
        if relative_movement:
            X = last_x + X
        delta_x = X - last_x 
        if abs(delta_x) > args.decimate:
            use_x = 1
            last_x = last_x + delta_x
    else:
        use_x = 0
            
            
    use_y = args.strip==False 
    Ycoordindates = re.search("Y([\+\-0-9\.]*)",line) 
    if Ycoordindates:
        Y = float(Ycoordindates.group(1))
        if relative_movement:
            Y = last_y + Y
        delta_y = Y - last_y 
        if abs(delta_y) > args.decimate:
            use_y = 1
            last_y = last_y + delta_y
    else:
        use_y = 0
            

    use_e = args.strip==False    
    Ecoordindates = re.search("E([\+\-0-9\.]*)",line) 
    if Ecoordindates:
        E = float(Ecoordindates.group(1))
        if relative_movement:
            E = last_e + E
        delta_e = E - last_e 
        if E!=last_e:
            use_e = 1
            delta_e = E-last_e
            last_e = last_e  + delta_e
    else:
        use_e = 0
        
    use_z = args.strip==False   
    Zcoordindates = re.search("Z([\+\-0-9\.]*)",line) 
    if Zcoordindates:
        Z = float(Zcoordindates.group(1))
        if relative_movement:
            Z = last_z + Z
        delta_z = Z - last_z
        if Z!=last_z:
            use_z = 1
            delta_z = Z-last_z 
            last_z = last_z + delta_z
    else:
        use_z = 0
        
    use_f = 0
    Feed = re.search("F([\+\-0-9\.]*)",line) 
    if Feed:
    # always use F is given -- need to investigate if it's proper to strip this out!            
        use_f = 1   
        F = float(Feed.group(1))
        if F!=last_f:
#            use_f = 1
            delta_f = last_f - F
            last_f = F
    else:
        use_f = 0

    # rebuild the G1 command
    if use_x==0 and use_y==0 and use_e==0 and use_z==0 and use_f==0:
        return ""
    line = "G1" 
    if output_relative_movement==False:
        if use_x==1:
            line = line + " X" + "{0:.5g}".format((last_x + args.xoffset) )
        if use_y==1:
            line = line + " Y" +"{0:.5g}".format((last_y + args.yoffset)) 
        if use_z==1:
            line = line + " Z" +"{0:.5g}".format(last_z) 
        if use_e==1:
            line = line + " E" +"{0:.6g}".format(last_e * args.extrusion_flow)
    else:
        if use_x==1:
            line = line + " X" + "{0:.5g}".format((delta_x + args.xoffset) )
            args.xoffset = 0
        if use_y==1:
            line = line + " Y" +"{0:.5g}".format((delta_y + args.yoffset)) 
            args.yoffset = 0 
        if use_z==1:
            line = line + " Z" +"{0:.5g}".format(delta_z) 
        if use_e==1:
            line = line + " E" +"{0:.6g}".format(delta_e * args.extrusion_flow)
        
    if Feed:    
        line = line + " F" +"{0:.6g}".format(last_f * args.feedrate)  
    if args.resume > 0:
        line = "; " + line
    return line + "\n"
    
    
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
            last_x = float(Xcoordindates.group(1))
        else:
            last_x = 0
    Ycoordindates = re.search("Y([\+\-0-9\.]*)",line) 
    if Ycoordindates:
        axis_found = True
        if isG92:
            last_y = float(Ycoordindates.group(1))
        else:
            last_y = 0
            
    Zcoordindates = re.search("Z([\+\-0-9\.]*)",line) 
    if Zcoordindates:
        axis_found = True
        if isG92:
            last_z = float(Zcoordindates.group(1))
        else:
            last_z = 0
            
    Ecoordindates = re.search("E([\+\-0-9\.]*)",line) 
    if Ecoordindates:
        axis_found = True
        if isG92:
            last_e = float(Ecoordindates.group(1))
        else:
            last_e = 0
# a G28 or G92 with no axes will home / reset ALL axes            
    if axis_found==False:
        last_x = last_y= last_e = last_z = 0

        
# adjust a comment based on the comment stripping / padding command    
def conditional_comment (str,start_of_line):
    global args    
    if args.comments=='remove':
        return ""
    rv = str
    if args.comments=='pad' and start_of_line:
        rv = "G0 " + str
    if rv[-1] =='\n':
        return rv
    return rv + "\n"
    
# #################################################################
# startlayer (string, outputfile) 
# returns the modified line string
#
# do things that happen only when a certain layer starts
# 
# 1. Print the layer number on the LCD
# 2. Do the magic raft cooling trick
# 3. Cool the bed at a certain layer

def startlayer (line, fo): 
    global linenumber,last_path_name,endquote,fan_speed,args,bed_temperature,current_layer,override_fan_on_this_layer,override_fan_off_this_layer,has_raft,ext_temperature,lcd_comment_string
    current_layer = current_layer + 1
    print ("---------------------\nProcessing layer # " , current_layer , " starting on line " ,linenumber)
    override_fan_on_this_layer = 0
    override_fan_off_this_layer = 0
# add a layer header and LCD message
    if args.print_layer:
        conditional_comment("; --------------------------------------",True);
        fo.write( lcd_comment_string + "Layer=" + str(current_layer)+ endquote+"\n")
        conditional_comment("; --------------------------------------",True);
        
#start of a new layer number:
    if has_raft==1 and args.cool_raft:
        if current_layer==2 or current_layer==3:
            print ("Adding commands for easier raft removal")
            fan_speed = args.cool_raft[0]
            insertline("M106 S"+str(args.cool_raft[0])+conditional_comment(" ; fan on for raft layer removal",False),fo)
            override_fan_on_this_layer = 1
            override_fan_off_this_layer = 1
        if current_layer==3:
            droptemp = clamp ((args.temperature*ext_temperature)-args.cool_raft[1] ,  args.minimum_temperature,  args.maximum_temperature)
            insertline("M104 S"+str(droptemp)+conditional_comment(" ; lowering temp for first object layer",False),fo)
        if current_layer==4:
            insertline("M104 S"+str(args.temperature*ext_temperature)+conditional_comment(" ; setting temp back to normal",False),fo)
            insertline("M107 "+conditional_comment("; fan off completely for second object layer!",False),fo)
            fan_speed =0
            print ("Done processing commands for easier raft removal")
            override_fan_on_this_layer = 1
        
        
    if args.cool_bed:
        if current_layer==args.cool_bed[1]:
            insertline("M140 S"+str(int((args.bed*bed_temperature)-args.cool_bed[0]))+conditional_comment(" ; dropping bed temperature by "+str(args.cool_bed[1]),False),fo)
    return line    

# ##################################################################
  
def main(argv):
   global output_relative_movement,relative_movement,linenumber,last_path_name,endquote,version_string,lcd_comment_string,bed_temperature,args,move_threshold,fan_speed,current_layer,override_fan_on_this_layer,override_fan_off_this_layer,has_raft,ext_temperature

   
   #deal with the command line: 
   parser = argparse.ArgumentParser(description='Monkey around with GCode (especially from KISSlicer)\rwritten by Lars Norpchen, http://www.octopusmotor.com')
   parser.add_argument('-i', '--input',required = True, metavar='filename',help='specify the input file to process')
   parser.add_argument('-o', '--output',required = True, metavar='filename',help='specify the output file to generate')
   parser.add_argument('-s', '--strip', action='store_true', help='Strip redundant move command parameters. Saves a little space, should not change the result, in theory... use at your own risk!')
   parser.add_argument('-d', '--decimate',type=float,metavar='mm', default=0, help='Drop XY movements smaller than this.  Useful to get rid of excessive "micromoves" that are below the printer\'s resolution.  Requires "--strip" option enabled to work')
   parser.add_argument('-u','--replace', action='append', metavar=('original', 'replacement'), nargs=2, help='Replace a code with another code. Regex coding is supported (^ for beginning of line, etc). Can be used to comment out codes by adding a ";" to  the code.')
   parser.add_argument('-f', '--fan', metavar='multiplier', type=float, default=1.0, help='Multiply all fan speeds by this.  This only affects fan speeds that were in the original file, not those fan speed commands added by options in this script')
   parser.add_argument('-t', '--temperature', metavar='multiplier', type=float, default=1.0, help='Multiply all extruder temperatures by this. ')
   parser.add_argument('-j', '--minimum-temperature', default = 170, metavar='degrees', type=int,  help='Enforce a minimum temperature for all extruder temperature settings (including raft cooling).  Will not override extruder off (temp=0) commands.')
   parser.add_argument('-n', '--maximum-temperature', default = 250, metavar='degrees', type=int,  help='Enforce a maximum temperature for all extruder temperature settings')
   parser.add_argument('-b', '--bed',  metavar='multiplier',type=float, default=1.0, help='Multiply all bed temps by this')
   parser.add_argument('-k', '--cool-bed',  type=int,nargs=2, metavar=('degrees', 'layer'), help='KISSlicer only. Decrease the bed temperature by DEGREES at specified LAYER')
   parser.add_argument('-q','--cool-support', metavar='fan_speed', type=int, default=0, help='KISSlicer only. Turns the fan on for all "Support Interface" paths. Fan speed is 0 - 255. ')
   parser.add_argument('-g','--cool-sparse-infill', metavar='fan_speed', type=int, default=0, help='KISSlicer only. Turns the fan on for all "Sparse Infill" paths. Fan speed is 0 - 255. ')
   parser.add_argument('-w','--cool-raft',  metavar=('fan_speed', 'temperaturedrop'), nargs=2, type=int, help='KISSlicer only. Adjusts the fan and extrusion temperature to make it easier to remove the raft.  Set the fan speed (0-255) and temperature reduction (in degrees) for first object layer')
   parser.add_argument('-x', '--xoffset',  metavar='mm',type=float, default=0, help='Offset all X movements by this.  Use only with absolute coordinate mode.')
   parser.add_argument('-y', '--yoffset', metavar='mm', type=float,  default=0,  help='Offset all Y movements by this.  Use only with absolute coordinate mode.')
   parser.add_argument('-r', '--feedrate', metavar='multiplier', type=float, default=1.0, help='Multiply all movement rates by this (X, Y, Z and Extruder)')
   parser.add_argument('-e', '--extrusion-flow' , metavar='multiplier', type=float,  default=1.0,  help='Multiply extrusion amount by this.')
   parser.add_argument('-m', '--move-header', action='store_true', help='KISSlicer only. Moves the slicing summary at the end of the file to the head of the file')
   parser.add_argument('-p', '--print-layer', action='store_true', help='KISSlicer only. Print the current layer number on the LCD display')
   parser.add_argument('-v', '--verbose', action='store_true', help='KISSlicer only. Show movement type comments on the LCD display.   This command can be risky on some machines because it adds a lot of extra chatter to the user interface and may cause problems during printing.')
   parser.add_argument('-l','--LCD-command', default='M70', help='Set the G-Code M command for showing a message on the device display.  M117 for Marlin, M70 for ReplicatorG (default)')
   parser.add_argument('-c', '--colored-movements', action='store_true', help='KISSlicer only. Set RGB LED to show the KISSlicer path type using the M420 command (Makerbot).  This command can be risky on some machines because it adds a lot of extra chatter to the user interface and may cause problems during printing.')
   parser.add_argument('--quote-messages', action='store_true', help='LCD display commands will wrap quotes around the message')
   parser.add_argument('--resume', type=int, metavar='line', default=-1,help='Resume an interrupted print from a given line number. X and Y position will be set for you, but you need to manually position the printer\'s Z height before resuming.  Line number is in the input file, which may change position in the output file based on other post processing commands. ')
   parser.add_argument('--movement', metavar=('abs or rel') ,help='Output all movement to use absolute or relative mode.' )
   parser.add_argument('--comments', metavar=('pad or remove'), default='none', help='Pad or remove comments from gcode file.  Pad adds an empty move command to the start of comment only lines.  Most hosts will not send comments to printer, however this can cause a line number mismatch between the original file and the printed file (which makes it harder to resume).')
   parser.add_argument('--version', action='version', version=version_string)
    
   args = parser.parse_args()

   endquote = ''
   if args.quote_messages:
        endquote = '"'
    
   inputfile=args.input #[0] 
   outputfile=args.output #[0]
   lcd_comment_string =  args.LCD_command+" "+endquote
   args.cool_support = clamp (args.cool_support,0,255)
   args.cool_sparse_infill = clamp (args.cool_sparse_infill,0,255)
   if args.cool_raft:
        args.cool_raft[0] = clamp (args.cool_raft[0],0,255)
       

   print ('------------------------------------')
 
   print ('Input file is "', inputfile)
   print ('Output file is "', outputfile)
   fi = open(inputfile)
   fo = open(outputfile,"w")
   lines = fi.readlines()
   print ('------------------------------------')
   fanspeedchanged=0
   endline = 1
   
   #OK, we're done with the parameters, let's do the work!
# start with a little header processing

   if args.move_header:
       lines = lines[-30:] + lines
   
   linenumber = 0
   if args.movement:
       if args.movement=="abs" or args.movement =="absolute":
            insertline (conditional_comment ("; forced movement absolute mode",True),fo)
            insertline ('G90',fo)
            output_relative_movement = False
       if args.movement=="rel" or args.movement =="relative":
            insertline (conditional_comment ("; forced movement relative mode",True),fo)
            insertline ('G91',fo)
            output_relative_movement = True
            
#process the rest of the file
   for line in lines[:-endline]:
        linenumber= linenumber+1
        if args.resume == linenumber:
            args.resume = -1
            insertline (conditional_comment ("; -------------- reset to resume",True),fo)
            print ("Resuming at line " , linenumber)
            if args.print_layer:
               insertline( lcd_comment_string + " Resuming layer " + str(current_layer)+ endquote,fo)

            #resuming print -- set the XY to home, then to the start pos
            insertline ('G28 X0 Y0',fo)
            insertline ('G1 X'+str(last_x) + " Y"+str(last_y) ,fo)
            #  reset the Z and E coordinates to where we left off, without moving them
            insertline ('G92 Z'+str(last_z) + " E"+str(last_e),fo)
            insertline ('G1 F'+str(last_f),fo)
            insertline (conditional_comment ("; ----------------- RESUMING HERE",True),fo)
           
        if args.replace:
            for a in args.replace:
                line = re.sub (a[0],a[1]+" ",line)

#first, replace any * in comments as they get confused with checksums
# when we start echoing comments to the LCD display
        line = re.sub ("\*","-",line)
#get rid of multiple whitespace        
#        line = re.sub ("\s\s*$"," ",line)
            
#read the fan speed since we may need to set it back later after messing with it
        fan_on = re.search ("^M106\s*S(\d*)",line)
        if fan_on:
            fan_speed = int(fan_on.group(1))
            if args.fan!=1.0:
                newspeed = int(fan_speed*args.fan)
                if newspeed > 255: 
                    newspeed = 255
                if newspeed <0:
                    newspeed =0
                insertline ("M106 S"+str(newspeed)+" ; existing fan speed command, adjusted by x"+str(args.fan),fo);
                line = ""
            else:
                print ("fan speed " + str(fan_speed))
            if override_fan_on_this_layer==1:
                insertline ("; disabled fan on: " + line ,fo);
                line = ""
        fan_off = re.search ("^M107.*",line)
        if fan_off:
            fan_speed = 0
            print ("fan off")
            if override_fan_off_this_layer==1:
                insertline ("; disabled fan off: " + line ,fo);
                line=""
            
#read the extr temperature                
        temp = re.search("^M10([49]) S(\d*)", line)
        if temp:
            x = int(temp.group(2))
            if x>0: 
                ext_temperature = clamp(int(x*args.temperature), args.minimum_temperature, args.maximum_temperature)
                print ("Extruder temperature command:  " + str(x) + " adjusting to " + str(ext_temperature))
                if args.temperature!=1.0 or ext_temperature!=x:
                    insertline ("M10"+temp.group(1)+" S"+str(ext_temperature)+" ; existing extruder temp command adjusted",fo)
                    line = ""
 #read the bed temperature  -- we'll need that to know what to set it to when we cool it down later in start layers
        temp = re.search("^M1([49])0 S(\d*)", line)
        if temp:
            x = int(temp.group(2))
            bed_temperature = clamp(int (x * args.bed),0,120 )
            print ("Bed temperature command:  " + str(x) + " adjusting to " + str(bed_temperature))
            if args.bed!=1.0  or bed_temperature!=x:
                insertline ("M1"+temp.group(1)+"0 S"+str(bed_temperature)+" ; existing bed temp command, adjusted",fo)
                line = ""
            
#check if it's a G1 movement
        temp = re.search("^G[01]\s+", line)
        if temp:
            line = process_G1_movement (line)
            
        temp = re.search("^G90\s+", line)
        if temp:
            relative_movement = False
            if args.movement:
                line = "; " + line
            else:
                output_relative_movement = relative_movement
            
        temp = re.search("^G91\s+", line)
        if temp:
            relative_movement = True
            if args.movement:
                line = "; " + line
            else:
                output_relative_movement = relative_movement

                

        temp = re.search("^G92\s", line)
        if temp:
            process_G92_G28_movement(line,True)
            if args.resume > 0:
                line = "; " + line

        temp = re.search("^G28\s", line)
        if temp:
            process_G92_G28_movement(line,False)
            if args.resume > 0:
                line = "; " + line

            
            
# process comment lines:
        #now look for interesting comments, like the path type:        
        comment_tag = re.search("^;\s+'(.*)'(.*)",line)
        if comment_tag:
            last_path_name = comment_tag.group(1)
            if args.verbose:
                insertline ((lcd_comment_string + last_path_name + +endquote),fo)
                
#handle adding the fan commands to start / stop around specific path types             
            if current_layer > 5 and last_path_name=="Support Interface" and args.cool_support>0:
                insertline("M106 S"+str(args.cool_support)+" ; fan on for support interface",fo)
                fanspeedchanged = 1
            elif current_layer > 5 and last_path_name=="Sparse Infill" and args.cool_sparse_infill>0:
                insertline("M106 S"+str(args.cool_sparse_infill)+" ; fan on for sparse infill",fo)
                fanspeedchanged = 1
            else:
                if fanspeedchanged==1:
                    insertline("M106 S"+str(int(fan_speed*args.fan))+" ; set fan speed back to last value",fo)
                    fanspeedchanged=0
            #fo.write (line)
            #continue;
            
#check for the raft -- if it does and we have the cool-raft option enabled, we'll deal with it in the start layers function
        if has_raft==0:
#            match = re.search("^;\s+'(Raft)|(Pillar)", line)
            match = re.search("^;\s+BEGIN_LAYER_RAFT", line)
            if match: 
                has_raft = 1
                print ("File has raft!")
                #fo.write (line)
                #continue;
            
 #check for the start of layer marker
        match = re.search("BEGIN_LAYER", line)
        if match:
            line = startlayer (line, fo)
            
        if args.print_layer:
            match = re.search("^; Estimated Build Time:\s*(.*)", line)
            if match:
                insertline(lcd_comment_string+"ETA: "+match.group(1)+endquote,fo)

    
# these are color codes for path type, unfortunately setting the I2C BlinkM LED causes 
# I2C lock ups if done too frequently during an active print job!!
# however, these commands may work better on another machine that supports like M420 command, 
# like the makerbot
        if args.colored_movements:
            line=re.sub("; 'Perimeter'","M420 R0 E255 B255 ; perimeter" ,line)
            line=re.sub("; 'Wipe (and De-string)'","M420 R255 E128 B0 ; wipe " ,line)
            line=re.sub("; 'Solid'","M420 R0 E0 B128 ; solid " ,line)
            line=re.sub("; 'Loop'","M420 R0 E64 B255 ; loop " ,line)
            line=re.sub("; 'Skirt'","M420 R220 E255 B64 ; skirt " ,line)
            line=re.sub("; 'Crown'","M420 R255 E0 B255 ; Crown " ,line)
            line=re.sub("; 'Stacked Sparse Infill'","M420 R0 E128 B0 ; Stacked Sparse Infill " ,line)
            line=re.sub("; 'Sparse Infill'","M420 R0 E255 B0 ; Sparse Infill " ,line)
            line=re.sub("; 'Pillar'","M420 R255 E0 B0 ; Pillar " ,line)
            line=re.sub("; 'Raft'","M420 R255 E0 B0 ; Raft " ,line)
            line=re.sub("; 'Support Interface'","M420 R128 E128 B128 ; Support Interface " ,line)
            line=re.sub("; 'Support Base'","M420 R255 E255 B255 ; Support Base " ,line)
            line=re.sub("; 'Prime Pillar'","M420 R128 E0 B255 ; Prime Pillar ",line)
        
           
        if args.comments=='remove':
            line=re.sub(";.*$","" ,line)
        if args.comments=='pad':
            comment = re.search("^;(.*)",line)
            if comment: 
                line='G0 ;' + comment.group(1) + "\n"
            
        if line!='\n':
            fo.write (line)
 
   fo.close()
   fi.close()
   print ("Done. ", linenumber, " lines processed")
    


if __name__ == "__main__":
   main(sys.argv[1:])    