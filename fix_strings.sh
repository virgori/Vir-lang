for file in stdlib/vir/compiler/sem_pass*.vri stdlib/vir/compiler/ast_to_mir.vri stdlib/vir/compiler/parser.vri; do
    # Add imports
    sed -i '' -e 's/import rt_streq, /import rt_streq, fat_str_eq, fat_str_len, fat_cstr_eq, /g' "$file"
    sed -i '' -e 's/import rt_streq,/import rt_streq, fat_str_eq, fat_str_len, fat_cstr_eq,/g' "$file"

    # Replace rt_strlen with fat_str_len for AST names
    sed -i '' -e 's/rt_strlen(name)/fat_str_len(name)/g' "$file"
    sed -i '' -e 's/rt_strlen(node.name)/fat_str_len(node.name)/g' "$file"
    sed -i '' -e 's/rt_strlen(node.name2)/fat_str_len(node.name2)/g' "$file"
    sed -i '' -e 's/rt_strlen(param.name2)/fat_str_len(param.name2)/g' "$file"
    sed -i '' -e 's/rt_strlen(field.name2)/fat_str_len(field.name2)/g' "$file"
    sed -i '' -e 's/rt_strlen(target_name)/fat_str_len(target_name)/g' "$file"
    sed -i '' -e 's/rt_strlen(sym_child.name)/fat_str_len(sym_child.name)/g' "$file"
    sed -i '' -e 's/rt_strlen(bind_name)/fat_str_len(bind_name)/g' "$file"

    # Replace rt_streq(sym_name, name) with fat_str_eq
    sed -i '' -e 's/rt_streq(sym_name, name)/fat_str_eq(sym_name, name)/g' "$file"
    sed -i '' -e 's/rt_streq(existing, name)/fat_str_eq(existing, name)/g' "$file"
    sed -i '' -e 's/rt_streq(vec_get_rt(names, i), name)/fat_str_eq(vec_get_rt(names, i), name)/g' "$file"
    sed -i '' -e 's/rt_streq(vec_get_rt(borrows, i), name)/fat_str_eq(vec_get_rt(borrows, i), name)/g' "$file"
    sed -i '' -e 's/rt_streq(vec_get_rt(bound_lhs, i), borrower)/fat_str_eq(vec_get_rt(bound_lhs, i), borrower)/g' "$file"
    sed -i '' -e 's/rt_streq(cname, name)/fat_str_eq(cname, name)/g' "$file"
    sed -i '' -e 's/rt_streq(entry.name, name)/fat_str_eq(entry.name, name)/g' "$file"

    # Replace rt_streq(name, "literal") with fat_cstr_eq(name, "literal")
    sed -i '' -E 's/rt_streq\(([^,]+),\s*("[^"]*")\)/fat_cstr_eq(\1, \2)/g' "$file"
done
