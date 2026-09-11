#!/usr/bin/env python3
"""Preflight / dry-mode report: which PIGSTI stages will run for config + samples.tsv.

Does not invoke aligners or other tools. Safe to run before a cluster submission.

  python scripts/pigsti_preflight.py --config config/config.yaml
  snakemake preflight
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import yaml


def _tsv_flag(row: dict, *keys: str) -> bool:
    for k in keys:
        if k not in row:
            continue
        raw = row.get(k)
        if raw is None:
            continue
        s = str(raw).strip().lower()
        if not s:
            continue
        if s in {"1", "true", "yes", "y", "t"}:
            return True
        if s in {"0", "false", "no", "n", "f"}:
            return False
    return False


def load_libraries(samples_tsv: str) -> list[dict]:
    rows: list[dict] = []
    with open(samples_tsv, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if reader.fieldnames:
            reader.fieldnames = [fn.strip().lstrip("\ufeff") for fn in reader.fieldnames]
        has_pcr = reader.fieldnames and "pcr" in reader.fieldnames
        for row in reader:
            if not row or not str(row.get("sample") or "").strip():
                continue
            sample = str(row["sample"]).strip()
            pcr = str(row["pcr"]).strip() if has_pcr and row.get("pcr") else sample
            rows.append(
                {
                    "sample": sample,
                    "pcr": pcr,
                    "pe": bool(str(row.get("r2") or "").strip()),
                    "skip_trimming": _tsv_flag(row, "skip_trimming"),
                    "skip_metagenomics": _tsv_flag(row, "skip_metagenomics", "skip_meta"),
                    "skip_pathogen": _tsv_flag(
                        row,
                        "skip_pathogen_authentication",
                        "skip_pathogen",
                        "skip_pathogen_auth",
                    ),
                    "force_host_species": str(row.get("force_host_species") or "").strip(),
                }
            )
    return rows


def yn(flag: bool) -> str:
    return "yes" if flag else "no"


def build_report(cfg: dict, libs: list[dict]) -> str:
    enable_trim = bool(cfg.get("enable_trimming", True))
    enable_meta = bool(cfg.get("enable_metagenomics", True))
    enable_auth = bool(cfg.get("enable_pathogen_authentication", True))
    if not enable_meta:
        enable_auth = False
    host_on = not bool(cfg.get("pathogen_screening_only", False))
    hops = bool(cfg.get("enable_hops", False)) and enable_meta
    decom = bool(cfg.get("enable_decom", False)) and enable_meta

    lines: list[str] = []
    lines.append("PIGSTI preflight (dry mode)")
    lines.append("=" * 56)
    lines.append("Global config:")
    lines.append(f"  enable_trimming:                 {enable_trim}")
    lines.append(f"  pathogen_screening_only:         {bool(cfg.get('pathogen_screening_only', False))}")
    lines.append(f"  host/mtDNA analysis:             {host_on}")
    lines.append(f"  enable_metagenomics:             {enable_meta}")
    lines.append(f"  enable_pathogen_authentication:  {enable_auth}")
    lines.append(f"  enable_hops / enable_decom:      {hops} / {decom}")
    lines.append("")
    lines.append("Snakemake stage targets (optional):")
    lines.append("  snakemake              → rule all (respects config)")
    lines.append("  snakemake host_only")
    lines.append("  snakemake metagenomics_only")
    lines.append("  snakemake pathogen_auth")
    lines.append("  snakemake preflight")
    lines.append("")
    lines.append(
        f"{'library':<24} {'bio':<16} trim  host  meta  auth  force_host_species"
    )
    lines.append("-" * 88)

    for lib in libs:
        do_trim = enable_trim and not lib["skip_trimming"]
        do_meta = enable_meta and not lib["skip_metagenomics"]
        do_auth = enable_auth and do_meta and not lib["skip_pathogen"]
        force = lib["force_host_species"] or "-"
        lines.append(
            f"{lib['pcr']:<24} {lib['sample']:<16} "
            f"{yn(do_trim):<5} {yn(host_on):<5} {yn(do_meta):<5} {yn(do_auth):<5} {force}"
        )

    n_force = sum(1 for L in libs if L["force_host_species"])
    n_skip_trim = sum(1 for L in libs if (not enable_trim) or L["skip_trimming"])
    n_skip_meta = sum(1 for L in libs if (not enable_meta) or L["skip_metagenomics"])
    lines.append("")
    lines.append(
        f"Libraries: {len(libs)} | skip/stage trim: {n_skip_trim} | "
        f"skip meta: {n_skip_meta} | force_host_species: {n_force}"
    )
    lines.append(
        "Notes: FastQ Screen is skipped when force_host_species is set; "
        "alignment uses the forced index key."
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--samples", default=None, help="Override samples TSV path")
    parser.add_argument("--output", default="", help="Optional report path")
    args = parser.parse_args()

    if not os.path.isfile(args.config):
        print(f"Missing config: {args.config}", file=sys.stderr)
        return 2
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    samples = args.samples or cfg.get("samples") or "config/samples.tsv"
    if not os.path.isfile(samples):
        print(f"Missing samples TSV: {samples}", file=sys.stderr)
        return 2

    report = build_report(cfg, load_libraries(samples))
    sys.stdout.write(report)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
