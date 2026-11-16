# Examples

Two units of a simulated embedded PC (EPC-24), each with the results of
three tools:

| File | Tool |
|---|---|
| `bench-result.json` | [bench-automation](https://github.com/steitec/bench-automation): power, supply rails, boot, on-device checks |
| `interface-test.json` | [interface-test-kit](https://github.com/steitec/interface-test-kit): USB, Ethernet, serial, LED (only EPC-24-00137) |
| `boot-log.xml` | [boot-log-diff](https://github.com/steitec/boot-log-diff) `--junit`: boot log against the golden log |

The boot logs behind `boot-log.xml` are in `boot-logs/` (the golden log of the
EPC-24 from bench-automation and one capture per unit). The RAM size from the
BIOS POST line is compared as an extra fact:

```console
boot-log-diff boot-logs/golden.log boot-logs/EPC-24-00142.log \
    --fact 'ram=POST: Memory (\d+ MB)' --junit EPC-24-00142/boot-log.xml
```

`limits.toml` tightens some limits of the raw data.

```console
# passes, exit status 0
test-protocol EPC-24-00137/* --limits limits.toml -o EPC-24-00137.html

# fails (SSD with reallocated sectors, half the RAM), exit status 1
test-protocol EPC-24-00142/* --limits limits.toml -o EPC-24-00142.html --lang de --approver
```

For EPC-24-00142 the tool warns that the limit for `write speed` matched no
measurement: that unit has no interface test.
