"""
手动生成 VeinMinerMod.class — NeoForge 连锁挖矿模组
不依赖 javac，直接用 Python 按 JVM Class 文件格式 (Java 21, major 65) 构造合法字节码。
"""
import struct

def u1(v): return struct.pack('>B', v & 0xFF)
def u2(v): return struct.pack('>H', v & 0xFFFF)
def u4(v): return struct.pack('>I', v & 0xFFFFFFFF)

class CPBuilder:
    """常量池构建器，自动去重"""
    def __init__(self):
        self.entries = []
        self.index = {}
    
    def add(self, tag, *args):
        key = (tag,) + args
        if key in self.index:
            return self.index[key]
        idx = len(self.entries) + 1
        self.entries.append((tag,) + args)
        self.index[key] = idx
        return idx
    
    def utf8(self, s):
        return self.add(1, s.encode('utf-8'))
    
    def cls(self, name):
        return self.add(7, self.utf8(name))
    
    def nat(self, name, desc):
        return self.add(12, self.utf8(name), self.utf8(desc))
    
    def mref(self, owner, name, desc):
        return self.add(10, self.cls(owner), self.nat(name, desc))
    
    def fref(self, owner, name, desc):
        return self.add(9, self.cls(owner), self.nat(name, desc))
    
    def string(self, s):
        return self.add(8, self.utf8(s))
    
    def methodType(self, desc):
        return self.add(16, self.utf8(desc))
    
    def methodHandle(self, kind, cpIdx):
        return self.add(15, kind, cpIdx)
    
    def invokeDynamic(self, bootstrapIdx, natIdx):
        return self.add(18, bootstrapIdx, natIdx)
    
    def serialize(self):
        buf = bytearray()
        for e in self.entries:
            tag = e[0]
            buf += u1(tag)
            if tag == 1:  # Utf8
                data = e[1]
                buf += u2(len(data)) + data
            elif tag in (7, 8, 16):  # Class, String, MethodType
                buf += u2(e[1])
            elif tag in (9, 10):  # Fieldref, Methodref
                buf += u2(e[1]) + u2(e[2])
            elif tag == 12:  # NameAndType
                buf += u2(e[1]) + u2(e[2])
            elif tag == 15:  # MethodHandle
                buf += u1(e[1]) + u2(e[2])
            elif tag == 18:  # InvokeDynamic
                buf += u2(e[1]) + u2(e[2])
        return bytes(buf)

class MethodBuilder:
    """构建单个方法的字节码"""
    def __init__(self, access, name_idx, desc_idx):
        self.access = access
        self.name_idx = name_idx
        self.desc_idx = desc_idx
        self.code = bytearray()
        self.max_stack = 0
        self.max_locals = 0
        self.stack_depth = 0
        self._labels = {}
        self._pending = []
    
    def _op(self, op, *args):
        self.code += u1(op)
        for a in args:
            self.code += u1(a) if a < 256 else u2(a)
    
    def _stack(self, delta):
        self.stack_depth += delta
        if self.stack_depth > self.max_stack:
            self.max_stack = self.stack_depth
    
    # Instructions
    def aload(self, n):
        if n == 0: self._op(0x2a)
        elif n == 1: self._op(0x2b)
        elif n == 2: self._op(0x2c)
        elif n == 3: self._op(0x2d)
        else: self._op(0x19, n)
        self._stack(1)
    
    def iload(self, n):
        if n == 0: self._op(0x1a)
        elif n == 1: self._op(0x1b)
        elif n == 2: self._op(0x1c)
        elif n == 3: self._op(0x1d)
        else: self._op(0x15, n)
        self._stack(1)
    
    def fload(self, n):
        if n == 0: self._op(0x22)
        elif n == 1: self._op(0x23)
        elif n == 2: self._op(0x24)
        elif n == 3: self._op(0x25)
        else: self._op(0x17, n)
        self._stack(1)
    
    def astore(self, n):
        if n == 0: self._op(0x4b)
        elif n == 1: self._op(0x4c)
        elif n == 2: self._op(0x4d)
        elif n == 3: self._op(0x4e)
        else: self._op(0x3a, n)
        self._stack(-1)
    
    def istore(self, n):
        if n == 0: self._op(0x3b)
        elif n == 1: self._op(0x3c)
        elif n == 2: self._op(0x3d)
        elif n == 3: self._op(0x3e)
        else: self._op(0x36, n)
        self._stack(-1)
    
    def fstore(self, n):
        if n == 0: self._op(0x43)
        elif n == 1: self._op(0x44)
        elif n == 2: self._op(0x45)
        elif n == 3: self._op(0x46)
        else: self._op(0x38, n)
        self._stack(-1)
    
    def aconst_null(self):
        self._op(0x01)
        self._stack(1)
    
    def iconst(self, n):
        if n == -1: self._op(0x02)
        elif n == 0: self._op(0x03)
        elif n == 1: self._op(0x04)
        elif n == 2: self._op(0x05)
        elif n == 3: self._op(0x06)
        elif n == 4: self._op(0x07)
        elif n == 5: self._op(0x08)
        else:
            if -128 <= n <= 127:
                self._op(0x10, n)
            else:
                self._op(0x11, (n >> 8) & 0xFF, n & 0xFF)
        self._stack(1)
    
    def ldc(self, cp):
        if cp < 256:
            self._op(0x12, cp)
        else:
            self._op(0x13, cp >> 8, cp & 0xFF)
        self._stack(1)
    
    def dup(self):
        self._op(0x59)
        self._stack(1)
    
    def pop(self):
        self._op(0x57)
        self._stack(-1)
    
    def getstatic(self, cp):
        self._op(0xb2, cp >> 8, cp & 0xFF)
        self._stack(1)
    
    def putstatic(self, cp):
        self._op(0xb3, cp >> 8, cp & 0xFF)
        self._stack(-1)
    
    def getfield(self, cp):
        self._op(0xb4, cp >> 8, cp & 0xFF)
        # stack: ref -> value, net 0
    
    def putfield(self, cp):
        self._op(0xb5, cp >> 8, cp & 0xFF)
        self._stack(-2)
    
    def invokevirtual(self, cp):
        self._op(0xb6, cp >> 8, cp & 0xFF)
        self._stack(-1)  # pops args+obj, pushes ret
    
    def invokespecial(self, cp):
        self._op(0xb7, cp >> 8, cp & 0xFF)
        self._stack(-1)
    
    def invokestatic(self, cp):
        self._op(0xb8, cp >> 8, cp & 0xFF)
        # can't easily track stack
    
    def invokeinterface(self, cp, count):
        self._op(0xb9, cp >> 8, cp & 0xFF, count, 0)
    
    def new(self, cp):
        self._op(0xbb, cp >> 8, cp & 0xFF)
        self._stack(1)
    
    def newarray(self, atype):
        self._op(0xbc, atype)
    
    def anewarray(self, cp):
        self._op(0xbd, cp >> 8, cp & 0xFF)
    
    def checkcast(self, cp):
        self._op(0xc0, cp >> 8, cp & 0xFF)
    
    def instanceof(self, cp):
        self._op(0xc1, cp >> 8, cp & 0xFF)
    
    def ifeq(self, offset):
        self._op(0x99, offset >> 8, offset & 0xFF)
        self._stack(-1)
    
    def ifne(self, offset):
        self._op(0x9a, offset >> 8, offset & 0xFF)
        self._stack(-1)
    
    def iflt(self, offset):
        self._op(0x9b, offset >> 8, offset & 0xFF)
        self._stack(-1)
    
    def ifge(self, offset):
        self._op(0x9c, offset >> 8, offset & 0xFF)
        self._stack(-1)
    
    def ifgt(self, offset):
        self._op(0x9d, offset >> 8, offset & 0xFF)
        self._stack(-1)
    
    def ifle(self, offset):
        self._op(0x9e, offset >> 8, offset & 0xFF)
        self._stack(-1)
    
    def if_icmpne(self, offset):
        self._op(0xa0, offset >> 8, offset & 0xFF)
        self._stack(-2)
    
    def if_icmpge(self, offset):
        self._op(0xa2, offset >> 8, offset & 0xFF)
        self._stack(-2)
    
    def if_icmpgt(self, offset):
        self._op(0xa3, offset >> 8, offset & 0xFF)
        self._stack(-2)
    
    def if_acmpne(self, offset):
        self._op(0xa6, offset >> 8, offset & 0xFF)
        self._stack(-2)
    
    def if_nonnull(self, offset):
        self._op(0xc7, offset >> 8, offset & 0xFF)
        self._stack(-1)
    
    def if_null(self, offset):
        self._op(0xc6, offset >> 8, offset & 0xFF)
        self._stack(-1)
    
    def goto(self, offset):
        self._op(0xa7, offset >> 8, offset & 0xFF)
    
    def areturn(self):
        self._op(0xb0)
        self._stack(-1)
    
    def ireturn(self):
        self._op(0xac)
        self._stack(-1)
    
    def freturn(self):
        self._op(0xae)
        self._stack(-1)
    
    def return_(self):
        self._op(0xb1)
    
    def athrow(self):
        self._op(0xbf)
        self._stack(-1)
    
    def iadd(self):
        self._op(0x60)
        self._stack(-1)
    
    def isub(self):
        self._op(0x64)
        self._stack(-1)
    
    def iand(self):
        self._op(0x7e)
        self._stack(-1)
    
    def ior(self):
        self._op(0x80)
        self._stack(-1)
    
    def ixor(self):
        self._op(0x82)
        self._stack(-1)
    
    def _get_pc(self):
        return len(self.code)
    
    def serialize(self, cp):
        buf = bytearray()
        buf += u2(self.access)
        buf += u2(self.name_idx)
        buf += u2(self.desc_idx)
        
        # Code attribute
        code_attr = bytearray()
        code_attr += u2(self.max_stack)
        code_attr += u2(self.max_locals)
        code_attr += u4(len(self.code))
        code_attr += bytes(self.code)
        code_attr += u2(0)  # exception_table
        code_attr += u2(0)  # attributes
        
        # Method attributes
        buf += u2(1)  # one attribute: Code
        buf += u2(cp.utf8("Code"))
        buf += u4(len(code_attr))
        buf += bytes(code_attr)
        
        return bytes(buf)


# ==================== BUILD ====================

cp = CPBuilder()

# ---- Utf8 constants ----
U_Code = cp.utf8("Code")
U_LineNumberTable = cp.utf8("LineNumberTable")
U_SourceFile = cp.utf8("SourceFile")
U_SourceFileVal = cp.utf8("VeinMinerMod.java")
U_this = cp.utf8("com/veinminer/VeinMinerMod")
U_object = cp.utf8("java/lang/Object")
U_init = cp.utf8("<init>")
U_initV = cp.utf8("()V")
U_clinit = cp.utf8("<clinit>")
U_onBlockBreak = cp.utf8("onBlockBreak")
U_eventDesc = cp.utf8("(Lnet/neoforged/neoforge/event/level/BlockEvent$BreakEvent;)V")

# ---- Class refs ----
C_this = cp.cls("com/veinminer/VeinMinerMod")
C_object = cp.cls("java/lang/Object")
C_modAnnot = cp.cls("net/neoforged/fml/common/Mod")
C_eventBusSub = cp.cls("net/neoforged/fml/common/EventBusSubscriber")
C_subscribeEvent = cp.cls("net/neoforged/bus/api/SubscribeEvent")
C_string = cp.cls("java/lang/String")
C_blockPos = cp.cls("net/minecraft/core/BlockPos")
C_serverPlayer = cp.cls("net/minecraft/server/level/ServerPlayer")
C_itemStack = cp.cls("net/minecraft/world/item/ItemStack")
C_level = cp.cls("net/minecraft/world/level/Level")
C_serverLevel = cp.cls("net/minecraft/server/level/ServerLevel")
C_block = cp.cls("net/minecraft/world/level/block/Block")
C_blockState = cp.cls("net/minecraft/world/level/block/state/BlockState")
C_breakEvent = cp.cls("net/neoforged/neoforge/event/level/BlockEvent$BreakEvent")
C_neoForge = cp.cls("net/neoforged/neoforge/common/NeoForge")

# ---- String constants ----
S_modId = cp.string("veinminer")

# ---- Method refs ----
M_obj_init = cp.mref("java/lang/Object", "<init>", "()V")

# Annotation stuff — we just need valid CP entries for @Mod("veinminer")
# The JVM class file will have RuntimeInvisibleAnnotations; we'll add them

# For @Mod("veinminer") we need methodref for Mod.value() which returns String
# But annotations are encoded differently — we'll skip complex annotations for now
# and rely on neoforge.mods.toml for mod discovery. The @Mod annotation is needed
# but can be simplified.

# Actually NeoForge requires @Mod on the class. Let's encode it properly.
# Annotation format: 
#   type_index (Utf8: Lnet/neoforged/fml/common/Mod;)
#   element_value_pairs: 1 pair
#     element_name_index (Utf8: "value")
#     element_value: 's' (string), const_value_index (Utf8: "veinminer")

U_Mod_desc = cp.utf8("Lnet/neoforged/fml/common/Mod;")
U_EventBusSub_desc = cp.utf8("Lnet/neoforged/fml/common/EventBusSubscriber;")
U_SubscribeEvent_desc = cp.utf8("Lnet/neoforged/bus/api/SubscribeEvent;")
U_mod_value = cp.utf8("value")
U_modId_str = cp.utf8("veinminer")

# for @EventBusSubscriber — no params needed (default)
# for @SubscribeEvent on method — no params

# MOD_ID field
U_MOD_ID = cp.utf8("MOD_ID")
U_String_desc = cp.utf8("Ljava/lang/String;")

# OFFSETS field
U_OFFSETS = cp.utf8("OFFSETS")
U_BlockPos_arr = cp.utf8("[Lnet/minecraft/core/BlockPos;")

# ========== Build class ==========

out = bytearray()
out += u4(0xCAFEBABE)   # magic
out += u2(0)             # minor
out += u2(65)            # major — Java 21 (compat with 25)

out += u2(len(cp.entries) + 1)  # cp_count
out += cp.serialize()

# Access flags: ACC_PUBLIC | ACC_SUPER
out += u2(0x0021)
# This class
out += u2(C_this)
# Super class
out += u2(C_object)

# Interfaces: 0
out += u2(0)

# ===== FIELDS =====
# 2 fields: MOD_ID (static final String), OFFSETS (static final BlockPos[])

field_count = 2
out += u2(field_count)

# MOD_ID
out += u2(0x0019)  # ACC_PUBLIC | ACC_STATIC | ACC_FINAL
out += u2(U_MOD_ID)
out += u2(U_String_desc)
# ConstantValue attribute
out += u2(1)
out += u2(cp.utf8("ConstantValue"))
out += u4(2)
out += u2(S_modId)

# OFFSETS
out += u2(0x0019)  # ACC_PUBLIC | ACC_STATIC | ACC_FINAL
out += u2(U_OFFSETS)
out += u2(U_BlockPos_arr)
out += u2(0)  # no attributes (initialized in <clinit>)

# ===== METHODS =====
# 3 methods: <init>, <clinit>, onBlockBreak
out += u2(3)

# --- Method 1: <init> ---
m = MethodBuilder(0x0001, U_init, U_initV)  # public
m.aload(0)
m.invokespecial(M_obj_init)
m.return_()
m.max_locals = 1
out += m.serialize(cp)

# --- Method 2: <clinit> (static initializer for OFFSETS) ---
# Builds the OFFSETS array
m2 = MethodBuilder(0x0008, U_clinit, U_initV)  # static
# This is complex — for now, let's skip OFFSETS initialization and handle it in onBlockBreak
# Actually, BlockPos[] array init is complex in bytecode. Let's make OFFSETS null 
# and compute offsets inline in onBlockBreak.
# Or better: just make offsets inline constants in the method body.

# For simplicity: <clinit> just returns
m2.return_()
m2.max_locals = 0
m2.max_stack = 0
out += m2.serialize(cp)

# --- Method 3: onBlockBreak ---
# public static void onBlockBreak(BlockEvent.BreakEvent event)
# This is the complex one. Let's write a simplified but working version.
# Full BFS is complex in hand-written bytecode. Let's do a simplified version:
# - Get player from event
# - Check shift key
# - Get origin block
# - Do a BFS up to 64 blocks
# - Handle durability
# - Break blocks

# Given the complexity, let's write a version that works but is minimal:
# The bytecode for the full BFS would be ~500+ instructions.
# Let me do it systematically...

m3 = MethodBuilder(0x0009, U_onBlockBreak, U_eventDesc)  # public static
# local slots:
# 0: event
# 1: player
# 2: level
# 3: serverLevel
# 4: origin (BlockPos)
# 5: targetState
# 6: targetBlock
# 7: tool
# 8: toolMaxDamage / toolHasDurability
# 9: toolCurrentDamage
# 10: toolRemainingDurability
# ... more for BFS

# We need a LOT of locals. Let's be strategic.
# The simplest approach that actually works:
# - Get event.getPlayer() -> if null return
# - Get event.getPos(), event.getState(), event.getLevel()
# - Check if level instanceof ServerLevel
# - Get tool durability info
# - BFS (complex but doable)
# - Break loop

# Given bytecode complexity, I'll generate a highly simplified but functional version.
# Let's use a different strategy: generate Java source and compile it using... wait, we can't.

# OK here's the plan: write a MINIMAL working class that just logs and cancels.
# Then we can iterate. For now let's make a functional skeleton.

print("CP entries:", len(cp.entries))

# Write just the minimal class file for now
with open('/sdcard/Download/veinminer-src/build/classes/com/veinminer/VeinMinerMod.class', 'wb') as f:
    f.write(bytes(out))

print(f"Class file written: {len(out)} bytes")
print("Done")
