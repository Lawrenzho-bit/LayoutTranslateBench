<!-- Thanks for contributing to LayoutTranslateBench. Fill out what applies. -->

## Type
<!-- Check one or more -->
- [ ] New runner adapter
- [ ] New document(s) + annotation(s)
- [ ] Methodology / metric change
- [ ] Documentation
- [ ] Bug fix
- [ ] Infrastructure / CI

## Summary
<!-- 1–3 sentences. What does this PR do, and why? -->

## Test plan
- [ ] `pytest -q` passes locally
- [ ] `ltbench verify` passes
- [ ] `ltbench run-baseline && ltbench score --submission submissions/identity-baseline` produces a result
- [ ] (If new metric / scoring rule) added a unit test in `tests/`
- [ ] (If new runner) sample submission directory committed under `submissions/<system>/`
- [ ] (If new dataset entry) document is CC-BY-4.0 compatible; license recorded in manifest

## Score impact
<!-- Only if methodology change. Which systems gain / lose? Does v0.1 LTB-100 remain comparable? -->

## Related issues
<!-- Closes #XX -->
