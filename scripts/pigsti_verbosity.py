"""Shared verbosity helpers for PIGSTI tool invocations.

Controlled by config key ``enable_verbose`` (default: false).

Quiet mode (default):
  - bowtie2 gets ``--quiet``
  - tool stderr goes to log files only (AdapterRemoval, Qualimap, DamageProfiler, BWA, …)
  - Picard MarkDuplicates gets ``QUIET=true``
  - Python scripts skip progress ``print`` noise

Verbose mode:
  - tool stderr is teed to the console and the log file
  - bowtie2 / Picard keep their normal chatter

Snakefile shell rules should prefer::

    params:
        verbose=VERBOSE_FLAG,          # "true" / "false"
        picard_quiet=PICARD_QUIET_ARG, # "" or "QUIET=true"

and redirect with ``>> {log} 2>&1`` (quiet) or tee when verbose.
Python rules should import from this module.
"""

from __future__ import annotations


def is_verbose(config: dict | None) -> bool:
    return bool((config or {}).get("enable_verbose", False))


def bowtie2_quiet_args(config: dict | None) -> list[str]:
    return [] if is_verbose(config) else ["--quiet"]


def bash_stderr_redirect(log_path: str, config: dict | None) -> str:
    """Shell fragment to attach after a command (before a pipe is fine for stderr)."""
    if is_verbose(config):
        return f"2> >(tee -a {log_path} >&2)"
    return f"2>> {log_path}"


def bash_stdio_redirect(log_path: str, config: dict | None) -> str:
    """Redirect both stdout and stderr (AdapterRemoval / Qualimap / DamageProfiler style)."""
    if is_verbose(config):
        return f"> >(tee -a {log_path}) 2> >(tee -a {log_path} >&2)"
    return f">> {log_path} 2>&1"


def picard_quiet_arg(config: dict | None) -> str:
    return "" if is_verbose(config) else "QUIET=true"


def vprint(config: dict | None, *args, **kwargs) -> None:
    if is_verbose(config):
        print(*args, **kwargs)
