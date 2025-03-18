
"""
PSID format

Written by stein.pedersen@gmail.com

"""

import sys
import numpy as np

psid_fields = [
  ('id',          'S4' ),
  ('version',     '>u2'),
  ('dataOffset',  '>u2'),
  ('loadAddress', '>u2'),
  ('initAddress', '>u2'),
  ('playAddress', '>u2'),
  ('songs',       '>u2'),
  ('startSong',   '>u2'),
  ('speed',       '>u4'),
  ('name',        'S32'),
  ('author',      'S32'),
  ('released',    'S32') 
  ]

psid2_fields = list(psid_fields)
psid2_fields.extend([
  ('flags',             '>u2'),
  ('startPage',         'u1' ),
  ('pageLength',        'u1' ),
  ('secondSIDAddress',  'u1' ),
  ('thirdSIDAddress',   'u1' )
  ])
  
psid_hdr_type = np.dtype(psid_fields)
psid2_hdr_type = np.dtype(psid2_fields)

flags_clock = {
    0:  'Unknown',
    1:  'PAL',
    2:  'NTSC',
    3:  'PAL & NTSC',
}

flags_sidModel = {
    0:  'Unknown',
    1:  '6581',
    2:  '8580',
    3:  '6581 and 8580',
}

def flags_desc(flags):
    clock     = flags_clock[(flags >> 2) & 3]
    sidModel  = flags_sidModel[(flags >> 4) & 3]
    return "{}, {}".format(clock, sidModel)

class SID(object):
    def __init__(self, data):
        if isinstance(data, bytes):
            self.data = data
        elif isinstance(data, np.ndarray):
            self.data = data.tobytes()
        else:
            raise TypeError(f'Unhandled "data" type {type(data)}')
        raw = np.frombuffer(self.data, dtype=np.uint8)
        hdr = raw[0:psid_hdr_type.itemsize].view(dtype=psid_hdr_type)
        id = hdr['id'].tostring()
        if id == b'PSID' or id == b'RSID':
            if hdr['version'] > 1:
                hdr = raw[0:psid2_hdr_type.itemsize].view(dtype=psid2_hdr_type)
            self.header = hdr
        else:
            raise TypeError()
        
    def get_body(self) -> bytes:
        data_offset = int(self.header['dataOffset'])
        if self.header['loadAddress'] == 0:
            # load address is the first 2 bytes
            data_offset += 2
        return self.data[data_offset:]
    
    def get_load_address(self) -> int:
        if self.header['loadAddress']:
            loadAddr = int(self.header['loadAddress'])
        else:
            data_offset = int(self.header['dataOffset'])
            loadAddr = int(np.frombuffer(self.data[data_offset:data_offset+2], dtype='<u2'))
        return loadAddr
        
    def __repr__(self):
        lines = []
        fields = sorted(self.header.dtype.fields.items(), key = lambda x: x[1][1])
        for field, type_ in fields:
            value = self.header[field][0]
            if not type_[0].kind == 'S':
                intvalue = int(value)
                value = f'${intvalue:04X}'
            extra = ''
            if field == 'flags':
                extra = " ({})".format(flags_desc(intvalue))
            if field == 'secondSIDAddress' and intvalue > 0:
                extra = " ({})".format(hex((intvalue << 4) | 0xd000))
            if field == 'thirdSIDAddress' and intvalue > 0:
                extra = " ({})".format(hex((intvalue << 4) | 0xd000))
            lines.append(f'{field:<20}: {value}{extra}')
        return '\n'.join(lines)

def load_sid(filename: str) -> SID:
    try:
        return SID(np.fromfile(filename, dtype=np.uint8))
    except TypeError:
        raise TypeError(f"Unknown SID format in file '{filename}'")
