import re

with open('/Users/gengyang/Vir/stdlib/vir/compiler/lir_codegen.vri', 'r') as f:
    content = f.read()

# Update Load
load_old = '''
            if dt == 3 and st1 == 4 do # Phys <- StackMem
                cb = arm64_ldr_reg(cb, rd as int, 31, soff as int)
            end
'''
load_new = '''
            if dt == 3 and st1 == 4 do # Phys <- StackMem
                if typ == 8 do # Vector
                    cb = arm64_ldr_q_reg(cb, rd as int, 31, soff as int)
                else
                    cb = arm64_ldr_reg(cb, rd as int, 31, soff as int)
                end
            end
'''
content = content.replace(load_old, load_new)

# Update Store
store_old = '''
            if dt == 4 and st1 == 3 do # StackMem <- Phys
                cb = arm64_str_reg(cb, rs1 as int, 31, doff as int)
            end
'''
store_new = '''
            if dt == 4 and st1 == 3 do # StackMem <- Phys
                if typ == 8 do # Vector
                    cb = arm64_str_q_reg(cb, rs1 as int, 31, doff as int)
                else
                    cb = arm64_str_reg(cb, rs1 as int, 31, doff as int)
                end
            end
'''
content = content.replace(store_old, store_new)

# Update Add
add_old = '''
        if op == 2 do # LirOp.Add
            if dt == 3 and st1 == 3 do
                cb = arm64_add_rrr(cb, rd as int, rd as int, rs1 as int)
            end
        end
'''
add_new = '''
        if op == 2 do # LirOp.Add
            if dt == 3 and st1 == 3 do
                if typ == 8 do
                    cb = arm64_fadd_v2d(cb, rd as int, rd as int, rs1 as int)
                else
                    cb = arm64_add_rrr(cb, rd as int, rd as int, rs1 as int)
                end
            end
        end
'''
content = content.replace(add_old, add_new)

# Update Sub
sub_old = '''
        if op == 3 do # LirOp.Sub
            if dt == 3 and st1 == 3 do
                cb = arm64_sub_rrr(cb, rd as int, rd as int, rs1 as int)
            end
        end
'''
sub_new = '''
        if op == 3 do # LirOp.Sub
            if dt == 3 and st1 == 3 do
                if typ == 8 do
                    cb = arm64_sub_v2d(cb, rd as int, rd as int, rs1 as int)
                else
                    cb = arm64_sub_rrr(cb, rd as int, rd as int, rs1 as int)
                end
            end
        end
'''
content = content.replace(sub_old, sub_new)

# Update Mul
mul_old = '''
        if op == 4 do # LirOp.Mul
            if dt == 3 and st1 == 3 do
                cb = arm64_mul_rrr(cb, rd as int, rd as int, rs1 as int)
            end
        end
'''
mul_new = '''
        if op == 4 do # LirOp.Mul
            if dt == 3 and st1 == 3 do
                if typ == 8 do
                    cb = arm64_fmul_v2d(cb, rd as int, rd as int, rs1 as int)
                else
                    cb = arm64_mul_rrr(cb, rd as int, rd as int, rs1 as int)
                end
            end
        end
'''
content = content.replace(mul_old, mul_new)

with open('/Users/gengyang/Vir/stdlib/vir/compiler/lir_codegen.vri', 'w') as f:
    f.write(content)

print("Updated lir_codegen.vri")
