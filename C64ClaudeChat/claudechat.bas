10 rem c64 claude chat client - github.com/mblakemore/c64claude
20 print chr$(147) : rem clear screen
30 poke 53280,0 : poke 53281,0 : rem black screen
40 print chr$(5) : rem white text
50 gosub 7000 : rem draw frame and title

100 rem memory locations
110 mi = 49152 : rem incoming message at $c000 (49152)
120 mo = 49408 : rem outgoing message at $c100 (49408)
130 ms = 49664 : rem message status at $c200 (49664): 0=none, 1=chunk, 2=last chunk
140 gosub 1000 : rem initialize variables

150 rem display welcome message
160 ms$ = "welcome!"
170 pf$ = chr$(156) + "sys: " + chr$(5) : rem purple "sys:" prefix, white message
180 gosub 8000 : rem wrap the message with prefix

200 rem main loop
210 gosub 2000 : rem check for new incoming messages
220 gosub 3000 : rem input handling
230 goto 200

1000 rem initialize variables
1010 ln = 5    : rem chat display start line (after title and border)
1020 ml = 16   : rem max lines in history
1030 cl = ln   : rem current line
1040 dim ch$(ml-1) : rem chat history array (ml entries)
1045 dim wl$(9) : rem array for wrapped lines (up to 10 lines)
1050 for i = 0 to ml-1
1060 ch$(i) = ""
1070 next i
1080 in$ = ""  : rem input buffer
1090 ol = 0    : rem old length of incoming message
1095 mw = 30   : rem max width for display
1100 rem clear memory locations to prevent weird messages
1110 poke mi, 0 : rem clear incoming message buffer
1120 poke mo, 0 : rem clear outgoing message buffer
1130 poke ms, 0 : rem clear message status
1140 return

2000 rem check for new incoming messages
2010 l = peek(mi) : rem first byte is length
2020 if l = 0 or l = ol then return : rem no new message
2030 ms$ = ""
2040 for i = 1 to l
2050   ms$ = ms$ + chr$(peek(mi+i))
2060 next i
2070 gosub 4000 : rem add message to chat history with prefix
2080 ol = l
2090 return

3000 rem input handling
3010 poke 214, 22 : poke 211, 1 : sys 58732 : rem position cursor at start of input line

3040 rem display static prompt only when needed
3050 if peek(1024+(22*40)+2) <> 62 then poke 214, 22 : poke 211, 2 : sys 58732 : print " ";chr$(30);">"; : rem green prompt

3070 rem get keystroke
3080 get k$
3090 if k$ = "" then return
3100 if k$ = chr$(13) then gosub 5000 : return : rem enter key = send

3110 rem handle backspace more efficiently
3120 if k$ <> chr$(20) then goto 3210
3130 if len(in$) = 0 then return : rem prevent error if buffer empty
3140 in$ = left$(in$, len(in$)-1)
3150 rem move cursor back one space and erase that character
3160 cp = len(in$) + 5 : rem cursor position (prompt is 3 chars: space+>+space)
3170 poke 214, 22 : poke 211, cp : sys 58732
3180 print " ";
3190 poke 214, 22 : poke 211, cp : sys 58732
3200 return

3210 if k$ < chr$(32) or k$ > chr$(96+26) then return : rem filter non-printable
3220 if len(in$) >= 245 then return : rem prevent input overflow - limit to 245 chars

3230 rem add character to input buffer and display just that character
3240 cp = len(in$) + 5 : rem cursor position after prompt
3250 poke 214, 22 : poke 211, cp : sys 58732
3260 print chr$(30);k$; : rem print just the new character in green
3270 in$ = in$ + k$
3280 return

4000 rem add message to chat history (ms$ contains message)
4010 rem no need to truncate message here - word wrap will handle it
4020 pf$ = chr$(28) + "ai: " + chr$(5) : rem red "ai:" prefix, white message
4030 gosub 8000 : rem wrap the message with prefix
4040 return

5000 rem send message with fixed chunking support
5010 if len(in$) = 0 then return
5020 ms$ = in$ : rem store for display

5025 rem check for commands
5026 if left$(in$, 8) = "/border " then gosub 9000 : return
5030 
5040 rem send message in chunks of up to 100 characters
5050 cl = 100 : rem chunk length
5060 tc = int((len(in$)-1)/cl) + 1 : rem total chunks
5070 
5080 for c = 1 to tc
5090   sp = (c-1)*cl + 1 : rem start position for this chunk
5100   ed = c*cl : rem end position for this chunk
5110   if ed > len(in$) then ed = len(in$) : rem adjust end if needed
5120 
5130   ch$ = mid$(in$, sp, ed-sp+1) : rem extract this chunk
5140 
5150   rem set status byte: 1 = more chunks coming, 2 = last chunk
5160   if c < tc then poke ms, 1 else poke ms, 2
5170 
5180   rem store chunk length
5190   poke mo, len(ch$)
5200 
5210   rem store chunk characters
5220   for i = 1 to len(ch$)
5230     poke mo+i, asc(mid$(ch$,i,1))
5240   next i
5250 
5260   rem wait for chunk to be read (wait for mo length to be reset to 0)
5270   t = ti
5280   rem wait loop with shorter timeout (1 second)
5290   if peek(mo) = 0 then goto 5340
5300   if (ti-t) >= 60 then goto 5340
5310   rem minimal delay - just enough to prevent tight loop
5320   for d = 1 to 2 : next d
5330   goto 5290
5340 next c
5350 
5360 rem add message to chat history
5370 pf$ = chr$(158) + "you: " + chr$(5) : rem yellow "you:" prefix, white message
5380 gosub 8000 : rem wrap the message with prefix

5390 rem reset the input buffer
5400 in$ = ""

5410 rem clear input line efficiently
5420 poke 214, 22 : poke 211, 5 : sys 58732
5430 for i = 1 to 36 : print " "; : next i
5440 poke 214, 22 : poke 211, 5 : sys 58732
5442 for i = 1 to 40 : print " "; : next i
5444 poke 214, 23 : poke 211, 5 : sys 58732
5450 return

6000 rem display chat history
6010 rem redraw all borders first to ensure they're consistent
6015 print chr$(5);
6020 for i = 0 to ml-1
6035   rem draw left border
6040   poke 214, ln+i : poke 211, 1 : sys 58732
6050   print chr$(221);
6060   
6070   rem draw right border
6080   poke 214, ln+i : poke 211, 38 : sys 58732
6090   print chr$(221);
6100 next i

6110 rem clear content area only (not borders)
6120 for i = 0 to ml-1
6130   poke 214, ln+i : poke 211, 2 : sys 58732
6140   print " ";
6150   for j = 1 to 34
6160     print " ";
6170   next j
6180 next i

6190 rem now draw all non-empty lines
6200 for i = 0 to ml-1
6210   if ch$(i) <> "" then gosub 6500
6220 next i
6230 return

6500 rem subroutine to print a single line
6510 poke 214, ln+i : poke 211, 3 : sys 58732
6520 print ch$(i);
6530 return

7000 rem draw frame and title
7010 print chr$(147) : rem clear screen
7020 print chr$(144) : rem black background
7030 rem draw box with box drawing characters
7040 rem top left corner
7050 print chr$(5);" "; chr$(176);
7060 rem top horizontal line (36 characters)
7070 for i = 1 to 36
7080   print chr$(196);
7090 next i
7100 rem top right corner
7110 print chr$(174)
7120 rem title bar - left border
7130 print " "; chr$(221);
7140 rem title in light blue (centered)
7150 print chr$(154);"     c64 claude chat client ";chr$(5);"v1.0    ";chr$(221)
7180 rem separator line - left border
7190 print " "; chr$(221);
7200 rem separator line (36 characters)
7210 print " ";
7220 for i = 1 to 34
7230   print chr$(196);
7240 next i
7250 print " ";chr$(221)
7260 rem chat lines (16 empty lines for chat history)
7270 for i = 1 to 16
7280   print " "; chr$(221);" ";
7290   for j = 1 to 34
7300     print " ";
7310   next j
7320   print " ";chr$(221)
7330 next i
7340 rem bottom border - left corner
7350 print " "; chr$(173);
7360 rem bottom horizontal line (36 characters)
7370 for i = 1 to 36
7380   print chr$(196);
7390 next i
7400 rem bottom right corner
7410 print chr$(189)
7420 return

8000 rem word wrap routine
8010 tx$ = ms$ : rem message to wrap
8020 rem pf$ contains prefix with color codes
8022 mw = 32 : rem increased max characters per line 
8025 lc = 0 : rem line count
8030 cp$ = "    " : rem continuation prefix (4 spaces)

8040 rem clear temp array
8050 for i = 0 to 9 : wl$(i) = "" : next i

8100 rem calculate available space
8110 fl = mw - len(pf$) + 2 : rem add 2 to compensate for visual difference
8120 if fl <= 0 then fl = 1 : rem safety check

8130 rem handle first line
8140 if len(tx$) <= fl then wl$(0) = pf$ + tx$ : lc = 1 : goto 8600
8150 rem find break point for first line
8160 bp = fl
8170 for j = fl to 1 step -1
8180   if mid$(tx$, j, 1) = " " then bp = j : j = 0
8190 next j
8200 if bp = fl then bp = fl-1 : rem force break if needed

8210 wl$(0) = pf$ + left$(tx$, bp)
8220 lc = 1
8230 tx$ = mid$(tx$, bp + 1)

8300 rem handle continuation lines
8310 cl = mw - len(cp$) : rem continuation line length
8320 if cl <= 0 then cl = 1 : rem safety check

8400 rem continuation line processing loop
8410 if len(tx$) = 0 then goto 8600 : rem done
8420 if len(tx$) <= cl then wl$(lc) = cp$ + tx$ : lc = lc + 1 : goto 8600
8430 rem find word break
8440 bp = cl
8450 for j = cl to 1 step -1
8460   if mid$(tx$, j, 1) = " " then bp = j : j = 0
8470 next j
8480 if bp = cl then bp = cl-1 : rem force break if needed
   
8490 wl$(lc) = cp$ + left$(tx$, bp)
8500 lc = lc + 1
8510 tx$ = mid$(tx$, bp + 1)
8520 if lc < 10 then goto 8400 : rem continue if room

8600 rem shift history and add wrapped lines
8610 for i = 0 to ml-1-lc
8620   ch$(i) = ch$(i+lc)
8630 next i
8640 rem add all wrapped lines to history
8650 for i = 0 to lc-1
8660   ch$(ml-lc+i) = wl$(i)
8670 next i
8680 rem update display
8690 gosub 6000
8700 return

9000 rem border command handler - format: /border colorname
9010 rem check if there's a color name provided
9015 if len(in$) <= 8 then ms$ = "usage: /border <color name>" : goto 9250

9020 rem extract color name - skip "/border " (8 characters)
9030 cl$ = mid$(in$, 9)
9040 cl = -1 : rem default to -1 for not found

9050 rem match color name to corresponding code
9060 if cl$ = "black" then cl = 0
9070 if cl$ = "white" then cl = 1
9080 if cl$ = "red" then cl = 2
9090 if cl$ = "cyan" then cl = 3
9100 if cl$ = "purple" then cl = 4
9110 if cl$ = "green" then cl = 5
9120 if cl$ = "blue" then cl = 6
9130 if cl$ = "yellow" then cl = 7
9140 if cl$ = "orange" then cl = 8
9150 if cl$ = "brown" then cl = 9
9160 if cl$ = "light red" then cl = 10
9170 if cl$ = "dark gray" then cl = 11
9180 if cl$ = "medium gray" then cl = 12
9190 if cl$ = "light green" then cl = 13
9200 if cl$ = "light blue" then cl = 14
9210 if cl$ = "light gray" then cl = 15

9220 rem if color found, change border color
9230 if cl >= 0 then poke 53280, cl : ms$ = "border color changed to " + cl$
9240 if cl < 0 then ms$ = "unknown color: " + cl$

9250 rem add message to chat history
9260 pf$ = chr$(156) + "sys: " + chr$(5) : rem purple "sys:" prefix, white message
9270 gosub 8000 : rem wrap the message with prefix

9280 rem reset the input buffer
9290 in$ = ""

9300 rem clear input line efficiently
9310 poke 214, 22 : poke 211, 5 : sys 58732
9320 for i = 1 to 36 : print " "; : next i
9330 poke 214, 22 : poke 211, 5 : sys 58732
9340 for i = 1 to 40 : print " "; : next i
9350 poke 214, 23 : poke 211, 5 : sys 58732
9360 return