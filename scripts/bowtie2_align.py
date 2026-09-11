import os
import sys

if "snakemake" in globals():
    reads_file = snakemake.input.reads
    species_file = snakemake.input.species
    output_file = snakemake.output.bam
    threads = snakemake.threads
    config = snakemake.config
else:
    raise RuntimeError("This script must be run via Snakemake")


def _ensure_scripts_path():
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)


_ensure_scripts_path()
from pigsti_verbosity import bash_stderr_redirect, bowtie2_quiet_args, vprint

# Read species exactly as-is
with open(species_file) as f:
    species = f.read().strip()

# Lookup bowtie2 index prefix in config
bt2_indices = config.get("bowtie2_indices", {})
index_prefix = bt2_indices.get(species)
if index_prefix is None:
    fallback = "Sheep"
    vprint(
        config,
        f"Warning: Species '{species}' not found in bowtie2_indices config, falling back to '{fallback}'.",
    )
    index_prefix = bt2_indices.get(fallback)
    if index_prefix is None:
        raise ValueError(
            f"No bowtie2 index for species '{species}' or fallback '{fallback}' found in config."
        )

log_file = output_file.replace(".bam", "_bowtie2.log")
os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
quiet = " ".join(bowtie2_quiet_args(config))
quiet_prefix = f"{quiet} " if quiet else ""
err_redir = bash_stderr_redirect(log_file, config)

cmd = (
    f"bowtie2 {quiet_prefix}--very-sensitive-local -x {index_prefix} -U {reads_file} -p {threads} "
    f"{err_redir} | samtools view -Sb - -F4 > {output_file}"
)

vprint(config, f"Running command:\n{cmd}")
exit_code = os.system(f"bash -c 'set -euo pipefail; {cmd}'")

if exit_code != 0:
    raise RuntimeError(f"bowtie2 alignment failed with exit code {exit_code} (see {log_file})")
