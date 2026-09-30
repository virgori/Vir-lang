# Compiler release process

Run the manual [compiler release workflow](../.github/workflows/virc-release.yml)
with a source ref and a **new** version tag. It pins the ref to one commit SHA,
rejects an existing tag, then builds and checks that exact source:

1. Rebuild compiler binaries on macOS ARM64, verify arithmetic output and
   embedded version, and run `run_tests.sh min` with the rebuilt compiler.
2. Execute Linux x86_64 and Linux ARM64 compiler smoke tests (ARM64 via QEMU),
   requiring exact arithmetic output.
3. Only after both jobs succeed, create and push the tag at the pinned SHA and
   publish the tested artifacts. A version mismatch fails before tagging.

Do not push release tags manually. The workflow enforces this ordering for
workflow-created tags; preventing direct tags requires a GitHub tag ruleset
restricting `v*` creation to the approved release actor. Repository-side YAML
cannot enforce that server-side permission. Configure and verify that ruleset
before treating the policy as universally enforced.

The legacy `release.yml` is manual and references archived package trees; it
is not the supported compiler release route. A green smoke suite does not
certify every language feature or backend. If publication fails after tagging,
inspect the successful validation run and recover publication separately;
this workflow deliberately rejects reusing an existing tag.
