package provenance

import rego.v1

clean := {
    "licence": 0,
    "weights_valid": true,
    "dataset_valid": true,
    "duplicate_weights": false,
    "dataset_allowed": true,
    "publisher_allowed": true,
    "parents": [{"id": 0, "registered": true, "revoked": false, "licence": 0}],
}

change(fields) := object.union(clean, fields)

test_clean if allow with input as clean
test_missing_parent if not allow with input as change({"parents": [{"id": 1, "registered": false}]})
test_revoked_parent if not allow with input as change({"parents": [{"id": 0, "registered": true, "revoked": true}]})
test_duplicate_parent if not allow with input as change({"parents": array.concat(clean.parents, clean.parents)})
test_missing_weights if not allow with input as change({"weights_valid": false})
test_missing_dataset if not allow with input as change({"dataset_valid": false})
test_duplicate_weights if not allow with input as change({"duplicate_weights": true})
test_unlisted_dataset if not allow with input as change({"dataset_allowed": false})
test_unauthorized_publisher if not allow with input as change({"publisher_allowed": false})
test_invalid_licence if not allow with input as change({"licence": 6})
test_stricter_parent if not allow with input as change({"parents": [{"id": 0, "registered": true, "revoked": false, "licence": 3}]})
test_unknown_child_licence if allow with input as change({"licence": 5})
test_no_derivatives_overrides_unknown if not allow with input as change({
    "licence": 5, "parents": [{"id": 0, "registered": true, "revoked": false, "licence": 4}],
})
