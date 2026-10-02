# Public engineering workflow

[Contributor setup and checks](../../CONTRIBUTING.md) are the portable entry
point. The [synthetic demo](../../examples/minimal_demo/README.md) imports the
existing pure model functions. No external data root is needed for either.

## Configuration boundaries

| Setting | Use | Public flow |
| --- | --- | --- |
| `ETF_QUANT_CONSOLE_CONFIG` | Absolute path to a machine-local console JSON config; `-Config` overrides it | Optional operations only |
| `ETF_QUANT_PIT_ROOT` | External, captured PIT evidence root for the offline builder | Not used by demo/unit tests |
| `ETF_QUANT_PROXY_ROOT` | External prior proxy evidence root for the offline builder | Not used by demo/unit tests |
| `ETF_QUANT_EXTERNAL_RUNTIME_ROOT` | Read-only maintainer acceptance fixture root | External test tier only |
| Research approval configuration | Explicit, approved Development artifact root | Optional API integration only |

Existing operational defaults remain compatible with the configured Windows
machine. Builder source imports now resolve from the checkout itself. Safe
runner/sidecar/API examples remain in each component directory; keep machine-local
values outside Git. CI leaves private runtime variables unset and mounts no data.

## Tool policy

`pyproject.toml` configures tools without making this repository an installable
package. Ruff checks all Python source except generated `.cache` output, with
conservative E/F/W/I, selected UP/B/SIM rules. Explicit certificate-bound
exceptions preserve bytes, and scalar Boolean style rules do not replace
elementwise Pandas expressions. No entire production directory is lint-excluded.

Mypy checks source, research, services and scripts. New code and selected mature
boundaries are strict; exact legacy diagnostics are counted in a per-file ratchet.
This is staged type checking, with no `ignore_errors` overrides or new widespread
`Any`/`type: ignore`. Optional framework imports lack public stubs and are the only
missing-import overrides.

`requirements-dev.txt` records intentional direct dependencies;
`requirements-dev.lock.txt` pins the complete tested resolution. The devcontainer
uses digest-pinned Python/Node bases. Neither changes production dependencies,
CNEquity nor `docker-compose.yml`.

## Inventory reproduction

Create a path manifest with `git ls-files` (include new staged files), then run:

```sh
python scripts/engineering/inventory.py --manifest <path-list.txt> --output <inventory.json>
```

The scanner parses source ASTs and reports locations/counts, never imports models
or reads market data. Complete-signature coverage excludes `self`/`cls`, includes
private/test functions and requires every parameter plus return annotation.
Docstring coverage is reported independently for functions, classes and modules.
Print/path/document categories are heuristics reviewed in the hardening report.

Historical Markdown and certified JSON remain in place. Logical archive links
prevent destructive moves of path-bound evidence. Superseded/duplicate status is
not guessed from a filename alone.
