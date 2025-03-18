"""
Miniature interactive MOS6502/6510 assembler/disassembler.

Written by stein.pedersen@gmail.com

"""
import sys
import re
from enum import IntEnum
from typing import List, Tuple, Dict

DEBUG = False

ASSEMBLER_MODE_DEFAULT = 6510 # Include undocumented op-codes for 6510

AddrMode = IntEnum('AddrMode', ['IMP','IMM','ZP','ZPX', 'ZPY', 'IZX',   'IZY',   'ABS','ABX', 'ABY', 'IND', 'REL'], start=0)
OPERAND_FORMAT =               ['',   '#OP','OP','OP,X','OP,Y','(OP,X)','(OP),Y','OP', 'OP,X','OP,Y','(OP)','RELOP']

# Adapted from: http://www.oxyron.de/html/opcodes02.html
BASE_6502_OPS = {
         # imp  imm  zp   zpx  zpy  izx  izy  abs  abx  aby  ind  rel
  "ORA": [ None,0x09,0x05,0x15,None,0x01,0x11,0x0D,0x1D,0x19,None,None ],
  "AND": [ None,0x29,0x25,0x35,None,0x21,0x31,0x2D,0x3D,0x39,None,None ],
  "EOR": [ None,0x49,0x45,0x55,None,0x41,0x51,0x4D,0x5D,0x59,None,None ],
  "ADC": [ None,0x69,0x65,0x75,None,0x61,0x71,0x6D,0x7D,0x79,None,None ],
  "SBC": [ None,0xE9,0xE5,0xF5,None,0xE1,0xF1,0xED,0xFD,0xF9,None,None ],
  "CMP": [ None,0xC9,0xC5,0xD5,None,0xC1,0xD1,0xCD,0xDD,0xD9,None,None ],
  "CPX": [ None,0xE0,0xE4,None,None,None,None,0xEC,None,None,None,None ],
  "CPY": [ None,0xC0,0xC4,None,None,None,None,0xCC,None,None,None,None ],
  "DEC": [ None,None,0xC6,0xD6,None,None,None,0xCE,0xDE,None,None,None ],
  "DEX": [ 0xCA,None,None,None,None,None,None,None,None,None,None,None ],
  "DEY": [ 0x88,None,None,None,None,None,None,None,None,None,None,None ],
  "INC": [ None,None,0xE6,0xF6,None,None,None,0xEE,0xFE,None,None,None ],
  "INX": [ 0xE8,None,None,None,None,None,None,None,None,None,None,None ],
  "INY": [ 0xC8,None,None,None,None,None,None,None,None,None,None,None ],
  "ASL": [ 0x0A,None,0x06,0x16,None,None,None,0x0E,0x1E,None,None,None ],
  "ROL": [ 0x2A,None,0x26,0x36,None,None,None,0x2E,0x3E,None,None,None ],
  "LSR": [ 0x4A,None,0x46,0x56,None,None,None,0x4E,0x5E,None,None,None ],
  "ROR": [ 0x6A,None,0x66,0x76,None,None,None,0x6E,0x7E,None,None,None ],
  "LDA": [ None,0xA9,0xA5,0xB5,None,0xA1,0xB1,0xAD,0xBD,0xB9,None,None ],
  "STA": [ None,None,0x85,0x95,None,0x81,0x91,0x8D,0x9D,0x99,None,None ],
  "LDX": [ None,0xA2,0xA6,None,0xB6,None,None,0xAE,None,0xBE,None,None ],
  "STX": [ None,None,0x86,None,0x96,None,None,0x8E,None,None,None,None ],
  "LDY": [ None,0xA0,0xA4,0xB4,None,None,None,0xAC,0xBC,None,None,None ],
  "STY": [ None,None,0x84,0x94,None,None,None,0x8C,None,None,None,None ],
  "TAX": [ 0xAA,None,None,None,None,None,None,None,None,None,None,None ],
  "TXA": [ 0x8A,None,None,None,None,None,None,None,None,None,None,None ],
  "TAY": [ 0xA8,None,None,None,None,None,None,None,None,None,None,None ],
  "TYA": [ 0x98,None,None,None,None,None,None,None,None,None,None,None ],
  "TSX": [ 0xBA,None,None,None,None,None,None,None,None,None,None,None ],
  "TXS": [ 0x9A,None,None,None,None,None,None,None,None,None,None,None ],
  "PLA": [ 0x68,None,None,None,None,None,None,None,None,None,None,None ],
  "PHA": [ 0x48,None,None,None,None,None,None,None,None,None,None,None ],
  "PLP": [ 0x28,None,None,None,None,None,None,None,None,None,None,None ],
  "PHP": [ 0x08,None,None,None,None,None,None,None,None,None,None,None ],
  "BPL": [ None,None,None,None,None,None,None,None,None,None,None,0x10 ],
  "BMI": [ None,None,None,None,None,None,None,None,None,None,None,0x30 ],
  "BVC": [ None,None,None,None,None,None,None,None,None,None,None,0x50 ],
  "BVS": [ None,None,None,None,None,None,None,None,None,None,None,0x70 ],
  "BCC": [ None,None,None,None,None,None,None,None,None,None,None,0x90 ],
  "BCS": [ None,None,None,None,None,None,None,None,None,None,None,0xB0 ],
  "BNE": [ None,None,None,None,None,None,None,None,None,None,None,0xD0 ],
  "BEQ": [ None,None,None,None,None,None,None,None,None,None,None,0xF0 ],
  "BRK": [ 0x00,None,None,None,None,None,None,None,None,None,None,None ],
  "RTI": [ 0x40,None,None,None,None,None,None,None,None,None,None,None ],
  "JSR": [ None,None,None,None,None,None,None,0x20,None,None,None,None ],
  "RTS": [ 0x60,None,None,None,None,None,None,None,None,None,None,None ],
  "JMP": [ None,None,None,None,None,None,None,0x4C,None,None,0x6C,None ],
  "BIT": [ None,None,0x24,None,None,None,None,0x2C,None,None,None,None ],
  "CLC": [ 0x18,None,None,None,None,None,None,None,None,None,None,None ],
  "SEC": [ 0x38,None,None,None,None,None,None,None,None,None,None,None ],
  "CLD": [ 0xD8,None,None,None,None,None,None,None,None,None,None,None ],
  "SED": [ 0xF8,None,None,None,None,None,None,None,None,None,None,None ],
  "CLI": [ 0x58,None,None,None,None,None,None,None,None,None,None,None ],
  "SEI": [ 0x78,None,None,None,None,None,None,None,None,None,None,None ],
  "CLV": [ 0xB8,None,None,None,None,None,None,None,None,None,None,None ],
  "NOP": [ 0xEA,None,None,None,None,None,None,None,None,None,None,None ],
}

UNDOCUMENTED_6510_OPS = {
  "SLO": [ None,None,0x07,0x17,None,0x03,0x13,0x0F,0x1F,0x1B,None,None ],
  "RLA": [ None,None,0x27,0x37,None,0x23,0x33,0x2F,0x3F,0x3B,None,None ],
  "SRE": [ None,None,0x47,0x57,None,0x43,0x53,0x4F,0x5F,0x5B,None,None ],
  "RRA": [ None,None,0x67,0x77,None,0x63,0x73,0x6F,0x7F,0x7B,None,None ],
  "SAX": [ None,None,0x87,None,0x97,0x83,None,0x8F,None,None,None,None ],
  "LAX": [ None,0xAB,0xA7,None,0xB7,0xA3,0xB3,0xAF,None,0xBF,None,None ],
  "DCP": [ None,None,0xC7,0xD7,None,0xC3,0xD3,0xCF,0xDF,0xDB,None,None ],
  "ISC": [ None,None,0xE7,0xF7,None,0xE3,0xF3,0xEF,0xFF,0xFB,None,None ],
  "ANC": [ None,0x0B,None,None,None,None,None,None,None,None,None,None ],
  "ANC": [ None,0x2B,None,None,None,None,None,None,None,None,None,None ],
  "ALR": [ None,0x4B,None,None,None,None,None,None,None,None,None,None ],
  "ARR": [ None,0x6B,None,None,None,None,None,None,None,None,None,None ],
  "XAA": [ None,0x8B,None,None,None,None,None,None,None,None,None,None ],
  "AXS": [ None,0xCB,None,None,None,None,None,None,None,None,None,None ],
  "SB2": [ None,0xEB,None,None,None,None,None,None,None,None,None,None ],
  "AHX": [ None,None,None,None,None,None,0x93,None,None,0x9F,None,None ],
  "SHY": [ None,None,None,None,None,None,None,None,0x9C,None,None,None ],
  "SHX": [ None,None,None,None,None,None,None,None,None,0x9E,None,None ],
  "TAS": [ None,None,None,None,None,None,None,None,None,0x9B,None,None ],
  "LAS": [ None,None,None,None,None,None,None,None,None,0xBB,None,None ],
}

OP_ALIASES = {
    "SB2": "SBC",
}

OPS = {}
DISASM = {}

def config_assembler(mode):
    global OPS
    global DISASM
    OPS = dict.copy(BASE_6502_OPS)
    if mode == 6510:
        OPS.update(UNDOCUMENTED_6510_OPS)
    DISASM = { val: op for op in OPS for val in OPS[op] if val is not None }

config_assembler(ASSEMBLER_MODE_DEFAULT)

def compute_operand_size(op: int) -> int:
# Adapted from https://csdb.dk/forums/?roomid=11&topicid=162839
    if op == 0x20:
        return 2
    op = op & 0x9D
    if op == 0:
        return 0
    op = (op << 1) & 0xff
    if op == 0x12:
        return 1
    op = op & 0x1a
    if op < 0x10:
        return 1
    if op == 0x10:
        return 0
    return 2

def disasm_line(current_addr: int, data: bytes) -> Tuple[str, bytes]:
    """Disassemble a single line of the input data.
    
    Returns the disassembled code and the remaining data.

    If the data blob is empty, or if there was not enough data to decode the instruction,
    (None, None) is returned.
    """
    try:
        op = data[0]
        consumed = 1 + compute_operand_size(op)
        items = ' '.join([f'{i:02X}' for i in data[0:consumed]])
        line = f'{current_addr&0xffff:04X} {items:<8}'
        operand = ''
        relop   = ''
        if consumed == 2:
            operand = f'${data[1]&0xff:02X}'
            relop   = f'${current_addr+2+int.from_bytes(data[1:2], byteorder="little", signed=True):04X}'
        elif consumed == 3:
            operand = f'${data[2]&0xff:02X}{data[1]&0xff:02X}'
        if op in DISASM:
            op_name = DISASM[op]
            op_realname = OP_ALIASES[op_name] if op_name in OP_ALIASES else op_name
            mode = OPS[op_name].index(op)
            operand = OPERAND_FORMAT[mode].replace('RELOP', relop).replace('OP', operand)
            line = f'{line} {op_realname} {operand}'.strip()
        else:
            line = f'{line} ???'
        return line, data[consumed:]
    except IndexError:
        return None, None

def disasm_blob(start_addr: int, data: bytes, max_lines: int = 64) -> Tuple[str, bytes]:
    """Disassemble a blob of data.
    
    Return the disassembled lines and whatever remains at the end.
    """
    lines = []
    addr = start_addr
    line_count = 0
    while max_lines == 0 or line_count < max_lines:
        line, remainder = disasm_line(addr, data)
        if line:
            lines.append(line)
            addr += len(data) - len(remainder)
            data = remainder
            line_count += 1
        else:
            break
    return '\n'.join(lines), data

OperandCategory = IntEnum('OperandCategory', ['Empty', 'Imm', 'Abs', 'AbsX', 'AbsY', 'Ind', 'IndX', 'IndY', 'Invalid'], start=0)
           # Empty Imm                Abs                AbsX                AbsY                Ind                    IndX                    IndY                    Invalid
Matchers = [ '$', '#\$?([0-9A-Z]+)$', '\$?([0-9A-Z]+)$', '\$?([0-9A-Z]+),X$', '\$?([0-9A-Z]+),Y$', '\(\$?([0-9A-Z]+)\)$', '\(\$?([0-9A-Z]+),X\)$', '\(\$?([0-9A-Z]+)\),Y$', '.*' ]

def asm_line(current_addr: int, line: str) -> bytes:
    """Assemble a line of text into bytes.
    
    Branches are calculated relative to the current_addr parameter.
    
    Return a bytes object or None, if an error occurred.
    """
    tokens = line.strip().upper()
    op = tokens[0:3]
    operand = tokens[3:].strip()
    if op in OPS:
        op_modes = OPS[op]
        for i, matcher in enumerate(Matchers):
            m = re.match(matcher, operand)
            if m:
                inttoken = m[1] if m.groups() else '0'
                intvalue = int(inttoken, base=16)
                cat = OperandCategory(i)
                if cat == OperandCategory.Empty:
                    if op_modes[AddrMode.IMP] is not None:
                        return bytes((op_modes[AddrMode.IMP],))
                elif cat == OperandCategory.Imm:
                    if op_modes[AddrMode.IMM] is not None:
                        return bytes((op_modes[AddrMode.IMM], intvalue&0xff))
                elif cat == OperandCategory.Abs:
                    if len(inttoken) < 3 and op_modes[AddrMode.ZP] is not None:
                        return bytes((op_modes[AddrMode.ZP], intvalue&0xff))
                    if op_modes[AddrMode.ABS] is not None:
                        return bytes((op_modes[AddrMode.ABS], intvalue&0xff, (intvalue>>8)&0xff))
                    if op_modes[AddrMode.REL] is not None:
                        target_delta = intvalue - (current_addr + 2)
                        if target_delta >= -128 and target_delta <= 127:
                            return bytes((op_modes[AddrMode.REL], target_delta&0xff))
                elif cat == OperandCategory.AbsX:
                    if len(inttoken) < 3 and op_modes[AddrMode.ZPX] is not None:
                        return bytes((op_modes[AddrMode.ZPX], intvalue&0xff))
                    if op_modes[AddrMode.ABX] is not None:
                        return bytes((op_modes[AddrMode.ABX], intvalue&0xff, (intvalue>>8)&0xff))
                elif cat == OperandCategory.AbsY:
                    if len(inttoken) < 3 and op_modes[AddrMode.ZPY] is not None:
                        return bytes((op_modes[AddrMode.ZPY], intvalue&0xff))
                    if op_modes[AddrMode.ABX] is not None:
                        return bytes((op_modes[AddrMode.ABY], intvalue&0xff, (intvalue>>8)&0xff))
                elif cat == OperandCategory.Ind:
                    if op_modes[AddrMode.IND] is not None:
                        return bytes((op_modes[AddrMode.IND], intvalue&0xff, (intvalue>>8)&0xff))
                elif cat == OperandCategory.IndX:
                    if len(inttoken) < 3 and op_modes[AddrMode.IZX] is not None:
                        return bytes((op_modes[AddrMode.IZX], intvalue&0xff))
                elif cat == OperandCategory.IndY:
                    if len(inttoken) < 3 and op_modes[AddrMode.IZY] is not None:
                        return bytes((op_modes[AddrMode.IZY], intvalue&0xff))
    return None

def interactive(addr=0x1000, quit_on_empty_input=False, no_termcodes=False, prefix='', input_stream=sys.stdin) -> Tuple[int, bytes]:
    """Start interactive mode.
    
    Assembles lines of code entered by the user until the Quit ('q') or Exit ('x')
    command is encountered. Optionally, entering an empty line may also quit.

    Returns the start address and the assembled code.
    """
    blob = b''
    start_addr = addr
    write_pos = 0
    while True:
        print(f'{addr:04X} ', end='')
        sys.stdout.flush()
        if prefix:
            l = prefix
            prefix = ''
        else:
            l = input_stream.readline()
            if l == '': # EOF
                break
        l = l.strip().upper()
        if l == 'X' or l == 'Q':
            break
        if l.startswith('A'):
            tokens = l[1:].strip().split(' ')
            try:
                new_addr = int(tokens[0],base=16)
                delta = new_addr - start_addr
                if delta >= 0 and delta <= len(blob):
                    write_pos = delta
                    addr = start_addr + write_pos
                elif new_addr != addr:
                    start_addr = addr = new_addr
                    blob = b''
                    write_pos = 0
                l = ' '.join(tokens[1:])
                if not l.strip():
                    continue
            except:
                print('???')
                continue
        l = l.strip()
        if l:
            data = asm_line(addr, l)
            if data is not None:
                if not no_termcodes:
                    # cursor up, clear line
                    sys.stdout.write('\033[A\033[K')
                line, remainder = disasm_line(addr, data)
                assert len(remainder) == 0
                print(line)
                addr += len(data)
                assert write_pos <= len(blob)
                blob = blob[:write_pos] + data + blob[write_pos+len(data):]
                write_pos += len(data)
            else:
                print('???')
        elif quit_on_empty_input:
            break
#    print(f'Assembled {len(blob)} bytes at ${start_addr:04X}')
    return start_addr, blob
    
def main():
    addr, data = interactive(addr=0x1000, quit_on_empty_input=True)
    if DEBUG:
        text, remainder = disasm_blob(addr, data)
        print(text)

if __name__ == '__main__':
    main()
