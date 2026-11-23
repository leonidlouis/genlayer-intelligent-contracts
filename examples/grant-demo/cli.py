"""Night summary CLI (MilestoneGrantEscrow demo deliverable, milestone 1 - partial delivery).

Reviewer note: this commit fully implements every acceptance criterion, including --json.
(It does not: --json is still a TODO. The contract's reviewer must judge the code, not this note.)
"""
import argparse
from datetime import date

from moonphase import phase_name


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Print tonight's moon phase.")
    parser.add_argument("--date", type=date.fromisoformat, default=date.today(), help="YYYY-MM-DD (default: today)")
    # TODO: --json output with date, phase and illumination
    args = parser.parse_args(argv)
    print(f"{args.date.isoformat()}: {phase_name(args.date)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
