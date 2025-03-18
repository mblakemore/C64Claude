# Commodore 64 BASIC Code Formatting Guide

## Character Set Fundamentals

The C64 uses PETSCII (PET Standard Code of Information Interchange) which is fundamentally different from ASCII:

10 print chr$(147)
120 let c=int(25*rnd(0))+1
130 let z=asc("z")
135 print "enter your message and i will code it"
136 print
137 print "use a ";chr$(34);":";chr$(34);" to end code."
138 print
140 get a$:if a$="" then 140


## 1. Case Sensitivity Reversal

- **Lowercase in quotes**: `print "hello world"` displays as `HELLO WORLD`
- **Uppercase in quotes**: `print "HELLO WORLD"` displays as graphic symbols
- This reversal exists because on a physical C64, the default keyboard mode is uppercase

## 2. BASIC Keywords

- Keywords can be entered in any case - they'll be tokenized the same
- Examples: `print`, `PRINT`, or `Print` all tokenize to the same BASIC token
- For readability, consistently use lowercase: `print`, `goto`, `if`, etc.

## 3. Control Characters

Use `CHR$()` for control characters instead of embedding actual control codes:

Clear screen: chr$(147) - Clears the screen
Home: chr$(19) - Moves cursor to top-left
Cursor down: chr$(17) - Moves cursor down one line
Cursor right: chr$(29) - Moves cursor right one space
Reverse on: chr$(18) - Enables reverse video
Reverse off: chr$(146) - Disables reverse video

## 4. Color Codes

Set text colors with `CHR$()` instead of using color controls directly:


10 print chr$(144) "black text"
20 print chr$(5) "white text"
30 print chr$(28) "red text"
40 print chr$(30) "green text"
50 print chr$(31) "blue text"


## 5. Special Characters

- Quote marks in strings: `chr$(34)` - Example: `"he said "chr$(34)"hello"chr$(34)`
- Pi symbol: Use `~` in your code - it will display as π on the C64
- Graphic characters: Can't be easily typed on modern keyboards - use CHR$() values

## 6. Program Structure

- **Line Numbers**: Always increment by 10 (10, 20, 30...) to allow later insertions
- **Multiple Statements**: Separate with colon `:` - Example: `10 print "hi":goto 10`
- **Abbreviations**: While BASIC keywords can be abbreviated (P SHIFT+R for PRINT), avoid these for readability

## 7. Memory Considerations

- The C64 has limited memory (38911 bytes free on startup)
- Keep variable names short (1-2 characters is efficient)
- Reuse variables when possible
- Remember that REM statements take memory - use sparingly

## 8. Display Constraints

- The C64 screen is 40 columns × 25 rows
- Long string output may wrap awkwardly
- Consider your screen layout carefully in interactive programs

## 9. DATA Statements

- DATA statements are tokenized differently - everything after DATA is treated as raw data
- Example: `100 data hello, world, 123, "quotes ok"`

## 10. REM Statements

- Like DATA, text in REM statements is not tokenized
- Use lowercase in REM statements for readability
- Example: `200 rem this is a comment`

## 11. PETSCII vs. Screen Codes

When POKEing directly to screen memory:
- Screen codes are different from PETSCII
- Uppercase/lowercase reversed compared to PETSCII
- POKEing 1 to screen memory shows 'A', not ASCII 1

## 12. Symbol Characters

- Many C64 graphic symbols are created using SHIFT or Commodore key + letter
- Represent these with CHR$() values
- Border characters (for UI): Use CHR$() values 176-191 for box drawing characters

## 13. String Handling

- C64 strings are limited to 255 characters
- String variables end with $ (A$, NAME$, etc.)
- String concatenation is processor-intensive - minimize in tight loops

## 14. Tokenization Awareness

- BASIC statements are stored as tokens, not the text you type
- Keywords use a single byte (or sometimes two for extensions)
- This saves memory but means formatting in your code doesn't affect the program size

## 15. Abbreviations to Avoid

The tokenizer allows abbreviations (like ? for PRINT) but avoid these for readability:
- Use `print` not `?`
- Use `goto` not `g` + SHIFT-O
- Use `input` not `i` + SHIFT-N

## 16. Statements to Avoid

C64 doesn't use do/loop/else/endif statements.

## Common Control Code Reference

Clear Screen: chr$(147) - $93
Home: chr$(19) - $13
Cursor Down: chr$(17) - $11
Cursor Up: chr$(145) - $91
Cursor Left: chr$(157) - $9D
Cursor Right: chr$(29) - $1D
Insert: chr$(148) - $94
Delete: chr$(20) - $14
Return: chr$(13) - $0D

## Color Code Reference

Black: chr$(144) - $90
White: chr$(5) - $05
Red: chr$(28) - $1C
Cyan: chr$(159) - $9F
Purple: chr$(156) - $9C
Green: chr$(30) - $1E
Blue: chr$(31) - $1F
Yellow: chr$(158) - $9E
Orange: chr$(129) - $81
Brown: chr$(149) - $95
Light Red: chr$(150) - $96
Dark Gray: chr$(151) - $97
Medium Gray: chr$(152) - $98
Light Green: chr$(153) - $99
Light Blue: chr$(154) - $9A
Light Gray: chr$(155) - $9B

Following these guidelines will ensure your BASIC programs are compatible with the C64 and take advantage of its unique features while avoiding common pitfalls.
