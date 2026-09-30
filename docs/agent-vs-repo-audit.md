# The agent installed on the AIOS laptop vs the repository: audit and sync

Date: 30 September 2026. Everything here was **measured** on the laptop (`aios`,
192.168.1.19) and on the VPS — not inferred from reading code.

## Summary

The installed agent and the repository were **diverged in both directions**, not simply
"the repo is ahead". Three files differed. Two of them were brought over today; the third
(`agent.py`) needs a hand merge and is deliberately left alone.

| File | Installed (before) | Repository | Now |
|---|---|---|---|
| `tools.py` | 15 Sep | 30 Sep | **synced** (`39d4762…`, byte-identical) |
| `process.py` | 9 Sep | 30 Sep | **synced** (`b3986f2…`, byte-identical) |
| `agent.py` | 14 Sep | 23 Sep | **not touched** — needs a hand merge |

## Three security defects, all measured

### 1. `process_start` did not consult the guard

Measured on `/home/aios/…`, a path **no** design exempts:

```
guard (run_command("rm -rf /home/aios/prueba"))  -> True    (would ask permission)
process_start("rm -rf /home/aios/prueba")        -> {"exit_code": 0}
                                                 -> directory DELETED, nobody asked
```

Not theoretical: **the production prompt tells the model to use `process_start`** for
interactive scripts. A model that follows its instructions lands here without meaning to.
A path the prompt itself recommends cannot be left without a guard.

**Before/after, same command:** before `exit_code 0` and the directory gone; now
`Command blocked` and the directory intact.

### 2. The guard ignored the user's "no" (repository)

`process.py` had:

```python
if not _confirm_destructive(command):     # returns "yes"/"no"/"timeout", NOT a bool
```

A non-empty string is always true in Python, so `not "no"` is `False` and the rejection
**never ran**. Measured:

```
guard asked          "NEEDS YOUR APPROVAL: rm -rf /home/ccmai/prueba-repo-process"
user answered        no  ("refused by the user")
command did          {"exit_code": 0}   -> the directory DISAPPEARED
```

It asked correctly and threw the answer away — worse than not asking, because it gives a
false sense of control. Fixed in `9fb27bf` with the same three-state rule its own
`tools.py` already used.

### 3. Installing by downloading

The guard covered `sven`/`apt`/`pip`/`make install`/`systemctl enable`, but **not**
installing software downloaded from the internet. Measured: when `sven` lacked a package,
the model went to GitHub with `curl`, unpacked into `/usr/local/bin` and `chmod +x`'d it.
All three commands said "go ahead", and it tried 6 times in 20 minutes. It survived **by
luck** (the URL 404'd; the file was 9 bytes). Fixed in `35353cc`: it **asks, it does not
forbid** — the destination decides, not the verb.

## The guard was not merely behind: it was wrong about `rm -rf`

Same 8-case table run against both designs. The repo gets **8/8**; the installed one failed
**6**:

| Command | Installed (old) | Repo | Should be |
|---|---|---|---|
| `rm -rf /` | blocks | blocks | blocks |
| `rm -rf /*` | **asks only** | **blocks** | blocks |
| `rm -rf /tmp/...` | **blocks, no way to approve** | stays quiet | quiet |
| `rm -rf /home/...` | **blocks, no way to approve** | asks | asks |
| `rm -rf build` | **blocks, no way to approve** | asks | asks |

The cause is one line: `re.search(r'\brm\s+-rf\s+/*\b', lower)`. `/*\b` means "a slash
followed by a word boundary", and between `/` and `t` of `/tmp` there **is** a word
boundary — so **any absolute path** matched and was blocked with no way to approve it,
while the catastrophic `rm -rf /*` fell through to the weak level.

Worst of both worlds: **annoying about the harmless, permissive about the irreparable.**

## What was done

- **`tools.py` and `process.py` brought over from the repo**, each verified before installing:
  the test bench is a full copy of the installed directory in `/tmp`, the real one is not
  touched until the battery passes. Then md5 compared against the source.
- **`agent.py` NOT touched**: the repository is ahead on the rules and the installed copy
  carries the swappable prompt. Copying in either direction loses work.
- **The regression battery grew from 76 to 96 cases** (`405d616`), covering everything closed
  today. And the proof that matters — run against the code of the earlier commits, it catches
  exactly the fixes of today:

```
with 9fb27bf  (current)   -> 96/96, 0 failures
with 35353cc  (one before) -> 94/96, 2 failures   <- the ignored "no"
with 80e0334  (two before) -> 80/96, 16 failures  <- installing by download
```

## Correction to an earlier version of this document

An earlier revision claimed the **repository** had lost the decision rule
(`_DECISION_RULE`, KNOWLEDGE explains / TASK executes) and that the machine had it. That was
**wrong, and backwards**. Verified with `git log -S _DECISION_RULE -- agent.py`: it entered
in `19af5be` (23 Sep) and **is still there**. The **installed copy** is the one missing it,
and it also still carries the line «For complex tasks, do NOT explain - EXECUTE» that the
repo removed — the commit removing it says the line clashed with «ask for confirmation
before destructive commands», and that the CONFIRM cases scored 0/4 because of it.

The only thing the installed copy has and the repo does not is the **swappable prompt**
(`build_system_prompt`), which was never versioned.

**And with the short prompt active none of those lines reach the model** — the file replaces
the whole prompt — so the divergence is dormant until someone goes back to the long prompt.

## Still open (measured, not fixed)

13 destination cases, 4 failures, and they are in **both** designs:

| Command | Says | Should say |
|---|---|---|
| `git clone <url> /usr/local/bin/x` | go ahead | ask |
| `git clone <url> /etc/x` | go ahead | ask |
| `git clone <url> /usr/share/x` | go ahead | ask |
| `cmake --install build` | go ahead | ask |

Everything else checks out: `cp`/`mv`/`install`/`tar -C` towards `/usr`, `/etc`,
`/usr/local/bin` ask, and `git clone` to `./` or `/tmp` stays quiet. `git clone <url> <dest>`
writes with the path as a **bare last argument**, so the "write to a system path" family
misses it. The download **URL** decides nothing (downloading is legitimate); the
**destination** is what matters.

## Note on where things run

The agent runs from `/usr/local/bin/aios-agent` on the laptop, which is **not a git repo** —
loose files. The launcher `/usr/local/bin/aios` is three lines and does
`cd /usr/local/bin/aios-agent`. The laptop's `/home/aios/aios-agent` **is** a git repo but
sits 41 commits behind and is not used for anything. **Nothing syncs git with what runs**:
a commit does not change the running agent.
