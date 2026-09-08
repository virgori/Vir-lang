import re

with open('/Users/gengyang/Vir/stdlib/vir/compiler/lir_regalloc_color.vri', 'r') as f:
    content = f.read()

# 1. Update color_to_phys
content = content.replace('func color_to_phys(color: i64, is_leaf: i64):', 'func color_to_phys(color: i64, is_leaf: i64, is_vector: i64):\n    if is_vector == 1 do out 12 + color end')

# 2. Update lir_rewrite_opnd
content = content.replace('out lir_opnd_phys_reg(color_to_phys(p_reg, is_leaf) as LirPhysReg)', 'is_vector = 0\n                if native_read_i64(opnd as i64, 0) == 7 do is_vector = 1 end\n                out lir_opnd_phys_reg(color_to_phys(p_reg, is_leaf, is_vector) as LirPhysReg)')

# 3. Add vreg_is_vector to lir_allocate_registers_color
init_code = '''
    assigned_stack = vec_new_rt()
    stack = vec_new_rt()
    vreg_is_vector = vec_new_rt()

    i = 0
    when i < n_nodes loop
        removed = vec_push_rt(removed, 0)
        assigned_phys = vec_push_rt(assigned_phys, -1)
        assigned_stack = vec_push_rt(assigned_stack, 0)
        vreg_is_vector = vec_push_rt(vreg_is_vector, 0)
        i = i + 1
    end
'''
content = re.sub(r'assigned_stack = vec_new_rt\(\)\n\s+stack = vec_new_rt\(\)\n\n\s+i = 0\n\s+when i < n_nodes loop\n\s+removed = vec_push_rt\(removed, 0\)\n\s+assigned_phys = vec_push_rt\(assigned_phys, -1\)\n\s+assigned_stack = vec_push_rt\(assigned_stack, 0\)\n\s+i = i \+ 1\n\s+end', init_code.strip(), content)

# 4. Extract vreg_is_vector in the loop
fbi_loop = '''
            if native_read_i64(ins_m as i64, 0) == 1 do # LirOp.Mov
'''
fbi_loop_new = '''
            d_opnd_v = native_read_i64(ins_m as i64, 16)
            s1_opnd_v = native_read_i64(ins_m as i64, 24)
            s2_opnd_v = native_read_i64(ins_m as i64, 32)
            if d_opnd_v != 0 and native_read_i64(d_opnd_v, 0) == 7 do vec_set_rt(vreg_is_vector, native_read_i64(d_opnd_v, 8), 1) end
            if s1_opnd_v != 0 and native_read_i64(s1_opnd_v, 0) == 7 do vec_set_rt(vreg_is_vector, native_read_i64(s1_opnd_v, 8), 1) end
            if s2_opnd_v != 0 and native_read_i64(s2_opnd_v, 0) == 7 do vec_set_rt(vreg_is_vector, native_read_i64(s2_opnd_v, 8), 1) end

            if native_read_i64(ins_m as i64, 0) == 1 do # LirOp.Mov
'''
content = content.replace(fbi_loop, fbi_loop_new)

# 5. Simplify K
simplify_old = '''
                deg = vec_get_rt(curr_degrees, i)
                if deg < K do
'''
simplify_new = '''
                deg = vec_get_rt(curr_degrees, i)
                is_v = vec_get_rt(vreg_is_vector, i)
                max_K = K
                if is_v == 1 do max_K = 16 end
                if deg < max_K do
'''
content = content.replace(simplify_old, simplify_new)

# 6. Select max_K
select_old = '''
        used_colors = vec_new_rt()
        c = 0
        when c < K loop
            used_colors = vec_push_rt(used_colors, 0)
            c = c + 1
        end
        j = 0
        when j < n_nodes loop
            if get_edge(ig, u, j) == 1 and intervals_overlap(vec_get_rt(intervals, u), vec_get_rt(intervals, j)) do
                neighbor_color = vec_get_rt(assigned_phys, j)
                if neighbor_color >= 0 and neighbor_color < K do
'''
select_new = '''
        is_v = vec_get_rt(vreg_is_vector, u)
        max_K = K
        if is_v == 1 do max_K = 16 end

        used_colors = vec_new_rt()
        c = 0
        when c < max_K loop
            used_colors = vec_push_rt(used_colors, 0)
            c = c + 1
        end
        j = 0
        when j < n_nodes loop
            if get_edge(ig, u, j) == 1 and intervals_overlap(vec_get_rt(intervals, u), vec_get_rt(intervals, j)) do
                if vec_get_rt(vreg_is_vector, j) == is_v do
                    neighbor_color = vec_get_rt(assigned_phys, j)
                    if neighbor_color >= 0 and neighbor_color < max_K do
                        vec_set_rt(used_colors, neighbor_color, 1)
                    end
                end
'''
content = content.replace(select_old, select_new)

# 7. Select partner_color < max_K
partner_old = '''
                partner_color = vec_get_rt(assigned_phys, partner)
                if partner_color >= 0 and partner_color < K do
'''
partner_new = '''
                partner_color = vec_get_rt(assigned_phys, partner)
                if partner_color >= 0 and partner_color < max_K do
'''
content = content.replace(partner_old, partner_new)


# 8. Stack size adjust
stack_old = '''
        if color != -1 do
            vec_set_rt(assigned_phys, u, color)
        else
            # Uncolorable: assign a dedicated stack slot (real spill).
            stack_size = stack_size + 8
            vec_set_rt(assigned_stack, u, stack_size)
        end
'''
stack_new = '''
        if color != -1 do
            vec_set_rt(assigned_phys, u, color)
        else
            # Uncolorable: assign a dedicated stack slot (real spill).
            if is_v == 1 do
                stack_size = stack_size + 16
            else
                stack_size = stack_size + 8
            end
            vec_set_rt(assigned_stack, u, stack_size)
        end
'''
content = content.replace(stack_old, stack_new)

with open('/Users/gengyang/Vir/stdlib/vir/compiler/lir_regalloc_color.vri', 'w') as f:
    f.write(content)

print("Updated lir_regalloc_color.vri")
