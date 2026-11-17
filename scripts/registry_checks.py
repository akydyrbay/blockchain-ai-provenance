"""Controlled integrity checks for the course registry's local replay fixture."""
from dataclasses import replace
from time import perf_counter_ns


def integrity_cases(records, verify, design, size):
    rows = []
    prior = []
    for record in records:
        cases = [
            ("clean", record, True),
            ("altered_weights", replace(record, weights=flipped(record.weights)), False),
            ("altered_dataset", replace(record, dataset=flipped(record.dataset)), False),
        ]
        alternative = next((index for index in prior if index not in record.parents), None)
        if record.parents and alternative is not None:
            cases.append(("different_parent", replace(record, parents=(alternative, *record.parents[1:])), False))
        for case, candidate, expected in cases:
            start = perf_counter_ns()
            accepted = verify(candidate)
            milliseconds = (perf_counter_ns() - start) / 1_000_000
            if accepted != expected:
                raise AssertionError(f"{design} {case}: verification of {record.name} returned {accepted}")
            rows.append({
                "design": design, "batch_size": size, "model_index": record.index, "scenario": case,
                "expected_verified": expected, "verified": accepted, "milliseconds": milliseconds,
            })
        prior.append(record.index)
    return rows


def flipped(value):
    return bytes([value[0] ^ 1]) + value[1:]


def registration_cases(records, publishers, outsider, decide, design, size):
    """Check the authorization and input rules with independent, read-only candidates."""
    import hashlib
    import random

    sample = random.Random(42).sample(records, min(100, len(records)))
    datasets = {record.dataset for record in records}
    outside = hashlib.sha256(b"provenance experiment: outside allowlist").digest()
    if outside in datasets:
        raise ValueError("The test dataset is part of the configured workload")
    nonexistent = max(record.index for record in records) + 1
    strict = design != "D1"
    rows = []
    for record in sample:
        sender = publishers[record.publisher]
        candidate = replace(record, parents=(), weights=hashlib.sha256(b"check:" + record.weights).digest())
        cases = [
            ("clean_candidate", candidate, sender, True),
            ("unknown_parent", replace(candidate, parents=(nonexistent,)), sender, False),
            ("unlisted_dataset", replace(candidate, dataset=outside), sender, not strict),
            ("unauthorized_publisher", candidate, outsider, not strict),
        ]
        for case, submission, submitter, expected in cases:
            accepted, evidence = decide(submission, submitter)
            if accepted != expected:
                raise AssertionError(f"{design} {case}: registration returned {accepted}")
            rows.append({
                "design": design, "batch_size": size, "model_index": record.index, "scenario": case,
                "expected_accepted": expected, "accepted": accepted, "evidence": evidence,
            })
    return rows
