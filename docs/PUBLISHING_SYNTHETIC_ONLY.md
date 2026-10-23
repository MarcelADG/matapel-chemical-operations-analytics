# Publishing the synthetic portfolio

Public examples must be independently generated fictional data. Replacing names, hashing IDs, rounding true amounts or aggregating true records does not make a company dataset synthetic.

`scripts/check_publication_safety.py` checks actual Git index blobs before a commit and every outgoing commit before a push. It denies private directories and accepts only file versions in `.publication-allowlist.json`. A locally sealed copy under `.git/` prevents an unnoticed manifest edit from approving new content. Install the already reviewed manifest on a new clone with `python3 scripts/check_publication_safety.py --install-hooks`.

Use `python3 scripts/check_publication_safety.py --working-tree` to check reviewed files. A changed file must be reviewed for source data, literal business metrics, embedded workbook records, image content and metadata before its new hash is deliberately approved. Do not generate approvals automatically as part of a routine commit. Hooks can be bypassed intentionally and do not replace review.

Real inputs, workbooks, databases, retrospective results and private documentation stay ignored locally. A forced `git add` is still rejected by the hook. Public sample outputs need both a reproducible synthetic generator and reviewed hashes. Private exporters must not target public/sample paths.

Cleaning current files does not remove earlier Git commits, GitHub caches, clones or forks. Repository-history remediation is a separate publishing action. This local preparation makes no change to GitHub visibility or remote content.


Historical public versions may be explicitly reviewed by both blob hash and immutable tree hash. Those historical allowances apply only while checking outgoing commits in a reviewed historical tree. They cannot approve a current staged or working-file change, bypass private-path restrictions, or approve a changed manifest. Current public files still require their current reviewed hashes.
