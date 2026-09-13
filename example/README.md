# CmdRouter example consumer

`Program.cs` spawns the router as a child process and talks to it over pipes: dirty command lines on `stdin`, one JSON
response per line on `stderr`. There is no input schema; the router eats every line whole and always answers exactly one
response, so the consumer reads with strict one-to-one framing. The router's `stdout` is left alone, which means live
logs stream to this console while only protocol lines travel the pipe.

Each response follows the full `INTERNAL_JSON_CONTRACT` (`Source/Protocol.cs`): `ok`, `code`, `kind`, `input`,
`command`, `value`, `parsed_args`, `error`, `message`, `exception`, with `null` for absent values. `error` itself is
`ParseError.to_dict()` (`kind`, `token_index`, `expected`, `token`, `suggestions`, `message`, `partial_args`, `code`).
`kind` tells the outcome apart: `COMMAND` ran an action (`value`/`parsed_args` set), `INPUT` passed plain text through
(no prefix, so `value` echoes the line), anything else is a failure whose detail lives in `message` plus `error`.

Run it with `just dotrun` (or `dotnet run --project example`). It sends a handful of labeled lines (valid commands, an
unknown command, a missing argument, plain-text/empty passthrough, a broken quote), prints one `Describe()` line per
answer, then closes `stdin` so the router exits cleanly and reports its exit code.
