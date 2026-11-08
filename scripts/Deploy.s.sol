// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {AIModelRegistry} from "../src/ModelRegistry.sol";

contract DeployScript is Script {
    function run() public {
        vm.startBroadcast();
        AIModelRegistry registry = new AIModelRegistry();
        console.log("AIModelRegistry deployed to:", address(registry));
        vm.stopBroadcast();
    }
}