import re

with open('/Users/gengyang/Vir/stdlib/vir/compiler/lir.vri', 'r') as f:
    lir_content = f.read()

# Add lir_opnd_vreg_vector
vreg_int_code = '''
func lir_opnd_vreg_int(r: i64):
    out lir_opnd_new(1, r, 0, 0, 0, 0)
end.
'''
vreg_vector_code = vreg_int_code + '''
func lir_opnd_vreg_vector(r: i64):
    out lir_opnd_new(7, r, 0, 0, 0, 0)
end.
'''
lir_content = lir_content.replace(vreg_int_code, vreg_vector_code)
lir_content = lir_content.replace('lir_opnd_vreg_int, lir_opnd_imm', 'lir_opnd_vreg_int, lir_opnd_vreg_vector, lir_opnd_imm')

with open('/Users/gengyang/Vir/stdlib/vir/compiler/lir.vri', 'w') as f:
    f.write(lir_content)

with open('/Users/gengyang/Vir/stdlib/vir/compiler/lir_lower.vri', 'r') as f:
    lir_lower_content = f.read()

# Update import
lir_lower_content = lir_lower_content.replace('lir_opnd_vreg_int, lir_opnd_imm', 'lir_opnd_vreg_int, lir_opnd_vreg_vector, lir_opnd_imm')

# Update lower_mir_opnd
lower_opnd_old = '''
func lower_mir_opnd(m_opnd: MirOperand):
    if mir_opnd_type(m_opnd) == MirOperandType.VReg do
        out lir_opnd_vreg_int(mir_opnd_vreg_id(m_opnd))
    eif mir_opnd_type(m_opnd) == MirOperandType.Imm do
'''
lower_opnd_new = '''
func lower_mir_opnd(m_opnd: MirOperand, is_vector: i64):
    if mir_opnd_type(m_opnd) == MirOperandType.VReg do
        if is_vector == 1 do
            out lir_opnd_vreg_vector(mir_opnd_vreg_id(m_opnd))
        else
            out lir_opnd_vreg_int(mir_opnd_vreg_id(m_opnd))
        end
    eif mir_opnd_type(m_opnd) == MirOperandType.Imm do
'''
lir_lower_content = lir_lower_content.replace(lower_opnd_old, lower_opnd_new)

# Update instr loop
instr_loop_old = '''
                l_ins = lir_instr_new(
                    l_op as i64,
                    LirType.Int64 as i64,
                    lower_mir_opnd(mir_instr_dst(m_ins)) as i64,
                    lower_mir_opnd(mir_instr_src1(m_ins)) as i64,
                    lower_mir_opnd(mir_instr_src2(m_ins)) as i64,
                    lower_mir_aux(m_ins)
                );
'''
instr_loop_new = '''
                is_vector = 0;
                l_type = LirType.Int64 as i64;
                if m_op >= 31 and m_op <= 36 do
                    is_vector = 1;
                    l_type = LirType.Vector as i64;
                end
                l_ins = lir_instr_new(
                    l_op as i64,
                    l_type,
                    lower_mir_opnd(mir_instr_dst(m_ins), is_vector) as i64,
                    lower_mir_opnd(mir_instr_src1(m_ins), is_vector) as i64,
                    lower_mir_opnd(mir_instr_src2(m_ins), is_vector) as i64,
                    lower_mir_aux(m_ins)
                );
'''
lir_lower_content = lir_lower_content.replace(instr_loop_old, instr_loop_new)

with open('/Users/gengyang/Vir/stdlib/vir/compiler/lir_lower.vri', 'w') as f:
    f.write(lir_lower_content)

print("Updated lir.vri and lir_lower.vri")
