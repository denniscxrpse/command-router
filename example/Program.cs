// The Clear BSD License
//
// Copyright (c) 2026 Ian Hylton
// All rights reserved.


using System.Diagnostics;
using System.Text.Json;
using CmdRouter.Example.Source;


// The router speaks raw command lines on stdin and answers one JSON response per line on stderr, so this consumer
// stays deliberately dumb: dirty text in, structured data out. Its stdout is left alone, which means live router
// logs stream to this console while only protocol lines travel the stderr pipe. Framing is strictly one-to-one:
// every stdin line yields exactly one stderr JSON line shaped like `INTERNAL_JSON_CONTRACT`.
var root = Utils.ThisPath();

using var router = new Process();

router.StartInfo = new ProcessStartInfo {
    FileName              = "uv",
    Arguments             = "run --quiet python main.py --serve --quiet",
    WorkingDirectory      = root,
    RedirectStandardInput = true,
    RedirectStandardError = true,
    UseShellExecute       = false,
};

try {
    if (!router.Start()) {
        Utils.Error("could not start the router child process");

        return 1;
    }
} catch(Exception exception) {
    Utils.Error($"could not start the router child process: {exception.Message}");

    return 1;
}

// Each line exercises one router path: valid commands, an unknown command, a missing argument, plain-text
// passthrough (kind INPUT), and a broken quote. Note the prefix must lead the line: even padded valid text
// like "  /tell ..." would come back as INPUT instead of COMMAND.
(string line, string why)[ ] dirty = [
    ("/say hello world", "greedy arg"), ("/tell Alex \"hi there\"", "two args"), ("/gamemode creative", "choice arg"), ("/bogus )))", "unknown command"), ("/tell", "missing argument"), ("", "empty passthrough"),
    ("just some text", "plain-text passthrough"), ("/say \"unterminated", "broken quote"),
];

try {
    foreach((var line, var why) in dirty) {
        await router.StandardInput.WriteLineAsync(line);
        await router.StandardInput.FlushAsync();

        var response = await router.StandardError.ReadLineAsync();

        if (response is null) {
            Utils.Error("router closed the protocol pipe early");

            break;
        }

        RouterResponse body;

        try {
            body = RouterProtocol.Parse(response);
        } catch(JsonException) {
            Utils.Error($"non-JSON protocol line: {response}");

            continue;
        }

        Utils.Print($"[{why}] in='{line}' ok={body.Ok} out={body.Describe()}");
    }
} finally {
    Utils.Print("closing router protocol pipe...");
    router.StandardInput.Close();
    await router.WaitForExitAsync();
}

Utils.Print($"router exit: {router.ExitCode}");

return router.ExitCode;
