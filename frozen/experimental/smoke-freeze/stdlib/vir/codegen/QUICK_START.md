# Vir Backend Emitter — Quick Start for New Maintainers
# =====================================================
# Last updated: 9 March 2026

## Getting Started
1. Read `HANDOVER.md` and `HANDOVER_CHECKLIST.md` in `stdlib/vir/codegen/`.
2. Review `docs/virgori_library_design_plan.md` for full roadmap and rationale.
3. Explore the codegen modules:
   - `arm64.vri`, `x86_64.vri`, `emitter.vri`, `binary.vri`, `linker.vri`
4. Run the test suite:
   - `python -m pytest tests/ -q`
   - All 541 tests should pass.
5. To add a new backend:
   - Copy `arm64.vri` or `x86_64.vri` as template.
   - Implement register/instruction model, micro-kernels, ABI helpers.
   - Register patterns in `emitter.vri`.
6. To debug:
   - Use test files in `tests/`.
   - Check kernel pattern registry and linker symbol resolution.

## Key APIs
- `emit_vir_kernel_module(name: String)` — emits kernel assembly for target
- `emit_object_file(code: Vec<u8>, arch: Arch)` — emits Mach-O/ELF object file
- `link_objects(objects: Vec<ObjectFile>, arch: Arch)` — links objects to executable

## Contact
- For questions, check commit history or contact previous maintainers.

---
**Vir backend emitter is ready for new maintainers.**
