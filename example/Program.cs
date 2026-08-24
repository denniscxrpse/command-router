// The Clear BSD License
//
// Copyright (c) 2026 Ian Hylton
// All rights reserved.


using Path = CmdRouter.Example.Utils.Path;


Path.Print("Hello, World!");

var l = new Dictionary<string, string> {
    ["asm"] = Path.Asm(),
    ["py"]  = Path.ThisPath(),
};

Path.Print(m:$"Current: '{l["asm"]}'");
Path.Print(m:$"Python:  '{l["py"]}'");

// TODO: Implement Command Router logic ...
