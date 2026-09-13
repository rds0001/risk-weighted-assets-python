## Summary

Describe the change and its purpose.

## Regulatory and data-contract impact

- [ ] No regulatory methodology or canonical data contract is affected.
- [ ] Affected methodology, assumptions and contracts are documented.

## Verification

- [ ] `python -m pytest`
- [ ] `python -m ruff check --no-cache src tests tools examples`
- [ ] `PYTHONPATH=src python tools/verify_source_tree.py`
- [ ] Wheel and sdist checks were run when packaging changed.

## Release boundary

- [ ] No confidential or real bank/customer data is included.
- [ ] No downloaded third-party publication or scaffold content is included.
