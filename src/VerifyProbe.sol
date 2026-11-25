// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract VerifyProbe {
    error VerificationCallFailed();

    function measure(address target, bytes calldata query)
        external
        view
        returns (uint256 gasUsed, bytes memory result)
    {
        uint256 before = gasleft();
        (bool ok, bytes memory response) = target.staticcall(query);
        gasUsed = before - gasleft();
        if (!ok) revert VerificationCallFailed();
        return (gasUsed, response);
    }
}
