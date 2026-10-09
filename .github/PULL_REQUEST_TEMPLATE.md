## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## How it was tested

<!-- The test you wrote first and saw fail, and what you ran. -->

## Checklist

- [ ] `./dev.sh` passes
- [ ] New behavior has a test that failed before the change
- [ ] `CHANGELOG.md` has a line under "Unreleased"
- [ ] No real client data in tests, fixtures or the description
- [ ] Anything that stores client data is in `tests/data_write_sites.json` and is removed by "Delete client data"
- [ ] No `shell=True`; serials and app ids go through `inputcheck`
