from idaapi import *
import os
import sys
import re
from clemency_inst import inst_json
########################################
# Decoder Function
########################################
def is_bit_string(strg, search=re.compile(r'[^01]').search):
    return not bool(search(strg))

def fetch(code, n):
    byte1 = (code >> (54 - 9 * 1)) & 0x1ff
    byte2 = (code >> (54 - 9 * 2)) & 0x1ff
    byte3 = (code >> (54 - 9 * 3)) & 0x1ff
    byte4 = (code >> (54 - 9 * 4)) & 0x1ff
    byte5 = (code >> (54 - 9 * 5)) & 0x1ff
    byte6 = (code >> (54 - 9 * 6)) & 0x1ff

    v = 0
    if n == 3:
        v = (byte2 << 18) + (byte1 << 9) + byte3
    return v

def match_inst(opbit, inst):
    off = 0
    for e in inst[1:]:
        # do match
        if is_bit_string(e[1]):
            if opbit[off:off+e[0]] != e[1]:
                return 0
        off += e[0]
    return 1

def decoder755127(self, code):
    inst_len = 3
    opcode = fetch(code, inst_len)
    opbit = "{:0{width}b}".format(opcode, width=9*inst_len)
    inst_table = [
            ['SMP', (7, '1010010'), (5, 'rA'), (5, 'rB'), (1, '1'), (2, 'Memory Flags'), (7, '0000000')],
            ]

    for inst in inst_table:
        m = match_inst(opbit, inst)
        if m > 0:
            self.cmd.itype = getattr(self, 'itype_' + inst[0])
            return inst_len
    return 0

########################################
# Processor Type
########################################
def ana(self):
    cmd = self.cmd
    current_ea = cmd.ea + cmd.size
    code_bit = ''
    for i in xrange(6):
        code_bit += '{:09b}'.format(get_full_byte(current_ea + i) & 0x1ff)
    code = int(code_bit, 2)

    decoder_list = [
            decoder755127,
            ]
    r = 0
    for d in decoder_list:
        r = d(self, code)
        if r > 0:
            break
    cmd.size += r
    return r

class CLEMENCY(processor_t):
    # IDP id ( Numbers above 0x8000 are reserved for the third-party modules)
    id = 0x8000 + 0x999
    # Processor features
    flag = PR_ADJSEGS | PRN_HEX | PR_WORD_INS
    # Number of bits in a byte for code segments (usually 8)
    # IDA supports values up to 32 bits
    cnbits = 9
    # Number of bits in a byte for non-code segments (usually 8)
    # IDA supports values up to 32 bits
    dnbits = 9
    # short processor names (NULL terminated)
    # Each name should be shorter than 9 characters
    psnames = ["clemency"]
    # long processor names (NULL terminated)
    # No restriction on name lengthes.
    plnames = ["cLemency"]

    segreg_size = 0

    ##########################
    # intruction
    # icode of the first instruction
    instruc_start = 0

    assembler = {
        "flag" : ASH_HEXF3 | ASD_DECF0 | ASO_OCTF1 | ASB_BINF3 | AS_NOTAB
               | AS_ASCIIC | AS_ASCIIZ,
        "uflag": 0,
        "name": "GNU assembler",

        "origin": ".org",
        "end": "end",
        "cmnt": ";",

        "ascsep": '"',
        "accsep": "'",
        "esccodes": "\"'",

        "a_ascii": ".ascii",
        "a_byte": ".byte",
        "a_word": ".word",
        "a_3byte": ".tribyte",

        "a_bss": "dfs %s",

        "a_seg": "seg",
        "a_curip": ".",
        "a_public": "",
        "a_weak": "",
        "a_extrn": ".extrn",
        "a_comdef": "",
        "a_align": ".align",

        "lbrace": "(",
        "rbrace": ")",
        "a_mod": "%",
        "a_band": "&",
        "a_bor": "|",
        "a_xor": "^",
        "a_bnot": "~",
        "a_shl": "<<",
        "a_shr": ">>",
        "a_sizeof_fmt": "size %s",
    }


    module = __import__('clemency')
    def __init__(self):
        processor_t.__init__(self)
        self._init_registers()
        self._init_instructions()

    def _init_registers(self):

        # Registers definition
        self.regNames = ["R%d" % (i) for i in xrange(29)] + ["ST", "RA", "PC", "FL"] + ["CS", "DS"]

        # Create the ireg_XXXX constants
        for i in xrange(len(self.regNames)):
            setattr(self, 'ireg_' + self.regNames[i], i)

        # Set fake segment registers
        self.regFirstSreg = self.regCodeSreg = self.ireg_CS
        self.regLastSreg = self.regDataSreg = self.ireg_DS

    def _init_instructions(self):
        class idef:
            def __init__(self, name, cmt, fmt, args):
                self.name = name
                self.cmt = cmt
                self.fmt = fmt
                self.args = args

        self.itable = {}
        Instructions = []
        for j in range(len(inst_json)):
            i = inst_json[j]
            args = []
            for a in i['args']:
                args.append((a['width'], a['value']))
            self.itable[j] = idef(i['name'], i['desc'], i['format'], args)

        for j in range(len(self.itable)):
            x = self.itable[j]
            d = dict(name = x.name, feature=0)
            if x.cmt:
                d['cmt'] = x.cmt
            Instructions.append(d)
            setattr(self, 'itype_' + x.name, j)

        self.instruc_end = len(Instructions) + 1
        self.instruc = Instructions
        self.icode_return = self.itype_RE

    def ana(self):
        reload(self.module)
        dynana = getattr(self.module, 'ana')
        return dynana(self)

    def emu(self):
        print "emu"
        return True

    def out(self):
        print "out"
        buf = idaapi.init_output_buffer(1024)
        OutMnem(12)
        term_output_buffer()
        cvar.gl_comm = 1
        MakeLine(buf)

    def outop(self, op):
        print "outop"
        return True

########################################
# Data format for TriBytes (9bits)
########################################
class tribyte_data_type(data_type_t):
    ASM_KEYWORD = ".tri"
    def __init__(self):
        data_type_t.__init__(self,
                             name = "py_tribyte",
                             hotkey = 'z',
                             value_size = 1,
                             menu_name = "TriBytes (9bits)",
                             asm_keyword = tribyte_data_type.ASM_KEYWORD)

    def calc_item_size(self, ea, maxsize):
        return 3

class tribyte_data_format(data_format_t):
    def __init__(self):
        data_format_t.__init__(self,
                               name = "py_tribyte_format",
                               menu_name = "TriBytes (9bits)")

    def printf(self, value, current_ea, operand_num, dtid):
        b1 = idaapi.get_full_byte(current_ea) & 0x1ff
        b2 = idaapi.get_full_byte(current_ea+1) & 0x1ff
        b3 = idaapi.get_full_byte(current_ea+2) & 0x1ff
        return hex((b2 << 18) + (b1 << 9) + b3)

def init_data_format():
    new_format = [
            (tribyte_data_type(), tribyte_data_format())
            ]
    register_data_types_and_formats(new_format)

########################################
# Processor Plugin Entry
########################################
def PROCESSOR_ENTRY():
    # new data format
    init_data_format()
    # add proc into module path
    script_path = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_path)
    sys.path.insert(0, script_dir)
    return CLEMENCY()