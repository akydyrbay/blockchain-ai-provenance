package provenance

import rego.v1

default allow := false

allow if {
    input.licence in {0, 1, 2, 3, 4, 5}
    input.weights_valid
    input.dataset_valid
    not input.duplicate_weights
    input.dataset_allowed
    input.publisher_allowed
    count(input.parents) == count({parent.id | some parent in input.parents})
    every parent in input.parents {
        parent.registered
        not parent.revoked
        compatible(input.licence, parent.licence)
    }
}

compatible(child, parent) if {
    parent != 4
    child == 5
}

compatible(child, parent) if {
    parent == 5
    child in {0, 1, 2, 3, 4}
}

compatible(child, parent) if {
    parent in {0, 1, 2, 3}
    child in {0, 1, 2, 3, 4}
    child >= parent
}
