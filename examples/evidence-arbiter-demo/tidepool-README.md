# tidepool

`tidepool` is a small command-line tool that watches a folder and mirrors new files to an S3-compatible bucket.

*Delivered by the contractor on 2026-10-31 for the EvidenceArbiter demo agreement.*

## Installation

```bash
pipx install tidepool
# or, from source
git clone https://example.org/tidepool.git && cd tidepool && pip install .
```

Requires Python 3.10 or newer. Credentials are read from the standard `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` environment variables.

## Usage

Mirror a folder once:

```bash
tidepool sync ./photos s3://my-bucket/photos
```

Watch a folder and upload new files as they appear:

```bash
tidepool watch ./inbox s3://my-bucket/inbox --interval 10
```

Show what would be uploaded without uploading anything:

```bash
tidepool sync ./photos s3://my-bucket/photos --dry-run
```

## License

MIT. See `LICENSE` in the repository.
