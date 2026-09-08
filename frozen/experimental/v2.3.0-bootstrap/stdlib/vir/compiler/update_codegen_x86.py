import re

with open('/Users/gengyang/Vir/stdlib/vir/compiler/lir_codegen_x86.vri', 'r') as f:
    content = f.read()

# Add SIMD imports
content = content.replace('import x86_emit_add_rr,', 'import x86_emit_addpd, x86_emit_subpd, x86_emit_mulpd, x86_emit_movupd_load, x86_emit_movupd_store, x86_emit_add_rr,')

# Update LirOp.Load
load_old = '''
            if dt == 3 and st1 == 4 do # Phys <- StackMem
                cb = x86_emit_mov_reg_mem(cb, rd as int, X86_RBP, soff as int)
            end
'''
load_new = '''
            if dt == 3 and st1 == 4 do # Phys <- StackMem
                if typ == 8 do # Vector
                    cb = x86_emit_movupd_load(cb, rd as int, X86_RBP)
                else
                    cb = x86_emit_mov_reg_mem(cb, rd as int, X86_RBP, soff as int)
                end
            end
'''
content = content.replace(load_old, load_new)

# Update LirOp.Store
store_old = '''
            if dt == 4 and st1 == 3 do # StackMem <- Phys
                cb = x86_emit_mov_mem_reg(cb, X86_RBP, doff as int, rs1 as int)
            end
'''
store_new = '''
            if dt == 4 and st1 == 3 do # StackMem <- Phys
                if typ == 8 do # Vector
                    cb = x86_emit_movupd_store(cb, X86_RBP, rs1 as int)
                else
                    cb = x86_emit_mov_mem_reg(cb, X86_RBP, doff as int, rs1 as int)
                end
            end
'''
content = content.replace(store_old, store_new)

# Update LirOp.Add
add_old = '''
        if op == 2 do # LirOp.Add
            if dt == 3 and st1 == 3 do
                cb = x86_emit_add_rr(cb, rd as int, rs1 as int)
            end
        end
'''
add_new = '''
        if op == 2 do # LirOp.Add
            if dt == 3 and st1 == 3 do
                if typ == 8 do
                    cb = x86_emit_addpd(cb, rd as int, rs1 as int)
                else
                    cb = x86_emit_add_rr(cb, rd as int, rs1 as int)
                end
            end
        end
'''
content = content.replace(add_old, add_new)

# Update LirOp.Sub
sub_old = '''
        if op == 3 do # LirOp.Sub
            if dt == 3 and st1 == 3 do
                cb = x86_emit_sub_rr(cb, rd as int, rs1 as int)
            end
        end
'''
sub_new = '''
        if op == 3 do # LirOp.Sub
            if dt == 3 and st1 == 3 do
                if typ == 8 do
                    cb = x86_emit_subpd(cb, rd as int, rs1 as int)
                else
                    cb = x86_emit_sub_rr(cb, rd as int, rs1 as int)
                end
            end
        end
'''
content = content.replace(sub_old, sub_new)

# Update LirOp.Mul
mul_old = '''
        if op == 4 do # LirOp.Mul
            if dt == 3 and st1 == 3 do
                cb = x86_emit_imul_rr(cb, rd as int, rs1 as int)
            end
        end
'''
mul_new = '''
        if op == 4 do # LirOp.Mul
            if dt == 3 and st1 == 3 do
                if typ == 8 do
                    cb = x86_emit_mulpd(cb, rd as int, rs1 as int)
                else
                    cb = x86_emit_imul_rr(cb, rd as int, rs1 as int)
                end
            end
        end
'''
content = content.replace(mul_old, mul_new)

with open('/Users/gengyang/Vir/stdlib/vir/compiler/lir_codegen_x86.vri', 'w') as f:
    f.write(content)

print("Updated lir_codegen_x86.vri")
