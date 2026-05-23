# FUP-1952 QA

Evidence:

- `tests/test_independent_qa_review_policy.py`
- `tests/test_review_role_policy.py`

Result: `agent-qa` can approve work completed by another owner when
`review_authorization=qa_role` is active.
